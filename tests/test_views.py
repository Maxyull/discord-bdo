import discord
import pytest

from src import blueprint as bp
from src import texts
from src import views
from src.github_bridge import GitHubError, IssueDraft
from src.profiles import Profile


class TestCustomIds:
    def test_ids_are_namespaced_and_carry_the_slug(self):
        assert views.bug_button_id("butin") == "bdo:bug:butin"
        assert views.idea_button_id("rubin") == "bdo:idea:rubin"

    def test_every_product_gets_distinct_ids(self):
        ids = [views.bug_button_id(p.slug) for p in bp.PRODUCTS]
        ids += [views.idea_button_id(p.slug) for p in bp.PRODUCTS]
        assert len(ids) == len(set(ids))

    def test_ids_fit_the_discord_100_char_limit(self):
        for product in bp.PRODUCTS:
            assert len(views.bug_button_id(product.slug)) <= 100
            assert len(views.idea_button_id(product.slug)) <= 100


class TestClip:
    def test_short_text_is_returned_stripped(self):
        assert views.clip("  hello  ", 50) == "hello"

    def test_long_text_gets_an_ellipsis_and_respects_the_limit(self):
        result = views.clip("y" * 300, 10)
        assert len(result) == 10 and result.endswith("…")

    def test_exact_length_is_untouched(self):
        assert views.clip("abcde", 5) == "abcde"


class TestThreadName:
    def test_prefix_is_kept(self):
        assert views.thread_name("🐛", "compteur bloqué").startswith("🐛 ")

    def test_newlines_are_flattened(self):
        assert "\n" not in views.thread_name("🐛", "a\nb\nc")

    def test_result_never_exceeds_the_discord_limit(self):
        name = views.thread_name("🐛", "mot " * 200)
        assert len(name) <= views.THREAD_NAME_LIMIT


class TestPanelEmbed:
    @pytest.mark.parametrize("product", bp.PRODUCTS, ids=lambda p: p.slug)
    def test_embed_names_the_product(self, product):
        embed = views.panel_embed(product)
        assert product.label in embed.title
        assert embed.colour.value == product.colour


class TestSupportPanel:
    @pytest.mark.parametrize("product", bp.PRODUCTS, ids=lambda p: p.slug)
    def test_panel_has_two_persistent_buttons(self, product):
        handler = views.ReportHandler(channels={}, github=None)
        panel = views.SupportPanel(product, handler)
        assert panel.timeout is None, "a timeout would kill the buttons after a restart"
        ids = {item.custom_id for item in panel.children}
        assert ids == {views.bug_button_id(product.slug), views.idea_button_id(product.slug)}


# --------------------------------------------------------------------------- #
# ReportHandler
# --------------------------------------------------------------------------- #


def http_error(status=500, message="boom"):
    """Build a real discord.HTTPException without touching the network."""
    response = type("Resp", (), {"status": status, "reason": message})()
    return discord.HTTPException(response, message)


class FakeStaffLog:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    async def send(self, content):
        if self.fail:
            raise http_error()
        self.sent.append(content)


class FakeGitHub:
    def __init__(self, result=None, error=None, enabled=True):
        self.enabled = enabled
        self.result = result
        self.error = error
        self.drafts = []

    async def create_issue(self, draft):
        self.drafts.append(draft)
        if self.error:
            raise self.error
        return self.result


class Issue:
    def __init__(self, url):
        self.url = url
        self.number = 1


DRAFT = IssueDraft(repo="o/r", title="t", body="b")


class TestReportHandler:
    async def test_no_github_returns_none(self):
        handler = views.ReportHandler(channels={}, github=None)
        assert await handler.create_issue(DRAFT) is None

    async def test_disabled_github_returns_none(self):
        handler = views.ReportHandler(channels={}, github=FakeGitHub(enabled=False))
        assert await handler.create_issue(DRAFT) is None

    async def test_dry_run_never_calls_github(self):
        gh = FakeGitHub(result=Issue("https://gh/1"))
        handler = views.ReportHandler(channels={}, github=gh, dry_run=True)
        assert await handler.create_issue(DRAFT) is None
        assert gh.drafts == []

    async def test_success_returns_the_url_and_logs_it(self):
        log = FakeStaffLog()
        handler = views.ReportHandler(
            channels={}, github=FakeGitHub(result=Issue("https://gh/9")), staff_log=log
        )
        assert await handler.create_issue(DRAFT) == "https://gh/9"
        assert any("https://gh/9" in line for line in log.sent)

    async def test_github_failure_is_swallowed_so_the_report_survives(self):
        log = FakeStaffLog()
        handler = views.ReportHandler(
            channels={},
            github=FakeGitHub(error=GitHubError("403 forbidden")),
            staff_log=log,
        )
        assert await handler.create_issue(DRAFT) is None
        assert any("403" in line for line in log.sent)

    async def test_a_broken_staff_log_does_not_raise(self):
        handler = views.ReportHandler(channels={}, github=None, staff_log=FakeStaffLog(fail=True))
        await handler.log_staff("anything")  # must not raise

    async def test_staff_log_message_is_clipped(self):
        log = FakeStaffLog()
        handler = views.ReportHandler(channels={}, github=None, staff_log=log)
        await handler.log_staff("x" * 5000)
        assert len(log.sent[0]) <= views.MESSAGE_LIMIT

    def test_channel_for_returns_none_when_absent(self):
        handler = views.ReportHandler(channels={}, github=None)
        assert handler.channel_for(bp.KEY_BUTIN_BUGS) is None


