"""007 T062: variable-power attacks scored by their decomp power (spec FR-012, US4, research R3)."""

import pytest

from platsim.optimizer import candidates as C
from platsim.optimizer import move_classes as MC

FOE = {s: i for i, (s, _, _) in enumerate(C.league_opponents())}


def test_return_friendship_255():
    assert C.variable_power("SPECIES_GARCHOMP", "MOVE_RETURN", 0) == ("TYPE_NORMAL", 102)


def test_hidden_power_from_ivs():
    assert C.hidden_power({k: 15 for k in ("hp", "atk", "def", "spa", "spd", "spe")}) == ("TYPE_DARK", 70)
    # all IVs 31: every low bit and second bit set -> type index 15 * 63 / 63 + 1 = 16 -> past MYSTERY = Dark, 70
    assert C.hidden_power({k: 31 for k in ("hp", "atk", "def", "spa", "spd", "spe")}) == ("TYPE_DARK", 70)
    # all IVs 0 -> Fighting, 30 (type index 1)
    assert C.hidden_power({k: 0 for k in ("hp", "atk", "def", "spa", "spd", "spe")}) == ("TYPE_FIGHTING", 30)


def test_weight_based_power():
    assert C.weight_hg("SPECIES_GARCHOMP") == 950
    assert C.variable_power("SPECIES_INFERNAPE", "MOVE_LOW_KICK", FOE["SPECIES_HIPPOWDON"])[1] == 120
    assert C.variable_power("SPECIES_INFERNAPE", "MOVE_LOW_KICK", FOE["SPECIES_ROSERADE"])[1] == 40


def test_gyro_ball_capped_and_magnitude_expected():
    p = C.variable_power("SPECIES_BRONZONG", "MOVE_GYRO_BALL", FOE["SPECIES_GARCHOMP"], level=55)[1]
    assert 1 <= p <= 150
    assert C.variable_power("SPECIES_GRAVELER", "MOVE_MAGNITUDE", 0) == ("TYPE_GROUND", 71.0)


def test_npc_trade_variant_uses_its_fixed_ivs(ledger):
    # Snowpoint's NPC-trade Haunter has fixed IVs (res/npc_trades data via the ledger's fixed_mon)
    v = next(x for x in C.variants("SPECIES_HAUNTER", ledger) if x.key != "own")
    ivs = C._variant_ivs(v, ledger)
    assert ivs == {"hp": 20, "atk": 25, "def": 15, "spa": 15, "spd": 15, "spe": 25}
    assert C.hidden_power(ivs) != C.hidden_power({k: 15 for k in ivs})  # its own Hidden Power
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
