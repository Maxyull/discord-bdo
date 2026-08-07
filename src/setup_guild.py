"""Reconcile a live Discord server with :mod:`blueprint`.

The function is *idempotent*: running it twice changes nothing the second
time. It never deletes anything. A channel removed from the blueprint stays on
the server until a human deletes it, because an automated delete of a channel
full of user reports is not a mistake anyone recovers from.
"""

from __future__ import annotations

import logging

import discord

from . import blueprint as bp
from . import guides
from . import texts

log = logging.getLogger("discord-bdo.setup")


class PermissionsMissing(RuntimeError):
    """The bot cannot build the server, with the reasons in plain words.

    Raised rather than returned: a field on the report can be ignored by a
    caller, and that is exactly how the CLI path ended up building half a
    server and dying on a bare Forbidden.
    """

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


# --------------------------------------------------------------------------- #
# Permission overwrites
# --------------------------------------------------------------------------- #


def overwrites_for(
    access: bp.Access,
    *,
    everyone: discord.Role,
    staff: discord.Role | None,
    moderator: discord.Role | None,
    muted: discord.Role | None,
    tester: discord.Role | None = None,
    bot_member: discord.Member | None = None,
) -> dict:
    """Build the permission table for one access level."""
    result: dict = {}

    if access is bp.Access.PUBLIC:
        result[everyone] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, create_public_threads=True
        )
    elif access is bp.Access.READ_ONLY:
        result[everyone] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            create_public_threads=False,
            # Replying inside an existing thread stays open: it is what makes
            # the guide forum useful (a question under the guide it is about)
            # without letting anyone open a channel-level topic.
            send_messages_in_threads=True,
            add_reactions=True,
        )
    elif access in (bp.Access.BETA_ONLY, bp.Access.BETA_READ_ONLY):
        result[everyone] = discord.PermissionOverwrite(view_channel=False)
        if tester is not None:
            result[tester] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                add_reactions=True,
                # Read-only beta channels still let testers reply inside a
                # thread: the channel stays clean, the discussion stays alive.
                send_messages=access is bp.Access.BETA_ONLY,
                send_messages_in_threads=True,
                create_public_threads=access is bp.Access.BETA_ONLY,
            )
    elif access is bp.Access.STAFF_ONLY:
        result[everyone] = discord.PermissionOverwrite(view_channel=False)
    else:  # pragma: no cover - Access is exhaustive
        raise ValueError(f"unhandled access level {access!r}")

    for role in (staff, moderator):
        if role is not None and access is not bp.Access.PUBLIC:
            result[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True
            )

    if muted is not None:
        result[muted] = discord.PermissionOverwrite(
            send_messages=False,
            send_messages_in_threads=False,
            create_public_threads=False,
            add_reactions=False,
        )

    # The bot must keep writing into read-only and staff channels.
    if bot_member is not None and access is not bp.Access.PUBLIC:
        result[bot_member] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_messages=True
        )

    return result


# --------------------------------------------------------------------------- #
# Lookup helpers
# --------------------------------------------------------------------------- #


#: Access levels that hide a channel from @everyone. A channel left at the
#: PUBLIC default inside one of these categories must inherit the restriction,
#: otherwise a single forgotten `access=` leaks a private channel to the world.
RESTRICTED = (bp.Access.BETA_ONLY, bp.Access.STAFF_ONLY)


def effective_access(
    category: bp.CategorySpec, channel: bp.ChannelSpec
) -> bp.Access:
    """Resolve a channel's access against its category's."""
    if category.access in RESTRICTED and channel.access is bp.Access.PUBLIC:
        return category.access
    return channel.access


def find_role(guild: discord.Guild, name: str) -> discord.Role | None:
    return discord.utils.get(guild.roles, name=name)


def find_category(guild: discord.Guild, name: str) -> discord.CategoryChannel | None:
    return discord.utils.get(guild.categories, name=name)


def normalise(name: str) -> str:
    """Discord lowercases text channel names and turns spaces into hyphens."""
    return name.strip().lower().replace(" ", "-")


def find_channel(
    category: discord.CategoryChannel, name: str
) -> discord.abc.GuildChannel | None:
    target = normalise(name)
    for channel in category.channels:
        if normalise(channel.name) == target:
            return channel
    return None


