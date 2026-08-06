"""Bot entry point.

Two jobs:

* keep the report buttons alive (persistent views, re-registered on boot);
* expose ``/setup`` so the server can be built or repaired without redeploying.
"""

from __future__ import annotations

import logging
import time

import discord
from discord import app_commands
from discord.ext import tasks

from . import blueprint as bp
from . import setup_guild
from . import status as status_probes
from . import texts
from .config import Config
from .github_bridge import GitHubClient
from .profiles import ProfileStore
from .views import (
    ReportHandler,
    SetupPanel,
    SupportPanel,
    panel_embed,
    setup_panel_embed,
)
from .views import setup_embed as views_setup_embed

log = logging.getLogger("discord-bdo.bot")

#: Attachment types counted as a usable screenshot.
IMAGE_TYPES = ("image/",)
VIDEO_TYPES = ("video/",)

#: How often the status board is refreshed. Short enough that an outage shows
#: up before people start asking, long enough to stay far from any rate limit.
STATUS_INTERVAL_MINUTES = 5
#: Even with nothing changing, rewrite the board this often so the "checked"
#: stamp proves the monitoring is still alive.
STATUS_MAX_SILENCE_SECONDS = 30 * 60


class BdoBot(discord.Client):
    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        # Members are needed to resolve roles when applying permissions, and to
        # hand out the Joueur role on arrival.
        intents.members = True
        # Attachments are blanked out without this intent, so screenshot
        # detection would silently never fire. It is privileged but free to
        # enable below 100 servers.
        intents.message_content = True
        super().__init__(intents=intents)

        self.config = config
        self.tree = app_commands.CommandTree(self)
        self.github = GitHubClient(config.github_token) if config.github_token else None
        self.profiles = ProfileStore(config.profiles_path)
        #: Filled on ready, per guild id.
        self.channels_by_guild: dict[int, dict[str, discord.abc.GuildChannel]] = {}
        #: Last published status snapshot, so the board is only rewritten when
        #: something actually changed.
        self._status_fingerprint: str = ""
        self._status_written_at: float = 0.0
        self._status_states: dict[str, status_probes.State] = {}

        # Registered here rather than in setup_hook so the command list can be
        # inspected without connecting to Discord.
        register_commands(self)

    # -- lifecycle ---------------------------------------------------------- #

    async def setup_hook(self) -> None:
        await self.profiles.setup()
        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("slash commands synced to guild %s", self.config.guild_id)
        else:
            await self.tree.sync()
            log.info("slash commands synced globally (can take up to an hour)")

    async def on_ready(self) -> None:
        for guild in self.guilds:
            channels = self.index_channels(guild)
            self.channels_by_guild[guild.id] = channels
            handler = self.build_handler(guild)
            for product in bp.PRODUCTS:
                # Re-registering the view is what makes buttons posted by a
                # previous run keep working after a restart.
                self.add_view(SupportPanel(product, handler))
            self.add_view(SetupPanel(handler))
        if not self.status_loop.is_running():
            self.status_loop.start()
        await self.change_presence(
            activity=discord.Game(name="Butin & Rubin · /aide")
        )
        log.info("logged in as %s on %d guild(s)", self.user, len(self.guilds))

    # -- helpers ------------------------------------------------------------ #

    @staticmethod
    def index_channels(guild: discord.Guild) -> dict[str, discord.abc.GuildChannel]:
        """Match live channels back to blueprint keys, by name."""
        wanted = {
            setup_guild.normalise(ch.name): ch.key
            for _, ch in bp.all_channel_specs()
            if ch.key
        }
        found: dict[str, discord.abc.GuildChannel] = {}
        for channel in guild.channels:
            key = wanted.get(setup_guild.normalise(channel.name))
            if key:
                found[key] = channel
        missing = set(wanted.values()) - set(found)
        if missing:
            log.warning("channels missing on %s: %s", guild.name, ", ".join(sorted(missing)))
        return found

    def build_handler(self, guild: discord.Guild) -> ReportHandler:
        channels = self.channels_by_guild.get(guild.id) or self.index_channels(guild)
        staff_log = channels.get(bp.KEY_STAFF_LOG)
        return ReportHandler(
            channels=channels,
            github=self.github,
            default_labels=self.config.github_default_labels,
            staff_log=staff_log if isinstance(staff_log, discord.TextChannel) else None,
            dry_run=self.config.dry_run,
            profiles=self.profiles,
        )

    # -- events -------------------------------------------------------------- #

    async def on_member_join(self, member: discord.Member) -> None:
        """Give every human the Joueur role, so @everyone stays technical."""
        if member.bot:
            return
        role = discord.utils.get(member.guild.roles, name=bp.ROLE_PLAYER)
        if role is None:
            return
        try:
            await member.add_roles(role, reason="discord-bdo: arrivée")
        except discord.HTTPException as exc:
            log.warning("could not give %s to %s: %s", bp.ROLE_PLAYER, member, exc)

    async def on_message(self, message: discord.Message) -> None:
        """Notice screenshots dropped into a report thread."""
        if message.author.bot or not message.attachments:
            return
        thread = message.channel
        if not isinstance(thread, discord.Thread):
            return
        if not isinstance(thread.parent, discord.ForumChannel):
            return
        if not self.is_report_forum(thread.parent):
            return
        if not any(is_visual(attachment) for attachment in message.attachments):
            return
        await self.mark_screenshot(thread, message)

    def is_report_forum(self, forum: discord.ForumChannel) -> bool:
        channels = self.channels_by_guild.get(forum.guild.id, {})
        watched = {
            channels.get(key)
            for key in (
                bp.KEY_BUTIN_BUGS,
                bp.KEY_RUBIN_BUGS,
                bp.KEY_BETA_FEEDBACK,
            )
        }
        return forum in watched

    async def mark_screenshot(
        self, thread: discord.Thread, message: discord.Message
    ) -> None:
        tag = discord.utils.find(
            lambda t: t.name == bp.TAG_HAS_SCREENSHOT, thread.parent.available_tags
        )
        already = tag is not None and tag in thread.applied_tags
        try:
            await message.add_reaction("📎")
        except discord.HTTPException:
            pass

        if already:
            # Thanking once per thread, not once per image.
            return

        if tag is not None:
            try:
                await thread.add_tags(tag, reason="discord-bdo: capture reçue")
            except discord.HTTPException as exc:
                log.warning("could not tag %s: %s", thread, exc)
        try:
            await thread.send(texts.SCREENSHOT_THANKS)
        except discord.HTTPException:
            pass

        handler = self.build_handler(thread.guild)
        await handler.log_staff(
            texts.LOG_SCREENSHOT.format(
                link=thread.jump_url, author=message.author.display_name
            )
        )

    # -- status board -------------------------------------------------------- #

    @tasks.loop(minutes=STATUS_INTERVAL_MINUTES)
    async def status_loop(self) -> None:
        try:
            await self.refresh_status()
        except Exception:  # a monitoring failure must never kill the bot
            log.exception("status refresh failed")

    @status_loop.before_loop
    async def _before_status(self) -> None:
        await self.wait_until_ready()

    async def refresh_status(self, force: bool = False) -> list:
        results = await status_probes.check_all(github_token=self.config.github_token)
        await self.announce_status_changes(results)

        fingerprint = status_probes.fingerprint(results)
        stale = (
            time.time() - self._status_written_at > STATUS_MAX_SILENCE_SECONDS
        )
        if not force and fingerprint == self._status_fingerprint and not stale:
            return results

        for guild in self.guilds:
            channels = self.channels_by_guild.get(guild.id) or self.index_channels(guild)
            channel = channels.get(bp.KEY_STATUS)
            if not isinstance(channel, discord.TextChannel):
                continue
            try:
                await setup_guild._replace_bot_message(channel, status_embed(results))
            except discord.HTTPException as exc:
                log.warning("could not publish the status board: %s", exc)

        self._status_fingerprint = fingerprint
        self._status_written_at = time.time()
        return results

    async def announce_status_changes(self, results) -> None:
        """Tell the staff when a service flips, once per transition."""
        changed = []
        for result in results:
            before = self._status_states.get(result.probe.key)
            if before is not None and before is not result.state:
                changed.append((result, before))
            self._status_states[result.probe.key] = result.state

        if not changed:
            return
        for guild in self.guilds:
            handler = self.build_handler(guild)
            for result, before in changed:
                await handler.log_staff(
                    texts.LOG_STATUS_CHANGE.format(
                        dot=result.state.dot,
                        label=result.probe.label,
                        before=before.value,
                        after=result.state.value,
                        note=f" ({result.note})" if result.note else "",
                    )
                )

    async def post_panels(
        self,
        guild: discord.Guild,
        channels: dict[str, discord.abc.GuildChannel],
        report: bp.SetupReport,
    ) -> None:
        """Put (or refresh) the button panels and the beta welcome message."""
        self.channels_by_guild[guild.id] = channels
        handler = self.build_handler(guild)

        beta_news = channels.get(bp.KEY_BETA_NEWS)
        if isinstance(beta_news, discord.TextChannel):
            await setup_guild._replace_bot_message(
                beta_news,
                discord.Embed(
                    title=texts.BETA_WELCOME_TITLE,
                    description=texts.BETA_WELCOME_BODY,
                    colour=discord.Colour(0x6BBF59),
                ),
            )
            report.updated_channels.append(beta_news.name)

        for product in bp.PRODUCTS:
            channel = channels.get(product.help_channel_key)
            if not isinstance(channel, discord.TextChannel):
                report.warnings.append(
                    f"Panneau {product.label} non posté : salon d'aide introuvable."
                )
                continue
            view = SupportPanel(product, handler)
            self.add_view(view)
            await setup_guild._replace_bot_message(
                channel, panel_embed(product), view=view
            )
            # The setup card is not a beta thing: anyone reporting a bug needs
            # one, so the panel sits next to the report buttons in both help
            # channels rather than behind the Tester role.
            setup_view = SetupPanel(handler)
            self.add_view(setup_view)
            await setup_guild._replace_bot_message(
                channel, setup_panel_embed(), view=setup_view
            )
            report.updated_channels.append(channel.name)


