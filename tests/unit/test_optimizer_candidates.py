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
        C.resolve_species(["garchmop", "gengar", "munchlax", "luxray", "gyarados", "gardevoir"], led)
    r = e.value.reasons
    assert "Garchomp" in r["garchmop"]
    assert "trade evolution" in r["gengar"]
    assert "excluded" in r["munchlax"]
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
