import pytest

from src.profiles import (
    Profile,
    ProfileStore,
    normalise_resolution,
    normalise_scaling,
)


@pytest.fixture
async def store():
    store = ProfileStore(":memory:")
    await store.setup()
    yield store
    await store.close()


SAMPLE = Profile(
    user_id=7,
    display_name="Maxyull",
    resolution="2560x1440",
    scaling="150%",
    display_mode="fenêtré sans bordure",
    game_language="français",
    hardware="Ryzen 5 5600 / RTX 3060 / 16 Go",
)


class TestStore:
    async def test_unknown_user_returns_none(self, store):
        assert await store.get(999) is None

    async def test_save_then_get_round_trips(self, store):
        await store.save(SAMPLE)
        loaded = await store.get(7)
        assert loaded.resolution == "2560x1440"
        assert loaded.display_mode == "fenêtré sans bordure"
        assert loaded.hardware.startswith("Ryzen")

    async def test_saving_twice_updates_rather_than_duplicates(self, store):
        await store.save(SAMPLE)
        await store.save(Profile(user_id=7, resolution="1920x1080"))
        assert await store.count() == 1
        assert (await store.get(7)).resolution == "1920x1080"

    async def test_updated_at_is_filled_by_the_database(self, store):
        await store.save(SAMPLE)
        assert (await store.get(7)).updated_at

    async def test_delete_reports_whether_anything_went(self, store):
        await store.save(SAMPLE)
        assert await store.delete(7) is True
        assert await store.delete(7) is False
        assert await store.get(7) is None

    async def test_users_are_independent(self, store):
        await store.save(SAMPLE)
        await store.save(Profile(user_id=8, resolution="3840x2160"))
        assert (await store.get(7)).resolution == "2560x1440"
        assert (await store.get(8)).resolution == "3840x2160"
        assert await store.count() == 2

    async def test_setup_is_idempotent(self, store):
        await store.save(SAMPLE)
        await store.setup()  # must not wipe the table
        assert await store.count() == 1


class TestProfileRendering:
    def test_empty_profile_is_flagged(self):
        assert Profile(user_id=1).is_empty is True

    def test_any_field_makes_it_non_empty(self):
        assert Profile(user_id=1, resolution="800x600").is_empty is False

    def test_blank_fields_are_skipped_in_lines(self):
        lines = Profile(user_id=1, resolution="800x600").as_lines()
        assert len(lines) == 1 and "800x600" in lines[0]

    def test_lines_are_bilingual_labelled(self):
        text = "\n".join(SAMPLE.as_lines())
        assert "Résolution" in text and "Resolution" in text

    def test_markdown_table_holds_only_filled_rows(self):
        table = Profile(user_id=1, resolution="800x600", scaling="100%").as_markdown_table()
        assert table.count("|\n") >= 2
        assert "Display mode" not in table

    def test_markdown_table_is_empty_for_an_empty_profile(self):
        assert Profile(user_id=1).as_markdown_table() == ""


class TestNormaliseResolution:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("2560x1440", "2560x1440"),
            ("2560 x 1440", "2560x1440"),
            ("2560X1440", "2560x1440"),
            ("2560*1440", "2560x1440"),
            ("2560×1440", "2560x1440"),
            ("1920 par 1080", "1920x1080"),
            ("1920 by 1080", "1920x1080"),
            ("  1920x1080  ", "1920x1080"),
        ],
    )
    def test_common_spellings_converge(self, raw, expected):
        assert normalise_resolution(raw) == expected

    def test_empty_stays_empty(self):
        assert normalise_resolution("   ") == ""

    def test_free_text_is_left_alone_rather_than_mangled(self):
        # Inventing a value would be worse than keeping the user's words.
        assert normalise_resolution("écran ultra large") == "écran ultra large"

    def test_partial_numbers_are_left_alone(self):
        assert normalise_resolution("2560 x large") == "2560 x large"


class TestNormaliseScaling:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("150%", "150%"),
            ("150", "150%"),
            ("1.5", "150%"),
            ("1,5", "150%"),
            ("100", "100%"),
            ("1", "100%"),
            ("  125 %  ", "125%"),
        ],
    )
    def test_common_spellings_converge(self, raw, expected):
        assert normalise_scaling(raw) == expected

    def test_empty_stays_empty(self):
        assert normalise_scaling("") == ""

    def test_free_text_is_left_alone(self):
        assert normalise_scaling("je sais pas") == "je sais pas"