# --------------------------------------------------------------------------- #
# open_thread
# --------------------------------------------------------------------------- #


class FakeThread:
    jump_url = "https://discord/thread"


class FakeForum(discord.ForumChannel):
    # ForumChannel exposes available_tags as a property; shadowing it with a
    # plain class attribute makes the instance assignment below legal.
    available_tags = ()

    def __init__(self, tags):
        self.available_tags = tags
        self.calls = []

    async def create_thread(self, *, name, content, applied_tags):
        self.calls.append((name, content, applied_tags))
        result = type("R", (), {"thread": FakeThread()})()
        return result


class FakeMessage:
    def __init__(self):
        self.thread_name = None

    async def create_thread(self, *, name):
        self.thread_name = name
        return FakeThread()


class FakeText(discord.TextChannel):
    def __init__(self):
        self.sent = []
        self.message = FakeMessage()

    async def send(self, content):
        self.sent.append(content)
        return self.message


def make_tag(name):
    tag = object.__new__(discord.ForumTag)
    tag.name = name
    tag.id = abs(hash(name)) % 10**6
    tag.emoji = None
    tag.moderated = False
    return tag


class TestOpenThread:
    async def test_forum_thread_gets_the_requested_tag(self):
        forum = FakeForum([make_tag("Nouveau / New"), make_tag("Corrigé / Fixed")])
        await views.open_thread(forum, name="n", body="b", tag_name="Nouveau / New")
        _, _, tags = forum.calls[0]
        assert [t.name for t in tags] == ["Nouveau / New"]

    async def test_unknown_tag_is_skipped_rather_than_failing(self):
        forum = FakeForum([make_tag("Nouveau / New")])
        await views.open_thread(forum, name="n", body="b", tag_name="Inexistant")
        assert forum.calls[0][2] == []

    async def test_text_channel_fallback_posts_then_threads(self):
        channel = FakeText()
        await views.open_thread(channel, name="mon fil", body="corps")
        assert channel.sent == ["corps"]
        assert channel.message.thread_name == "mon fil"

    async def test_body_is_clipped_to_the_message_limit(self):
        channel = FakeText()
        await views.open_thread(channel, name="n", body="z" * 5000)
        assert len(channel.sent[0]) <= views.MESSAGE_LIMIT

    async def test_unsupported_channel_type_is_rejected_loudly(self):
        with pytest.raises(TypeError):
            await views.open_thread(object(), name="n", body="b")


class TestTextsAreBilingual:
    @pytest.mark.parametrize(
        "text",
        [texts.WELCOME_BODY, texts.RULES_BODY, texts.PANEL_BODY],
        ids=["welcome", "rules", "panel"],
    )
    def test_both_languages_are_present(self, text):
        assert "🇫🇷" in text and "🇬🇧" in text

    def test_button_labels_fit_discord_80_char_limit(self):
        assert len(texts.BTN_BUG) <= 80
        assert len(texts.BTN_IDEA) <= 80

    @pytest.mark.parametrize("product", bp.PRODUCTS, ids=lambda p: p.slug)
    def test_modal_titles_fit_the_45_char_limit(self, product):
        assert len(texts.MODAL_BUG_TITLE.format(label=product.label)) <= 45
        assert len(texts.MODAL_IDEA_TITLE.format(label=product.label)) <= 45

    def test_field_labels_fit_the_45_char_limit(self):
        for label in (
            texts.FIELD_SUMMARY_LABEL,
            texts.FIELD_VERSION_LABEL,
            texts.FIELD_SYSTEM_LABEL,
            texts.FIELD_STEPS_LABEL,
            texts.FIELD_IDEA_LABEL,
            texts.FIELD_PROBLEM_LABEL,
            texts.FIELD_RESOLUTION_LABEL,
            texts.FIELD_SCALING_LABEL,
            texts.FIELD_DISPLAY_MODE_LABEL,
            texts.FIELD_GAME_LANGUAGE_LABEL,
            texts.FIELD_HARDWARE_LABEL,
        ):
            assert len(label) <= 45, label

    def test_placeholders_fit_the_100_char_limit(self):
        for name in dir(texts):
            if name.endswith("_PLACEHOLDER"):
                assert len(getattr(texts, name)) <= 100, name

    def test_setup_modal_title_fits_the_45_char_limit(self):
        assert len(texts.MODAL_SETUP_TITLE) <= 45

    def test_setup_buttons_fit_the_80_char_limit(self):
        assert len(texts.BTN_SETUP) <= 80
        assert len(texts.BTN_SETUP_SHOW) <= 80

    def test_beta_welcome_is_bilingual_and_fits_an_embed(self):
        assert "🇫🇷" in texts.BETA_WELCOME_BODY and "🇬🇧" in texts.BETA_WELCOME_BODY
        assert len(texts.BETA_WELCOME_BODY) <= 4096

    def test_setup_panel_body_is_bilingual_and_fits_an_embed(self):
        assert "🇫🇷" in texts.SETUP_PANEL_BODY and "🇬🇧" in texts.SETUP_PANEL_BODY
        assert len(texts.SETUP_PANEL_BODY) <= 4096


