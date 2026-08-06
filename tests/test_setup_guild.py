import discord
import pytest

from src import blueprint as bp
from src import setup_guild


def make_role(name, rid):
    role = object.__new__(discord.Role)
    role.name = name
    role.id = rid
    return role


EVERYONE = make_role("@everyone", 1)
STAFF = make_role(bp.ROLE_DEV, 2)
MODERATOR = make_role(bp.ROLE_MOD, 3)
MUTED = make_role(bp.ROLE_MUTED, 4)
TESTER = make_role(bp.ROLE_TESTER, 5)


def build(access, **kwargs):
    params = dict(
        everyone=EVERYONE,
        staff=STAFF,
        moderator=MODERATOR,
        muted=MUTED,
        tester=TESTER,
    )
    params.update(kwargs)
    return setup_guild.overwrites_for(access, **params)


class TestNormalise:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Chat FR", "chat-fr"),
            ("  butin-bugs  ", "butin-bugs"),
            ("Vocal / Voice", "vocal-/-voice"),
            ("ALREADY-LOW", "already-low"),
        ],
    )
    def test_matches_discord_normalisation(self, raw, expected):
        assert setup_guild.normalise(raw) == expected


class TestOverwrites:
    def test_public_lets_everyone_write(self):
        table = build(bp.Access.PUBLIC)
        assert table[EVERYONE].view_channel is True
        assert table[EVERYONE].send_messages is True

    def test_public_does_not_add_staff_entries(self):
        # @everyone already grants what staff needs, an extra row is noise.
        table = build(bp.Access.PUBLIC)
        assert STAFF not in table and MODERATOR not in table

    def test_read_only_blocks_everyone_but_allows_reactions(self):
        table = build(bp.Access.READ_ONLY)
        assert table[EVERYONE].view_channel is True
        assert table[EVERYONE].send_messages is False
        assert table[EVERYONE].add_reactions is True

    def test_read_only_allows_replying_inside_a_thread(self):
        # What makes the guide forum usable: a question under the guide it is
        # about, without letting anyone open a channel-level topic.
        table = build(bp.Access.READ_ONLY)
        assert table[EVERYONE].send_messages_in_threads is True
        assert table[EVERYONE].create_public_threads is False

    def test_read_only_still_lets_staff_write(self):
        table = build(bp.Access.READ_ONLY)
        assert table[STAFF].send_messages is True
        assert table[MODERATOR].send_messages is True

    def test_staff_only_hides_the_channel(self):
        table = build(bp.Access.STAFF_ONLY)
        assert table[EVERYONE].view_channel is False
        assert table[STAFF].view_channel is True

    def test_muted_is_silenced_everywhere(self):
        for access in bp.Access:
            table = build(access)
            assert table[MUTED].send_messages is False
            assert table[MUTED].add_reactions is False

    def test_bot_keeps_write_access_to_restricted_channels(self):
        bot = make_role("bot-member", 9)
        table = build(bp.Access.READ_ONLY, bot_member=bot)
        assert table[bot].send_messages is True

    def test_bot_is_not_added_to_public_channels(self):
        bot = make_role("bot-member", 9)
        assert bot not in build(bp.Access.PUBLIC, bot_member=bot)

    def test_missing_optional_roles_are_simply_absent(self):
        table = build(
            bp.Access.READ_ONLY, staff=None, moderator=None, muted=None, tester=None
        )
        assert set(table) == {EVERYONE}


class TestBetaOverwrites:
    def test_beta_channels_are_hidden_from_everyone(self):
        for access in (bp.Access.BETA_ONLY, bp.Access.BETA_READ_ONLY):
            assert build(access)[EVERYONE].view_channel is False

    def test_testers_see_and_write_in_a_beta_channel(self):
        table = build(bp.Access.BETA_ONLY)
        assert table[TESTER].view_channel is True
        assert table[TESTER].send_messages is True

    def test_read_only_beta_lets_testers_read_but_not_post(self):
        table = build(bp.Access.BETA_READ_ONLY)
        assert table[TESTER].view_channel is True
        assert table[TESTER].send_messages is False

    def test_read_only_beta_still_allows_thread_replies(self):
        # The channel stays a clean noticeboard while discussion continues
        # inside threads, which is the whole point of the split.
        assert build(bp.Access.BETA_READ_ONLY)[TESTER].send_messages_in_threads is True

    def test_staff_keeps_access_to_beta(self):
        table = build(bp.Access.BETA_ONLY)
        assert table[STAFF].view_channel is True
        assert table[MODERATOR].view_channel is True

    def test_without_a_tester_role_nobody_is_granted_access(self):
        table = build(bp.Access.BETA_ONLY, tester=None)
        assert table[EVERYONE].view_channel is False
        assert TESTER not in table


