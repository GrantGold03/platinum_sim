"""007 T014: required-HM placement respects moves a paired test adopted (spec FR-014, research R6)."""

import pytest

from platsim.legality import movesources as MS
from platsim.optimizer import candidates as C
from platsim.optimizer import resources as R

LV = 57


@pytest.fixture(scope="module")
def milotic(ledger):
    """A Milotic set with two attacks plus Toxic and Recover, all legal at Lv 57 (checked)."""
    v = C.variants("SPECIES_MILOTIC", ledger)[0]
    mc = C.member_candidates("SPECIES_MILOTIC", v, LV, ledger)
    attacks = [m for m in mc.movesets[0] if m != "MOVE_SURF"][:2]
    moves = tuple(attacks) + ("MOVE_TOXIC", "MOVE_RECOVER")
    for m in moves + ("MOVE_SURF",):
        assert any(MS.sources("SPECIES_MILOTIC", m, LV, ledger, o) for o in v.options(ledger)), m
    return R.MemberSpec("SPECIES_MILOTIC", v.key, moves)


def _placed(spec, ledger):
    out, missing = R.place_required_hms((spec,), [LV], ledger, ("surf",))
    assert missing is None
    return out[0].moves


def test_unadopted_status_move_gives_way_first(ledger, milotic):
    moves = _placed(milotic, ledger)
    lost = set(milotic.moves) - set(moves)
    assert "MOVE_SURF" in moves and lost <= {"MOVE_TOXIC", "MOVE_RECOVER"} and len(lost) == 1


def test_adopted_status_move_is_kept(ledger, milotic):
    from dataclasses import replace

    moves = _placed(replace(milotic, adopted=("MOVE_TOXIC",)), ledger)
    assert "MOVE_TOXIC" in moves and "MOVE_RECOVER" not in moves and "MOVE_SURF" in moves


def test_both_adopted_then_weakest_attack_goes(ledger, milotic):
    from dataclasses import replace

    spec = replace(milotic, adopted=("MOVE_TOXIC", "MOVE_RECOVER"))
    moves = _placed(spec, ledger)
    assert {"MOVE_TOXIC", "MOVE_RECOVER", "MOVE_SURF"} <= set(moves)
    attacks = [m for m in milotic.moves if m not in ("MOVE_TOXIC", "MOVE_RECOVER")]
    weakest = min(attacks, key=lambda m: (sum(C.move_value("SPECIES_MILOTIC", m)), milotic.moves.index(m)))
    assert weakest not in moves


def test_adopted_is_not_serialised_when_empty(milotic):
    from dataclasses import replace

    d = R.spec_to_json((milotic,))[0]
    assert "adopted" not in d  # specs without adoptions serialise exactly as before 007
    assert set(d) == {"species", "variant", "moves", "item", "ability", "ability_reason"}
    spec = replace(milotic, adopted=("MOVE_TOXIC",))
    assert R.spec_to_json((spec,))[0]["adopted"] == ["MOVE_TOXIC"]
    assert R.spec_from_json(R.spec_to_json((spec,)))[0] == spec
