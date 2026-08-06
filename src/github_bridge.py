"""Turn a Discord report into a GitHub issue.

The HTTP layer is injected so the whole module is testable without network
access, and so a GitHub outage can never take the bot down: every failure is
reported back as a :class:`GitHubError` and the Discord thread still exists.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import aiohttp

log = logging.getLogger("discord-bdo.github")

API_ROOT = "https://api.github.com"
#: GitHub answers within a second normally; past this the report is worthless
#: to the user waiting in Discord, so we give up and let them retry.
TIMEOUT_SECONDS = 15


class GitHubError(RuntimeError):
    """Any failure while talking to GitHub, with a message safe to show."""


@dataclass(frozen=True)
class IssueDraft:
    repo: str
    title: str
    body: str
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class CreatedIssue:
    number: int
    url: str


class GitHubClient:
    """Minimal GitHub issues client.

    ``session_factory`` exists purely for tests; production code leaves it
    alone and gets a real :class:`aiohttp.ClientSession`.
    """

    def __init__(self, token: str, *, session_factory=None) -> None:
        self._token = token
        self._session_factory = session_factory or self._default_session

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    def _default_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "discord-bdo",
            },
        )

    async def create_issue(self, draft: IssueDraft) -> CreatedIssue:
        if not self.enabled:
            raise GitHubError("no GitHub token configured")

        payload: dict[str, object] = {"title": draft.title, "body": draft.body}
        if draft.labels:
            payload["labels"] = list(draft.labels)

        url = f"{API_ROOT}/repos/{draft.repo}/issues"
        try:
            session = self._session_factory()
            async with session as client:
                async with client.post(url, json=payload) as response:
                    if response.status == 201:
                        data = await response.json()
                        return CreatedIssue(
                            number=int(data["number"]), url=str(data["html_url"])
                        )
                    detail = await response.text()
                    raise GitHubError(
                        f"GitHub answered {response.status}: {detail[:200]}"
                    )
        except GitHubError:
            raise
        except Exception as exc:  # network error, timeout, malformed JSON
            raise GitHubError(f"{type(exc).__name__}: {exc}") from exc


def build_labels(kind: str, extra: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Labels for a report of the given ``kind`` (``bug`` or ``idea``).

    Deduplicated while preserving order, because GitHub rejects an issue whose
    label list repeats a name.
    """
    base = "bug" if kind == "bug" else "enhancement"
    ordered: list[str] = []
    for label in (base, *extra):
        if label and label not in ordered:
            ordered.append(label)
    return tuple(ordered)


def truncate_title(text: str, limit: int = 120) -> str:
    """GitHub accepts long titles but a wall of text is unusable in a list."""
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"
