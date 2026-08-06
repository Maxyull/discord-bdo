import pytest

from src import config as cfg


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        "DISCORD_TOKEN",
        "DISCORD_GUILD_ID",
        "GITHUB_TOKEN",
        "GITHUB_DEFAULT_LABELS",
        "DRY_RUN",
        "LOG_LEVEL",
        "RUBIN_API_URL",
        "RUBIN_API_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_missing_token_is_a_clear_error():
    with pytest.raises(cfg.ConfigError, match="DISCORD_TOKEN"):
        cfg.load(env_file="does-not-exist", require_token=True)


def test_token_optional_when_not_required():
    conf = cfg.load(env_file="does-not-exist", require_token=False)
    assert conf.discord_token == ""


def test_reads_values(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", " abc ")
    monkeypatch.setenv("DISCORD_GUILD_ID", "1234567890")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_x")
    conf = cfg.load(env_file="does-not-exist")
    assert conf.discord_token == "abc"
    assert conf.guild_id == 1234567890
    assert conf.github_enabled is True


def test_guild_id_must_be_numeric(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "abc")
    monkeypatch.setenv("DISCORD_GUILD_ID", "mon-serveur")
    with pytest.raises(cfg.ConfigError, match="nombre entier"):
        cfg.load(env_file="does-not-exist")


def test_empty_guild_id_is_allowed(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "abc")
    monkeypatch.setenv("DISCORD_GUILD_ID", "   ")
    assert cfg.load(env_file="does-not-exist").guild_id is None


def test_github_disabled_without_token(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "abc")
    assert cfg.load(env_file="does-not-exist").github_enabled is False


def test_labels_are_split_and_stripped(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "abc")
    monkeypatch.setenv("GITHUB_DEFAULT_LABELS", " discord , triage ,, ")
    assert cfg.load(env_file="does-not-exist").github_default_labels == (
        "discord",
        "triage",
    )


@pytest.mark.parametrize("value,expected", [("1", True), ("oui", True), ("0", False), ("", False)])
def test_dry_run_parsing(monkeypatch, value, expected):
    monkeypatch.setenv("DISCORD_TOKEN", "abc")
    monkeypatch.setenv("DRY_RUN", value)
    assert cfg.load(env_file="does-not-exist").dry_run is expected


class TestRubinApiSettings:
    def test_the_default_points_at_the_live_api(self, monkeypatch):
        monkeypatch.setenv("DISCORD_TOKEN", "abc")
        conf = cfg.load(env_file="does-not-exist")
        assert conf.rubin_api_url == "https://rubin.maxyull.fr"
        assert conf.rubin_api_timeout == 5.0

    def test_the_url_can_be_overridden(self, monkeypatch):
        monkeypatch.setenv("DISCORD_TOKEN", "abc")
        monkeypatch.setenv("RUBIN_API_URL", "https://essai.local")
        assert cfg.load(env_file="does-not-exist").rubin_api_url == "https://essai.local"

    def test_the_timeout_accepts_a_decimal(self, monkeypatch):
        monkeypatch.setenv("DISCORD_TOKEN", "abc")
        monkeypatch.setenv("RUBIN_API_TIMEOUT", "2.5")
        assert cfg.load(env_file="does-not-exist").rubin_api_timeout == 2.5

    def test_a_non_numeric_timeout_is_refused(self, monkeypatch):
        monkeypatch.setenv("DISCORD_TOKEN", "abc")
        monkeypatch.setenv("RUBIN_API_TIMEOUT", "vite")
        with pytest.raises(cfg.ConfigError, match="nombre"):
            cfg.load(env_file="does-not-exist")

    @pytest.mark.parametrize("value", ["0", "-3"])
    def test_a_non_positive_timeout_is_refused(self, monkeypatch, value):
        # A zero timeout makes every call fail instantly and looks like an
        # outage in the status board.
        monkeypatch.setenv("DISCORD_TOKEN", "abc")
        monkeypatch.setenv("RUBIN_API_TIMEOUT", value)
        with pytest.raises(cfg.ConfigError, match="positif"):
            cfg.load(env_file="does-not-exist")
