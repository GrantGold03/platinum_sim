"""Feature 022: the runner-up pairing rule, the comparison record and run_adaptive's borderline extension (no battles)."""

from __future__ import annotations

import random

import pytest

from platsim import sampling as S
from platsim.optimizer.pairing import paired_outcomes
from platsim.optimizer.run import _comparison_record, paired_outcomes_full
from platsim.sim.seeds import derive_seed
from platsim.stats import mcnemar_exact


def _full(i, cleared):
    return {"ok": True, "cleared": cleared, "player_policy": "p", "opponent_policy": "o", "final_levels": [50] * 6,
            "battles": [{"trainer": t, "won": True, "end": "win", "turns": 10, "log_hash": "h", "seed": f"s{i}"}
                        for t in ("aaron", "bertha", "flint", "lucian")]
            + [{"trainer": "cynthia", "won": cleared, "end": "win" if cleared else "loss", "turns": 18, "log_hash": "h",
                "seed": f"s{i}", "state_before": {"levels": [50]}}]}


def _cyn(j, won):
    return {"ok": True, "cleared": won, "player_policy": "p", "opponent_policy": "o", "final_levels": [50] * 6,
            "battles": [{"trainer": "cynthia", "won": won, "end": "win" if won else "loss", "turns": 18, "log_hash": "h",
                         "seed": f"c{j}", "state_before": {"levels": [50]}}]}


def test_pairing_neither_switched_is_the_full_pairing():
    a = [_full(i, i % 3 != 0) for i in range(100)]
    b = [_full(i, i % 4 != 0) for i in range(100)]
    p = paired_outcomes(a, [], b, [])
    assert p.full_pairs == 100 and p.cynthia_only_pairs == 0 and p.excluded == 0 and p.pairs == 100
    assert p.a_flags == [r["cleared"] for r in a] and p.b_flags == [r["cleared"] for r in b]
    assert paired_outcomes_full(a, b) == p


def test_pairing_both_switched_at_different_runs_pairs_by_index_then_ordinal_and_excludes_the_surplus():
    a_full, a_cyn = [_full(i, True) for i in range(300)], [_cyn(j, j % 5 != 0) for j in range(1700)]
    b_full, b_cyn = [_full(i, True) for i in range(500)], [_cyn(j, j % 7 != 0) for j in range(1500)]
    p = paired_outcomes(a_full, a_cyn, b_full, b_cyn)
    assert p.full_pairs == 300 and p.cynthia_only_pairs == 1500 and p.pairs == 1800
    assert p.excluded == (500 - 300) + (1700 - 1500)
    assert len(p.a_flags) == len(p.b_flags) == 1800


def test_pairing_one_switched_excludes_its_cynthia_only_runs():
    a_full, a_cyn = [_full(i, True) for i in range(300)], [_cyn(j, True) for j in range(1700)]
    b_full = [_full(i, True) for i in range(2000)]
    p = paired_outcomes(a_full, a_cyn, b_full, [])
    assert p.full_pairs == 300 and p.cynthia_only_pairs == 0 and p.excluded == 1700 + 1700


def test_positive_and_negative_controls():
    a_full, b_full = [_full(i, True) for i in range(200)], [_full(i, False) for i in range(200)]
    a_cyn, b_cyn = [_cyn(j, True) for j in range(100)], [_cyn(j, False) for j in range(100)]
    p = paired_outcomes(a_full, a_cyn, b_full, b_cyn)
    cmp = mcnemar_exact(p.a_flags, p.b_flags)
    assert cmp.verdict == "A" and cmp.a_only == 300 and cmp.b_only == 0
    same = [_full(i, i % 2 == 0) for i in range(200)]
    p2 = paired_outcomes(same, [], [dict(r) for r in same], [])
    cmp2 = mcnemar_exact(p2.a_flags, p2.b_flags)
    assert cmp2.verdict == "indistinguishable" and cmp2.a_only == cmp2.b_only == 0