def status_embed(results) -> discord.Embed:
    state = status_probes.overall(results)
    return discord.Embed(
        title=texts.STATUS_TITLE.format(
            dot=state.dot, headline=status_probes.HEADLINES[state]
        ),
        description=status_probes.render_description(results, int(time.time())),
        colour=discord.Colour(status_probes.COLOURS[state]),
    )


def _is_staff(interaction: discord.Interaction) -> bool:
    member = interaction.user
    if not isinstance(member, discord.Member):
        return False
    if member.guild_permissions.administrator:
        return True
    return any(role.name in (bp.ROLE_DEV, bp.ROLE_MOD) for role in member.roles)


def is_visual(attachment: discord.Attachment) -> bool:
    """Whether an attachment counts as a screenshot or a screen recording."""
    content_type = (attachment.content_type or "").lower()
    if content_type.startswith(IMAGE_TYPES + VIDEO_TYPES):
        return True
    # Discord omits content_type on some uploads, so fall back to the name.
    name = (attachment.filename or "").lower()
    return name.endswith(
        (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".mp4", ".mov", ".webm")
    )


# --------------------------------------------------------------------------- #
# Slash commands
# --------------------------------------------------------------------------- #


def register_commands(bot: BdoBot) -> None:
    @bot.tree.command(
        name="setup",
        description="Construit ou répare le serveur (staff) / Build or repair the server",
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_command(interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "À lancer dans le serveur. / Run this inside the server.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            report = await setup_guild.run(interaction.guild, post_panels=bot.post_panels)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Il me manque des droits. Donnez au bot un rôle Administrateur, "
                "placé au-dessus des autres, puis relancez.",
                ephemeral=True,
            )
            return
        await interaction.followup.send(f"```\n{report.summary()[:1900]}\n```", ephemeral=True)

    @bot.tree.command(
        name="etat",
        description="État des services en direct / Live service status",
    )
    async def status_command(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        results = await status_probes.check_all(github_token=bot.config.github_token)
        await interaction.followup.send(embed=status_embed(results), ephemeral=True)

    @bot.tree.command(
        name="config",
        description="Voir une fiche de configuration / Show a setup card",
    )
    @app_commands.describe(membre="Laisser vide pour voir la vôtre / leave empty for yours")
    async def config_command(
        interaction: discord.Interaction, membre: discord.Member | None = None
    ) -> None:
        target = membre or interaction.user
        # Anyone can look up their own card; reading someone else's is a staff
        # action, since it is hardware information about a real person.
        if membre is not None and not _is_staff(interaction):
            await interaction.response.send_message(
                "Seul le staff peut consulter la fiche d'un autre membre.\n"
                "Only staff can look up someone else's card.",
                ephemeral=True,
            )
            return

        profile = await bot.build_handler(interaction.guild).profile_for(target.id)
        if profile is None or profile.is_empty:
            channels = bot.channels_by_guild.get(
                interaction.guild.id if interaction.guild else 0, {}
            )
            channel = channels.get(bp.KEY_STAFF_SETUPS)
            where = channel.mention if channel else "#beta-configs"
            await interaction.response.send_message(
                texts.SETUP_EMPTY.format(channel=where), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=views_setup_embed(profile), ephemeral=True
        )

    @bot.tree.command(
        name="aide",
        description="Où signaler un bug ou proposer une idée / Where to report",
    )
    async def help_command(interaction: discord.Interaction) -> None:
        lines = [
            "**🇫🇷** Boutons de rapport dans les salons d'aide :",
            "**🇬🇧** Report buttons live in the help channels:",
            "",
        ]
        channels = bot.channels_by_guild.get(
            interaction.guild.id if interaction.guild else 0, {}
        )
        for product in bp.PRODUCTS:
            channel = channels.get(product.help_channel_key)
            where = channel.mention if channel else "`#" + product.slug + "-aide-help`"
            lines.append(f"{product.emoji} **{product.label}** → {where}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
