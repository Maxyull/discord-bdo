import asyncio

import pytest

from src import blueprint as bp
from src import status
from src.status import Probe, ProbeResult, State


class FakeResponse:
    def __init__(self, status_code=200, payload=None, raise_on_json=False):
        self.status = status_code
        self._payload = payload
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
    """Stands in for aiohttp.ClientSession."""

    def __init__(self, response=None, raiser=None):
        self.response = response
        self.raiser = raiser
        self.urls = []

    def get(self, url, allow_redirects=True):
        self.urls.append(url)
        if self.raiser:
            raise self.raiser
        return self.response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def clock(*values):
    """Monotonic stub returning the given readings in order."""
    it = iter(values)
    return lambda: next(it)


PROBE = Probe(key="p", label="P", url="https://example.test/")


class TestCheck:
    async def test_expected_code_is_green(self):
        result = await status.check(PROBE, FakeSession(FakeResponse(200)))
        assert result.state is State.OK

    async def test_latency_is_measured(self):
        result = await status.check(
            PROBE, FakeSession(FakeResponse(200)), now=clock(10.0, 10.25)
        )
        assert result.latency == pytest.approx(0.25)

    async def test_server_error_is_red(self):
        result = await status.check(PROBE, FakeSession(FakeResponse(503)))
        assert result.state is State.DOWN
        assert "503" in result.note

    @pytest.mark.parametrize("code", [301, 404, 418])
    async def test_unexpected_but_not_server_error_is_amber(self, code):
        # The service answered, just not as agreed. That is a different
        # problem from being down, and colouring it red cries wolf.
        result = await status.check(PROBE, FakeSession(FakeResponse(code)))
        assert result.state is State.WARN

    async def test_a_declared_redirect_is_green(self):
        probe = Probe(key="p", label="P", url="u", expect=(200, 302))
        result = await status.check(probe, FakeSession(FakeResponse(302)))
        assert result.state is State.OK

    async def test_redirects_are_not_followed(self):
        # Following them would measure the destination, not the service.
        session = FakeSession(FakeResponse(200))
        await status.check(PROBE, session)
        assert session.urls == ["https://example.test/"]

    async def test_slow_but_working_is_amber(self):
        probe = Probe(key="p", label="P", url="u", warn_after=1.0)
        result = await status.check(
            probe, FakeSession(FakeResponse(200)), now=clock(0.0, 4.0)
        )
        assert result.state is State.WARN
        assert "lent" in result.note

    async def test_timeout_is_red(self):
        result = await status.check(
            PROBE, FakeSession(raiser=asyncio.TimeoutError())
        )
        assert result.state is State.DOWN
        assert result.latency is None

    async def test_network_error_is_red_and_never_raises(self):
        result = await status.check(
            PROBE, FakeSession(raiser=OSError("connection refused"))
        )
        assert result.state is State.DOWN
        assert "OSError" in result.note


class TestJsonHealthCheck:
    probe = Probe(key="p", label="P", url="u", expect_json=("etat", "ok"))

    async def test_healthy_body_is_green(self):
        result = await status.check(
            self.probe, FakeSession(FakeResponse(200, {"etat": "ok"}))
        )
        assert result.state is State.OK

    async def test_a_service_declaring_itself_sick_is_amber_despite_the_200(self):
        result = await status.check(
            self.probe, FakeSession(FakeResponse(200, {"etat": "degraded"}))
        )
        assert result.state is State.WARN
        assert "degraded" in result.note

    async def test_missing_field_is_amber(self):
        result = await status.check(
            self.probe, FakeSession(FakeResponse(200, {"autre": 1}))
        )
        assert result.state is State.WARN

    async def test_unreadable_body_is_amber_not_a_crash(self):
        result = await status.check(
            self.probe, FakeSession(FakeResponse(200, raise_on_json=True))
        )
        assert result.state is State.WARN


def result(key, state, latency=0.1, impact=""):
    return ProbeResult(
        Probe(key=key, label=key, url="u", impact=impact), state, latency
    )


class TestOverall:
    def test_all_green_is_green(self):
        assert status.overall([result("a", State.OK)]) is State.OK

    def test_the_worst_state_wins(self):
        results = [result("a", State.OK), result("b", State.WARN), result("c", State.DOWN)]
        assert status.overall(results) is State.DOWN

    def test_one_amber_among_greens_shows_amber(self):
        assert status.overall([result("a", State.OK), result("b", State.WARN)]) is State.WARN

    def test_unknown_beats_ok_but_loses_to_warn(self):
        assert status.overall([result("a", State.OK), result("b", State.UNKNOWN)]) is State.UNKNOWN
        assert status.overall([result("a", State.UNKNOWN), result("b", State.WARN)]) is State.WARN

    def test_no_results_is_unknown(self):
        assert status.overall([]) is State.UNKNOWN