def test_comparison_record_carries_the_four_new_keys_and_handles_no_pairs():
    a_full, b_full = [_full(i, True) for i in range(50)], [_full(i, i % 2 == 0) for i in range(50)]
    p = paired_outcomes(a_full, [], b_full, [])
    rec = _comparison_record(mcnemar_exact(p.a_flags, p.b_flags), p)
    for k in ("pairs", "excluded", "full_pairs", "cynthia_only_pairs", "n_paired", "p_value", "verdict"):
        assert k in rec
    assert rec["n_paired"] == rec["pairs"] == 50 and rec["verdict"] == "winner better"
    empty = paired_outcomes([], [_cyn(0, True)], [_full(0, True)], [])
    rec2 = _comparison_record(None, empty)
    assert rec2["pairs"] == 0 and rec2["verdict"] == "no same-kind pairs" and rec2["excluded"] == 2


class _Pool:
    """Full runs from a scripted (e4_all_won, cyn_won) list indexed by request seed; Cynthia-only from a seeded stream."""

    def __init__(self, full_outcomes, cyn_p, size=4, seed=7):
        self.size = size
        self.full = full_outcomes
        self.by_seed = {derive_seed("m", i, 0): i for i in range(len(full_outcomes))}
        self.rng = random.Random(seed)
        self.cyn_p = cyn_p
        self.cyn_cache = {}

    def map(self, reqs):
        out = []
        for r in reqs:
            if r.get("trainers") == ["cynthia"]:
                j = int(r["seed"] == r["seed"]) and None  # placeholder to keep flake8 quiet
                key = r["seed"]
                if key not in self.cyn_cache:
                    self.cyn_cache[key] = self.rng.random() < self.cyn_p
                won = self.cyn_cache[key]
                res = _cyn(0, won); res["battles"][0]["seed"] = key; res["battles"][0]["state_before"] = r["start_state"]
                out.append(res)
            else:
                i = self.by_seed[r["seed"]]
                e4, cw = self.full[i]
                res = _full(i, cw and e4)
                if not e4:
                    res["battles"] = res["battles"][:3] + [dict(res["battles"][3], won=False, end="loss")]
                    res["cleared"] = False
                out.append(res)
        return out


def _stream(n, p_clear, seed=3):
    rng = random.Random(seed)
    return [(True, rng.random() < p_clear) for _ in range(n)]


def test_borderline_extension_resolves_a_straddle_with_cynthia_only_runs_and_is_chunk_independent():
    # true clear rate 0.78: the composite interval straddles 0.75 at 200 runs and resolves after several hundred more
    # seed 5 (checked offline): the interval straddles 0.75 at 200 runs and 389 Cynthia-only runs resolve it (589 total)
    outcomes = _stream(4000, 0.78, seed=5)
    kw = dict(master="m", min_runs=200, max_runs=4000, target=None, player_policy="p", floor=0.9, opponent_policy="o",
              borderline_threshold=0.75, borderline_max_runs=4000)
    a = S.run_adaptive(_Pool(outcomes, 0.78, size=4, seed=5), [{"species": "x"}], **kw)
    b = S.run_adaptive(_Pool(outcomes, 0.78, size=16, seed=5), [{"species": "x"}], **kw)
    for r in (a, b):
        assert r.switch_run is not None and r.borderline_extended
        assert r.extension["cynthia_only"] > 0 and r.extension["full"] == 0
    assert a.n_runs == b.n_runs and len(a.cynthia_only_results) == len(b.cynthia_only_results)
    assert [x["battles"][0]["seed"] for x in a.cynthia_only_results] == [x["battles"][0]["seed"] for x in b.cynthia_only_results]
    reached, n_full = S.e4_pass_stats(a.full_results)
    w = sum(x["battles"][0]["won"] for x in a.cynthia_only_results) + sum(S.cynthia_battle(x)["won"] for x in a.full_results)
    c = S.composite_estimate(reached, n_full, w, len(a.cynthia_only_results) + reached)
    assert not (c.ci95[0] < 0.75 <= c.ci95[1])  # resolved
    assert a.n_runs == 589 and a.extension["cynthia_only"] == 389


def test_borderline_extension_stops_at_the_cap_while_still_straddling():
    outcomes = _stream(600, 0.75)
    r = S.run_adaptive(_Pool(outcomes, 0.75, size=4), [{"species": "x"}], master="m", min_runs=200, max_runs=600,
                       target=None, player_policy="p", floor=0.9, opponent_policy="o",
                       borderline_threshold=0.75, borderline_max_runs=260)
    assert r.borderline_extended and r.n_runs <= 260
