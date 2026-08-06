import pytest

from src.profiles import (
    MACHINE_FIELDS,
    SCREEN_FIELDS,
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
    ui_scale="110%",
    display_mode="fenêtré sans bordure",
    game_language="français",
    cpu="Ryzen 5 5600",
    gpu="RTX 3060",
    ram="16 Go",
)


class TestStore:
    async def test_unknown_user_returns_none(self, store):
        assert await store.get(999) is None

    async def test_save_then_get_round_trips(self, store):
        await store.save(SAMPLE)
        loaded = await store.get(7)
        assert loaded.resolution == "2560x1440"
        assert loaded.display_mode == "fenêtré sans bordure"
        assert loaded.ui_scale == "110%"
        assert loaded.cpu == "Ryzen 5 5600"
        assert loaded.gpu == "RTX 3060"

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


class TestPartialSave:
    """The two forms must not erase each other's columns."""

    async def test_machine_form_keeps_the_screen_values(self, store):
        await store.save(
            Profile(user_id=1, resolution="2560x1440", ui_scale="110%"),
            only=SCREEN_FIELDS,
        )
        await store.save(Profile(user_id=1, cpu="Ryzen 5"), only=MACHINE_FIELDS)
        loaded = await store.get(1)
        assert loaded.resolution == "2560x1440"
        assert loaded.ui_scale == "110%"
        assert loaded.cpu == "Ryzen 5"

    async def test_screen_form_keeps_the_machine_values(self, store):
        await store.save(Profile(user_id=1, cpu="Ryzen 5", ram="16 Go"), only=MACHINE_FIELDS)
        await store.save(Profile(user_id=1, resolution="800x600"), only=SCREEN_FIELDS)
        loaded = await store.get(1)
        assert loaded.cpu == "Ryzen 5"
        assert loaded.ram == "16 Go"
        assert loaded.resolution == "800x600"

    async def test_a_full_save_still_overwrites_everything(self, store):
        await store.save(SAMPLE)
        await store.save(Profile(user_id=7, resolution="800x600"))
        loaded = await store.get(7)
        assert loaded.resolution == "800x600"
        assert loaded.cpu == ""

    async def test_an_unknown_column_is_refused_rather_than_ignored(self, store):
        with pytest.raises(ValueError, match="unknown profile columns"):
            await store.save(Profile(user_id=1), only=("nope",))

    async def test_updating_one_form_refreshes_the_timestamp(self, store):
        await store.save(SAMPLE)
        await store.save(Profile(user_id=7, cpu="i5"), only=MACHINE_FIELDS)
        assert (await store.get(7)).updated_at


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

    def test_both_scales_are_distinct_rows(self):
        # Windows scaling and the game's UI scale are independent settings;
        # collapsing them would lose the one that explains the bug.
        table = Profile(user_id=1, scaling="150%", ui_scale="110%").as_markdown_table()
        assert "| Windows scaling | 150% |" in table
        assert "| Game UI scale | 110% |" in table

    def test_screen_info_is_tracked_separately_from_the_machine(self):
        assert Profile(user_id=1, cpu="Ryzen").has_screen_info is False
        assert Profile(user_id=1, resolution="800x600").has_screen_info is True

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