class TestEffectiveAccess:
    def test_public_channel_inherits_a_beta_category(self):
        category = bp.CategorySpec(name="c", channels=(), access=bp.Access.BETA_ONLY)
        channel = bp.ChannelSpec(name="x")
        assert setup_guild.effective_access(category, channel) is bp.Access.BETA_ONLY

    def test_public_channel_inherits_a_staff_category(self):
        category = bp.CategorySpec(name="c", channels=(), access=bp.Access.STAFF_ONLY)
        channel = bp.ChannelSpec(name="x")
        assert setup_guild.effective_access(category, channel) is bp.Access.STAFF_ONLY

    def test_an_explicit_channel_access_wins(self):
        category = bp.CategorySpec(name="c", channels=(), access=bp.Access.BETA_ONLY)
        channel = bp.ChannelSpec(name="x", access=bp.Access.BETA_READ_ONLY)
        assert setup_guild.effective_access(category, channel) is bp.Access.BETA_READ_ONLY

    def test_a_public_category_does_not_restrict_anything(self):
        category = bp.CategorySpec(name="c", channels=(), access=bp.Access.PUBLIC)
        channel = bp.ChannelSpec(name="x")
        assert setup_guild.effective_access(category, channel) is bp.Access.PUBLIC

    def test_unknown_access_level_raises(self):
        with pytest.raises(ValueError):
            build("nonsense")


class FakeChannel:
    def __init__(self, name):
        self.name = name


class FakeCategory:
    def __init__(self, names):
        self.channels = [FakeChannel(n) for n in names]


class TestFindChannel:
    def test_exact_match(self):
        category = FakeCategory(["chat-fr", "chat-en"])
        assert setup_guild.find_channel(category, "chat-fr").name == "chat-fr"

    def test_match_is_case_and_space_insensitive(self):
        category = FakeCategory(["chat-fr"])
        assert setup_guild.find_channel(category, "Chat FR") is not None

    def test_missing_channel_returns_none(self):
        assert setup_guild.find_channel(FakeCategory([]), "chat-fr") is None


# --------------------------------------------------------------------------- #
# Regression tests: bugs that would silently corrupt a live server
# --------------------------------------------------------------------------- #


class TestRegressions:
    def test_read_only_channels_never_grant_send_to_everyone(self):
        """A release channel that everyone can post in is spam within a day."""
        for _, spec in bp.all_channel_specs():
            if spec.access is bp.Access.READ_ONLY:
                table = build(bp.Access.READ_ONLY)
                assert table[EVERYONE].send_messages is False

    def test_staff_channels_are_invisible_to_everyone(self):
        staff_category = next(c for c in bp.CATEGORIES if c.access is bp.Access.STAFF_ONLY)
        for _ in staff_category.channels:
            assert build(bp.Access.STAFF_ONLY)[EVERYONE].view_channel is False

    def test_normalise_is_idempotent(self):
        # ensure_channels compares stored names to normalised blueprint names;
        # if normalise were not idempotent, every run would recreate channels.
        for _, spec in bp.all_channel_specs():
            once = setup_guild.normalise(spec.name)
            assert setup_guild.normalise(once) == once

    def test_no_beta_channel_is_ever_visible_to_everyone(self):
        """The whole point of the category; one wrong access leaks test builds."""
        beta = next(c for c in bp.CATEGORIES if c.access is bp.Access.BETA_ONLY)
        for spec in beta.channels:
            access = setup_guild.effective_access(beta, spec)
            assert build(access)[EVERYONE].view_channel is False, spec.name

    def test_role_order_puts_dev_on_top_and_muted_at_the_bottom(self):
        names = [r.name for r in bp.ROLES]
        assert names[0] == bp.ROLE_DEV
        assert names[-1] == bp.ROLE_MUTED
        assert names.index(bp.ROLE_MOD) < names.index(bp.ROLE_TESTER)

    def test_every_forum_declares_tags(self):
        # An untagged bug forum makes triage impossible, and views.py assumes
        # BUG_TAGS[0] / IDEA_TAGS[0] exist on the channel.
        for _, spec in bp.all_channel_specs():
            if spec.kind is bp.ChannelKind.FORUM:
                assert spec.tags, spec.name
