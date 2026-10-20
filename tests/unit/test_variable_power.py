"""010 (from 007 T062): variable-power attacks scored by their decomp power; Hidden Power never offered
(010 FR-001, FR-002; user 2026-10-19)."""

import pytest

from platsim.optimizer import candidates as C
from platsim.optimizer import move_classes as MC

FOE = {s: i for i, (s, _, _) in enumerate(C.league_opponents())}


def test_return_friendship_255():
    assert C.variable_power("SPECIES_GARCHOMP", "MOVE_RETURN", 0) == ("TYPE_NORMAL", 102)


def test_hidden_power_formula_kept_but_never_offered(ledger):
    # the formula stays correct (the battle engine still computes Hidden Power for League foes) ...
    assert C.hidden_power({k: 15 for k in ("hp", "atk", "def", "spa", "spd", "spe")}) == ("TYPE_DARK", 70)
    assert C.hidden_power({k: 0 for k in ("hp", "atk", "def", "spa", "spd", "spe")}) == ("TYPE_FIGHTING", 30)
    # ... but no member is offered it: uniform IVs of 15 make its type and power an artifact (user 2026-10-19)
    from platsim.decomp.moves import load_moves
    assert not C.is_attack(load_moves()["MOVE_HIDDEN_POWER"])
    assert "BATTLE_EFFECT_RANDOM_POWER_BASED_ON_IVS" in C.NOT_OFFERED_VARIABLE
    for sp in ("SPECIES_SNORLAX", "SPECIES_HAUNTER"):  # Haunter: also its NPC-trade variant with fixed IVs
        for v in C.variants(sp, ledger):
            assert "MOVE_HIDDEN_POWER" not in C.member_candidates(sp, v, 60, ledger).pool
    # positive control: both learn it at 60 (TM10), so the exclusion is what keeps it out
    assert any("MOVE_HIDDEN_POWER" in C.legal_moves(v, 60, ledger) for v in C.variants("SPECIES_HAUNTER", ledger))


def test_weight_based_power():
    assert C.weight_hg("SPECIES_GARCHOMP") == 950
    assert C.variable_power("SPECIES_INFERNAPE", "MOVE_LOW_KICK", FOE["SPECIES_HIPPOWDON"])[1] == 120
    assert C.variable_power("SPECIES_INFERNAPE", "MOVE_LOW_KICK", FOE["SPECIES_ROSERADE"])[1] == 40


def test_gyro_ball_capped_and_magnitude_expected():
    p = C.variable_power("SPECIES_BRONZONG", "MOVE_GYRO_BALL", FOE["SPECIES_GARCHOMP"], level=55)[1]
    assert 1 <= p <= 150
    assert C.variable_power("SPECIES_GRAVELER", "MOVE_MAGNITUDE", 0) == ("TYPE_GROUND", 71.0)


def test_npc_trade_variant_uses_its_fixed_ivs(ledger):
    # Snowpoint's NPC-trade Haunter has fixed IVs; they set its stats (Gyro Ball's speed ratio uses them)
    v = next(x for x in C.variants("SPECIES_HAUNTER", ledger) if x.key != "own")
    ivs = C._variant_ivs(v, ledger)
    assert ivs == {"hp": 20, "atk": 25, "def": 15, "spa": 15, "spd": 15, "spe": 25}
    own = next(x for x in C.variants("SPECIES_HAUNTER", ledger) if x.key == "own")
    assert C._variant_ivs(own, ledger) == {k: 15 for k in ivs}


@pytest.mark.parametrize("move", ["MOVE_FRUSTRATION", "MOVE_SEISMIC_TOSS", "MOVE_FLAIL", "MOVE_NATURAL_GIFT", "MOVE_FLING"])
def test_excluded_variable_and_fixed(move, ledger):
    assert MC.move_class(move).category in ("conditional_attack", "fixed_damage")
    v = C.variants("SPECIES_SNORLAX", ledger)[0]
    mc = C.member_candidates("SPECIES_SNORLAX", v, 60, ledger)
    assert move not in mc.pool


def test_return_enters_the_pool(ledger):
    v = C.variants("SPECIES_SNORLAX", ledger)[0]
    mc = C.member_candidates("SPECIES_SNORLAX", v, 60, ledger)
    assert "MOVE_RETURN" in mc.pool and mc.scores["MOVE_RETURN"] > 0


@pytest.mark.parametrize("species,move", [("SPECIES_GRAVELER", "MOVE_MAGNITUDE"), ("SPECIES_TENTACRUEL", "MOVE_WRING_OUT"),
                                          ("SPECIES_INFERNAPE", "MOVE_PUNISHMENT")])
def test_unmodelled_variable_power_not_offered(species, move, ledger):
    """010 FR-011: the battle player does not compute these powers, so they are never offered."""
    vs = C.variants(species, ledger)
    assert any(move in C.legal_moves(v, 60, ledger) for v in vs)  # positive control: it is learnable
    for v in vs:
        assert move not in C.member_candidates(species, v, 60, ledger).pool


def test_unmodelled_effects_are_not_attacks():
    from platsim.decomp.moves import load_moves
    mv = load_moves()
    for m in ("MOVE_MAGNITUDE", "MOVE_WRING_OUT", "MOVE_CRUSH_GRIP", "MOVE_PUNISHMENT", "MOVE_HIDDEN_POWER"):
        assert not C.is_attack(mv[m]), m
    for m in ("MOVE_RETURN", "MOVE_GRASS_KNOT", "MOVE_LOW_KICK", "MOVE_GYRO_BALL"):  # the four offered
        assert C.is_attack(mv[m]), m


def test_gyro_ball_enters_bronzongs_pool(ledger):
    v = C.variants("SPECIES_BRONZONG", ledger)[0]
    assert "MOVE_GYRO_BALL" in C.member_candidates("SPECIES_BRONZONG", v, 55, ledger).pool


def test_pool_is_additive(ledger):
    """010 FR-010: with variable power switched off, the fixed-power pool is what remains."""
    v = C.variants("SPECIES_INFERNAPE", ledger)[0]
    with_vp = C.member_candidates("SPECIES_INFERNAPE", v, 55, ledger).pool
    from platsim.decomp.moves import load_moves
    saved = dict(C.NOT_OFFERED_VARIABLE)
    try:
        C.NOT_OFFERED_VARIABLE.update({m.effect: "off" for m in load_moves().values()
                                       if MC.move_class(m.const).category == MC.VARIABLE_ATTACK})
        without = C.member_candidates("SPECIES_INFERNAPE", v, 55, ledger).pool
    finally:
        C.NOT_OFFERED_VARIABLE.clear(); C.NOT_OFFERED_VARIABLE.update(saved)
    assert set(without) <= set(with_vp) and "MOVE_GRASS_KNOT" in set(with_vp) - set(without)
    assert len(without) == C.POOL
