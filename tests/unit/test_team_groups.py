"""004: choose-one groups (starter choice, fossil Trainer ID parity) and breeding sources.

Game facts used below (decomp, path:line):
- The starter is one of three: res/field/scripts/scripts_route_201.s (StartChooseStarterScene,
  GivePokemon VAR_0x8000); src/choose_starter/choose_starter_app.c.
- Skull Fossil weights odd 25 / even 0, Armor Fossil odd 0 / even 25, before the National Dex
  (src/underground/mining.c sMiningObjects; chosen in Mining_GetWeightOfItem).
- Day-Care compatibility: src/overlay005/daycare.c BoxMon_GetPairDaycareCompatibilityScore.
"""

import pytest

from platsim.legality import movesources as MS
from platsim.optimizer import candidates as C
from platsim.optimizer.api import InvalidRequest

OTHERS = ["SPECIES_GARCHOMP", "SPECIES_GYARADOS", "SPECIES_LUCARIO", "SPECIES_STARAPTOR"]


# --- US1: starters ------------------------------------------------------------------------------

def test_mixed_starters_conflict(ledger):
    got = MS.team_group_conflicts(["SPECIES_TORTERRA", "SPECIES_INFERNAPE"], ledger)
    assert set(got) == {"SPECIES_TORTERRA", "SPECIES_INFERNAPE"}
    assert "only one starter" in got["SPECIES_TORTERRA"] and "2 lines" in got["SPECIES_TORTERRA"]
    three = MS.team_group_conflicts(["SPECIES_TORTERRA", "SPECIES_INFERNAPE", "SPECIES_EMPOLEON"], ledger)
    assert set(three) == {"SPECIES_TORTERRA", "SPECIES_INFERNAPE", "SPECIES_EMPOLEON"}


def test_one_starter_line_is_fine(ledger):
    assert MS.team_group_conflicts(["SPECIES_INFERNAPE", "SPECIES_MONFERNO"], ledger) == {}
    assert MS.team_group_conflicts(["SPECIES_INFERNAPE"] * 3, ledger) == {}
    assert MS.team_group_conflicts(["SPECIES_EMPOLEON"], ledger) == {}


def test_bred_starter_carries_the_starter_choice(ledger):
    """B1: the Day-Care option of a starter line is in the starter group with that line's choice."""
    bred = next(o for o in MS.source_options("SPECIES_INFERNAPE", ledger) if o.kind == MS.BREED)
    assert (bred.exclusive_group, bred.group_choice) == (MS.STARTER_GROUP, "SPECIES_CHIMCHAR")
    gift = next(o for o in MS.source_options("SPECIES_INFERNAPE", ledger) if o.kind == "gift")
    assert (gift.exclusive_group, gift.group_choice) == (MS.STARTER_GROUP, "SPECIES_CHIMCHAR")
    # positive control: an ordinary bred line stays ungrouped
    gible = next(o for o in MS.source_options("SPECIES_GARCHOMP", ledger) if o.kind == MS.BREED)
    assert gible.exclusive_group is None


def test_optimizer_refuses_mixed_starters(ledger):
    with pytest.raises(InvalidRequest) as e:
        C.resolve_species(["torterra", "infernape", *OTHERS], ledger)
    assert set(e.value.reasons) == {"torterra", "infernape"}
    assert "only one starter" in str(e.value)
    ok = C.resolve_species(["infernape", "monferno", *OTHERS], ledger)
    assert ok[:2] == ["SPECIES_INFERNAPE", "SPECIES_MONFERNO"] and len(ok) == 6


# --- US4: fossils -------------------------------------------------------------------------------

def test_fossil_revivals_split_by_trainer_id(ledger):
    want = {"SPECIES_CRANIDOS": "odd", "SPECIES_SHIELDON": "even"}
    for sp, parity in want.items():
        rev = [c.entry for c in ledger.pre(subject=sp) if c.entry.kind == "gift"]
        assert rev and all((e.exclusive_group, e.group_choice) == (MS.TID_GROUP, parity) for e in rev), rev
        assert all(any("src/underground/mining.c:" in s for s in e.src) for e in rev)
    # positive control: of the 85 mining rows, only Armor and Skull Fossil are dug for one parity
    # only before the National Dex; every other pre-National-Dex mining item has both parities.
    from platsim.availability.sources import fossil_parity, underground_entries

    one_sided = {e.subject for e in underground_entries() if "National Dex" not in e.detail
                 and fossil_parity(e.subject) is not None}
    assert one_sided == {"ITEM_SKULL_FOSSIL", "ITEM_ARMOR_FOSSIL"}


