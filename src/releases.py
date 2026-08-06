"""Latest published version of each tool.

"Which version am I supposed to have" is the single most common question on a
tool's Discord, and the answer already exists on GitHub. Reading it live beats
writing it in a pinned message that goes stale on the next release.

Results are cached: the answer changes a few times a month, and an unauthenticated
GitHub caller only gets 60 requests an hour.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import aiohttp

log = logging.getLogger("discord-bdo.releases")

API_ROOT = "https://api.github.com"
TIMEOUT_SECONDS = 10
#: A release is published a few times a month at most.
CACHE_SECONDS = 15 * 60


class ReleaseError(RuntimeError):
    """GitHub could not be reached or answered something unusable."""


@dataclass(frozen=True)
class Release:
    tag: str
    url: str
    published_at: str = ""
    #: Unix timestamp, 0 when GitHub gave no parsable date.
    published_ts: int = 0

    @property
    def stamp(self) -> str:
        """Discord renders this as a local, self-updating date."""
        return f"<t:{self.published_ts}:R>" if self.published_ts else ""


def _parse_ts(raw: str) -> int:
    """GitHub returns ISO-8601 in UTC, e.g. 2026-08-06T12:34:56Z."""
    if not raw:
        return 0
    try:
        parsed = time.strptime(raw, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return 0
    return int(time.mktime(parsed) - time.timezone)


class ReleaseClient:
    def __init__(self, token: str = "", *, session_factory=None, now=time.monotonic) -> None:
        self._token = token
        self._session_factory = session_factory or self._default_session
        self._now = now
        self._cache: dict[str, tuple[float, Release]] = {}

    def _default_session(self) -> aiohttp.ClientSession:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "discord-bdo",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS), headers=headers
        )

    def cached(self, repo: str) -> Release | None:
        entry = self._cache.get(repo)
        if entry is None:
            return None
        stored_at, release = entry
        if self._now() - stored_at > CACHE_SECONDS:
            return None
        return release

    async def latest(self, repo: str) -> Release:
        hit = self.cached(repo)
        if hit is not None:
            return hit

        url = f"{API_ROOT}/repos/{repo}/releases/latest"
        try:
            session = self._session_factory()
            async with session as client:
                async with client.get(url) as response:
                    if response.status == 404:
                        raise ReleaseError("aucune version publiée")
                    if response.status != 200:
                        raise ReleaseError(f"GitHub a répondu {response.status}")
                    payload = await response.json(content_type=None)
        except ReleaseError:
            raise
        except Exception as exc:
            raise ReleaseError(f"{type(exc).__name__}: {exc}") from exc

        tag = str(payload.get("tag_name") or "").strip()
        if not tag:
            raise ReleaseError("réponse sans numéro de version")

        published = str(payload.get("published_at") or "")
        release = Release(
            tag=tag,
            url=str(payload.get("html_url") or f"https://github.com/{repo}/releases/latest"),
            published_at=published,
            published_ts=_parse_ts(published),
        )
        self._cache[repo] = (self._now(), release)
        return release
