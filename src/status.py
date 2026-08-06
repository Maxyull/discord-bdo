"""Service probes behind the status channel.

Everything a member cares about is "can I download it" and "does the sync
work". So the probes point at what actually breaks the experience, not at
machines: the Rubin API's own health endpoint, the two download endpoints, and
the third-party references both tools read from.

The HTTP layer is injected, so the whole module is testable without network
access and a probe failure can never take the bot down.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum

import aiohttp

log = logging.getLogger("discord-bdo.status")

#: A probe that has not answered by then is red regardless of what it would
#: have said: a user staring at a frozen window has the same experience.
TIMEOUT_SECONDS = 10


class State(str, Enum):
    OK = "ok"
    WARN = "warn"
    DOWN = "down"
    UNKNOWN = "unknown"

    @property
    def dot(self) -> str:
        return {
            State.OK: "🟢",
            State.WARN: "🟡",
            State.DOWN: "🔴",
            State.UNKNOWN: "⚪",
        }[self]

    @property
    def rank(self) -> int:
        """Higher is worse. Used to pick the overall state."""
        return {State.OK: 0, State.UNKNOWN: 1, State.WARN: 2, State.DOWN: 3}[self]


@dataclass(frozen=True)
class Probe:
    key: str
    label: str
    url: str
    #: HTTP codes that mean "this is working". Some endpoints answer 302.
    expect: tuple[int, ...] = (200,)
    #: ``(field, value)`` checked in the JSON body. A service that answers 200
    #: while declaring itself unhealthy is amber, not green.
    expect_json: tuple[str, str] | None = None
    #: Above this many seconds the probe is amber even when it answered.
    warn_after: float = 3.0
    #: Shown to members: what stops working when this is red.
    impact: str = ""
    #: Send the GitHub token when there is one, to stay clear of the 60/h
    #: unauthenticated rate limit.
    github_auth: bool = False


PROBES: tuple[Probe, ...] = (
    Probe(
        key="rubin_api",
        label="API Rubin",
        url="https://rubin.maxyull.fr/sante",
        expect_json=("etat", "ok"),
        impact="Rubin ne peut plus envoyer ses temps / Rubin cannot sync your runs",
    ),
    Probe(
        key="butin_download",
        label="Téléchargement Butin / Butin download",
        url="https://api.github.com/repos/Maxyull/butin-bdo/releases/latest",
        github_auth=True,
        impact="Impossible de télécharger Butin / Butin cannot be downloaded",
    ),
    Probe(
        key="rubin_download",
        label="Téléchargement Rubin / Rubin download",
        url="https://api.github.com/repos/Maxyull/rubin-bdo/releases/latest",
        github_auth=True,
        impact="Impossible de télécharger Rubin / Rubin cannot be downloaded",
    ),
    Probe(
        key="bdocodex",
        label="Référentiel BDOCodex",
        url="https://bdocodex.com/",
        expect=(200, 301, 302),
        impact="Les noms d'objets et de quêtes ne se mettent plus à jour / Item and quest names stop updating",
    ),
    Probe(
        key="veliainn",
        label="Prix Veliainn / Veliainn prices",
        url="https://veliainn.com/",
        expect=(200, 301, 302),
        impact="Les prix de Butin peuvent dater / Butin prices may be stale",
    ),
    Probe(
        key="site",
        label="Site maxyull.fr",
        url="https://maxyull.fr/",
        impact="",
    ),
)


@dataclass(frozen=True)
class ProbeResult:
    probe: Probe
    state: State
    latency: float | None = None
    note: str = ""

    @property
    def line(self) -> str:
        parts = [f"{self.state.dot} **{self.probe.label}**"]
        if self.latency is not None:
            parts.append(f"`{self.latency * 1000:.0f} ms`")
        if self.note:
            parts.append(f"— {self.note}")
        return " ".join(parts)


async def check(
    probe: Probe, session: aiohttp.ClientSession, *, now=time.monotonic
) -> ProbeResult:
    """Run one probe. Never raises: a probe error is a result, not a crash."""
    started = now()
    try:
        async with session.get(probe.url, allow_redirects=False) as response:
            elapsed = now() - started

            if response.status not in probe.expect:
                # 5xx is the service failing; anything else unexpected means it
                # answered but not as agreed, which is a different problem.
                state = State.DOWN if response.status >= 500 else State.WARN
                return ProbeResult(probe, state, elapsed, f"HTTP {response.status}")

            if probe.expect_json is not None:
                field, wanted = probe.expect_json
                try:
                    payload = await response.json(content_type=None)
                    actual = str(payload.get(field, ""))
                except Exception:
                    return ProbeResult(probe, State.WARN, elapsed, "réponse illisible")
                if actual != wanted:
                    return ProbeResult(
                        probe, State.WARN, elapsed, f"{field}={actual or '?'}"
                    )

            if elapsed > probe.warn_after:
                return ProbeResult(probe, State.WARN, elapsed, "lent / slow")
            return ProbeResult(probe, State.OK, elapsed)

    except asyncio.TimeoutError:
        return ProbeResult(probe, State.DOWN, None, "pas de réponse / timeout")
    except Exception as exc:
        log.warning("probe %s failed: %s", probe.key, exc)
        return ProbeResult(probe, State.DOWN, None, type(exc).__name__)


async def check_all(
    probes=PROBES, *, github_token: str = "", session_factory=None
) -> list[ProbeResult]:
    """Run every probe concurrently. One slow probe must not delay the rest."""
    if session_factory is None:
        def session_factory():
            headers = {"User-Agent": "discord-bdo-status"}
            if github_token:
                headers["Authorization"] = f"Bearer {github_token}"
            return aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
                headers=headers,
            )

    session = session_factory()
    async with session as client:
        return list(await asyncio.gather(*(check(p, client) for p in probes)))


def overall(results) -> State:
    """The worst state present, which is what the headline must show."""
    if not results:
        return State.UNKNOWN
    return max((r.state for r in results), key=lambda s: s.rank)


def fingerprint(results) -> str:
    """Identity of a status snapshot, ignoring latency.

    The message is only edited when this changes: Discord renders the
    "checked <t:...:R>" stamp itself, so a steady green board needs no writes.
    """
    return "|".join(f"{r.probe.key}={r.state.value}" for r in results)


HEADLINES = {
    State.OK: "Tout fonctionne / All systems go",
    State.WARN: "Fonctionnement dégradé / Degraded",
    State.DOWN: "Panne en cours / Outage",
    State.UNKNOWN: "État inconnu / Unknown",
}

COLOURS = {
    State.OK: 0x3BA55D,
    State.WARN: 0xE8A33D,
    State.DOWN: 0xD73A49,
    State.UNKNOWN: 0x8A8A8A,
}

LEGEND = (
    "🟢 fonctionne · 🟡 dégradé ou lent · 🔴 en panne\n"
    "🟢 working · 🟡 degraded or slow · 🔴 down"
)


def render_description(results, checked_at: int) -> str:
    """Body of the status message.

    ``checked_at`` is a unix timestamp; Discord turns ``<t:…:R>`` into a
    self-updating "3 minutes ago" on the reader's side, which is why the bot
    does not have to rewrite the message just to refresh a clock.
    """
    lines = [result.line for result in results]

    broken = [r for r in results if r.state is not State.OK and r.probe.impact]
    if broken:
        lines.append("")
        lines.extend(f"> {r.probe.impact}" for r in broken)

    lines.append("")
    lines.append(LEGEND)
    lines.append(f"Dernière vérification / last checked <t:{checked_at}:R>")
    return "\n".join(lines)
