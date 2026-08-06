"""Bot entry point.

Two jobs:

* keep the report buttons alive (persistent views, re-registered on boot);
* expose ``/setup`` so the server can be built or repaired without redeploying.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from . import blueprint as bp
from . import setup_guild
from .config import Config
from .github_bridge import GitHubClient
from .views import ReportHandler, SupportPanel, panel_embed

log = logging.getLogger("discord-bdo.bot")


class BdoBot(discord.Client):
    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        # Members are needed to resolve roles when applying permissions.
        intents.members = True
        super().__init__(intents=intents)

        self.config = config
        self.tree = app_commands.CommandTree(self)
        self.github = GitHubClient(config.github_token) if config.github_token else None
        #: Filled on ready, per guild id.
        self.channels_by_guild: dict[int, dict[str, discord.abc.GuildChannel]] = {}

        # Registered here rather than in setup_hook so the command list can be
        # inspected without connecting to Discord.
        register_commands(self)

    # -- lifecycle ---------------------------------------------------------- #

    async def setup_hook(self) -> None:
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
        )

    async def post_panels(
        self,
        guild: discord.Guild,
        channels: dict[str, discord.abc.GuildChannel],
        report: bp.SetupReport,
    ) -> None:
        """Put (or refresh) the button panel in each help channel."""
        self.channels_by_guild[guild.id] = channels
        handler = self.build_handler(guild)
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
            report.updated_channels.append(channel.name)


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
