"""The blueprint is data, so these tests are the cheapest guard rail we have:
they catch a broken server layout before a single API call is made.
"""

import pytest

from src import blueprint as bp
from src.setup_guild import normalise


def test_channel_keys_are_unique():
    keys = [ch.key for _, ch in bp.all_channel_specs() if ch.key]
    assert len(keys) == len(set(keys)), "two channels share a key"


def test_channel_names_are_unique_after_discord_normalisation():
    # Discord lowercases and hyphenates, so "Chat FR" and "chat-fr" collide.
    names = [normalise(ch.name) for _, ch in bp.all_channel_specs()]
    assert len(names) == len(set(names))


def test_category_names_are_unique():
    names = [c.name for c in bp.CATEGORIES]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("product", bp.PRODUCTS, ids=lambda p: p.slug)
def test_product_channel_keys_exist(product):
    declared = bp.channel_keys()
    for attr in (
        "help_channel_key",
        "bug_channel_key",
        "idea_channel_key",
        "release_channel_key",
    ):
        assert getattr(product, attr) in declared, attr


@pytest.mark.parametrize("product", bp.PRODUCTS, ids=lambda p: p.slug)
def test_bug_and_idea_channels_are_forums(product):
    by_key = {ch.key: ch for _, ch in bp.all_channel_specs() if ch.key}
    assert by_key[product.bug_channel_key].kind is bp.ChannelKind.FORUM
    assert by_key[product.idea_channel_key].kind is bp.ChannelKind.FORUM


@pytest.mark.parametrize("product", bp.PRODUCTS, ids=lambda p: p.slug)
def test_product_repo_looks_like_owner_slash_name(product):
    owner, _, name = product.repo.partition("/")
    assert owner and name and "/" not in name


def test_release_channels_are_read_only():
    by_key = {ch.key: ch for _, ch in bp.all_channel_specs() if ch.key}
    for product in bp.PRODUCTS:
        assert by_key[product.release_channel_key].access is bp.Access.READ_ONLY


def test_staff_category_is_staff_only():
    staff = next(c for c in bp.CATEGORIES if "Staff" in c.name)
    assert staff.access is bp.Access.STAFF_ONLY


def test_forum_tags_start_with_the_new_state():
    # views.py always applies tag index 0 to a fresh report.
    assert bp.BUG_TAGS[0].startswith("Nouveau")
    assert bp.IDEA_TAGS[0].startswith("Nouveau")


def test_forum_tag_names_fit_discord_limit():
    for tag in bp.BUG_TAGS + bp.IDEA_TAGS:
        assert len(tag) <= 20, f"{tag!r} exceeds the 20-char forum tag limit"


def test_product_lookup():
    assert bp.product("butin").label == "Butin"
    with pytest.raises(KeyError):
        bp.product("nope")


def test_requires_community_is_true_because_forums_exist():
    assert bp.requires_community() is True


def test_staff_role_is_the_only_administrator():
    admins = [r.name for r in bp.ROLES if "administrator" in r.permissions]
    assert admins == [bp.ROLE_DEV]


def test_muted_role_has_no_permissions():
    muted = next(r for r in bp.ROLES if r.name == bp.ROLE_MUTED)
    assert muted.permissions == ()


class TestSetupReport:
    def test_empty_report_reads_as_unchanged(self):
        report = bp.SetupReport()
        assert report.changed is False
        assert "déjà conforme" in report.summary()

    def test_skipped_alone_is_not_a_change(self):
        report = bp.SetupReport(skipped=["salon chat-fr"])
        assert report.changed is False

    def test_summary_lists_what_happened(self):
        report = bp.SetupReport(created_roles=["Staff"], created_channels=["chat-fr"])
        summary = report.summary()
        assert report.changed is True
        assert "Staff" in summary and "chat-fr" in summary
