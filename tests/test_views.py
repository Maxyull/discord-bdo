import discord
import pytest

from src import blueprint as bp
from src import texts
from src import views
from src.github_bridge import GitHubError, IssueDraft
from src.profiles import (
    DISPLAY_MODES,
    GAME_LANGUAGES,
    MACHINE_FIELDS,
    SCREEN_FIELDS,
    WINDOWS_SCALES,
    Profile,
)


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
            texts.FIELD_UI_SCALE_LABEL,
            texts.FIELD_DISPLAY_MODE_LABEL,
            texts.FIELD_GAME_LANGUAGE_LABEL,
            texts.FIELD_CPU_LABEL,
            texts.FIELD_GPU_LABEL,
            texts.FIELD_RAM_LABEL,
        ):
            assert len(label) <= 45, label

    def test_placeholders_fit_the_100_char_limit(self):
        for name in dir(texts):
            if name.endswith("_PLACEHOLDER"):
                assert len(getattr(texts, name)) <= 100, name

    def test_setup_modal_titles_fit_the_45_char_limit(self):
        assert len(texts.MODAL_SCREEN_TITLE) <= 45
        assert len(texts.MODAL_MACHINE_TITLE) <= 45

    def test_setup_buttons_fit_the_80_char_limit(self):
        for label in (
            texts.BTN_SETUP_SCREEN,
            texts.BTN_SETUP_MACHINE,
            texts.BTN_SETUP_SHOW,
        ):
            assert len(label) <= 80, label

    def test_beta_welcome_is_bilingual_and_fits_an_embed(self):
        assert "🇫🇷" in texts.BETA_WELCOME_BODY and "🇬🇧" in texts.BETA_WELCOME_BODY
        assert len(texts.BETA_WELCOME_BODY) <= 4096

    def test_setup_panel_body_is_bilingual_and_fits_an_embed(self):
        assert "🇫🇷" in texts.SETUP_PANEL_BODY and "🇬🇧" in texts.SETUP_PANEL_BODY
        assert len(texts.SETUP_PANEL_BODY) <= 4096


class TestSetupPanel:
    def test_three_persistent_buttons_with_stable_ids(self):
        handler = views.ReportHandler(channels={}, github=None)
        panel = views.SetupPanel(handler)
        assert panel.timeout is None
        assert {item.custom_id for item in panel.children} == {
            views.SETUP_SCREEN_ID,
            views.SETUP_MACHINE_ID,
            views.SETUP_SHOW_ID,
        }

    def test_setup_ids_do_not_collide_with_product_ids(self):
        product_ids = {views.bug_button_id(p.slug) for p in bp.PRODUCTS}
        product_ids |= {views.idea_button_id(p.slug) for p in bp.PRODUCTS}
        for setup_id in (
            views.SETUP_SCREEN_ID,
            views.SETUP_MACHINE_ID,
            views.SETUP_SHOW_ID,
        ):
            assert setup_id not in product_ids


def handler():
    return views.ReportHandler(channels={}, github=None)


class TestScreenModal:
    def test_exactly_five_fields_which_is_the_discord_maximum(self):
        assert len(views.ScreenModal(handler()).children) == 5

    def test_it_writes_only_the_screen_columns(self):
        # Otherwise submitting it would blank the machine values.
        assert views.ScreenModal.COLUMNS == SCREEN_FIELDS

    def test_free_text_fields_are_prefilled_from_an_existing_card(self):
        existing = Profile(user_id=1, resolution="1920x1080", ui_scale="110%")
        modal = views.ScreenModal(handler(), existing)
        assert modal.resolution.default == "1920x1080"
        assert modal.ui_scale.default == "110%"

    def test_a_picker_preselects_the_stored_value(self):
        existing = Profile(user_id=1, scaling="150%", display_mode="fenêtré")
        modal = views.ScreenModal(handler(), existing)
        assert [o.value for o in modal.scaling.options if o.default] == ["150%"]
        assert [o.value for o in modal.display_mode.options if o.default] == ["fenêtré"]

    def test_preselection_matches_the_value_not_the_label(self):
        # Rewording a label must not orphan every card already filled in.
        existing = Profile(user_id=1, game_language="english")
        modal = views.ScreenModal(handler(), existing)
        choisi = [o for o in modal.game_language.options if o.default]
        assert len(choisi) == 1 and choisi[0].value == "english"

    def test_a_card_with_no_value_preselects_nothing(self):
        modal = views.ScreenModal(handler())
        assert not [o for o in modal.scaling.options if o.default]

    def test_an_unknown_stored_value_preselects_nothing_rather_than_guessing(self):
        # Cards filled in before the pickers existed can hold anything.
        existing = Profile(user_id=1, display_mode="borderless windowed")
        modal = views.ScreenModal(handler(), existing)
        assert not [o for o in modal.display_mode.options if o.default]

    def test_missing_values_leave_the_field_blank_not_the_string_none(self):
        assert views.ScreenModal(handler()).resolution.default is None

    def test_the_free_text_fields_are_required(self):
        modal = views.ScreenModal(handler())
        assert modal.resolution.required is True
        assert modal.ui_scale.required is True

    def test_the_fixed_value_fields_are_pickers(self):
        # Typing is where "fenetré sans bordure" and "borderless" come from,
        # three spellings of one setting that then have to be reconciled.
        modal = views.ScreenModal(handler())
        for champ in (modal.scaling, modal.display_mode, modal.game_language):
            assert isinstance(champ, discord.ui.Select)

    def test_a_picker_forces_exactly_one_answer(self):
        modal = views.ScreenModal(handler())
        for champ in (modal.scaling, modal.display_mode, modal.game_language):
            assert champ.min_values == 1
            assert champ.max_values == 1

    def test_pickers_are_wrapped_in_a_label(self):
        # A Select carries no label of its own; unwrapped, the member sees a
        # dropdown with no idea what it is for.
        modal = views.ScreenModal(handler())
        etiquetes = [c for c in modal.children if isinstance(c, discord.ui.Label)]
        assert len(etiquetes) == 3
        assert all(e.text for e in etiquetes)

    def test_every_offered_choice_carries_a_stored_value(self):
        for choix in (WINDOWS_SCALES, DISPLAY_MODES, GAME_LANGUAGES):
            for valeur, libelle in choix:
                assert valeur and libelle

    def test_choice_labels_fit_the_100_char_limit(self):
        for choix in (WINDOWS_SCALES, DISPLAY_MODES, GAME_LANGUAGES):
            for valeur, libelle in choix:
                assert len(libelle) <= 100
                assert len(valeur) <= 100

    def test_windows_offers_a_custom_scaling_escape_hatch(self):
        # Windows lets you type any value between 100 and 500; without this
        # anyone off the standard steps could not answer at all.
        assert any(v == "autre" for v, _ in WINDOWS_SCALES)