def test_fossil_line_conflicts(ledger):
    got = MS.team_group_conflicts(["SPECIES_RAMPARDOS", "SPECIES_BASTIODON"], ledger)
    assert set(got) == {"SPECIES_RAMPARDOS", "SPECIES_BASTIODON"} and "Trainer ID" in got["SPECIES_RAMPARDOS"]
    assert MS.team_group_conflicts(["SPECIES_RAMPARDOS", "SPECIES_CRANIDOS"], ledger) == {}
    # one starter line plus one fossil line is fine
    assert MS.team_group_conflicts(["SPECIES_INFERNAPE", "SPECIES_BASTIODON"], ledger) == {}


def test_fossil_revival_is_limited_by_the_fossil(ledger):
    """FR-012: a revival uses up one fossil; fossils are dug again and again before the Champion."""
    assert ledger.item_copies("ITEM_SKULL_FOSSIL") == MS.UNLIMITED
    rev = next(o for o in MS.source_options("SPECIES_RAMPARDOS", ledger) if o.kind == "gift")
    assert rev.quantity == MS.UNLIMITED and dict(rev.consumes).get("ITEM_SKULL_FOSSIL") == 1


def test_options_and_groups(ledger):
    """T020a: spec Edge Cases and US4 scenario 4."""
    from platsim.legality.models import LegalityOptions

    post = ledger.with_options(LegalityOptions(allow_post_game_pokemon=True))
    starters = ["SPECIES_TURTWIG", "SPECIES_GROTLE", "SPECIES_TORTERRA", "SPECIES_CHIMCHAR", "SPECIES_MONFERNO",
                "SPECIES_INFERNAPE", "SPECIES_PIPLUP", "SPECIES_PRINPLUP", "SPECIES_EMPOLEON"]
    free = [sp for sp in starters for c in post.pre(subject=sp)
            if c.entry.kind in MS.ACQUIRE_KINDS and not c.entry.exclusive_group]
    clash = MS.team_group_conflicts(["SPECIES_TORTERRA", "SPECIES_INFERNAPE"], post)
    # a post-game source outside the group frees that line (B1); with either line free, no conflict
    lines_free = {sp for sp in free if sp in starters[:6]}
    if lines_free:
        assert clash == {}, (free, clash)
    else:  # observed 2026-10-13: no post-game starter source exists, so the rule still holds
        assert set(clash) == {"SPECIES_TORTERRA", "SPECIES_INFERNAPE"}, free
    # B1 positive control: one ungrouped entry anywhere in the mother line frees the eggs
    assert MS._line_group(["SPECIES_INFERNAPE"], ledger) == (MS.STARTER_GROUP, "SPECIES_CHIMCHAR")
    assert MS._line_group(["SPECIES_INFERNAPE", "SPECIES_GARCHOMP"], ledger) == (None, None)
    # fossils: the National Dex weights keep the parity split, so post-game changes nothing
    assert set(MS.team_group_conflicts(["SPECIES_RAMPARDOS", "SPECIES_BASTIODON"], post)) == {
        "SPECIES_RAMPARDOS", "SPECIES_BASTIODON"}
    # allow_unobtainable_pokemon: starters have in-game entries, so no synthetic source is added;
    # since 005 the option lifts the groups instead (a second Platinum game; see
    # test_second_game_option_lifts_groups), so the mixed team no longer conflicts.
    unob = ledger.with_options(LegalityOptions(allow_unobtainable_pokemon=True))
    assert not [o for o in MS.source_options("SPECIES_TORTERRA", unob) if o.kind == MS.OUTSIDE]
    assert MS.team_group_conflicts(["SPECIES_TORTERRA", "SPECIES_INFERNAPE"], unob) == {}


# --- US2: breeding partner ----------------------------------------------------------------------

def _fresh(ledger):
    """Context: clear the ledger's derived caches (breed_mothers, source_options) and restore them
    afterwards, so a monkeypatched rule is actually recomputed."""
    import contextlib

    @contextlib.contextmanager
    def cm():
        saved = dict(ledger.derived)
        ledger.derived.clear()
        try:
            yield
        finally:
            ledger.derived.clear()
            ledger.derived.update(saved)
    return cm()


def test_every_breed_source_has_a_partner(ledger):
    assert not ledger.species_sources("SPECIES_DITTO"), "Ditto is not obtainable before the Champion"
    bm = MS.breed_mothers(ledger)
    assert len(bm) == 86, len(bm)
    missing = [egg for egg, (mothers, ditto) in bm.items() if not (ditto or MS.compatible_father(mothers, ledger))]
    assert missing == []