# --------------------------------------------------------------------------- #
# Steps
# --------------------------------------------------------------------------- #


#: What the setup pass actually needs. Checked up front rather than discovered
#: halfway through, when half the server is built and the error message is a
#: bare Forbidden.
REQUIRED_PERMISSIONS = (
    ("manage_channels", "Gérer les salons"),
    ("manage_roles", "Gérer les rôles"),
    ("view_channel", "Voir les salons"),
    ("send_messages", "Envoyer des messages"),
    ("embed_links", "Intégrer des liens"),
    ("create_public_threads", "Créer des fils publics"),
    ("send_messages_in_threads", "Envoyer des messages dans les fils"),
    ("read_message_history", "Voir l'historique des messages"),
)


def preflight(guild: discord.Guild) -> list[str]:
    """Reasons the setup would fail, in the member's own words.

    Empty list means go. Being told what is missing beats a half-built server
    and a Forbidden with no context.
    """
    me = guild.me
    if me is None:  # pragma: no cover - only before the member cache fills
        return []

    problems: list[str] = []
    permissions = me.guild_permissions
    if not permissions.administrator:
        for name, label in REQUIRED_PERMISSIONS:
            if not getattr(permissions, name, False):
                problems.append(texts.PREFLIGHT_MISSING_PERM.format(name=label))

    # Creating roles is not enough: Discord refuses to let the bot manage any
    # role above its own, and the blueprint's top role is meant to be Dev.
    highest_bot_role = me.top_role.position if me.top_role else 0
    blocking = [
        role
        for role in guild.roles
        if role.name in {spec.name for spec in bp.ROLES}
        and role.position >= highest_bot_role
    ]
    if blocking:
        problems.append(texts.PREFLIGHT_LOW_ROLE)

    return problems


async def ensure_roles(guild: discord.Guild, report: bp.SetupReport) -> dict[str, discord.Role]:
    roles: dict[str, discord.Role] = {}
    for spec in bp.ROLES:
        existing = find_role(guild, spec.name)
        permissions = discord.Permissions(**{name: True for name in spec.permissions})
        if existing is None:
            created = await guild.create_role(
                name=spec.name,
                colour=discord.Colour(spec.colour),
                hoist=spec.hoist,
                mentionable=spec.mentionable,
                permissions=permissions,
                reason="discord-bdo setup",
            )
            roles[spec.name] = created
            report.created_roles.append(spec.name)
            log.info("role created: %s", spec.name)
        else:
            roles[spec.name] = existing
            report.skipped.append(f"rôle {spec.name}")

    await order_roles(guild, roles, report)
    return roles


async def order_roles(
    guild: discord.Guild, roles: dict[str, discord.Role], report: bp.SetupReport
) -> None:
    """Put the roles in blueprint order, Dev at the top.

    Discord decides who can moderate whom by list position, not by permission
    name, so a Mod role sitting under Joueur cannot time anyone out. Creation
    order alone does not guarantee this, hence the explicit pass.
    """
    ordered = [roles[spec.name] for spec in bp.ROLES if spec.name in roles]
    if not ordered:
        return

    # Position 0 is @everyone, so the lowest blueprint role starts at 1.
    positions = {
        role: index for index, role in enumerate(reversed(ordered), start=1)
    }
    if all(role.position == position for role, position in positions.items()):
        return

    try:
        await guild.edit_role_positions(positions=positions, reason="discord-bdo setup")
    except discord.HTTPException as exc:
        report.warnings.append(
            "Ordre des rôles non appliqué "
            f"({getattr(exc, 'text', None) or exc}). "
            "Remontez le rôle du bot au-dessus de Dev, puis relancez /setup."
        )
        return
    report.updated_roles.extend(spec.name for spec in bp.ROLES if spec.name in roles)


