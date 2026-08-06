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
from .profiles import (
    DISPLAY_MODES,
    GAME_LANGUAGES,
    LABELS_EN,
    MACHINE_FIELDS,
    SCREEN_FIELDS,
    WINDOWS_SCALES,
    Profile,
    ProfileStore,
    normalise_resolution,
    normalise_scaling,
)

log = logging.getLogger("discord-bdo.views")

CUSTOM_ID_PREFIX = "bdo"

#: Discord hard limits. Exceeding them is a 400 from the API, so we cut first.
THREAD_NAME_LIMIT = 100
MESSAGE_LIMIT = 2000


def bug_button_id(slug: str) -> str:
    return f"{CUSTOM_ID_PREFIX}:bug:{slug}"


def idea_button_id(slug: str) -> str:
    return f"{CUSTOM_ID_PREFIX}:idea:{slug}"


SETUP_SCREEN_ID = f"{CUSTOM_ID_PREFIX}:setup:screen"
SETUP_MACHINE_ID = f"{CUSTOM_ID_PREFIX}:setup:machine"
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
    return "".join(
        f"| {label} | {getattr(profile, attr)} |\n"
        for attr, label in LABELS_EN
        if getattr(profile, attr)
    )


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

    async def save_profile(
        self, profile: Profile, only: tuple[str, ...] | None = None
    ) -> bool:
        """Persist a setup card. Returns whether it actually landed."""
        if self.profiles is None:
            log.warning("no profile store configured, setup card dropped")
            return False
        try:
            await self.profiles.save(profile, only=only)
        except Exception as exc:
            log.warning("profile save failed for %s: %s", profile.user_id, exc)
            return False
        return True

    async def publish_setup_card(self, profile: Profile) -> None:
        """Mirror the card into the beta channel, replacing the member's old one.

        Editing in place rather than appending keeps the channel usable as a
        directory: one message per tester, always current.
        """
        channel = self.channels.get(bp.KEY_STAFF_SETUPS)
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
# The setup card: screen form + machine form
# --------------------------------------------------------------------------- #