class TestSetupPanel:
    def test_two_persistent_buttons_with_stable_ids(self):
        handler = views.ReportHandler(channels={}, github=None)
        panel = views.SetupPanel(handler)
        assert panel.timeout is None
        assert {item.custom_id for item in panel.children} == {
            views.SETUP_EDIT_ID,
            views.SETUP_SHOW_ID,
        }

    def test_setup_ids_do_not_collide_with_product_ids(self):
        product_ids = {views.bug_button_id(p.slug) for p in bp.PRODUCTS}
        product_ids |= {views.idea_button_id(p.slug) for p in bp.PRODUCTS}
        assert views.SETUP_EDIT_ID not in product_ids
        assert views.SETUP_SHOW_ID not in product_ids


class TestSetupModal:
    def test_exactly_five_fields_which_is_the_discord_maximum(self):
        modal = views.SetupModal(views.ReportHandler(channels={}, github=None))
        assert len(modal.children) == 5

    def test_fields_are_prefilled_from_an_existing_card(self):
        existing = Profile(user_id=1, resolution="1920x1080", scaling="100%")
        modal = views.SetupModal(
            views.ReportHandler(channels={}, github=None), existing
        )
        assert modal.resolution.default == "1920x1080"
        assert modal.scaling.default == "100%"

    def test_missing_values_leave_the_field_blank_not_the_string_none(self):
        modal = views.SetupModal(views.ReportHandler(channels={}, github=None))
        assert modal.resolution.default is None

    def test_only_resolution_scaling_and_mode_are_required(self):
        modal = views.SetupModal(views.ReportHandler(channels={}, github=None))
        assert modal.resolution.required is True
        assert modal.scaling.required is True
        assert modal.display_mode.required is True
        assert modal.game_language.required is False
        assert modal.hardware.required is False


class FakeUser:
    id = 42
    display_name = "Testeur"


class TestSetupModalToProfile:
    def build(self, **values):
        modal = views.SetupModal(views.ReportHandler(channels={}, github=None))
        for field, value in values.items():
            getattr(modal, field)._value = value
        return modal

    def test_values_are_normalised_on_the_way_in(self):
        modal = self.build(
            resolution="2560 * 1440",
            scaling="1.5",
            display_mode="  fenêtré  ",
            game_language="français",
            hardware="RTX  3060\n16 Go",
        )
        profile = modal.to_profile(FakeUser())
        assert profile.resolution == "2560x1440"
        assert profile.scaling == "150%"
        assert profile.display_mode == "fenêtré"
        assert profile.hardware == "RTX 3060 16 Go"

    def test_the_discord_user_id_is_the_key(self):
        profile = self.build(
            resolution="1920x1080", scaling="100%", display_mode="fullscreen"
        ).to_profile(FakeUser())
        assert profile.user_id == 42
        assert profile.display_name == "Testeur"


class TestProfileFailuresAreSurvivable:
    class BrokenStore:
        async def get(self, user_id):
            raise RuntimeError("database is locked")

        async def save(self, profile):
            raise RuntimeError("disk full")

    async def test_a_broken_lookup_returns_none_instead_of_raising(self):
        handler = views.ReportHandler(
            channels={}, github=None, profiles=self.BrokenStore()
        )
        assert await handler.profile_for(1) is None

    async def test_a_broken_save_is_reported_as_a_failure(self):
        handler = views.ReportHandler(
            channels={}, github=None, profiles=self.BrokenStore()
        )
        assert await handler.save_profile(Profile(user_id=1)) is False

    async def test_saving_without_a_store_fails_rather_than_pretending(self):
        handler = views.ReportHandler(channels={}, github=None)
        assert await handler.save_profile(Profile(user_id=1)) is False

    def test_embed_descriptions_fit_the_4096_char_limit(self):
        assert len(texts.WELCOME_BODY) <= 4096
        assert len(texts.RULES_BODY) <= 4096
        assert len(texts.PANEL_BODY) <= 4096
