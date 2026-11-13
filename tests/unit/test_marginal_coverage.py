"""Feature 026: candidate sets by marginal coverage (spec FR-001 to FR-009a, FR-014, FR-015).

Parts 1 to 3 use synthetic per-opponent values (three or four opponents) and an explicit cost predicate, so the rules are
tested as rules; part 4 pins the real B2 controls at level 48 against the pre-feature snapshot; part 5 the allocation.
"""

from __future__ import annotations

import json

import pytest

from platsim import pins
from platsim.optimizer import candidates as C

SNAPSHOT = pins.REPO_ROOT / "specs" / "026-marginal-coverage-sets" / "evidence" / "candidates-main.json"


@pytest.fixture(scope="module")
def led():
    from platsim.availability.ledger import build_ledger
    from platsim.legality.models import LegalityOptions

    return build_ledger().with_options(LegalityOptions())


# ---- part 1: definitions (FR-001, FR-006) ---------------------------------------------------------------------------
# opponent 4 is immune to A and B (value 0): the only opponent no cost-free move answers
VALS = {"A": [100.0, 100.0, 10.0, 0.0], "B": [90.0, 90.0, 9.0, 0.0], "Cfree": [0.0, 0.0, 50.0, 0.0],
        "D": [5.0, 5.0, 5.0, 0.0], "Ecost": [0.0, 0.0, 60.0, 40.0], "Fcost": [0.0, 0.0, 55.0, 0.0]}
SCORES = {m: sum(v) for m, v in VALS.items()}
IS_COST = lambda m: ("turn" if m.endswith("cost") else ("damage" if m.endswith("dmg") else None))  # noqa: E731  (cost tier)


def test_marginal_and_dead_moves():
    assert C.marginal("B", ["A", "B", "Cfree"], VALS) == 0.0
    assert C.marginal("Cfree", ["A", "B", "Cfree"], VALS) == 40.0
    assert C.dead_moves(["A", "B", "Cfree"], VALS) == ["B"]
    assert C.dead_moves(["A", "Cfree"], VALS) == []


def test_live_moves_given_the_two_strongest():
    cands = ["A", "B", "Cfree", "D"]
    assert C.live_moves(cands, VALS, SCORES) == ["Cfree"]  # D is never the best anywhere; B is redundant with A


def test_takeover():
    assert C.takeover("Cfree", ["A", "B"], VALS) == {2}
    assert C.takeover("Ecost", ["A", "B"], VALS) == {2, 3}
    assert C.takeover("D", ["A", "B"], VALS) == set()


def test_cost_preference():
    # a cost move with the same takeover as a cost-free one loses even with the larger gain
    assert C.prefer_cost_free(["Cfree", "Fcost"], ["A", "B"], VALS, SCORES, cost_tier=IS_COST) == "Cfree"
    # a cost move that answers an opponent no cost-free move answers (opponent 4, immune to A and B) may enter
    assert C.prefer_cost_free(["Cfree", "Ecost"], ["A", "B"], VALS, SCORES, cost_tier=IS_COST) == "Ecost"
    # the same cost move is refused once a cost-free move in the set hits opponent 4, even weakly
    v2 = dict(VALS, A=[100.0, 100.0, 10.0, 1.0])
    assert C.prefer_cost_free(["Cfree", "Ecost"], ["A", "B"], v2, SCORES, cost_tier=IS_COST) == "Cfree"
    assert C.prefer_cost_free(["Ecost"], ["A", "B"], v2, SCORES, cost_tier=IS_COST) is None
    # a damage-cost move (recoil, self stat drop) is compared with cost-free candidates only: it enters for the opponent
    # the cost-free candidate does not take over, even though A (cost-free, in the set) hits it
    v3 = dict(v2, Gdmg=[0.0, 0.0, 60.0, 40.0])
    assert C.prefer_cost_free(["Cfree", "Gdmg"], ["A", "B"], v3, {**SCORES, "Gdmg": 100.0}, cost_tier=IS_COST) == "Gdmg"
    assert C.prefer_cost_free(["Cfree", "Fcost"], ["A", "B"], v3, SCORES, cost_tier=IS_COST) == "Cfree"
    # nothing with positive contribution: None
    assert C.prefer_cost_free(["B", "D"], ["A"], VALS, SCORES, cost_tier=IS_COST) is None