class _BaseSetupModal(discord.ui.Modal):
    """Shared submit path for the two halves of the setup card.

    Subclasses declare ``COLUMNS`` and build their own fields; the save is
    scoped to those columns so one form never blanks the other's values.
    """

    COLUMNS: tuple[str, ...] = ()

    def __init__(self, title: str, handler: ReportHandler) -> None:
        super().__init__(title=title)
        self.handler = handler

    def collect(self) -> dict[str, str]:  # pragma: no cover - overridden
        raise NotImplementedError

    def to_profile(self, user: discord.abc.User) -> Profile:
        return Profile(
            user_id=user.id,
            display_name=getattr(user, "display_name", str(user)),
            **self.collect(),
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        profile = self.to_profile(interaction.user)

        if not await self.handler.save_profile(profile, only=self.COLUMNS):
            await interaction.followup.send(texts.ERR_GENERIC, ephemeral=True)
            return

        await interaction.followup.send(texts.SETUP_SAVED, ephemeral=True)
        # Publish the merged card, not just what this one form carried.
        merged = await self.handler.profile_for(interaction.user.id) or profile
        await self.handler.publish_setup_card(merged)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:  # pragma: no cover - defensive
        log.exception("setup modal failed", exc_info=error)
        await _report_error(interaction)


def _picker(choices, current: str, placeholder: str) -> discord.ui.Select:
    """A dropdown whose stored value is preselected when there is one.

    ``current`` is matched against the stored value, not the label: the label
    can be reworded without orphaning every card already filled in.
    """
    options = [
        discord.SelectOption(label=label, value=value, default=value == current)
        for value, label in choices
    ]
    return discord.ui.Select(placeholder=placeholder, options=options, min_values=1, max_values=1)


def _chosen(select: discord.ui.Select) -> str:
    """The single selected value, or empty when the member picked nothing."""
    return select.values[0] if select.values else ""


def _previous(existing, attr):
    """Prefill value, or None so the field renders empty rather than "None"."""
    return (getattr(existing, attr, "") if existing else "") or None


class ScreenModal(_BaseSetupModal):
    """Five fields, which is exactly Discord's per-modal limit.

    These are the ones that decide how the OCR behaves, which is why the
    machine specs were split into their own form rather than squeezed in here.
    """

    COLUMNS = SCREEN_FIELDS

    def __init__(self, handler: ReportHandler, existing: Profile | None = None) -> None:
        super().__init__(texts.MODAL_SCREEN_TITLE, handler)

        self.resolution = discord.ui.TextInput(
            label=texts.FIELD_RESOLUTION_LABEL,
            placeholder=texts.FIELD_RESOLUTION_PLACEHOLDER,
            default=_previous(existing, "resolution"),
            max_length=40,
        )
        self.scaling = _picker(
            WINDOWS_SCALES,
            getattr(existing, "scaling", "") if existing else "",
            texts.FIELD_SCALING_PLACEHOLDER,
        )
        self.ui_scale = discord.ui.TextInput(
            label=texts.FIELD_UI_SCALE_LABEL,
            placeholder=texts.FIELD_UI_SCALE_PLACEHOLDER,
            default=_previous(existing, "ui_scale"),
            max_length=20,
        )
        self.display_mode = _picker(
            DISPLAY_MODES,
            getattr(existing, "display_mode", "") if existing else "",
            texts.FIELD_DISPLAY_MODE_PLACEHOLDER,
        )
        self.game_language = _picker(
            GAME_LANGUAGES,
            getattr(existing, "game_language", "") if existing else "",
            texts.FIELD_GAME_LANGUAGE_PLACEHOLDER,
        )
        # A Select cannot carry its own label, it has to be wrapped. Text
        # inputs still carry theirs, so only the pickers are wrapped here.
        self.add_item(self.resolution)
        self.add_item(
            discord.ui.Label(
                text=texts.FIELD_SCALING_LABEL,
                description=texts.FIELD_SCALING_HINT,
                component=self.scaling,
            )
        )
        self.add_item(self.ui_scale)
        self.add_item(
            discord.ui.Label(
                text=texts.FIELD_DISPLAY_MODE_LABEL, component=self.display_mode
            )
        )
        self.add_item(
            discord.ui.Label(
                text=texts.FIELD_GAME_LANGUAGE_LABEL, component=self.game_language
            )
        )

    def collect(self) -> dict[str, str]:
        return {
            "resolution": normalise_resolution(self.resolution.value),
            # Both scales are percentages typed by hand, so the same tolerant
            # parser applies: "1.5", "150" and "150 %" all mean 150%.
            # Picked from a list, so already canonical: no normalisation, and
            # nothing to reconcile later.
            "scaling": _chosen(self.scaling),
            "ui_scale": normalise_scaling(self.ui_scale.value),
            "display_mode": _chosen(self.display_mode),
            "game_language": _chosen(self.game_language),
        }


class MachineModal(_BaseSetupModal):
    """The PC itself. Optional: it matters for slowness, not for OCR accuracy."""

    COLUMNS = MACHINE_FIELDS

    def __init__(self, handler: ReportHandler, existing: Profile | None = None) -> None:
        super().__init__(texts.MODAL_MACHINE_TITLE, handler)

        self.cpu = discord.ui.TextInput(
            label=texts.FIELD_CPU_LABEL,
            placeholder=texts.FIELD_CPU_PLACEHOLDER,
            default=_previous(existing, "cpu"),
            max_length=80,
            required=False,
        )
        self.gpu = discord.ui.TextInput(
            label=texts.FIELD_GPU_LABEL,
            placeholder=texts.FIELD_GPU_PLACEHOLDER,
            default=_previous(existing, "gpu"),
            max_length=80,
            required=False,
        )
        self.ram = discord.ui.TextInput(
            label=texts.FIELD_RAM_LABEL,
            placeholder=texts.FIELD_RAM_PLACEHOLDER,
            default=_previous(existing, "ram"),
            max_length=40,
            required=False,
        )
        for item in (self.cpu, self.gpu, self.ram):
            self.add_item(item)

    def collect(self) -> dict[str, str]:
        return {
            "cpu": " ".join(self.cpu.value.split()),
            "gpu": " ".join(self.gpu.value.split()),
            "ram": " ".join(self.ram.value.split()),
        }


class SetupPanel(discord.ui.View):
    def __init__(self, handler: ReportHandler) -> None:
        super().__init__(timeout=None)
        self.handler = handler

        buttons = (
            (texts.BTN_SETUP_SCREEN, SETUP_SCREEN_ID, discord.ButtonStyle.primary,
             self._on_screen),
            (texts.BTN_SETUP_MACHINE, SETUP_MACHINE_ID, discord.ButtonStyle.secondary,
             self._on_machine),
            (texts.BTN_SETUP_SHOW, SETUP_SHOW_ID, discord.ButtonStyle.secondary,
             self._on_show),
        )
        for label, custom_id, style, callback in buttons:
            button = discord.ui.Button(label=label, style=style, custom_id=custom_id)
            button.callback = callback
            self.add_item(button)

    async def _on_screen(self, interaction: discord.Interaction) -> None:
        existing = await self.handler.profile_for(interaction.user.id)
        await interaction.response.send_modal(ScreenModal(self.handler, existing))

    async def _on_machine(self, interaction: discord.Interaction) -> None:
        existing = await self.handler.profile_for(interaction.user.id)
        await interaction.response.send_modal(MachineModal(self.handler, existing))

    async def _on_show(self, interaction: discord.Interaction) -> None:
        profile = await self.handler.profile_for(interaction.user.id)
        if profile is None or profile.is_empty:
            await interaction.response.send_message(
                texts.SETUP_EMPTY.format(channel="ce salon / this channel"),
                ephemeral=True,
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
