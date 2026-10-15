"""007 T035: the alternatives stage (optimizer/alternatives.py; spec FR-005, FR-007, FR-008, FR-013, SC-003, SC-007)."""

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace

import pytest

from platsim.optimizer import alternatives as A
from platsim.optimizer import item_classes as IC
from platsim.optimizer import move_classes as MC
from platsim.optimizer import candidates as C
from platsim.optimizer import resources as R
from platsim.pins import REPO_ROOT

LV = 55
B4 = ("SPECIES_ROSERADE", "SPECIES_BLISSEY", "SPECIES_GLISCOR", "SPECIES_MILOTIC", "SPECIES_BRONZONG", "SPECIES_LUCARIO")


@pytest.fixture(scope="module")
def b4(ledger):
    specs, cands = [], []
    for c in B4:
        v = C.variants(c, ledger)[0]
        mc = C.member_candidates(c, v, LV, ledger, team=B4)
        specs.append(R.MemberSpec(c, v.key, mc.movesets[0], mc.items[mc.movesets[0]][0]))
        cands.append({v.key: mc})
    fixed = R.repair(tuple(specs), [LV] * 6, ledger, [d[s.variant].ranked for d, s in zip(cands, specs)])
    assert not isinstance(fixed, R.Refusal), fixed  # single-copy TMs: as the optimizer does
    return fixed[0], cands


def test_generation_sorted_and_without_excluded_moves(b4):
    specs, cands = b4
    for slot, s in enumerate(specs):
        mc = cands[slot][s.variant]
        alts = A.generate(s, mc, slot)
        assert alts == sorted(alts, key=lambda a: a.key())
        assert len({a.key() for a in alts}) == len(alts)
        for a in alts:
            assert not {"MOVE_SCREECH", "MOVE_SEISMIC_TOSS", "MOVE_FRUSTRATION"} & set(a.moves)  # SC-007
            assert set(a.added) <= set(mc.legal_status)
            assert all(m not in mc.excluded for m in a.moves if m in a.added)


def test_weakest_two_slots_only(b4):
    specs, cands = b4
    s, mc = specs[3], cands[3][specs[3].variant]  # Milotic
    weakest = sorted(range(4), key=lambda j: (mc.scores.get(s.moves[j], 0.0), j))[:2]
    keep = {s.moves[j] for j in range(4) if j not in weakest}
    for a in A.generate(s, mc, 3):
        if a.kind == "status":
            assert keep <= set(a.moves), a  # only the two weakest slots change
    assert len(A.generate(s, mc, 3, all_slots=True)) > len(A.generate(s, mc, 3))


def test_structured_stall_set_for_milotic(b4):
    specs, cands = b4
    alts = A.generate(specs[3], cands[3][specs[3].variant], 3)
    st = [a for a in alts if a.kind == "structured"]
    assert st, "no structured set"
    assert any({"MOVE_TOXIC", "MOVE_RECOVER"} <= set(a.moves) for a in st), [a.moves for a in st]


def test_generation_is_deterministic_across_processes():
    code = ("import json; from platsim.availability.ledger import build_ledger; from platsim.optimizer import candidates as C, "
            "resources as R, alternatives as A; led = build_ledger(); c = 'SPECIES_MILOTIC'; v = C.variants(c, led)[0]; "
            f"mc = C.member_candidates(c, v, {LV}, led); s = R.MemberSpec(c, v.key, mc.movesets[0]); "
            "print(json.dumps([a.key() for a in A.generate(s, mc, 3)]))")
    outs = []
    for hs in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": hs}
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=REPO_ROOT, check=True)
        outs.append(r.stdout.strip().splitlines()[-1])
    assert outs[0] == outs[1]


def test_holm_hand_example():
    # p = 0.01, 0.04, 0.03 -> sorted 0.01 (x3 = 0.03), 0.03 (x2 = 0.06), 0.04 (x1 = 0.04 -> running max 0.06)
    assert A.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_added_status_moves_survive_required_hm_placement(ledger, b4):
    specs, cands = b4
    s, mc = specs[3], cands[3][specs[3].variant]
    a = next(x for x in A.generate(s, mc, 3) if "MOVE_WATERFALL" not in x.moves and len(x.added) == 2)
    alt = replace(s, moves=a.moves, adopted=a.added)
    placed, missing = R.place_required_hms((alt,), [LV], ledger, ("waterfall",))
    assert missing is None
    assert set(a.added) <= set(placed[0].moves) and "MOVE_WATERFALL" in placed[0].moves
    # positive control: without the adopted marks Waterfall replaces a status move first
    plain, _ = R.place_required_hms((replace(alt, adopted=()),), [LV], ledger, ("waterfall",))
    assert not set(a.added) <= set(plain[0].moves)


class FakePool:
    """Deterministic stand-in for the worker pool: a run's outcome depends on the team and seed only."""

    def __init__(self, favourite: str):
        self.favourite = favourite
        self.calls = 0

    def map(self, reqs):
        out = []
        for q in reqs:
            self.calls += 1
            h = int(hashlib.sha256(f"{json.dumps(q['team'], sort_keys=True)}|{q['seed']}".encode()).hexdigest(), 16)
            moves = {m for b in q["team"] for m in [x["move"] if isinstance(x, dict) else x for x in b.get("moves", [])]}
            p = 0.9 if self.favourite in moves else 0.5
            won = (h % 1000) / 1000 < p
            out.append({"ok": True, "cleared": won, "battles": [{"won": won}], "player_policy": q["player_policy"],
                        "opponent_policy": q["opponent_policy"]})
        return out


def test_run_stage_records_every_alternative_and_adopts_a_clear_winner(ledger, b4):
    from platsim.evaluate import worker_team

    specs, cands = b4

    def wteam(sp, levels):
        r = R.realize(sp, levels, ledger)
        return None if isinstance(r, R.Refusal) else worker_team(r.team, ledger)

    pool = FakePool("toxic")
    new, recs = A.run_stage(pool=pool, specs=specs, cands=cands, levels=[LV] * 6, led=ledger, seed="t", n_full=200,
                            round_size=5, wteam=wteam, members=4)
    members = [r for r in recs if r.get("member_done")]
    assert [m["slot"] for m in members] == [1, 2, 3, 4]
    for m in members:
        slot = m["slot"] - 1
        team = tuple(s.species for s in specs)
        alts = A.generate(specs[slot], cands[slot][specs[slot].variant], slot,
                          items=lambda mv, sp=specs[slot].species: IC.items_for(sp, mv, team, ledger, MC.ALT_POLICY))
        entries = [r for r in recs if not r.get("member_done") and r["slot"] == m["slot"]]
        assert len(entries) == len(alts) == m["alternatives"]  # SC-003: each exactly once (items included, US2)
        assert any(e["kind"] == "item" for e in entries)
        assert all("verdict" in e for e in entries)
    # a team carrying Toxic clears 90% vs 50% in the fake pool: the first member that can add it adopts it
    # (after that every team carries Toxic, so no later member gains from it), and the move is marked adopted
    gained = [i for i, (a, b) in enumerate(zip(specs, new)) if "MOVE_TOXIC" in b.moves and "MOVE_TOXIC" not in a.moves]
    assert len(gained) == 1, gained
    i = gained[0]
    assert "MOVE_TOXIC" in new[i].adopted
    assert [e for e in recs if not e.get("member_done") and e["slot"] == i + 1 and e.get("adopted")]
    assert next(m for m in members if m["slot"] == i + 1)["adopted_spec"]["moves"] == list(new[i].moves)