# ---- part 2: the pool (FR-002) --------------------------------------------------------------------------------------
def _synthetic_member():
    # ten same-type moves with the highest scores, one weaker other-type move that is the best against opponent 3
    vals = {f"X{i}": [100.0 - i, 100.0 - i, 10.0 - i / 10, 0.0] for i in range(10)}
    vals["W"] = [0.0, 0.0, 60.0, 0.0]
    scores = {m: sum(v) for m, v in vals.items()}
    return vals, scores


def test_pool_by_marginal_holds_the_live_other_type_move():
    vals, scores = _synthetic_member()
    cands = sorted(vals)
    score_pool = sorted(cands, key=lambda m: (-scores[m], m))[:C.POOL]
    assert "W" not in score_pool
    pool = C.pool_by_marginal(cands, vals, scores, cost_tier=IS_COST)
    assert pool[0] == "X0" and "W" in pool and len(pool) == C.POOL
    assert pool[1] == "W"  # the only move adding coverage enters second; the rest fill by score
    assert pool[2:] == [f"X{i}" for i in range(1, 9)]


def test_pool_cost_preference_solar_beam_versus_grass_knot():
    vals, scores = _synthetic_member()
    vals["Scost"] = [0.0, 0.0, 70.0, 0.0]  # a stronger charge-turn move answering the same opponent as W
    scores = {m: sum(v) for m, v in vals.items()}
    pool = C.pool_by_marginal(sorted(vals), vals, scores, cost_tier=IS_COST)
    assert "W" in pool and pool.index("W") == 1 and "Scost" not in pool[:2]
    del vals["W"]; scores = {m: sum(v) for m, v in vals.items()}
    pool = C.pool_by_marginal(sorted(vals), vals, scores, cost_tier=IS_COST)
    assert "Scost" not in pool  # X0 still hits opponent 3: the turn-cost move is refused and the pool fills cost-free
    for m in vals:  # opponent 3 immune to every X move: now nothing cost-free answers it and the cost move may enter
        if m.startswith("X"):
            vals[m][2] = 0.0
    scores = {m: sum(v) for m, v in vals.items()}
    pool = C.pool_by_marginal(sorted(vals), vals, scores, cost_tier=IS_COST)
    assert pool[1] == "Scost"


# ---- part 3: ranking and set selection (FR-003, FR-004, FR-004a, FR-005) -------------------------------------------
def _five_live():
    # a member with exactly five legal attacks, each the best against one of five opponents: no three 4-sets can be
    # pairwise two apart (any two 4-subsets of five differ by one move)
    vals = {m: [0.0] * 5 for m in "PQRST"}
    for i, m in enumerate("PQRST"):
        vals[m][i] = 100.0 - i
    scores = {m: sum(v) for m, v in vals.items()}
    return vals, scores


def test_choose_sets_five_live_moves_gives_three_all_live_sets_one_apart():
    vals, scores = _five_live()
    cands = sorted(vals)
    pool = C.pool_by_marginal(cands, vals, scores, cost_tier=IS_COST)
    ranked = C.rank_sets(pool, vals, scores)
    sets, one_apart, reason = C.choose_sets(ranked, 3, cands, vals, scores, cost_tier=IS_COST)
    assert len(sets) == 3 and reason is None
    assert all(not C.dead_moves(s, vals) for s in sets)
    assert len(one_apart) == 2 and all(s in sets for s in one_apart)
    assert sets[0] == ("P", "Q", "R", "S")


def test_one_apart_only_replaces_a_set_with_a_dead_move():
    # six live moves plus a filler: set 2 two apart is all-live, so it is kept even though a one-apart set scores higher
    vals = {m: [0.0] * 6 for m in "PQRSTU"}
    for i, m in enumerate("PQRSTU"):
        vals[m][i] = 100.0 - i
    vals["f"] = [1.0] * 6
    scores = {m: sum(v) for m, v in vals.items()}
    cands = sorted(vals)
    pool = C.pool_by_marginal(cands, vals, scores, cost_tier=IS_COST)
    sets, one_apart, _ = C.choose_sets(C.rank_sets(pool, vals, scores), 2, cands, vals, scores, cost_tier=IS_COST)
    assert sets[0] == ("P", "Q", "R", "S") and sets[1] == ("P", "Q", "T", "U") and one_apart == []
    # a tie between two moves counts for the one first by name: only the other is dead
    assert C.dead_moves(["A", "A2", "Cfree"], {"A": [10.0, 0.0], "A2": [10.0, 0.0], "Cfree": [0.0, 5.0]}) == ["A2"]