def test_no_partner_no_breed_source(ledger, monkeypatch):
    """Positive control: with no compatible father for the Gible line, its breed option disappears."""
    real = MS.compatible_father
    gible_line = {"SPECIES_GIBLE", "SPECIES_GABITE", "SPECIES_GARCHOMP"}
    monkeypatch.setattr(MS, "compatible_father",
                        lambda mothers, led: None if set(mothers) <= gible_line else real(mothers, led))
    with _fresh(ledger):
        assert "SPECIES_GIBLE" not in MS.breed_mothers(ledger)
        assert not [o for o in MS.source_options("SPECIES_GARCHOMP", ledger) if o.kind == MS.BREED]
        assert "SPECIES_CHIMCHAR" in MS.breed_mothers(ledger)  # other lines unaffected


# --- US3: one-time parents ----------------------------------------------------------------------

def test_one_time_parents_still_breed(ledger):
    """Breeding from one female does not use her up (research R3), so these stay breedable."""
    for sp in ("SPECIES_LUCARIO", "SPECIES_VAPOREON"):
        bred = [o for o in MS.source_options(sp, ledger) if o.kind == MS.BREED]
        assert bred and bred[0].exclusive_group is None and "one-time parent" in bred[0].detail, sp
    # Riley's Lucario plus a bred Lucario: fine at team level
    assert MS.team_group_conflicts(["SPECIES_LUCARIO", "SPECIES_LUCARIO"], ledger) == {}


def test_female_rule_follows_the_game_formula():
    """pokemon.c SpeciesData_GetGenderOf: female iff ratio > (personality & 0xFF).
    Chatot is 50% female (threshold 127, generated/gender_ratios.txt); the Eterna NPC trade's
    personality 2151 has low byte 103, so that Chatot is female; low byte 200 would be male."""
    assert MS._gender_ratio_value("GENDER_RATIO_FEMALE_50") == 127
    assert MS._female_with("SPECIES_CHATOT", 2151) is True
    assert MS._female_with("SPECIES_CHATOT", 200) is False
    assert MS._female_with("SPECIES_CHATOT", None) is True  # random personality
    assert MS._female_with("SPECIES_GALLADE", None) is False  # male-only
    assert MS._female_with("SPECIES_BRONZONG", None) is False  # genderless


def test_fixed_male_parent_cannot_breed(ledger, monkeypatch):
    """Positive control for B3: if Riley's egg could only hatch male, the Riolu line has no mother."""
    real = MS._female_with
    line = {"SPECIES_RIOLU", "SPECIES_LUCARIO"}
    monkeypatch.setattr(MS, "_female_with", lambda c, p: False if c in line else real(c, p))
    with _fresh(ledger):
        assert "SPECIES_RIOLU" not in MS.breed_mothers(ledger)
        assert not [o for o in MS.source_options("SPECIES_LUCARIO", ledger) if o.kind == MS.BREED]
    assert "SPECIES_RIOLU" in MS.breed_mothers(ledger)  # restored


# --- SC-002 / SC-003 ------------------------------------------------------------------------------

def _count_teams(led, groups: bool | None = None) -> int:
    """Species-only teams of six distinct species that some source assignment can build: per-option
    quantity, limited item copies (evolution items, fossils) and, if `groups`, one choice per
    choose-one group. Species with a free option (unlimited, ungrouped, no limited item) never bind,
    so only subsets of the others are enumerated; the rest are counted with C(free, 6-k).
    `groups=None` asks the engine (MS.groups_enforced: lifted by allow_unobtainable_pokemon, 005)."""
    if groups is None:
        groups = MS.groups_enforced(led)
    from collections import Counter
    from math import comb

    allowed = [c for c in MS.by_constant() if MS.source_options(c, led)]
    copies: dict[str, object] = {}

    def lim(o):
        out = []
        for it, n in o.consumes:
            if it not in copies:
                copies[it] = led.item_copies(it)
            if copies[it] != MS.UNLIMITED:
                out.append((it, n))
        return out

    def free(o):
        return o.quantity == MS.UNLIMITED and not (groups and o.exclusive_group) and not lim(o)

    special = [c for c in allowed if not any(free(o) for o in MS.source_options(c, led))]
    n_free = len(allowed) - len(special)

    def feasible(team):
        src, held, items = Counter(), {}, Counter()

        def go(i):
            if i == len(team):
                return True
            for o in MS.source_options(team[i], led):
                if o.quantity != MS.UNLIMITED and src[o.id] >= int(o.quantity):
                    continue
                g = o.exclusive_group if groups else None
                if g and held.get(g, o.group_choice) != o.group_choice:
                    continue
                li = lim(o)
                if any(items[it] + n > copies[it] for it, n in li):
                    continue
                fresh = g and g not in held
                src[o.id] += 1
                if g:
                    held[g] = o.group_choice
                for it, n in li:
                    items[it] += n
                if go(i + 1):
                    return True
                src[o.id] -= 1
                if fresh:
                    del held[g]
                for it, n in li:
                    items[it] -= n
            return False
        return go(0)

    by_k = Counter()

    def dfs(start, team):
        by_k[len(team)] += 1
        if len(team) < 6:
            for j in range(start, len(special)):
                if feasible(team + [special[j]]):
                    dfs(j + 1, team + [special[j]])
    dfs(0, [])
    return sum(n * comb(n_free, 6 - k) for k, n in by_k.items())


