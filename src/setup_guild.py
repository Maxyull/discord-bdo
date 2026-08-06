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
from . import texts

log = logging.getLogger("discord-bdo.setup")


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
            add_reactions=True,
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
    return roles


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
            staff=roles.get(bp.ROLE_STAFF),
            moderator=roles.get(bp.ROLE_MODERATOR),
            muted=roles.get(bp.ROLE_MUTED),
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
            access = (
                bp.Access.STAFF_ONLY
                if cat_spec.access is bp.Access.STAFF_ONLY
                else ch_spec.access
            )
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
    """Post ``embed``, editing the bot's previous message if there is one.

    Without this the setup script would stack a new copy of the rules every
    time it runs.
    """
    async for message in channel.history(limit=50):
        if message.author.id == channel.guild.me.id and message.embeds:
            await message.edit(embed=embed, view=view)
            return message
    return await channel.send(embed=embed, view=view)


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
    """Full setup pass. ``post_panels`` is injected by the bot to add buttons."""
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

    if post_panels is not None:
        await post_panels(guild, channels, report)

    return report
