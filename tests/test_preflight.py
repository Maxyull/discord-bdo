"""The permission check that runs before /setup touches anything."""

import pytest

from src import blueprint as bp
from src import setup_guild


class FakePermissions:
    def __init__(self, administrator=False, **granted):
        self.administrator = administrator
        self._granted = granted

    def __getattr__(self, name):
        return self._granted.get(name, False)


class FakeRole:
    def __init__(self, name, position):
        self.name = name
        self.position = position


class FakeMember:
    def __init__(self, permissions, top_position=100):
        self.guild_permissions = permissions
        self.top_role = FakeRole("bot", top_position)


class FakeGuild:
    def __init__(self, me, roles=()):
        self.me = me
        self.roles = list(roles)


ALL_GRANTED = {name: True for name, _ in setup_guild.REQUIRED_PERMISSIONS}


class TestPreflight:
    def test_an_administrator_bot_placed_on_top_is_clear(self):
        guild = FakeGuild(FakeMember(FakePermissions(administrator=True), 100))
        assert setup_guild.preflight(guild) == []

    def test_the_exact_permission_set_is_enough_without_administrator(self):
        guild = FakeGuild(FakeMember(FakePermissions(**ALL_GRANTED), 100))
        assert setup_guild.preflight(guild) == []

    def test_a_missing_permission_is_named_in_french(self):
        granted = dict(ALL_GRANTED)
        granted["manage_channels"] = False
        guild = FakeGuild(FakeMember(FakePermissions(**granted), 100))
        problems = setup_guild.preflight(guild)
        assert len(problems) == 1
        assert "Gérer les salons" in problems[0]

    def test_every_missing_permission_is_listed_not_just_the_first(self):
        guild = FakeGuild(FakeMember(FakePermissions(), 100))
        assert len(setup_guild.preflight(guild)) == len(
            setup_guild.REQUIRED_PERMISSIONS
        )

    def test_a_blueprint_role_above_the_bot_blocks_the_run(self):
        # Discord refuses to let the bot manage a role placed above its own,
        # and the run would die halfway with a bare Forbidden.
        guild = FakeGuild(
            FakeMember(FakePermissions(administrator=True), 5),
            roles=[FakeRole(bp.ROLE_DEV, 9)],
        )
        problems = setup_guild.preflight(guild)
        assert any("trop bas" in p for p in problems)

    def test_a_blueprint_role_below_the_bot_is_fine(self):
        guild = FakeGuild(
            FakeMember(FakePermissions(administrator=True), 9),
            roles=[FakeRole(bp.ROLE_DEV, 5)],
        )
        assert setup_guild.preflight(guild) == []

    def test_an_equal_position_counts_as_blocking(self):
        # Ties are resolved against the bot by Discord.
        guild = FakeGuild(
            FakeMember(FakePermissions(administrator=True), 5),
            roles=[FakeRole(bp.ROLE_MOD, 5)],
        )
        assert setup_guild.preflight(guild) != []

    def test_unrelated_roles_above_the_bot_are_ignored(self):
        # Someone else's role sitting on top is not our problem.
        guild = FakeGuild(
            FakeMember(FakePermissions(administrator=True), 5),
            roles=[FakeRole("Nitro Booster", 20)],
        )
        assert setup_guild.preflight(guild) == []

    def test_no_member_object_yet_does_not_crash(self):
        assert setup_guild.preflight(FakeGuild(None)) == []


class TestRequiredPermissions:
    def test_each_entry_has_a_human_label(self):
        for name, label in setup_guild.REQUIRED_PERMISSIONS:
            assert name and label
            assert label != name

    def test_channel_and_role_management_are_required(self):
        names = {name for name, _ in setup_guild.REQUIRED_PERMISSIONS}
        assert {"manage_channels", "manage_roles"} <= names


class FakeRoleWithId(FakeRole):
    def __init__(self, name, position, rid):
        super().__init__(name, position)
        self.id = rid


class TestEffectiveRoleOrder:
    """Found in production: the bot could manage all five roles, `/tester`
    worked, and the report still said "remontez le rôle du bot". Discord ranks
    equal positions among themselves, so absolute positions are the wrong
    question; the displayed order is the one that counts.
    """

    def build(self, noms_dans_l_ordre_affiche):
        # guild.roles is lowest-first, so the displayed top comes last.
        roles = [
            FakeRoleWithId(nom, 1, index)
            for index, nom in enumerate(reversed(noms_dans_l_ordre_affiche))
        ]
        guild = FakeGuild(FakeMember(FakePermissions(administrator=True), 1))
        guild.roles = roles
        return guild, {r.name: r for r in roles}

    def test_an_already_correct_order_is_recognised(self):
        noms = [spec.name for spec in bp.ROLES]
        guild, par_nom = self.build(noms)
        ordered = [par_nom[n] for n in noms]
        assert setup_guild.effective_order_is_correct(guild, ordered) is True

    def test_a_swapped_pair_is_detected(self):
        noms = [spec.name for spec in bp.ROLES]
        inverse = [noms[1], noms[0]] + noms[2:]
        guild, par_nom = self.build(inverse)
        ordered = [par_nom[n] for n in noms]
        assert setup_guild.effective_order_is_correct(guild, ordered) is False

    def test_unrelated_roles_do_not_disturb_the_comparison(self):
        # A Nitro Booster role sitting between two of ours is not a mistake.
        noms = [spec.name for spec in bp.ROLES]
        avec_intrus = [noms[0], "Nitro Booster"] + noms[1:]
        guild, par_nom = self.build(avec_intrus)
        ordered = [par_nom[n] for n in noms]
        assert setup_guild.effective_order_is_correct(guild, ordered) is True
