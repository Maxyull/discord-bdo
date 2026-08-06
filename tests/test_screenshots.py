"""Screenshot detection and the setup card injected into reports."""

import pytest

from src import blueprint as bp
from src import texts
from src.bot import is_visual
from src.profiles import Profile
from src.views import format_setup_block, format_setup_rows


class FakeAttachment:
    def __init__(self, filename="", content_type=None):
        self.filename = filename
        self.content_type = content_type


class TestIsVisual:
    @pytest.mark.parametrize(
        "content_type",
        ["image/png", "image/jpeg", "image/gif", "video/mp4", "IMAGE/PNG"],
    )
    def test_image_and_video_content_types_count(self, content_type):
        assert is_visual(FakeAttachment("x", content_type)) is True

    @pytest.mark.parametrize(
        "name",
        ["capture.png", "shot.JPG", "clip.mp4", "record.webm", "bug.jpeg"],
    )
    def test_extension_is_used_when_discord_omits_the_type(self, name):
        # Discord leaves content_type empty on some uploads; falling back to
        # the filename is what keeps detection from silently missing them.
        assert is_visual(FakeAttachment(name, None)) is True

    @pytest.mark.parametrize(
        "attachment",
        [
            FakeAttachment("journal.txt", "text/plain"),
            FakeAttachment("session.csv", "text/csv"),
            FakeAttachment("archive.zip", "application/zip"),
            FakeAttachment("", None),
        ],
    )
    def test_other_files_are_not_screenshots(self, attachment):
        assert is_visual(attachment) is False


PROFILE = Profile(
    user_id=1,
    resolution="2560x1440",
    scaling="150%",
    display_mode="fenêtré sans bordure",
    game_language="français",
    hardware="RTX 3060",
)


class TestSetupInjection:
    def test_block_lists_every_filled_field(self):
        block = format_setup_block(PROFILE)
        for value in ("2560x1440", "150%", "fenêtré sans bordure", "RTX 3060"):
            assert value in block

    def test_missing_profile_says_so_instead_of_being_blank(self):
        # A silent gap reads as "the reporter has a plain setup", which is the
        # wrong conclusion to hand a maintainer.
        assert "Pas de fiche" in format_setup_block(None)

    def test_empty_profile_is_treated_as_missing(self):
        assert "Pas de fiche" in format_setup_block(Profile(user_id=1))

    def test_rows_are_github_table_lines(self):
        rows = format_setup_rows(PROFILE)
        assert rows.startswith("| Resolution | 2560x1440 |")
        assert rows.endswith("\n")

    def test_rows_skip_blank_fields(self):
        rows = format_setup_rows(Profile(user_id=1, resolution="800x600"))
        assert "Scaling" not in rows

    def test_rows_are_empty_without_a_profile(self):
        assert format_setup_rows(None) == ""

    def test_issue_body_stays_valid_markdown_without_a_profile(self):
        body = texts.ISSUE_BUG_BODY.format(
            author="a",
            version="1.0",
            system="Win11",
            setup_rows="",
            summary="s",
            steps="st",
            thread_url="u",
        )
        # The table must end cleanly on its last row: a stray "| |" line would
        # render as an empty row on GitHub.
        table = body.split("### Summary")[0].strip().splitlines()
        assert table[-1] == "| OS | Win11 |"

    def test_issue_body_keeps_the_table_together_with_a_profile(self):
        body = texts.ISSUE_BUG_BODY.format(
            author="a",
            version="1.0",
            system="Win11",
            setup_rows=format_setup_rows(PROFILE),
            summary="s",
            steps="st",
            thread_url="u",
        )
        assert "| OS | Win11 |\n| Resolution | 2560x1440 |" in body


class TestScreenshotTag:
    def test_the_tag_is_declared_on_both_bug_forums(self):
        by_key = {ch.key: ch for _, ch in bp.all_channel_specs() if ch.key}
        for product in bp.PRODUCTS:
            assert bp.TAG_HAS_SCREENSHOT in by_key[product.bug_channel_key].tags

    def test_the_tag_is_not_a_reporter_choice(self):
        # It is set by the bot when an image lands, so it must stay out of the
        # list a reporter picks from.
        assert bp.TAG_HAS_SCREENSHOT not in bp.BUG_TAGS

    def test_forums_stay_under_the_20_tag_limit(self):
        for _, spec in bp.all_channel_specs():
            if spec.kind is bp.ChannelKind.FORUM:
                assert len(spec.tags) <= 20, spec.name

    def test_the_screenshot_ask_is_bilingual_and_fits_a_message(self):
        assert "🇫🇷" in texts.SCREENSHOT_ASK and "🇬🇧" in texts.SCREENSHOT_ASK
        assert len(texts.SCREENSHOT_ASK) <= 2000
