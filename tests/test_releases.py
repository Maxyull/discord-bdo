import pytest

from src.releases import CACHE_SECONDS, Release, ReleaseClient, ReleaseError, _parse_ts


class FakeResponse:
    def __init__(self, status=200, payload=None, raise_on_json=False):
        self.status = status
        self._payload = payload or {}
        self._raise = raise_on_json

    async def json(self, content_type=None):
        if self._raise:
            raise ValueError("not json")
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, response=None, raiser=None):
        self.response = response
        self.raiser = raiser
        self.calls = 0

    def get(self, url):
        self.calls += 1
        if self.raiser:
            raise self.raiser
        return self.response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


PAYLOAD = {
    "tag_name": "v0.4.0",
    "html_url": "https://github.com/Maxyull/butin-bdo/releases/tag/v0.4.0",
    "published_at": "2026-08-06T12:13:36Z",
}


def client(session, now=None):
    counter = {"t": 0.0}

    def clock():
        return counter["t"]

    c = ReleaseClient("", session_factory=lambda: session, now=now or clock)
    c._counter = counter
    return c


class TestLatest:
    async def test_reads_the_tag_and_url(self):
        c = client(FakeSession(FakeResponse(200, PAYLOAD)))
        release = await c.latest("Maxyull/butin-bdo")
        assert release.tag == "v0.4.0"
        assert release.url.endswith("v0.4.0")

    async def test_a_repo_without_a_release_says_so_plainly(self):
        c = client(FakeSession(FakeResponse(404)))
        with pytest.raises(ReleaseError, match="aucune version"):
            await c.latest("o/r")

    @pytest.mark.parametrize("status", [401, 403, 500])
    async def test_other_http_errors_are_reported(self, status):
        c = client(FakeSession(FakeResponse(status)))
        with pytest.raises(ReleaseError, match=str(status)):
            await c.latest("o/r")

    async def test_network_failure_is_wrapped(self):
        c = client(FakeSession(raiser=TimeoutError("slow")))
        with pytest.raises(ReleaseError, match="TimeoutError"):
            await c.latest("o/r")

    async def test_unreadable_body_is_wrapped(self):
        c = client(FakeSession(FakeResponse(200, raise_on_json=True)))
        with pytest.raises(ReleaseError):
            await c.latest("o/r")

    async def test_a_reply_without_a_tag_is_refused(self):
        # Better to say "unavailable" than to show an empty version number.
        c = client(FakeSession(FakeResponse(200, {"html_url": "u"})))
        with pytest.raises(ReleaseError, match="numéro de version"):
            await c.latest("o/r")

    async def test_a_missing_url_falls_back_to_the_releases_page(self):
        c = client(FakeSession(FakeResponse(200, {"tag_name": "v1"})))
        release = await c.latest("Maxyull/butin-bdo")
        assert "Maxyull/butin-bdo" in release.url


class TestCache:
    async def test_a_second_call_does_not_hit_github(self):
        session = FakeSession(FakeResponse(200, PAYLOAD))
        c = client(session)
        await c.latest("o/r")
        await c.latest("o/r")
        assert session.calls == 1

    async def test_the_cache_expires(self):
        session = FakeSession(FakeResponse(200, PAYLOAD))
        c = client(session)
        await c.latest("o/r")
        c._counter["t"] = CACHE_SECONDS + 1
        await c.latest("o/r")
        assert session.calls == 2

    async def test_each_repo_is_cached_separately(self):
        session = FakeSession(FakeResponse(200, PAYLOAD))
        c = client(session)
        await c.latest("a/one")
        await c.latest("b/two")
        assert session.calls == 2

    def test_an_unknown_repo_has_no_cached_entry(self):
        assert client(FakeSession()).cached("never/asked") is None


class TestTimestamp:
    def test_a_github_date_becomes_a_unix_stamp(self):
        assert _parse_ts("2026-08-06T12:13:36Z") > 0

    @pytest.mark.parametrize("raw", ["", "hier", "2026-08-06", "not a date"])
    def test_anything_unparsable_yields_zero_rather_than_raising(self, raw):
        assert _parse_ts(raw) == 0

    def test_the_stamp_is_a_self_updating_discord_tag(self):
        assert Release(tag="v1", url="u", published_ts=1700000000).stamp == (
            "<t:1700000000:R>"
        )

    def test_no_stamp_when_the_date_was_unusable(self):
        # An empty string renders as nothing, rather than as 1970.
        assert Release(tag="v1", url="u", published_ts=0).stamp == ""