def test_species_team_count(ledger):
    """SC-002: 55,192,424,630 = sum over i starter-line and j fossil-line members of
    w_s(i) w_f(j) C(175, 6-i-j) (one starter line of 3, one fossil line of 2, 175 others).
    Positive control: without the group rule every 6-subset of the 188 is buildable, C(188, 6)."""
    from math import comb

    assert _count_teams(ledger) == 55_192_424_630
    assert _count_teams(ledger, groups=False) == comb(188, 6) == 56_574_476_596


def _final_forms(allowed_keys: set[str]) -> set[str]:
    """Allowed species with no allowed evolution target (data/generated/species.json)."""
    import json

    from platsim.pins import REPO_ROOT

    sp = json.loads((REPO_ROOT / "data" / "generated" / "species.json").read_text())["species"]
    key_of = {f"SPECIES_{k.upper()}": k for k in sp}
    return {k for k in allowed_keys
            if not any(key_of.get(e["target"]) in allowed_keys for e in sp[k].get("evolutions") or [])}


def test_allowed_final_forms(catalog):
    """SC-003: 004 changes no species' availability: the 188 allowed species and the 98 final forms
    listed in allowed_pokemon.md (generated 2026-10-13, before 004) are unchanged."""
    import re

    from platsim.pins import REPO_ROOT

    allowed = {s.key for s in catalog.species if catalog.status(s).available}
    assert len(allowed) == 188
    text = (REPO_ROOT / "allowed_pokemon.md").read_text().split("## Flat list of final forms", 1)[1]
    listed = set(re.findall(r"^- (.+?) \(", text, re.M))
    finals = {catalog.get(k).name for k in _final_forms(allowed)}
    assert len(listed) == 98 and finals == listed, (finals ^ listed)
    # positive control: dropping Garchomp makes Gabite a final form
    assert "Gabite" in {catalog.get(k).name for k in _final_forms(allowed - {"garchomp"})}


# --- 005: the second-game option lifts the groups -----------------------------------------------

def _second_game(ledger):
    from platsim.legality.models import LegalityOptions

    return ledger.with_options(LegalityOptions(allow_unobtainable_pokemon=True))


def test_second_game_option_lifts_groups(ledger):
    on = _second_game(ledger)
    assert MS.groups_enforced(ledger) is True and MS.groups_enforced(on) is False
    assert MS.team_group_conflicts(["SPECIES_TORTERRA", "SPECIES_INFERNAPE"], on) == {}
    assert MS.team_group_conflicts(["SPECIES_RAMPARDOS", "SPECIES_BASTIODON"], on) == {}
    assert set(MS.team_group_conflicts(["SPECIES_TORTERRA", "SPECIES_INFERNAPE"], ledger)) == {
        "SPECIES_TORTERRA", "SPECIES_INFERNAPE"}  # option off: as in 004
    got = C.resolve_species(["torterra", "infernape", *OTHERS], on)
    assert got[:2] == ["SPECIES_TORTERRA", "SPECIES_INFERNAPE"] and len(got) == 6


def test_second_game_members_by_team_order():
    from types import SimpleNamespace as O

    t = O(exclusive_group=MS.STARTER_GROUP, group_choice="SPECIES_TURTWIG")
    c = O(exclusive_group=MS.STARTER_GROUP, group_choice="SPECIES_CHIMCHAR")
    f_odd = O(exclusive_group=MS.TID_GROUP, group_choice="odd")
    f_even = O(exclusive_group=MS.TID_GROUP, group_choice="even")
    free = O(exclusive_group=None, group_choice=None)
    assert MS.second_game_members([t, c, free]) == [1]
    assert MS.second_game_members([c, t, free]) == [1]
    assert MS.second_game_members([c, c, free]) == []
    assert MS.second_game_members([t, c, c, f_odd, f_even, None]) == [1, 2, 4]


def test_species_team_count_second_game(ledger):
    """005 SC-002: with "Pokémon unobtainable in one Platinum game" the engine builds every 6-subset of
    its 310 species: C(310, 6). Positive control: the 004 groups forced on give 1,163,212,171,902,
    so starter / fossil mixing adds 10,868,759,583 teams."""
    from math import comb

    on = _second_game(ledger)
    assert sum(1 for c in MS.by_constant() if MS.source_options(c, on)) == 310
    assert _count_teams(on) == comb(310, 6) == 1_174_080_931_485
    assert _count_teams(on, groups=True) == 1_163_212_171_902