async def ensure_community(guild: discord.Guild, report: bp.SetupReport) -> bool:
    """Enable the Community feature, needed for forum channels.

    Returns whether forums can be created. A failure here is not fatal: the
    caller falls back to plain text channels and says so in the report.
    """
    if "COMMUNITY" in guild.features:
        return True

    rules = discord.utils.get(guild.text_channels, name=normalise("règles-rules"))
    updates = discord.utils.get(
        guild.text_channels, name=normalise("annonces-announcements")
    )
    if rules is None or updates is None:
        report.warnings.append(
            "Mode Communauté non activé : salons de règles/annonces introuvables."
        )
        return False

    try:
        await guild.edit(
            community=True,
            rules_channel=rules,
            public_updates_channel=updates,
            verification_level=discord.VerificationLevel.medium,
            explicit_content_filter=discord.ContentFilter.all_members,
            reason="discord-bdo setup: forums require Community",
        )
    except discord.HTTPException as exc:
        report.warnings.append(
            "Mode Communauté non activé automatiquement "
            f"({exc.text or exc}). Activez-le dans Paramètres du serveur > "
            "Activer la communauté, puis relancez le script : les forums seront créés."
        )
        return False

    log.info("community mode enabled")
    return True


async def _create_channel(
    guild: discord.Guild,
    category: discord.CategoryChannel,
    spec: bp.ChannelSpec,
    *,
    overwrites: dict,
    forums_available: bool,
    report: bp.SetupReport,
) -> discord.abc.GuildChannel:
    kind = spec.kind
    if kind is bp.ChannelKind.FORUM and not forums_available:
        report.warnings.append(
            f"{spec.name} créé en salon texte : le mode Communauté n'est pas actif."
        )
        kind = bp.ChannelKind.TEXT

    common = {
        "name": spec.name,
        "category": category,
        "overwrites": overwrites,
        "reason": "discord-bdo setup",
    }

    if kind is bp.ChannelKind.VOICE:
        return await guild.create_voice_channel(**common)

    if kind is bp.ChannelKind.FORUM:
        channel = await guild.create_forum(topic=spec.topic or None, **common)
        if spec.tags:
            await channel.edit(
                available_tags=[discord.ForumTag(name=tag) for tag in spec.tags],
                reason="discord-bdo setup",
            )
        return channel

    return await guild.create_text_channel(
        topic=spec.topic or None,
        slowmode_delay=spec.slowmode,
        **common,
    )


async def ensure_channels(
    guild: discord.Guild,
    roles: dict[str, discord.Role],
    report: bp.SetupReport,
    *,
    forums_available: bool,
) -> dict[str, discord.abc.GuildChannel]:
    """Create every missing category and channel. Returns channels by key."""
    by_key: dict[str, discord.abc.GuildChannel] = {}
    everyone = guild.default_role
    bot_member = guild.me

    def build_overwrites(access: bp.Access) -> dict:
        return overwrites_for(
            access,
            everyone=everyone,
            staff=roles.get(bp.ROLE_DEV),
            moderator=roles.get(bp.ROLE_MOD),
            muted=roles.get(bp.ROLE_MUTED),
            tester=roles.get(bp.ROLE_TESTER),
            bot_member=bot_member,
        )

    for cat_spec in bp.CATEGORIES:
        category = find_category(guild, cat_spec.name)
        if category is None:
            category = await guild.create_category(
                name=cat_spec.name,
                overwrites=build_overwrites(cat_spec.access),
                reason="discord-bdo setup",
            )
            report.created_categories.append(cat_spec.name)
            log.info("category created: %s", cat_spec.name)
        else:
            report.skipped.append(f"catégorie {cat_spec.name}")

        for ch_spec in cat_spec.channels:
            access = effective_access(cat_spec, ch_spec)
            existing = find_channel(category, ch_spec.name)
            if existing is None:
                existing = await _create_channel(
                    guild,
                    category,
                    ch_spec,
                    overwrites=build_overwrites(access),
                    forums_available=forums_available,
                    report=report,
                )
                report.created_channels.append(ch_spec.name)
                log.info("channel created: %s", ch_spec.name)
            else:
                report.skipped.append(f"salon {ch_spec.name}")

            if ch_spec.key:
                by_key[ch_spec.key] = existing

    return by_key


