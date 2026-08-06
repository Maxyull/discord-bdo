import pytest

from src.github_bridge import (
    CreatedIssue,
    GitHubClient,
    GitHubError,
    IssueDraft,
    build_labels,
    truncate_title,
)


class FakeResponse:
    def __init__(self, status, payload=None, text=""):
        self.status = status
        self._payload = payload or {}
        self._text = text

    async def json(self):
        return self._payload

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Stands in for aiohttp.ClientSession, records what was sent."""

    def __init__(self, response=None, raiser=None):
        self.response = response
        self.raiser = raiser
        self.calls = []

    def post(self, url, json=None):
        self.calls.append((url, json))
        if self.raiser:
            raise self.raiser
        return self.response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def client_with(session):
    return GitHubClient("token", session_factory=lambda: session)


class TestCreateIssue:
    async def test_success_returns_number_and_url(self):
        session = FakeSession(
            FakeResponse(201, {"number": 42, "html_url": "https://gh/i/42"})
        )
        issue = await client_with(session).create_issue(
            IssueDraft(repo="o/r", title="t", body="b", labels=("bug",))
        )
        assert issue == CreatedIssue(number=42, url="https://gh/i/42")

    async def test_posts_to_the_repo_issues_endpoint(self):
        session = FakeSession(FakeResponse(201, {"number": 1, "html_url": "u"}))
        await client_with(session).create_issue(
            IssueDraft(repo="Maxyull/butin-bdo", title="t", body="b")
        )
        url, payload = session.calls[0]
        assert url == "https://api.github.com/repos/Maxyull/butin-bdo/issues"
        assert payload == {"title": "t", "body": "b"}

    async def test_labels_are_sent_when_present(self):
        session = FakeSession(FakeResponse(201, {"number": 1, "html_url": "u"}))
        await client_with(session).create_issue(
            IssueDraft(repo="o/r", title="t", body="b", labels=("bug", "discord"))
        )
        assert session.calls[0][1]["labels"] == ["bug", "discord"]

    @pytest.mark.parametrize("status", [401, 403, 404, 422, 500])
    async def test_http_failure_raises_githuberror(self, status):
        session = FakeSession(FakeResponse(status, text="nope"))
        with pytest.raises(GitHubError, match=str(status)):
            await client_with(session).create_issue(
                IssueDraft(repo="o/r", title="t", body="b")
            )

    async def test_network_failure_is_wrapped(self):
        session = FakeSession(raiser=TimeoutError("too slow"))
        with pytest.raises(GitHubError, match="TimeoutError"):
            await client_with(session).create_issue(
                IssueDraft(repo="o/r", title="t", body="b")
            )

    async def test_without_token_the_client_refuses(self):
        with pytest.raises(GitHubError, match="no GitHub token"):
            await GitHubClient("").create_issue(IssueDraft(repo="o/r", title="t", body="b"))

    def test_enabled_reflects_the_token(self):
        assert GitHubClient("x").enabled is True
        assert GitHubClient("").enabled is False


class TestLabels:
    def test_bug_and_idea_map_to_github_conventions(self):
        assert build_labels("bug")[0] == "bug"
        assert build_labels("idea")[0] == "enhancement"

    def test_extras_are_appended(self):
        assert build_labels("bug", ("discord",)) == ("bug", "discord")

    def test_duplicates_are_dropped_because_github_rejects_them(self):
        assert build_labels("bug", ("bug", "discord", "discord")) == ("bug", "discord")

    def test_empty_extras_are_ignored(self):
        assert build_labels("bug", ("", "discord")) == ("bug", "discord")


class TestTruncateTitle:
    def test_short_title_untouched(self):
        assert truncate_title("court") == "court"

    def test_whitespace_is_collapsed(self):
        assert truncate_title("a\n\n b  c") == "a b c"

    def test_long_title_is_cut_with_ellipsis(self):
        result = truncate_title("x" * 200, limit=20)
        assert len(result) == 20 and result.endswith("…")
