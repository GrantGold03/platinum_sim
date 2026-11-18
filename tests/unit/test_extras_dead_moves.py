"""Feature 027: the extra candidate sets under the 026 dead-move rule (spec FR-001 to FR-007)."""

from __future__ import annotations

import importlib.util
import json
import sys

import pytest

from platsim import pins
from platsim.optimizer import candidates as C

SNAPSHOT = pins.REPO_ROOT / "specs" / "027-extras-dead-moves" / "evidence" / "candidates-main.json"
B2 = ["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"]
TIER = lambda m: None  # noqa: E731  (no cost moves in the synthetic tables)


def _helper():
    path = pins.REPO_ROOT / "specs" / "027-extras-dead-moves" / "scripts" / "attribution.py"
    spec = importlib.util.spec_from_file_location("attribution_027", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["attribution_027"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def led():
    from platsim.availability.ledger import build_ledger
    from platsim.legality.models import LegalityOptions

    return build_ledger().with_options(LegalityOptions())


# ---- part 1: choose_sets' new options (T004) -------------------------------------------------------------------------
def _six_live():
    vals = {m: [0.0] * 6 for m in "PQRSTU"}
    for i, m in enumerate("PQRSTU"):
        vals[m][i] = 100.0 - i
    return vals, {m: sum(v) for m, v in vals.items()}


def test_defaults_reproduce_the_base_selection():
    vals, scores = _six_live()
    cands = sorted(vals)
    ranked = C.rank_sets(C.pool_by_marginal(cands, vals, scores, cost_tier=TIER), vals, scores)
    a = C.choose_sets(ranked, 3, cands, vals, scores, cost_tier=TIER)
    b = C.choose_sets(ranked, 3, cands, vals, scores, cost_tier=TIER, exclude=frozenset(), require=None)
    assert a == b


def test_exclude_and_require_with_stats():
    vals, scores = _six_live()
    cands = sorted(vals)
    ranked = C.rank_sets(C.pool_by_marginal(cands, vals, scores, cost_tier=TIER), vals, scores)
    first = C.choose_sets(ranked, 1, cands, vals, scores, cost_tier=TIER)[0][0]
    st = {}
    sets, _, _ = C.choose_sets(ranked, 1, cands, vals, scores, cost_tier=TIER, exclude=frozenset({first}), stats=st)
    assert sets[0] != first and st["excluded"] >= 1
    st = {}
    sets, _, _ = C.choose_sets(ranked, 3, cands, vals, scores, cost_tier=TIER, require=lambda c: "U" in c, stats=st)
    assert sets and all("U" in c for c in sets) and st["required"] >= 1


def test_duplicate_of_a_base_set_is_excluded_and_the_shortfall_counted():
    # five live moves only: every repaired 4-set is one of five; excluding three leaves two
    vals = {m: [0.0] * 5 for m in "PQRST"}
    for i, m in enumerate("PQRST"):
        vals[m][i] = 100.0 - i
    scores = {m: sum(v) for m, v in vals.items()}
    cands = sorted(vals)
    ranked = C.rank_sets(cands, vals, scores)
    base, _, _ = C.choose_sets(ranked, 3, cands, vals, scores, cost_tier=TIER)
    st = {}
    extra, _, _ = C.choose_sets(ranked, 3, cands, vals, scores, cost_tier=TIER, exclude=frozenset(base), stats=st)
    assert not set(extra) & set(base) and len(extra) == 2 and st["excluded"] >= 3


def test_filler_extra_keeps_its_reason():
    # nothing live beyond A and B: an extra keeps dead moves and carries the reason
    vals = {"A": [100.0, 0.0, 10.0], "B": [0.0, 100.0, 9.0], "Cx": [80.0, 80.0, 8.0], "Dx": [70.0, 70.0, 7.0], "Ex": [60.0, 60.0, 6.0]}
    scores = {m: sum(v) for m, v in vals.items()}
    cands = sorted(vals)
    sets, _, why = C.choose_sets(C.rank_sets(cands, vals, scores), 1, cands, vals, scores, cost_tier=TIER,
                                 require=lambda c: "Cx" in c)
    assert sets and C.dead_moves(sets[0], vals) and why


# ---- part 2: the real controls (T008) --------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def b2(led):
    consts = C.resolve_species(B2, led)
    return consts, {c: C.member_candidates(c, C.variants(c, led)[0], 48, led, team=tuple(consts)) for c in consts}


def test_infernape_extras_have_no_fire_punch_and_no_unexplained_dead_move(b2):
    A = _helper()
    consts, mcs = b2
    mc = mcs[consts[1]]
    for e in A.extras_of(mc):
        assert "MOVE_FIRE_PUNCH" not in e["set"], e
        assert not e["dead"] or e["filler_reason"], e


def test_every_offered_extra_is_live_or_explained_on_b2(b2):
    A = _helper()
    consts, mcs = b2
    for c, mc in mcs.items():
        for e in A.extras_of(mc):
            assert not e["dead"] or e["filler_reason"], (c, e)
            if e["kind"] == "variable_power":
                assert any(m in C.OFFERED_VARIABLE and m not in e["dead"] for m in e["set"]), (c, e)
        assert sum(mc.extras_by_kind.values()) == mc.extras
        for kind, d in mc.dropped_extras.items():
            assert d["offered"] < C.K_MOVESETS and d["reason"]


def test_base_sets_items_and_setup_equal_the_pre_feature_snapshot(led):
    A = _helper()
    snap = json.loads(SNAPSHOT.read_text())
    assert len(snap) == 36
    for key, rec in snap.items():
        mc = A.recompute(rec, led)
        defects = [r for r in A.attribute(rec, mc) if r["cause"] == "defect" and r["kind"] != "extra"]
        assert not defects, (key, defects)


def test_member_notes_use_the_sets_own_filler_reason():
    from platsim.optimizer import resources as R
    from platsim.optimizer.run import _member_notes

    class FakeState:
        def __init__(self, members):
            self.members = members

        def stage(self, name):
            return {"members": self.members} if name == "prune" else None

    ms = ("MOVE_THUNDERBOLT", "MOVE_SHADOW_BALL", "MOVE_THUNDER", "MOVE_RETURN")
    key = "|".join(ms)
    members = [{"own": {"dead_moves": {key: ["MOVE_THUNDER"]}, "no_live_reason": None,
                        "filler_reasons": {key: C.FILLER_REASON}}}]
    notes = _member_notes(FakeState(members), (R.MemberSpec("SPECIES_ROTOM", "own", ms, None),), None)
    assert notes == [f"Rotom: Thunder is filler: {C.FILLER_REASON}"]
