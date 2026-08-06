import discord
import pytest

from src import blueprint as bp
from src.bot import BdoBot
from src.config import Config


def make_config(**kwargs):
    base = dict(
        discord_token="token",
        guild_id=42,
        github_token="",
        github_default_labels=("discord",),
        log_level="INFO",
        dry_run=False,
    )
    base.update(kwargs)
    return Config(**base)


@pytest.fixture
def bot():
    return BdoBot(make_config())


class TestConstruction:
    def test_commands_are_registered_at_construction(self, bot):
        names = {cmd.name for cmd in bot.tree.get_commands()}
        own = {"setup", "aide", "config", "etat", "version", "tester"}
        assert own <= names

    def test_the_rubin_lookup_commands_are_absorbed(self, bot):
        # This bot replaces rubin-bot rather than running beside it: two
        # processes sharing one token fight over the same Gateway session and
        # knock each other offline in a loop.
        names = {c.name for c in bot.tree.get_commands()}
        assert {"rapides", "chaine", "quete"} <= names

    def test_the_rubin_api_client_is_built(self, bot):
        assert bot.rubin_api is not None

    def test_command_names_are_unique(self, bot):
        # Two sources of commands now; a duplicate would be rejected by
        # Discord at sync time, hours after the deploy.
        names = [c.name for c in bot.tree.get_commands()]
        assert len(names) == len(set(names))

    def test_tester_is_gated_on_managing_roles(self, bot):
        tester = next(c for c in bot.tree.get_commands() if c.name == "tester")
        assert tester.default_permissions.manage_roles is True

    def test_version_is_open_to_everyone(self, bot):
        version = next(c for c in bot.tree.get_commands() if c.name == "version")
        assert version.default_permissions is None

    def test_the_status_loop_is_declared_but_not_started_yet(self, bot):
        # It starts in on_ready; starting it in __init__ would need a running
        # event loop and would break every offline test.
        assert bot.status_loop.is_running() is False
        assert bot.status_loop.minutes == 5

    def test_setup_command_is_admin_only(self, bot):
        setup = next(c for c in bot.tree.get_commands() if c.name == "setup")
        assert setup.default_permissions.administrator is True

    def test_members_intent_is_on_because_roles_are_needed(self, bot):
        assert bot.intents.members is True

    def test_message_content_intent_is_on_for_screenshot_detection(self, bot):
        # Without it Discord blanks out message.attachments, so on_message
        # would never see a screenshot and the detection would fail silently.
        assert bot.intents.message_content is True

    def test_config_command_is_open_to_everyone(self, bot):
        # Members must be able to check their own card; the staff-only guard on
        # looking up *someone else* lives in the handler, not in the command.
        config = next(c for c in bot.tree.get_commands() if c.name == "config")
        assert config.default_permissions is None

    def test_github_client_absent_without_token(self, bot):
        assert bot.github is None

    def test_github_client_present_with_token(self):
        assert BdoBot(make_config(github_token="ghp_x")).github is not None


class FakeChannel:
    def __init__(self, name):
        self.name = name


class FakeGuild:
    def __init__(self, names):
        self.id = 42
        self.name = "test"
        self.channels = [FakeChannel(n) for n in names]


class TestIndexChannels:
    def test_every_blueprint_key_is_found_on_a_complete_server(self):
        names = [ch.name for _, ch in bp.all_channel_specs()]
        found = BdoBot.index_channels(FakeGuild(names))
        assert set(found) == bp.channel_keys()

    def test_missing_channels_are_simply_absent(self):
        found = BdoBot.index_channels(FakeGuild(["chat-fr"]))
        assert found == {}

    def test_matching_survives_discord_name_normalisation(self):
        # Discord stores "règles-rules" lowercased; the blueprint name already
        # is, but a manual rename could introduce case or spaces.
        found = BdoBot.index_channels(FakeGuild(["Butin-Bugs"]))
        assert bp.KEY_BUTIN_BUGS in found

    def test_unknown_channels_are_ignored(self):
        found = BdoBot.index_channels(FakeGuild(["un-salon-perso", "chat-fr"]))
        assert found == {}


class TestBuildHandler:
    def test_handler_carries_the_configured_labels(self, bot):
        handler = bot.build_handler(FakeGuild([]))
        assert handler.default_labels == ("discord",)

    def test_staff_log_is_none_when_the_channel_is_missing(self, bot):
        assert bot.build_handler(FakeGuild([])).staff_log is None

    def test_dry_run_is_propagated(self):
        bot = BdoBot(make_config(dry_run=True))
        assert bot.build_handler(FakeGuild([])).dry_run is True

    def test_a_non_text_staff_log_is_rejected_rather_than_crashing_later(self, bot):
        # index_channels matches by name only, so a voice channel named
        # staff-journal would otherwise be handed to .send().
        guild = FakeGuild(["staff-journal"])
        assert bot.build_handler(guild).staff_log is None