def test_choose_sets_nothing_live_keeps_todays_sets_with_the_reason():
    vals = {"A": [100.0, 100.0, 10.0], "B": [90.0, 90.0, 9.0], "Cx": [80.0, 80.0, 8.0], "Dx": [70.0, 70.0, 7.0],
            "Ex": [60.0, 60.0, 6.0]}
    scores = {m: sum(v) for m, v in vals.items()}
    cands = sorted(vals)
    pool = C.pool_by_marginal(cands, vals, scores, cost_tier=IS_COST)
    ranked = C.rank_sets(pool, vals, scores)
    sets, one_apart, reason = C.choose_sets(ranked, 3, cands, vals, scores, cost_tier=IS_COST)
    assert sets and reason and "two strongest" in reason and one_apart == []
    today = sorted(ranked, key=lambda c: (-C.coverage([vals[m] for m in c]), -sum(scores[m] for m in c), c))
    assert sets[0] == today[0]  # pass 3 keeps today's key


def test_choose_sets_replaces_a_dead_move_from_outside_the_pool():
    vals, scores = _synthetic_member()  # X0..X9 and W
    cands = sorted(vals)
    pool = sorted(cands, key=lambda m: (-scores[m], m))[:C.POOL]  # today's score pool: W outside it
    ranked = C.rank_sets(pool, vals, scores)
    sets, _, reason = C.choose_sets(ranked, 1, cands, vals, scores, cost_tier=IS_COST)
    # W (outside the score pool) replaces a dead move; the other two slots stay dead because only X0 and W are ever best,
    # and the member is listed with the "live moves fill the sets" reason
    assert "W" in sets[0] and "X0" in sets[0]
    assert set(C.dead_moves(sets[0], vals)) <= {f"X{i}" for i in range(1, 10)} and reason and "live moves" in reason


# ---- part 4: the real controls on the six B2 species at level 48 (SC-001, SC-002) ------------------------------------
B2 = ["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"]


@pytest.fixture(scope="module")
def b2(led):
    consts = C.resolve_species(B2, led)
    return consts, {c: C.member_candidates(c, C.variants(c, led)[0], 48, led, team=tuple(consts)) for c in consts}


def _vals(mc):
    return {m: C.move_value(mc.species, m, mc.ref_level) for ms in mc.movesets for m in ms}


def _base(mc):
    return mc.movesets[:len(mc.movesets) - mc.extras]


def test_infernape_has_no_fire_punch_and_a_live_fourth_slot(b2):
    consts, mcs = b2
    mc = mcs[consts[1]]
    base = _base(mc)
    assert all("MOVE_FIRE_PUNCH" not in ms for ms in base)
    assert all("MOVE_SOLAR_BEAM" not in ms for ms in base)
    vals = _vals(mc)
    assert all(not C.dead_moves(ms, vals) for ms in base), mc.dead_moves
    assert any("MOVE_GRASS_KNOT" in ms for ms in base)
    assert len(base) == 3 and mc.no_live_reason is None  # one_apart only if two apart was impossible (it was not)


def test_floatzel_and_weavile_gain_brick_break_and_lose_dead_moves(b2):
    consts, mcs = b2
    for c in (consts[4], consts[5]):
        mc = mcs[c]
        vals = _vals(mc)
        assert "MOVE_BRICK_BREAK" in mc.pool and any("MOVE_BRICK_BREAK" in ms for ms in _base(mc)), c
        assert all(not C.dead_moves(ms, vals) for ms in _base(mc)), (c, mc.dead_moves)


def test_rotom_unchanged_and_listed_with_the_reason(b2):
    consts, mcs = b2
    snap = json.loads(SNAPSHOT.read_text())
    mc = mcs[consts[3]]
    rec = snap[f"B2quick|{consts[3]}|own"]
    old_base = [tuple(x) for x in rec["movesets"][:len(rec["movesets"]) - rec.get("extras", 0)]]
    assert list(_base(mc)) == old_base
    assert mc.no_live_reason and "two strongest" in mc.no_live_reason
    assert mc.summary()["no_live_reason"] == mc.no_live_reason