class TestMachineModal:
    def test_three_fields(self):
        assert len(views.MachineModal(handler()).children) == 3

    def test_it_writes_only_the_machine_columns(self):
        assert views.MachineModal.COLUMNS == MACHINE_FIELDS

    def test_every_field_is_optional(self):
        modal = views.MachineModal(handler())
        assert all(item.required is False for item in modal.children)

    def test_fields_are_prefilled(self):
        modal = views.MachineModal(handler(), Profile(user_id=1, gpu="RTX 3060"))
        assert modal.gpu.default == "RTX 3060"


class FakeUser:
    id = 42
    display_name = "Testeur"


class TestModalToProfile:
    def build(self, modal_class, **values):
        modal = modal_class(handler())
        for field, value in values.items():
            champ = getattr(modal, field)
            if isinstance(champ, discord.ui.Select):
                # BaseSelect.values falls back to _values outside an interaction.
                champ._values = [value] if value else []
            else:
                champ._value = value
        return modal

    def test_free_text_is_normalised_on_the_way_in(self):
        modal = self.build(
            views.ScreenModal,
            resolution="2560 * 1440",
            ui_scale="110",
            scaling="150%",
            display_mode="fenêtré",
            game_language="français",
        )
        profile = modal.to_profile(FakeUser())
        assert profile.resolution == "2560x1440"
        assert profile.ui_scale == "110%"

    def test_picked_values_are_stored_verbatim(self):
        # They come from a list, so they are already canonical: normalising
        # them again could only corrupt a value we chose ourselves.
        modal = self.build(
            views.ScreenModal,
            resolution="1920x1080",
            ui_scale="100",
            scaling="125%",
            display_mode="fenêtré sans bordure",
            game_language="english",
        )
        profile = modal.to_profile(FakeUser())
        assert profile.scaling == "125%"
        assert profile.display_mode == "fenêtré sans bordure"
        assert profile.game_language == "english"

    def test_an_untouched_picker_stores_nothing_rather_than_a_default(self):
        modal = self.build(
            views.ScreenModal, resolution="1920x1080", ui_scale="100"
        )
        profile = modal.to_profile(FakeUser())
        assert profile.scaling == ""
        assert profile.display_mode == ""

    def test_the_two_scales_stay_separate(self):
        modal = self.build(
            views.ScreenModal,
            resolution="1920x1080",
            scaling="150%",
            ui_scale="100",
            display_mode="plein écran",
            game_language="",
        )
        profile = modal.to_profile(FakeUser())
        assert (profile.scaling, profile.ui_scale) == ("150%", "100%")

    def test_machine_values_are_whitespace_collapsed(self):
        modal = self.build(
            views.MachineModal, cpu="Ryzen  5\n5600", gpu="RTX 3060", ram=" 16 Go "
        )
        profile = modal.to_profile(FakeUser())
        assert profile.cpu == "Ryzen 5 5600"
        assert profile.ram == "16 Go"

    def test_the_discord_user_id_is_the_key(self):
        profile = self.build(
            views.ScreenModal,
            resolution="1920x1080",
            scaling="100%",
            ui_scale="100%",
            display_mode="plein écran",
            game_language="",
        ).to_profile(FakeUser())
        assert profile.user_id == 42
        assert profile.display_name == "Testeur"


class TestProfileFailuresAreSurvivable:
    class BrokenStore:
        async def get(self, user_id):
            raise RuntimeError("database is locked")

        async def save(self, profile, only=None):
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
