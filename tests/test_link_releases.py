import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "link_releases.py"
spec = importlib.util.spec_from_file_location("link_releases", SCRIPT)
link_releases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(link_releases)


class TestDiscordDeliveryUrl:
    def test_github_suffix_is_added(self):
        assert link_releases.discord_delivery_url(
            "https://discord.com/api/webhooks/1/abc"
        ) == "https://discord.com/api/webhooks/1/abc/github"

    def test_existing_suffix_is_not_doubled(self):
        url = "https://discord.com/api/webhooks/1/abc/github"
        assert link_releases.discord_delivery_url(url) == url

    def test_trailing_slash_and_spaces_are_tolerated(self):
        assert link_releases.discord_delivery_url(
            "  https://discord.com/api/webhooks/1/abc/  "
        ).endswith("/abc/github")

    def test_legacy_discordapp_host_is_accepted(self):
        assert link_releases.discord_delivery_url(
            "https://discordapp.com/api/webhooks/1/abc"
        ).endswith("/github")

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/hook",
            "http://discord.com/api/webhooks/1/abc",  # plain http
            "https://discord.com/channels/1/2",
        ],
    )
    def test_anything_else_is_refused(self, url):
        with pytest.raises(ValueError):
            link_releases.discord_delivery_url(url)


def test_only_release_events_are_subscribed():
    # A "push" subscription would post every commit into the release channel.
    assert link_releases.EVENTS == ["release"]