def test_garchomp_unchanged_and_staraptor_takes_return_without_a_cost_move(b2):
    consts, mcs = b2
    snap = json.loads(SNAPSHOT.read_text())
    rec = snap[f"B2quick|{consts[0]}|own"]
    old_base = [tuple(x) for x in rec["movesets"][:len(rec["movesets"]) - rec.get("extras", 0)]]
    assert list(_base(mcs[consts[0]])) == old_base
    # Staraptor (Normal/Flying): Return is a same-type 102-power move, so it enters the pool and a base set (the spec's
    # "unchanged" expectation predates variable moves joining the pool); Fly and Giga Impact (cost moves) stay out while
    # Aerial Ace and Return answer the same opponents
    mc = mcs[consts[2]]
    base = _base(mc)
    assert "MOVE_RETURN" in base[0] and "MOVE_CLOSE_COMBAT" in base[0] and "MOVE_AERIAL_ACE" in base[0]
    assert all("MOVE_FLY" not in ms and "MOVE_GIGA_IMPACT" not in ms for ms in base), base
    # Return, Close Combat and Aerial Ace cover every League opponent, so the fourth slot is a filler, kept (the set is not
    # dropped for a weaker all-live one) and listed with the reason
    assert mc.dead_moves[base[0]] and mc.no_live_reason and "live moves" in mc.no_live_reason
    assert all(len(C.dead_moves(ms, _vals(mc))) <= 1 for ms in base)


def test_extras_still_follow_their_kinds(b2):
    consts, mcs = b2
    for c, mc in mcs.items():
        assert sum(mc.extras_by_kind.values()) == mc.extras
        for ms, item in mc.item_extras.items():
            assert mc.items[ms][0] == item
        assert set(mc.dead_moves) == set(_base(mc))


# ---- part 4b: the optimizer's filler-move note from the prune stage's summaries (FR-009a, T012) ---------------------
def test_optimizer_member_notes_from_candidate_summaries():
    from platsim.optimizer import resources as R
    from platsim.optimizer.run import _member_notes

    class FakeState:
        def __init__(self, members):
            self.members = members

        def stage(self, name):
            return {"members": self.members} if name == "prune" else None

    ms = ("MOVE_THUNDERBOLT", "MOVE_SHADOW_BALL", "MOVE_THUNDER", "MOVE_OMINOUS_WIND")
    members = [{"own": {"dead_moves": {"|".join(ms): ["MOVE_THUNDER", "MOVE_OMINOUS_WIND"]}, "no_live_reason": C.NO_LIVE_REASON}},
               {"own": {"dead_moves": {}, "no_live_reason": None}}]
    specs = (R.MemberSpec("SPECIES_ROTOM", "own", ms, None), R.MemberSpec("SPECIES_GARCHOMP", "own", ("MOVE_EARTHQUAKE",), None))
    notes = _member_notes(FakeState(members), specs, None)
    assert notes == [f"Rotom: Thunder, Ominous Wind are filler: {C.NO_LIVE_REASON}"]
    # a chosen set that is not one of the summarised sets (repaired) gets no note
    other = (R.MemberSpec("SPECIES_ROTOM", "own", ("MOVE_THUNDERBOLT",), None),)
    assert _member_notes(FakeState(members), other, None) == []


# ---- part 5: the team-level allocation of contested resources (FR-014, FR-015, SC-008; story 3) --------------------
@pytest.fixture(scope="module")
def b2_alloc(led):
    from platsim.optimizer.run import _build_cands

    consts = C.resolve_species(B2, led)
    cands, record = _build_cands(consts, led, 48)
    return consts, cands, record


def _first(mcs):
    return next(iter(mcs.values()))


def test_b2_allocation_record_names_the_contested_tms(b2_alloc):
    consts, cands, record = b2_alloc
    garchomp, infernape = consts[0], consts[1]
    for tm in ("TM26", "TM71"):  # Earthquake, Stone Edge: one copy each, both wanted by Garchomp's and Infernape's first sets
        rec = record[tm]
        assert rec["copies"] == 1
        assert [x[0] for x in rec["contenders"]] == [garchomp, infernape] and rec["contenders"][0][1] > rec["contenders"][1][1]
        assert rec["given_to"] == [garchomp] and infernape in rec["rebuilt"]
    mc = _first(cands[1])
    assert {"MOVE_EARTHQUAKE", "MOVE_STONE_EDGE"} <= mc.unavailable
    assert all("MOVE_EARTHQUAKE" not in ms and "MOVE_STONE_EDGE" not in ms for ms in mc.movesets)
    assert any("MOVE_GRASS_KNOT" in ms for ms in mc.movesets[:3])  # a live coverage move it can learn on this team
    assert all(x[1] >= 0 for rec in record.values() for x in rec["contenders"])