async def _replace_bot_message(
    channel: discord.TextChannel, embed: discord.Embed, *, view=None
) -> discord.Message:
    """Post ``embed``, editing the bot's previous copy of *this* embed.

    Matching on the embed title rather than on "any embed by the bot" matters
    in #beta-configs, where the bot also posts one setup card per tester: a
    looser match would overwrite a member's card with the panel.
    """
    async for message in channel.history(limit=100):
        if (
            message.author.id == channel.guild.me.id
            and message.embeds
            and message.embeds[0].title == embed.title
        ):
            await message.edit(embed=embed, view=view)
            return message
    return await channel.send(embed=embed, view=view)


async def existing_thread_titles(forum: discord.ForumChannel) -> set[str]:
    """Titles already in the forum, active and archived.

    Archived threads count: a guide nobody read for a week is archived by
    Discord, and re-posting it would leave two copies with the same name.
    """
    titles = {thread.name for thread in forum.threads}
    try:
        async for thread in forum.archived_threads(limit=200):
            titles.add(thread.name)
    except discord.HTTPException as exc:  # missing permission, rate limit
        log.warning("could not list archived threads: %s", exc)
    return titles


async def post_guides(
    channels: dict[str, discord.abc.GuildChannel], report: bp.SetupReport
) -> None:
    """Seed the guide forum, skipping anything already there.

    Existing threads are never edited: a guide corrected by hand on Discord
    must survive the next ``/setup``.
    """
    forum = channels.get(bp.KEY_GUIDES)
    if not isinstance(forum, discord.ForumChannel):
        if forum is not None:
            report.warnings.append(
                "Guides non publiés : le salon n'est pas un forum "
                "(mode Communauté inactif ?)."
            )
        return

    already = await existing_thread_titles(forum)
    by_name = {tag.name: tag for tag in forum.available_tags}

    for guide in guides.GUIDES:
        if guide.title in already:
            report.skipped.append(f"guide {guide.title}")
            continue
        tags = [by_name[name] for name in guide.tags if name in by_name]
        try:
            await forum.create_thread(
                name=guide.title, content=guide.body, applied_tags=tags
            )
        except discord.HTTPException as exc:
            report.warnings.append(f"Guide « {guide.title} » non publié : {exc.text or exc}")
            continue
        report.created_channels.append(f"guide {guide.title}")
        log.info("guide posted: %s", guide.title)


async def post_static_messages(
    channels: dict[str, discord.abc.GuildChannel], report: bp.SetupReport
) -> None:
    welcome = channels.get(bp.KEY_WELCOME)
    if isinstance(welcome, discord.TextChannel):
        await _replace_bot_message(
            welcome,
            discord.Embed(
                title=texts.WELCOME_TITLE,
                description=texts.WELCOME_BODY,
                colour=discord.Colour(0xE8A33D),
            ),
        )
        report.updated_channels.append(welcome.name)

    rules = channels.get(bp.KEY_RULES)
    if isinstance(rules, discord.TextChannel):
        await _replace_bot_message(
            rules,
            discord.Embed(
                title=texts.RULES_TITLE,
                description=texts.RULES_BODY,
                colour=discord.Colour(0x4E9BD1),
            ),
        )
        report.updated_channels.append(rules.name)


async def run(guild: discord.Guild, *, post_panels=None) -> bp.SetupReport:
    """Full setup pass. ``post_panels`` is injected by the bot to add buttons.

    Raises :class:`PermissionsMissing` before touching anything when the bot
    lacks the rights to finish.
    """
    problems = preflight(guild)
    if problems:
        raise PermissionsMissing(problems)

    report = bp.SetupReport()

    roles = await ensure_roles(guild, report)

    # First pass: text channels must exist before Community can be enabled,
    # because Discord requires a rules channel and an updates channel.
    forums_available = "COMMUNITY" in guild.features
    channels = await ensure_channels(
        guild, roles, report, forums_available=forums_available
    )

    if not forums_available and bp.requires_community():
        forums_available = await ensure_community(guild, report)
        if forums_available:
            # Second pass now that forums are allowed.
            channels = await ensure_channels(
                guild, roles, report, forums_available=True
            )

    await post_static_messages(channels, report)
    await post_guides(channels, report)

    if post_panels is not None:
        await post_panels(guild, channels, report)

    return report
