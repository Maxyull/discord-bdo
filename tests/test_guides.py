"""The guide content, and the rule that re-running setup never duplicates it."""

import discord
import pytest

from src import blueprint as bp
from src import guides
from src import setup_guild


class TestContent:
    def test_the_offline_check_passes(self):
        assert guides.check() == []

    def test_titles_are_unique(self):
        titles = [g.title for g in guides.GUIDES]
        assert len(titles) == len(set(titles))

    @pytest.mark.parametrize("guide", guides.GUIDES, ids=lambda g: g.title)
    def test_body_fits_a_discord_message(self, guide):
        assert len(guide.body) <= guides.BODY_LIMIT

    @pytest.mark.parametrize("guide", guides.GUIDES, ids=lambda g: g.title)
    def test_title_fits_a_thread_name(self, guide):
        assert len(guide.title) <= 100

    @pytest.mark.parametrize("guide", guides.GUIDES, ids=lambda g: g.title)
    def test_tags_are_declared_on_the_forum(self, guide):
        # A tag the forum does not carry is silently dropped by Discord, so the
        # guide would land untagged and unfindable.
        assert guide.tags
        assert set(guide.tags) <= set(bp.GUIDE_TAGS)

    def test_both_tools_have_an_install_guide(self):
        installs = [g for g in guides.GUIDES if guides.TAG_INSTALL in g.tags]
        tags = {tag for g in installs for tag in g.tags}
        assert guides.TAG_BUTIN in tags
        assert guides.TAG_RUBIN in tags

    def test_there_is_a_troubleshooting_guide(self):
        assert any(guides.TAG_TROUBLE in g.tags for g in guides.GUIDES)

    def test_links_point_at_the_real_repositories(self):
        text = " ".join(g.body for g in guides.GUIDES)
        assert "github.com/Maxyull/butin-bdo" in text
        assert "github.com/Maxyull/rubin-bdo" in text

    def test_no_guide_invents_a_download_page(self):
        # Anything that looks like a release link must be one of the two repos.
        for guide in guides.GUIDES:
            for line in guide.body.splitlines():
                if "releases" in line:
                    assert "Maxyull/butin-bdo" in line or "Maxyull/rubin-bdo" in line

    def test_the_calibration_guide_warns_about_scale_changes(self):
        # The single most common cause of "it stopped counting", and the whole
        # reason the setup card asks for both scales.
        trouble = next(g for g in guides.GUIDES if guides.TAG_TROUBLE in g.tags)
        assert "échelle" in trouble.body.lower()


# --------------------------------------------------------------------------- #
# Posting
# --------------------------------------------------------------------------- #


def make_tag(name):
    tag = object.__new__(discord.ForumTag)
    tag.name = name
    tag.id = abs(hash(name)) % 10**6
    tag.emoji = None
    tag.moderated = False
    return tag


class FakeThread:
    def __init__(self, name):
        self.name = name


class FakeForum(discord.ForumChannel):
    available_tags = ()
    threads = ()

    def __init__(self, existing=(), archived=(), fail=False):
        self.available_tags = [make_tag(name) for name in bp.GUIDE_TAGS]
        self.threads = [FakeThread(name) for name in existing]
        self._archived = [FakeThread(name) for name in archived]
        self.created = []
        self.fail = fail

    def archived_threads(self, limit=None):
        async def gen():
            for thread in self._archived:
                yield thread

        return gen()

    async def create_thread(self, *, name, content, applied_tags):
        if self.fail:
            raise discord.HTTPException(
                type("R", (), {"status": 403, "reason": "nope"})(), "forbidden"
            )
        self.created.append((name, content, applied_tags))
        return type("R", (), {"thread": FakeThread(name)})()


def report():
    return bp.SetupReport()


class TestPostGuides:
    async def test_an_empty_forum_receives_every_guide(self):
        forum = FakeForum()
        rep = report()
        await setup_guild.post_guides({bp.KEY_GUIDES: forum}, rep)
        assert len(forum.created) == len(guides.GUIDES)

    async def test_running_twice_creates_nothing_the_second_time(self):
        forum = FakeForum(existing=[g.title for g in guides.GUIDES])
        rep = report()
        await setup_guild.post_guides({bp.KEY_GUIDES: forum}, rep)
        assert forum.created == []
        assert len(rep.skipped) == len(guides.GUIDES)

    async def test_an_archived_guide_is_not_reposted(self):
        # Discord archives quiet threads; without checking archived ones the
        # forum would slowly fill with duplicates of the same guide.
        forum = FakeForum(archived=[guides.GUIDES[0].title])
        await setup_guild.post_guides({bp.KEY_GUIDES: forum}, report())
        assert guides.GUIDES[0].title not in [name for name, _, _ in forum.created]

    async def test_only_the_missing_guides_are_added(self):
        forum = FakeForum(existing=[guides.GUIDES[0].title])
        await setup_guild.post_guides({bp.KEY_GUIDES: forum}, report())
        assert len(forum.created) == len(guides.GUIDES) - 1

    async def test_tags_are_applied(self):
        forum = FakeForum()
        await setup_guild.post_guides({bp.KEY_GUIDES: forum}, report())
        name, _, tags = forum.created[0]
        assert [t.name for t in tags] == list(guides.GUIDES[0].tags)

    async def test_a_missing_forum_is_silently_skipped(self):
        rep = report()
        await setup_guild.post_guides({}, rep)
        assert rep.warnings == []

    async def test_a_text_channel_fallback_is_reported_not_crashed(self):
        # Happens when Community mode could not be enabled and the forum was
        # created as a plain text channel instead.
        rep = report()
        await setup_guild.post_guides({bp.KEY_GUIDES: object()}, rep)
        assert any("forum" in w for w in rep.warnings)

    async def test_a_failing_post_is_reported_and_the_rest_continues(self):
        forum = FakeForum(fail=True)
        rep = report()
        await setup_guild.post_guides({bp.KEY_GUIDES: forum}, rep)
        assert len(rep.warnings) == len(guides.GUIDES)
        assert rep.created_channels == []