def test_b2_every_offered_set_is_buildable_beside_the_others_first_sets(b2_alloc, led):
    from platsim.optimizer import resources as R

    consts, cands, record = b2_alloc
    firsts = [R.MemberSpec(c, "own", _first(mcs).movesets[0], None) for c, mcs in zip(consts, cands)]
    base = R.realize(tuple(firsts), [48] * 6, led)
    assert not isinstance(base, R.Refusal), base
    rr = R.repair(tuple(firsts), [48] * 6, led, [_first(mcs).ranked for mcs in cands])
    assert rr[1] == [], rr[1]  # zero repair notes for the baseline
    for slot, mcs in enumerate(cands):
        mc = _first(mcs)
        sets = list(mc.movesets) + ([mc.setup_moveset] if mc.setup_moveset else [])
        for ms in sets:
            specs = tuple(R.MemberSpec(consts[slot], "own", ms, None) if i == slot else firsts[i] for i in range(6))
            real = R.realize(specs, [48] * 6, led)
            assert not isinstance(real, R.Refusal), (consts[slot], ms, real)
            notes = R.repair(specs, [48] * 6, led, [_first(x).ranked for x in cands])[1]
            assert notes == [], (consts[slot], ms, notes)


def test_no_contest_team_equals_member_by_member(led):
    from platsim.optimizer.allocation import allocate

    # a two-member team whose first sets share no single-copy resource: the lists are unchanged and the record empty
    consts = C.resolve_species(["rotom", "staraptor", "luxray", "gardevoir", "gyarados", "bronzong"], led)
    cands = [{v.key: C.member_candidates(c, v, 48, led, team=tuple(consts)) for v in C.variants(c, led)} for c in consts]
    out, record = allocate(consts, led, cands)
    for mcs, mcs2 in zip(cands, out):
        for k in mcs:
            if mcs2[k].unavailable == frozenset():
                assert mcs[k].movesets == mcs2[k].movesets
    assert all(rec["contenders"] == [] or rec["given_to"] for rec in record.values())


def test_lower_slot_wins_a_contested_tm_on_gain(led, monkeypatch):
    from platsim.optimizer import allocation as AL

    # a synthetic two-member contention where the second slot's first set loses more coverage without the TM
    consts = ["SPECIES_A", "SPECIES_B"]

    class MC:
        def __init__(self, species, moves, pool, gain):
            self.species, self.movesets, self.pool, self.variable_offered = species, [tuple(moves)], list(pool), []
            self.ref_level, self.unavailable, self.ranked, self.gain = 48, frozenset(), [tuple(moves)], gain
            self.variant = type("V", (), {"key": "own", "species": species, "options": lambda self2, led: []})()
            self.setup_moveset = None

    needs_map = {"MOVE_X": {"TM99": 1}}
    monkeypatch.setattr(AL, "_cheapest_uses", lambda species, variant, move, level, led: dict(needs_map.get(move, {})))
    monkeypatch.setattr(AL, "_legal", lambda variant, level, led: ["MOVE_X", "MOVE_Y"])
    monkeypatch.setattr(AL.R, "copies", lambda r, led, team=None: 1)
    built = {}

    def fake_mc(const, variant, level, led, team=None, unavailable=frozenset()):
        mc = MC(const, ["MOVE_Y"] if "MOVE_X" in unavailable else ["MOVE_X"], ["MOVE_X", "MOVE_Y"], 0)
        mc.unavailable = frozenset(unavailable)
        built[const] = mc
        return mc

    monkeypatch.setattr(AL.C, "member_candidates", fake_mc)
    cov = {("SPECIES_A", ("MOVE_X",)): 100.0, ("SPECIES_A", ("MOVE_Y",)): 90.0, ("SPECIES_B", ("MOVE_X",)): 100.0, ("SPECIES_B", ("MOVE_Y",)): 10.0}
    monkeypatch.setattr(AL, "_coverage_of", lambda mc, ms: cov[(mc.species, tuple(ms))])
    cands = [{"own": MC("SPECIES_A", ["MOVE_X"], ["MOVE_X", "MOVE_Y"], 0)}, {"own": MC("SPECIES_B", ["MOVE_X"], ["MOVE_X", "MOVE_Y"], 0)}]
    out, record = AL.allocate(consts, None, cands)
    assert record["TM99"]["given_to"] == ["SPECIES_B"] and record["TM99"]["rebuilt"] == ["SPECIES_A"]
    assert out[0]["own"].movesets == [("MOVE_Y",)] and out[1]["own"].movesets == [("MOVE_X",)]
