"""Persistent buttons and the forms behind them.

``custom_id`` values are stable strings built from the product slug. They must
never change: Discord stores them inside the posted message, so a renamed id
turns every existing button into a dead one.
"""

from __future__ import annotations

import logging

import discord

from . import blueprint as bp
from . import texts
from .github_bridge import GitHubClient, GitHubError, IssueDraft, build_labels, truncate_title
from .profiles import Profile, ProfileStore, normalise_resolution, normalise_scaling

log = logging.getLogger("discord-bdo.views")

CUSTOM_ID_PREFIX = "bdo"

#: Discord hard limits. Exceeding them is a 400 from the API, so we cut first.
THREAD_NAME_LIMIT = 100
MESSAGE_LIMIT = 2000


def bug_button_id(slug: str) -> str:
    return f"{CUSTOM_ID_PREFIX}:bug:{slug}"


def idea_button_id(slug: str) -> str:
    return f"{CUSTOM_ID_PREFIX}:idea:{slug}"


SETUP_EDIT_ID = f"{CUSTOM_ID_PREFIX}:setup:edit"
SETUP_SHOW_ID = f"{CUSTOM_ID_PREFIX}:setup:show"


def clip(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def thread_name(prefix: str, summary: str) -> str:
    return clip(f"{prefix} {' '.join(summary.split())}", THREAD_NAME_LIMIT)


# --------------------------------------------------------------------------- #
# Thread creation, shared by both modals
# --------------------------------------------------------------------------- #


async def open_thread(
    channel: discord.abc.GuildChannel,
    *,
    name: str,
    body: str,
    tag_name: str | None = None,
) -> discord.Thread:
    """Create a thread in a forum, or in a text channel used as a fallback."""
    body = clip(body, MESSAGE_LIMIT)

    if isinstance(channel, discord.ForumChannel):
        tags: list[discord.ForumTag] = []
        if tag_name:
            found = discord.utils.find(
                lambda t: t.name == tag_name, channel.available_tags
            )
            if found is not None:
                tags.append(found)
        created = await channel.create_thread(name=name, content=body, applied_tags=tags)
        return created.thread

    if isinstance(channel, discord.TextChannel):
        message = await channel.send(body)
        return await message.create_thread(name=name)

    raise TypeError(f"cannot open a thread in {type(channel).__name__}")


def format_setup_block(profile: Profile | None) -> str:
    """The setup lines as they appear inside a Discord bug thread."""
    if profile is None or profile.is_empty:
        return texts.SETUP_MISSING_IN_REPORT + "\n"
    return texts.THREAD_BUG_SETUP.format(lines="\n".join(profile.as_lines()))


def format_setup_rows(profile: Profile | None) -> str:
    """The setup rows appended to the GitHub issue's table."""
    if profile is None or profile.is_empty:
        return ""
    rows = [
        ("Resolution", profile.resolution),
        ("Scaling", profile.scaling),
        ("Display mode", profile.display_mode),
        ("Game language", profile.game_language),
        ("Hardware", profile.hardware),
    ]
    return "".join(f"| {name} | {value} |\n" for name, value in rows if value)


async def ask_for_screenshot(thread: discord.Thread) -> None:
    """Post the screenshot instructions, swallowing any posting failure."""
    try:
        await thread.send(texts.SCREENSHOT_ASK)
    except discord.HTTPException as exc:  # the report itself already landed
        log.warning("could not ask for a screenshot in %s: %s", thread, exc)


class ReportHandler:
    """Everything a modal needs to do its job, injected rather than imported.

    Keeping the collaborators here means the modals hold no global state and
    the whole submit path can be tested with fakes.
    """

    def __init__(
        self,
        *,
        channels: dict[str, discord.abc.GuildChannel],
        github: GitHubClient | None,
        default_labels: tuple[str, ...] = (),
        staff_log: discord.TextChannel | None = None,
        dry_run: bool = False,
        profiles: ProfileStore | None = None,
    ) -> None:
        self.channels = channels
        self.github = github
        self.default_labels = default_labels
        self.staff_log = staff_log
        self.dry_run = dry_run
        self.profiles = profiles

    def channel_for(self, key: str) -> discord.abc.GuildChannel | None:
        return self.channels.get(key)

    async def profile_for(self, user_id: int) -> Profile | None:
        """Never let a storage failure block a report: no card is survivable."""
        if self.profiles is None:
            return None
        try:
            return await self.profiles.get(user_id)
        except Exception as exc:  # sqlite locked, file gone, disk full
            log.warning("profile lookup failed for %s: %s", user_id, exc)
            return None

    async def save_profile(self, profile: Profile) -> bool:
        """Persist a setup card. Returns whether it actually landed."""
        if self.profiles is None:
            log.warning("no profile store configured, setup card dropped")
            return False
        try:
            await self.profiles.save(profile)
        except Exception as exc:
            log.warning("profile save failed for %s: %s", profile.user_id, exc)
            return False
        return True

    async def publish_setup_card(self, profile: Profile) -> None:
        """Mirror the card into the beta channel, replacing the member's old one.

        Editing in place rather than appending keeps the channel usable as a
        directory: one message per tester, always current.
        """
        channel = self.channels.get(bp.KEY_BETA_SETUPS)
        if not isinstance(channel, discord.TextChannel):
            return
        embed = setup_embed(profile)
        marker = f"<@{profile.user_id}>"
        try:
            async for message in channel.history(limit=200):
                if (
                    message.author.id == channel.guild.me.id
                    and message.content == marker
                ):
                    await message.edit(content=marker, embed=embed)
                    return
            await channel.send(content=marker, embed=embed)
        except discord.HTTPException as exc:
            log.warning("could not publish the setup card: %s", exc)

    async def log_staff(self, message: str) -> None:
        if self.staff_log is None:
            return
        try:
            await self.staff_log.send(clip(message, MESSAGE_LIMIT))
        except discord.HTTPException as exc:  # never let logging break a report
            log.warning("staff log failed: %s", exc)

    async def create_issue(self, draft: IssueDraft) -> str | None:
        """Return the issue URL, or ``None`` when GitHub is off or failing."""
        if self.github is None or not self.github.enabled:
            return None
        if self.dry_run:
            log.info("dry run: would open %s / %s", draft.repo, draft.title)
            return None
        try:
            issue = await self.github.create_issue(draft)
        except GitHubError as exc:
            log.warning("github issue failed: %s", exc)
            await self.log_staff(
                texts.LOG_ISSUE_FAIL.format(link=draft.title, error=exc)
            )
            return None
        await self.log_staff(texts.LOG_ISSUE_OK.format(url=issue.url))
        return issue.url


# --------------------------------------------------------------------------- #
# Modals
# --------------------------------------------------------------------------- #


class BugModal(discord.ui.Modal):
    def __init__(self, product: bp.ProductSpec, handler: ReportHandler) -> None:
        super().__init__(title=texts.MODAL_BUG_TITLE.format(label=product.label))
        self.product = product
        self.handler = handler

        self.summary = discord.ui.TextInput(
            label=texts.FIELD_SUMMARY_LABEL,
            placeholder=texts.FIELD_SUMMARY_PLACEHOLDER,
            max_length=140,
        )
        self.version = discord.ui.TextInput(
            label=texts.FIELD_VERSION_LABEL,
            placeholder=texts.FIELD_VERSION_PLACEHOLDER,
            max_length=40,
        )
        self.system = discord.ui.TextInput(
            label=texts.FIELD_SYSTEM_LABEL,
            placeholder=product.platform_hint,
            max_length=60,
            required=False,
        )
        self.steps = discord.ui.TextInput(
            label=texts.FIELD_STEPS_LABEL,
            placeholder=texts.FIELD_STEPS_PLACEHOLDER,
            style=discord.TextStyle.paragraph,
            max_length=1500,
        )
        for item in (self.summary, self.version, self.system, self.steps):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        channel = self.handler.channel_for(self.product.bug_channel_key)
        if channel is None:
            await interaction.followup.send(texts.ERR_NO_CHANNEL, ephemeral=True)
            return

        author = interaction.user
        system = self.system.value.strip() or "non précisé / not stated"
        profile = await self.handler.profile_for(author.id)
        body = texts.THREAD_BUG_BODY.format(
            author=author.mention,
            version=self.version.value.strip(),
            system=system,
            setup=format_setup_block(profile),
            steps=self.steps.value.strip(),
        )

        thread = await open_thread(
            channel,
            name=thread_name("🐛", self.summary.value),
            body=body,
            tag_name=bp.BUG_TAGS[0],
        )
        # A bug that reads the screen is half-reported without an image, so the
        # ask goes in the thread rather than being buried in the form.
        await ask_for_screenshot(thread)

        issue_url = await self.handler.create_issue(
            IssueDraft(
                repo=self.product.repo,
                title=truncate_title(f"[Discord] {self.summary.value}"),
                body=texts.ISSUE_BUG_BODY.format(
                    author=author.display_name,
                    version=self.version.value.strip(),
                    system=system,
                    setup_rows=format_setup_rows(profile),
                    summary=self.summary.value.strip(),
                    steps=self.steps.value.strip(),
                    thread_url=thread.jump_url,
                ),
                labels=build_labels("bug", self.handler.default_labels),
            )
        )

        answer = texts.ACK_BUG.format(link=thread.jump_url)
        if issue_url:
            answer += texts.ACK_GITHUB.format(issue_url=issue_url)
        await interaction.followup.send(answer, ephemeral=True)

        await self.handler.log_staff(
            texts.LOG_REPORT.format(
                kind="Bug",
                product=self.product.label,
                author=author.display_name,
                link=thread.jump_url,
            )
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:  # pragma: no cover - defensive
        log.exception("bug modal failed", exc_info=error)
        await _report_error(interaction)


class IdeaModal(discord.ui.Modal):
    def __init__(self, product: bp.ProductSpec, handler: ReportHandler) -> None:
        super().__init__(title=texts.MODAL_IDEA_TITLE.format(label=product.label))
        self.product = product
        self.handler = handler

        self.summary = discord.ui.TextInput(
            label=texts.FIELD_IDEA_LABEL,
            placeholder=texts.FIELD_IDEA_PLACEHOLDER,
            max_length=140,
        )
        self.problem = discord.ui.TextInput(
            label=texts.FIELD_PROBLEM_LABEL,
            placeholder=texts.FIELD_PROBLEM_PLACEHOLDER,
            style=discord.TextStyle.paragraph,
            max_length=1500,
        )
        for item in (self.summary, self.problem):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        channel = self.handler.channel_for(self.product.idea_channel_key)
        if channel is None:
            await interaction.followup.send(texts.ERR_NO_CHANNEL, ephemeral=True)
            return

        author = interaction.user
        body = texts.THREAD_IDEA_BODY.format(
            author=author.mention, problem=self.problem.value.strip()
        )
        thread = await open_thread(
            channel,
            name=thread_name("💡", self.summary.value),
            body=body,
            tag_name=bp.IDEA_TAGS[0],
        )

        issue_url = await self.handler.create_issue(
            IssueDraft(
                repo=self.product.repo,
                title=truncate_title(f"[Discord] {self.summary.value}"),
                body=texts.ISSUE_IDEA_BODY.format(
                    author=author.display_name,
                    summary=self.summary.value.strip(),
                    problem=self.problem.value.strip(),
                    thread_url=thread.jump_url,
                ),
                labels=build_labels("idea", self.handler.default_labels),
            )
        )

        answer = texts.ACK_IDEA.format(link=thread.jump_url)
        if issue_url:
            answer += texts.ACK_GITHUB.format(issue_url=issue_url)
        await interaction.followup.send(answer, ephemeral=True)

        await self.handler.log_staff(
            texts.LOG_REPORT.format(
                kind="Idée",
                product=self.product.label,
                author=author.display_name,
                link=thread.jump_url,
            )
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:  # pragma: no cover - defensive
        log.exception("idea modal failed", exc_info=error)
        await _report_error(interaction)


async def _report_error(interaction: discord.Interaction) -> None:
    try:
        if interaction.response.is_done():
            await interaction.followup.send(texts.ERR_GENERIC, ephemeral=True)
        else:
            await interaction.response.send_message(texts.ERR_GENERIC, ephemeral=True)
    except discord.HTTPException:  # pragma: no cover - nothing left to do
        pass


# --------------------------------------------------------------------------- #
# The panel
# --------------------------------------------------------------------------- #


class SupportPanel(discord.ui.View):
    """Two buttons, alive forever (``timeout=None`` plus stable custom ids)."""

    def __init__(self, product: bp.ProductSpec, handler: ReportHandler) -> None:
        super().__init__(timeout=None)
        self.product = product
        self.handler = handler

        bug = discord.ui.Button(
            label=texts.BTN_BUG,
            style=discord.ButtonStyle.danger,
            custom_id=bug_button_id(product.slug),
        )
        bug.callback = self._on_bug
        self.add_item(bug)

        idea = discord.ui.Button(
            label=texts.BTN_IDEA,
            style=discord.ButtonStyle.primary,
            custom_id=idea_button_id(product.slug),
        )
        idea.callback = self._on_idea
        self.add_item(idea)

    async def _on_bug(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(BugModal(self.product, self.handler))

    async def _on_idea(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(IdeaModal(self.product, self.handler))


# --------------------------------------------------------------------------- #
# Beta: the hardware setup card
# --------------------------------------------------------------------------- #


class SetupModal(discord.ui.Modal):
    """Five fields, which is exactly Discord's per-modal limit.

    Pre-filled from the stored card when there is one, so updating a single
    value does not mean retyping the other four.
    """

    def __init__(self, handler: ReportHandler, existing: Profile | None = None) -> None:
        super().__init__(title=texts.MODAL_SETUP_TITLE)
        self.handler = handler

        def previous(attr: str) -> str:
            return getattr(existing, attr, "") if existing else ""

        self.resolution = discord.ui.TextInput(
            label=texts.FIELD_RESOLUTION_LABEL,
            placeholder=texts.FIELD_RESOLUTION_PLACEHOLDER,
            default=previous("resolution") or None,
            max_length=40,
        )
        self.scaling = discord.ui.TextInput(
            label=texts.FIELD_SCALING_LABEL,
            placeholder=texts.FIELD_SCALING_PLACEHOLDER,
            default=previous("scaling") or None,
            max_length=20,
        )
        self.display_mode = discord.ui.TextInput(
            label=texts.FIELD_DISPLAY_MODE_LABEL,
            placeholder=texts.FIELD_DISPLAY_MODE_PLACEHOLDER,
            default=previous("display_mode") or None,
            max_length=60,
        )
        self.game_language = discord.ui.TextInput(
            label=texts.FIELD_GAME_LANGUAGE_LABEL,
            placeholder=texts.FIELD_GAME_LANGUAGE_PLACEHOLDER,
            default=previous("game_language") or None,
            max_length=30,
            required=False,
        )
        self.hardware = discord.ui.TextInput(
            label=texts.FIELD_HARDWARE_LABEL,
            placeholder=texts.FIELD_HARDWARE_PLACEHOLDER,
            default=previous("hardware") or None,
            style=discord.TextStyle.paragraph,
            max_length=300,
            required=False,
        )
        for item in (
            self.resolution,
            self.scaling,
            self.display_mode,
            self.game_language,
            self.hardware,
        ):
            self.add_item(item)

    def to_profile(self, user: discord.abc.User) -> Profile:
        return Profile(
            user_id=user.id,
            display_name=getattr(user, "display_name", str(user)),
            resolution=normalise_resolution(self.resolution.value),
            scaling=normalise_scaling(self.scaling.value),
            display_mode=self.display_mode.value.strip(),
            game_language=self.game_language.value.strip(),
            hardware=" ".join(self.hardware.value.split()),
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        profile = self.to_profile(interaction.user)

        saved = await self.handler.save_profile(profile)
        if not saved:
            await interaction.followup.send(texts.ERR_GENERIC, ephemeral=True)
            return

        await interaction.followup.send(texts.SETUP_SAVED, ephemeral=True)
        await self.handler.publish_setup_card(profile)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:  # pragma: no cover - defensive
        log.exception("setup modal failed", exc_info=error)
        await _report_error(interaction)


class SetupPanel(discord.ui.View):
    def __init__(self, handler: ReportHandler) -> None:
        super().__init__(timeout=None)
        self.handler = handler

        edit = discord.ui.Button(
            label=texts.BTN_SETUP,
            style=discord.ButtonStyle.primary,
            custom_id=SETUP_EDIT_ID,
        )
        edit.callback = self._on_edit
        self.add_item(edit)

        show = discord.ui.Button(
            label=texts.BTN_SETUP_SHOW,
            style=discord.ButtonStyle.secondary,
            custom_id=SETUP_SHOW_ID,
        )
        show.callback = self._on_show
        self.add_item(show)

    async def _on_edit(self, interaction: discord.Interaction) -> None:
        existing = await self.handler.profile_for(interaction.user.id)
        await interaction.response.send_modal(SetupModal(self.handler, existing))

    async def _on_show(self, interaction: discord.Interaction) -> None:
        profile = await self.handler.profile_for(interaction.user.id)
        if profile is None or profile.is_empty:
            channel = self.handler.channel_for(bp.KEY_BETA_SETUPS)
            where = channel.mention if channel else "#beta-configs"
            await interaction.response.send_message(
                texts.SETUP_EMPTY.format(channel=where), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=setup_embed(profile), ephemeral=True
        )


def setup_embed(profile: Profile) -> discord.Embed:
    return discord.Embed(
        description=texts.SETUP_CARD.format(
            author=profile.display_name or f"<@{profile.user_id}>",
            lines="\n".join(profile.as_lines()),
            updated=profile.updated_at or "—",
        ),
        colour=discord.Colour(0x6BBF59),
    )


def setup_panel_embed() -> discord.Embed:
    return discord.Embed(
        title=texts.SETUP_PANEL_TITLE,
        description=texts.SETUP_PANEL_BODY,
        colour=discord.Colour(0x6BBF59),
    )


def panel_embed(product: bp.ProductSpec) -> discord.Embed:
    return discord.Embed(
        title=texts.PANEL_TITLE.format(emoji=product.emoji, label=product.label),
        description=texts.PANEL_BODY,
        colour=discord.Colour(product.colour),
    )
