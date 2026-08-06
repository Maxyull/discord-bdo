"""Declarative description of the Discord server.

This module holds *data only*: no network calls, no discord.py objects.
``setup_guild`` reads this blueprint and reconciles the live server with it,
which makes the whole server layout reviewable in one file and unit-testable
without a Discord connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# --------------------------------------------------------------------------- #
# Roles
# --------------------------------------------------------------------------- #

#: Role granted to the owner. Never created by the bot (Discord assigns the
#: server owner implicitly); listed here so permission tables can reference it.
ROLE_DEV = "Dev"
ROLE_MOD = "Mod"
#: Gates the private beta category. Handed out by the staff, never automatic.
ROLE_TESTER = "Tester"
#: Given to every human on arrival, so @everyone can stay a technical fallback.
ROLE_PLAYER = "Joueur"
ROLE_MUTED = "Muted"


@dataclass(frozen=True)
class RoleSpec:
    name: str
    colour: int
    hoist: bool = False
    mentionable: bool = False
    #: Permission names from :class:`discord.Permissions` set to ``True``.
    permissions: tuple[str, ...] = ()


#: Order matters: index 0 sits at the top of the server's role list. Discord
#: refuses to let a role manage anything placed above it, so Dev must lead.
ROLES: tuple[RoleSpec, ...] = (
    RoleSpec(
        name=ROLE_DEV,
        colour=0xE8A33D,  # amber, matches the Butin accent
        hoist=True,
        mentionable=True,
        permissions=("administrator",),
    ),
    RoleSpec(
        name=ROLE_MOD,
        colour=0x4E9BD1,
        hoist=True,
        mentionable=True,
        permissions=(
            "manage_messages",
            "manage_threads",
            "moderate_members",
            "kick_members",
            "mute_members",
            "read_message_history",
            "view_channel",
            "send_messages",
        ),
    ),
    RoleSpec(
        name=ROLE_TESTER,
        colour=0x6BBF59,
        hoist=True,
        mentionable=True,
    ),
    RoleSpec(
        name=ROLE_PLAYER,
        colour=0x9AA4B2,
        hoist=False,
        mentionable=False,
    ),
    RoleSpec(
        name=ROLE_MUTED,
        colour=0x555555,
        hoist=False,
        mentionable=False,
    ),
)


# --------------------------------------------------------------------------- #
# Channels
# --------------------------------------------------------------------------- #


class ChannelKind(str, Enum):
    TEXT = "text"
    FORUM = "forum"
    VOICE = "voice"


class Access(str, Enum):
    """Who can see and write in a channel."""

    #: Everyone reads, everyone writes.
    PUBLIC = "public"
    #: Everyone reads, only staff writes (announcements, rules).
    READ_ONLY = "read_only"
    #: Only the Tester role (and staff) sees the channel at all.
    BETA_ONLY = "beta_only"
    #: Testers read, only staff writes.
    BETA_READ_ONLY = "beta_read_only"
    #: Only staff sees the channel at all.
    STAFF_ONLY = "staff_only"


@dataclass(frozen=True)
class ChannelSpec:
    #: Channel name, lowercase and hyphenated as Discord normalises it anyway.
    name: str
    kind: ChannelKind = ChannelKind.TEXT
    topic: str = ""
    access: Access = Access.PUBLIC
    #: Stable key used by the bot to find the channel again (stored in code,
    #: not in Discord). Only set it for channels the bot must post into.
    key: str = ""
    #: Forum tags, forum channels only.
    tags: tuple[str, ...] = ()
    #: Seconds of slowmode, 0 disables it.
    slowmode: int = 0


@dataclass(frozen=True)
class CategorySpec:
    name: str
    channels: tuple[ChannelSpec, ...]
    access: Access = Access.PUBLIC


# Channel keys the bot code refers to. Keeping them as constants means a typo
# is a NameError at import time rather than a silent no-op at runtime.
KEY_ANNOUNCEMENTS = "announcements"
KEY_RULES = "rules"
KEY_WELCOME = "welcome"
KEY_GUIDES = "guides"
KEY_BUTIN_HELP = "butin_help"
KEY_BUTIN_BUGS = "butin_bugs"
KEY_BUTIN_IDEAS = "butin_ideas"
KEY_BUTIN_RELEASES = "butin_releases"
KEY_RUBIN_HELP = "rubin_help"
KEY_RUBIN_BUGS = "rubin_bugs"
KEY_RUBIN_IDEAS = "rubin_ideas"
KEY_RUBIN_RELEASES = "rubin_releases"
KEY_BETA_NEWS = "beta_news"
KEY_BETA_CHAT = "beta_chat"
KEY_BETA_FEEDBACK = "beta_feedback"
KEY_STAFF_SETUPS = "staff_setups"
KEY_STAFF_LOG = "staff_log"

#: Forum tags shared by every bug forum.
BUG_TAGS = ("Nouveau / New", "Confirmé / Confirmed", "Corrigé / Fixed", "Rejeté / Declined")
IDEA_TAGS = ("Nouveau / New", "Retenu / Planned", "Fait / Shipped", "Rejeté / Declined")
BETA_TAGS = ("Nouveau / New", "Lu / Seen", "Traité / Handled")

#: One shared guide forum for both tools, so the tags carry the sorting rather
#: than two half-empty channels. Product tags come first: they are the filter
#: people reach for.
GUIDE_TAGS = (
    "🪙 Butin",
    "⏱️ Rubin",
    "Installation",
    "Calibrage / Setup",
    "Astuce / Tip",
    "Dépannage",
)

#: Applied to a bug thread once a screenshot lands in it. Kept out of BUG_TAGS
#: on purpose: it is a state the bot sets, not one a reporter picks.
TAG_HAS_SCREENSHOT = "Capture / Screenshot"


CATEGORIES: tuple[CategorySpec, ...] = (
    CategorySpec(
        name="📢 Infos",
        channels=(
            ChannelSpec(
                name="bienvenue-welcome",
                key=KEY_WELCOME,
                access=Access.READ_ONLY,
                topic="Présentation du serveur / Server introduction",
            ),
            ChannelSpec(
                name="règles-rules",
                key=KEY_RULES,
                access=Access.READ_ONLY,
                topic="À lire avant de poster / Read before posting",
            ),
            ChannelSpec(
                name="annonces-announcements",
                key=KEY_ANNOUNCEMENTS,
                access=Access.READ_ONLY,
                topic="Nouveautés des deux logiciels / News about both tools",
            ),
            ChannelSpec(
                name="guides-tutoriels",
                kind=ChannelKind.FORUM,
                key=KEY_GUIDES,
                access=Access.READ_ONLY,
                tags=GUIDE_TAGS,
                topic=(
                    "Un fil par guide, pour les deux logiciels. Filtrez par étiquette. "
                    "Seule l'équipe ouvre un fil, tout le monde peut y poser une "
                    "question. / One thread per guide, for both tools. Filter by tag; "
                    "the team opens threads, anyone can ask inside one."
                ),
            ),
        ),
    ),
    CategorySpec(
        name="💬 Communauté",
        channels=(
            ChannelSpec(
                name="chat-fr",
                topic="Discussion générale en français. Black Desert, les outils, le reste.",
            ),
            ChannelSpec(
                name="chat-en",
                topic="General chat in English. Black Desert, the tools, anything else.",
            ),
            ChannelSpec(
                name="captures-screenshots",
                topic="Vos drops, vos sessions, vos records / Your drops, sessions and records",
            ),
            ChannelSpec(
                name="Vocal / Voice",
                kind=ChannelKind.VOICE,
            ),
        ),
    ),
    CategorySpec(
        name="🪙 Butin",
        channels=(
            ChannelSpec(
                name="butin-aide-help",
                key=KEY_BUTIN_HELP,
                topic="Installation, calibrage, questions sur le suivi de butin / Butin support",
            ),
            ChannelSpec(
                name="butin-bugs",
                kind=ChannelKind.FORUM,
                key=KEY_BUTIN_BUGS,
                tags=BUG_TAGS + (TAG_HAS_SCREENSHOT,),
                topic=(
                    "Un fil par bug. Utilisez le bouton dans #butin-aide-help pour "
                    "que la version et le système soient remplis automatiquement."
                ),
            ),
            ChannelSpec(
                name="butin-suggestions",
                kind=ChannelKind.FORUM,
                key=KEY_BUTIN_IDEAS,
                tags=IDEA_TAGS,
                topic="Un fil par suggestion. Votez avec 👍. / One thread per suggestion, vote with 👍.",
            ),
            ChannelSpec(
                name="butin-versions-releases",
                key=KEY_BUTIN_RELEASES,
                access=Access.READ_ONLY,
                topic="Publications automatiques depuis GitHub / Automatic GitHub releases",
            ),
        ),
    ),
    CategorySpec(
        name="⏱️ Rubin",
        channels=(
            ChannelSpec(
                name="rubin-aide-help",
                key=KEY_RUBIN_HELP,
                topic="Installation et questions sur le chronomètre de quêtes / Rubin support",
            ),
            ChannelSpec(
                name="rubin-bugs",
                kind=ChannelKind.FORUM,
                key=KEY_RUBIN_BUGS,
                tags=BUG_TAGS + (TAG_HAS_SCREENSHOT,),
                topic=(
                    "Un fil par bug. Utilisez le bouton dans #rubin-aide-help pour "
                    "que la version et le système soient remplis automatiquement."
                ),
            ),
            ChannelSpec(
                name="rubin-suggestions",
                kind=ChannelKind.FORUM,
                key=KEY_RUBIN_IDEAS,
                tags=IDEA_TAGS,
                topic="Un fil par suggestion. Votez avec 👍. / One thread per suggestion, vote with 👍.",
            ),
            ChannelSpec(
                name="rubin-versions-releases",
                key=KEY_RUBIN_RELEASES,
                access=Access.READ_ONLY,
                topic="Publications automatiques depuis GitHub / Automatic GitHub releases",
            ),
        ),
    ),
    CategorySpec(
        name="🧪 Bêta",
        access=Access.BETA_ONLY,
        channels=(
            ChannelSpec(
                name="beta-annonces-news",
                key=KEY_BETA_NEWS,
                access=Access.BETA_READ_ONLY,
                topic="Versions de test, ce qu'il faut essayer / Test builds and what to try",
            ),
            ChannelSpec(
                name="beta-chat",
                key=KEY_BETA_CHAT,
                topic="Discussion entre testeurs / Chat between testers",
            ),
            ChannelSpec(
                name="beta-retours-feedback",
                kind=ChannelKind.FORUM,
                key=KEY_BETA_FEEDBACK,
                tags=BETA_TAGS,
                topic="Un fil par retour de test / One thread per test report",
            ),
        ),
    ),
    CategorySpec(
        name="🔒 Staff",
        access=Access.STAFF_ONLY,
        channels=(
            ChannelSpec(
                name="staff-chat", access=Access.STAFF_ONLY),
            ChannelSpec(
                name="staff-configs",
                key=KEY_STAFF_SETUPS,
                access=Access.STAFF_ONLY,
                topic=(
                    "Annuaire des fiches de configuration, une par membre, mise à "
                    "jour en place. Données matérielles : ne pas ouvrir aux membres."
                ),
            ),
            ChannelSpec(
                name="staff-journal",
                key=KEY_STAFF_LOG,
                access=Access.STAFF_ONLY,
                topic="Traces du bot : rapports reçus, issues GitHub créées, erreurs.",
            ),
        ),
    ),
)


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProductSpec:
    """One of the two tools the server is built around."""

    #: Stable identifier used in button custom_ids. Never change it once the
    #: buttons are live: existing messages would stop responding.
    slug: str
    label: str
    emoji: str
    colour: int
    repo: str
    help_channel_key: str
    bug_channel_key: str
    idea_channel_key: str
    release_channel_key: str
    #: Extra fields shown in the bug modal, on top of the shared ones.
    platform_hint: str


PRODUCTS: tuple[ProductSpec, ...] = (
    ProductSpec(
        slug="butin",
        label="Butin",
        emoji="🪙",
        colour=0xE8A33D,
        repo="Maxyull/butin-bdo",
        help_channel_key=KEY_BUTIN_HELP,
        bug_channel_key=KEY_BUTIN_BUGS,
        idea_channel_key=KEY_BUTIN_IDEAS,
        release_channel_key=KEY_BUTIN_RELEASES,
        platform_hint="Windows 10 / Windows 11",
    ),
    ProductSpec(
        slug="rubin",
        label="Rubin",
        emoji="⏱️",
        colour=0xC1352C,
        repo="Maxyull/rubin-bdo",
        help_channel_key=KEY_RUBIN_HELP,
        bug_channel_key=KEY_RUBIN_BUGS,
        idea_channel_key=KEY_RUBIN_IDEAS,
        release_channel_key=KEY_RUBIN_RELEASES,
        platform_hint="Windows 10 / Windows 11",
    ),
)

PRODUCTS_BY_SLUG: dict[str, ProductSpec] = {p.slug: p for p in PRODUCTS}


def product(slug: str) -> ProductSpec:
    """Return the product for ``slug`` or raise a helpful error."""
    try:
        return PRODUCTS_BY_SLUG[slug]
    except KeyError:
        known = ", ".join(sorted(PRODUCTS_BY_SLUG))
        raise KeyError(f"unknown product {slug!r} (known: {known})") from None


def all_channel_specs() -> list[tuple[CategorySpec, ChannelSpec]]:
    """Flatten the blueprint into ``(category, channel)`` pairs."""
    return [(cat, ch) for cat in CATEGORIES for ch in cat.channels]


def channel_keys() -> set[str]:
    """Every non-empty channel key declared in the blueprint."""
    return {ch.key for _, ch in all_channel_specs() if ch.key}


#: Channels that only exist once the server is a Community server.
def requires_community() -> bool:
    return any(
        ch.kind is ChannelKind.FORUM for _, ch in all_channel_specs()
    )


@dataclass
class SetupReport:
    """What ``setup_guild`` actually did, so the run can be summarised."""

    created_roles: list[str] = field(default_factory=list)
    updated_roles: list[str] = field(default_factory=list)
    created_categories: list[str] = field(default_factory=list)
    created_channels: list[str] = field(default_factory=list)
    updated_channels: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(
            self.created_roles
            or self.updated_roles
            or self.created_categories
            or self.created_channels
            or self.updated_channels
        )

    def summary(self) -> str:
        lines: list[str] = []
        for title, items in (
            ("Rôles créés", self.created_roles),
            ("Rôles mis à jour", self.updated_roles),
            ("Catégories créées", self.created_categories),
            ("Salons créés", self.created_channels),
            ("Salons mis à jour", self.updated_channels),
            ("Inchangés", self.skipped),
            ("Avertissements", self.warnings),
        ):
            if items:
                lines.append(f"{title} ({len(items)}) : {', '.join(items)}")
        return "\n".join(lines) if lines else "Rien à faire, le serveur est déjà conforme."
