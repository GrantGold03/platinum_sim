"""T061/T062: optimizer candidate generation and team-wide resource assignment (no workers).

Game facts used (copied from the decomp, path:line):
- Type chart: Electric -> Water super effective (pokeplatinum/src/battle/battle_lib.c:2416), Electric ->
  Ground immune (:2419), Electric -> Flying super effective (:2420); TYPE_MULTI_* values in
  include/constants/battle.h:144-146.
- sTypeBoostingItems includes { HOLD_EFFECT_ARCEUS_DRAGON, TYPE_DRAGON } (battle_lib.c:6545).
- TM26 has one item ball before the Champion: res/field/events/events_wayward_cave_1f.json:54
  (the ledger's count is asserted, not typed: copies are read from the ledger).
- Haunter -> Gengar EVO_TRADE: res/pokemon/haunter/data.json:110-111.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from platsim.legality import movesources as MS
from platsim.optimizer import candidates as C
from platsim.optimizer import resources as R
from platsim.optimizer.api import InvalidRequest


@pytest.fixture(scope="module")
def led():
    from platsim.availability.ledger import build_ledger

    return build_ledger()


def test_type_chart_positive_controls():
    assert C.type_mult("TYPE_ELECTRIC", ("TYPE_WATER", "TYPE_FLYING")) == 4.0
    assert C.type_mult("TYPE_ELECTRIC", ("TYPE_GROUND", "TYPE_GROUND")) == 0.0
    assert C.type_mult("TYPE_ELECTRIC", ("TYPE_ELECTRIC",)) == 0.5
    assert "HOLD_EFFECT_ARCEUS_DRAGON" in C.type_boost_items()["TYPE_DRAGON"]
    assert C.expectimax_self_boosts()["ATK_UP_2"] == {"atk": 2}  # parsed from sim/policy/expectimax2.mjs


def test_dominance_rule_r8():
    mk = lambda **k: SimpleNamespace(**{"type": "TYPE_FIRE", "category": "CLASS_SPECIAL", "accuracy": 100,  # noqa: E731
                                        "priority": 0, "power": 90, "effect": C.PLAIN, "effect_chance": 0, **k})
    strong, weak = mk(power=95), mk(power=40)
    assert C.dominates(strong, weak) and not C.dominates(weak, strong)
    assert not C.dominates(strong, mk(power=40, effect="BATTLE_EFFECT_BURN_HIT", effect_chance=10))  # side effect kept
    assert not C.dominates(mk(power=120, accuracy=85), weak)  # different accuracy class
    assert not C.dominates(mk(power=150, effect="BATTLE_EFFECT_RECHARGE_AFTER"), weak)  # drawback


def test_resolve_species_errors(led):
    assert C.resolve_species(["Garchomp", "garchomp", "SPECIES_LUXRAY", "luxray", "gyarados", "Gardevoir"], led)[0] == \
        "SPECIES_GARCHOMP"
    with pytest.raises(InvalidRequest) as e:
        C.resolve_species(["garchmop", "gengar", "bulbasaur", "luxray", "gyarados", "gardevoir"], led)
    r = e.value.reasons
    assert "Garchomp" in r["garchmop"]
    assert "trade evolution" in r["gengar"]
    assert "bulbasaur" in r  # no source in Platinum (003: Munchlax is no longer excluded)
    assert list(C.resolve_species(["munchlax", "snorlax", "luxray", "gyarados", "gardevoir", "garchomp"], led))[:2] == \
        ["SPECIES_MUNCHLAX", "SPECIES_SNORLAX"]
    with pytest.raises(InvalidRequest):
        C.resolve_species(["garchomp"], led)


def test_single_copy_tm_is_never_given_twice(led):
    assert led.tm_copies("TM26") == 1
    # Positive control: at Lv 55 Garchomp and Gyarados know Earthquake only through a TM (computed, not typed).
    for sp in ("SPECIES_GARCHOMP", "SPECIES_GYARADOS"):
        kinds = {c.source_kind for c in MS.sources(sp, "MOVE_EARTHQUAKE", 55, led)}
        assert kinds == {"tm"}, (sp, kinds)
    a = R.MemberSpec("SPECIES_GARCHOMP", "own", ("MOVE_EARTHQUAKE", "MOVE_DRAGON_CLAW"), "sitrus_berry")
    b = R.MemberSpec("SPECIES_GYARADOS", "own", ("MOVE_EARTHQUAKE", "MOVE_AQUA_TAIL"), "sitrus_berry")
    one = R.realize((a,), [55], led)
    assert not isinstance(one, R.Refusal) and one.uses == {"TM26": 1}
    both = R.realize((a, b), [55, 55], led)
    assert isinstance(both, R.Refusal) and both.slot == 1
    # repair gives slot 2 its next-best buildable set, which the independent validator accepts
    ranked = [[a.moves], [b.moves, ("MOVE_AQUA_TAIL", "MOVE_ICE_FANG")]]
    specs, notes = R.repair((a, b), [55, 55], led, ranked)
    assert specs[1].moves == ("MOVE_AQUA_TAIL", "MOVE_ICE_FANG") and notes


def test_member_candidates_and_full_team_validate(led):
    from platsim.legality.validator import validate

    consts = C.resolve_species(["infernape", "staraptor", "luxray", "garchomp", "gyarados", "gardevoir"], led)
    cands = [C.member_candidates(c, C.variants(c, led)[0], 55, led) for c in consts]
    for mc in cands:
        assert 1 <= len(mc.movesets) <= C.K_MOVESETS and mc.ranked
        for ms in mc.movesets:
            assert len(ms) <= 4 and all(C.is_attack(C.load_moves()[m]) for m in ms)
        assert set(mc.pruned).isdisjoint(mc.pool)
    specs = tuple(R.MemberSpec(c, "own", mc.movesets[0], mc.items[mc.movesets[0]][0]) for c, mc in zip(consts, cands))
    specs, _ = R.repair(specs, [55] * 6, led, [mc.ranked for mc in cands])
    real = R.realize(specs, [55] * 6, led)
    assert not isinstance(real, R.Refusal)
    assert validate(real.team, led) == []
    floors = [R.member_floor(s, led) for s in specs]
    assert all(f is not None and f <= 55 for f in floors)
    for s, f in zip(specs, floors):  # the floor is the lowest legal level
        assert not isinstance(R.realize((s,), [f], led), R.Refusal)
        if f > 1:
            assert isinstance(R.realize((s,), [f - 1], led), R.Refusal)


# --- Feature 013: no single-use non-berry held item is ever a candidate (FR-003, SC-001, SC-004) ---

def _sash_as_type_boost(monkeypatch):
    """Make every attack type's boost item a HOLD_EFFECT_ENDURE item, so the type-boost branch of
    held_item_candidates proposes Focus Sash (1 pre-Champion copy, Route 221 house)."""
    real = C.type_boost_items()
    monkeypatch.setattr(C, "type_boost_items", lambda: {t: ["HOLD_EFFECT_ENDURE"] for t in real})


def test_single_use_item_never_offered(led, monkeypatch):
    assert led.item_copies("ITEM_FOCUS_SASH") != 0  # the injection can only work if a copy exists
    _sash_as_type_boost(monkeypatch)
    out = C.held_item_candidates("SPECIES_GARCHOMP", ("MOVE_EARTHQUAKE",), led)
    assert "focus_sash" not in out
    assert "sitrus_berry" in out


def test_single_use_guard_control(led, monkeypatch):
    # Control: with the filter switched off the same injection does reach the output, so the test above can fail.
    _sash_as_type_boost(monkeypatch)
    monkeypatch.setattr(C, "is_excluded_single_use", lambda item: False)
    assert "focus_sash" in C.held_item_candidates("SPECIES_GARCHOMP", ("MOVE_EARTHQUAKE",), led)


def test_no_single_use_candidates_sweep(led):
    from platsim.decomp.item_use import is_excluded_single_use

    snorlax_team = ("SPECIES_SNORLAX", "SPECIES_GARCHOMP", "SPECIES_EMPOLEON")
    cases = [
        ("SPECIES_SNORLAX", ("MOVE_BODY_SLAM", "MOVE_EARTHQUAKE"), snorlax_team),
        ("SPECIES_GARCHOMP", ("MOVE_EARTHQUAKE", "MOVE_DRAGON_CLAW"), snorlax_team),
        ("SPECIES_EMPOLEON", ("MOVE_SURF", "MOVE_ICE_BEAM"), ("SPECIES_EMPOLEON", "SPECIES_GARCHOMP")),
        ("SPECIES_GARCHOMP", ("MOVE_EARTHQUAKE",), None),
    ]
    seen = set()
    for const, moves, team in cases:
        out = C.held_item_candidates(const, moves, led, team)
        assert not any(is_excluded_single_use(it) for it in out), (const, out)
        seen.update(out)
    assert "sitrus_berry" in seen and "leftovers" in seen  # berries and non-consumed items are still offered


# --- Feature 014: damage boosters (Expert Belt, Wise Glasses, Muscle Band; chosen by hold effect) ---
# Pre-Champion copies come from the ledger: Expert Belt 1 (scripts_route_221_house.s:39), Wise Glasses 1
# (scripts_celestic_town_northwest_house.s:69), Muscle Band 0 (Battle Frontier only).
BOOSTERS = {"expert_belt", "wise_glasses", "muscle_band"}


def test_damage_booster_group_from_item_data():
    from platsim.decomp.items import load_items

    effects = {"HOLD_EFFECT_POWER_UP_SE", "HOLD_EFFECT_POWER_UP_PHYS", "HOLD_EFFECT_POWER_UP_SPEC"}
    assert {it.key for it in load_items().values() if it.hold_effect in effects} == BOOSTERS


def test_damage_boosters_special(led):
    out = C.held_item_candidates("SPECIES_EMPOLEON", ("MOVE_SURF",), led)
    assert out == ["sitrus_berry", "splash_plate", "expert_belt", "wise_glasses"]


def test_damage_boosters_physical(led):
    out = C.held_item_candidates("SPECIES_GARCHOMP", ("MOVE_EARTHQUAKE",), led)
    assert out == ["sitrus_berry", "earth_plate", "expert_belt"]  # Muscle Band: no pre-Champion copy


def test_damage_boosters_after_existing_items(led):
    out = C.held_item_candidates("SPECIES_SNORLAX", ("MOVE_BODY_SLAM",), led, ("SPECIES_SNORLAX", "SPECIES_GARCHOMP"))
    assert out == ["sitrus_berry", "silk_scarf", "leftovers", "expert_belt"]


def test_no_damage_booster_without_an_attack(led):
    out = C.held_item_candidates("SPECIES_GARCHOMP", ("MOVE_SWORDS_DANCE",), led)
    assert not BOOSTERS & set(out)


def test_muscle_band_offered_when_it_has_a_copy(led, monkeypatch):
    # Positive control for the copy check: give Muscle Band one copy and it is offered for a physical moveset.
    assert led.item_copies("ITEM_MUSCLE_BAND") == 0

    class OneMuscleBand:
        def __getattr__(self, name):
            return getattr(led, name)

        def item_copies(self, const):
            return 1 if const == "ITEM_MUSCLE_BAND" else led.item_copies(const)

    monkeypatch.setattr(C, "_ITEM_COPIES", {})
    stub = OneMuscleBand()
    assert "muscle_band" in C.held_item_candidates("SPECIES_GARCHOMP", ("MOVE_EARTHQUAKE",), stub)
    assert "muscle_band" not in C.held_item_candidates("SPECIES_EMPOLEON", ("MOVE_SURF",), stub)  # special: Wise Glasses


def test_damage_boosters_keep_h2_rule(led):
    from platsim.decomp.item_use import is_excluded_single_use

    for const, moves in (("SPECIES_EMPOLEON", ("MOVE_SURF",)), ("SPECIES_GARCHOMP", ("MOVE_EARTHQUAKE",))):
        assert not any(is_excluded_single_use(it) for it in C.held_item_candidates(const, moves, led))


def test_single_expert_belt_is_never_given_twice(led):
    from dataclasses import replace

    from platsim.legality.models import TeamCandidate
    from platsim.legality.validator import validate

    assert led.item_copies("ITEM_EXPERT_BELT") == 1
    a = R.MemberSpec("SPECIES_GARCHOMP", "own", ("MOVE_EARTHQUAKE", "MOVE_DRAGON_CLAW"), "expert_belt")
    b = R.MemberSpec("SPECIES_EMPOLEON", "own", ("MOVE_SURF",), "expert_belt")
    one = R.realize((a,), [55], led)
    assert not isinstance(one, R.Refusal) and one.uses.get("ITEM_EXPERT_BELT") == 1
    both = R.realize((a, b), [55, 55], led)
    assert isinstance(both, R.Refusal) and both.slot == 1
    # Positive control: the independent validator flags a hand-built team with two holders.
    other = R.realize((replace(b, item="sitrus_berry"),), [55], led)
    assert not isinstance(other, R.Refusal)
    two = TeamCandidate([one.team.builds[0], replace(other.team.builds[0], held_item="expert_belt")])
    assert any(v.code == "ITEM_COPIES" for v in validate(two, led))


def test_damage_booster_sources_in_report(led):
    from platsim.report.sources import team_sources

    for item, place, script in (("wise_glasses", "Celestic Town", "scripts_celestic_town_northwest_house.s"),
                                ("expert_belt", "Route 221", "scripts_route_221_house.s")):
        real = R.realize((R.MemberSpec("SPECIES_EMPOLEON", "own", ("MOVE_SURF",), item),), [55], led)
        assert not isinstance(real, R.Refusal), item
        _, held, refs = team_sources(real.team, led)
        assert held[0] and place.lower() in held[0].lower().replace("_", " "), (item, held[0])
        assert any(script in r for r in refs[0]), (item, refs[0])