class TestFingerprint:
    def test_same_states_give_the_same_fingerprint(self):
        a = [result("x", State.OK, latency=0.1)]
        b = [result("x", State.OK, latency=9.9)]
        assert status.fingerprint(a) == status.fingerprint(b)

    def test_latency_alone_does_not_trigger_a_rewrite(self):
        # This is what lets a steady green board sit there without the bot
        # editing it every five minutes.
        assert status.fingerprint([result("x", State.OK, 0.05)]) == status.fingerprint(
            [result("x", State.OK, 2.0)]
        )

    def test_a_state_change_changes_the_fingerprint(self):
        assert status.fingerprint([result("x", State.OK)]) != status.fingerprint(
            [result("x", State.DOWN)]
        )

    def test_it_distinguishes_which_service_broke(self):
        first = [result("a", State.DOWN), result("b", State.OK)]
        second = [result("a", State.OK), result("b", State.DOWN)]
        assert status.fingerprint(first) != status.fingerprint(second)


class TestRender:
    def test_each_service_gets_a_line_with_its_dot(self):
        text = status.render_description(
            [result("a", State.OK), result("b", State.DOWN)], 1700000000
        )
        assert "🟢 **a**" in text
        assert "🔴 **b**" in text

    def test_the_impact_of_a_broken_service_is_spelled_out(self):
        text = status.render_description(
            [result("a", State.DOWN, impact="Rubin ne synchronise plus")], 1700000000
        )
        assert "Rubin ne synchronise plus" in text

    def test_a_working_service_does_not_list_its_impact(self):
        text = status.render_description(
            [result("a", State.OK, impact="Rubin ne synchronise plus")], 1700000000
        )
        assert "Rubin ne synchronise plus" not in text

    def test_the_legend_is_bilingual(self):
        text = status.render_description([result("a", State.OK)], 1700000000)
        assert "fonctionne" in text and "working" in text

    def test_the_timestamp_is_a_self_updating_discord_stamp(self):
        # Plain text would go stale between edits; <t:…:R> is rendered by the
        # client, so the board stays honest without being rewritten.
        text = status.render_description([result("a", State.OK)], 1700000000)
        assert "<t:1700000000:R>" in text

    def test_it_fits_an_embed_description(self):
        results = [result(p.key, State.DOWN, impact=p.impact) for p in status.PROBES]
        assert len(status.render_description(results, 1700000000)) <= 4096


class TestProbeDeclarations:
    def test_keys_are_unique(self):
        keys = [p.key for p in status.PROBES]
        assert len(keys) == len(set(keys))

    def test_every_url_is_https(self):
        for probe in status.PROBES:
            assert probe.url.startswith("https://"), probe.key

    def test_both_tools_have_a_download_probe(self):
        urls = " ".join(p.url for p in status.PROBES)
        assert "butin-bdo/releases/latest" in urls
        assert "rubin-bdo/releases/latest" in urls

    def test_the_rubin_api_probe_checks_the_body_not_just_the_code(self):
        probe = next(p for p in status.PROBES if p.key == "rubin_api")
        assert probe.expect_json == ("etat", "ok")

    def test_github_probes_carry_the_token(self):
        # Unauthenticated GitHub allows 60 requests an hour per IP; two probes
        # every five minutes is fine, but the token keeps a margin.
        for probe in status.PROBES:
            if "api.github.com" in probe.url:
                assert probe.github_auth is True

    def test_probes_that_matter_explain_what_breaks(self):
        for probe in status.PROBES:
            if probe.key != "site":
                assert probe.impact, probe.key

    def test_every_state_has_a_dot_a_headline_and_a_colour(self):
        for state in State:
            assert state.dot
            assert status.HEADLINES[state]
            assert status.COLOURS[state]


class TestStatusChannel:
    def test_the_channel_is_declared_and_locked(self):
        by_key = {ch.key: ch for _, ch in bp.all_channel_specs() if ch.key}
        spec = by_key[bp.KEY_STATUS]
        # Members must not be able to post in a status board.
        assert spec.access is bp.Access.READ_ONLY
        assert spec.kind is bp.ChannelKind.TEXT
