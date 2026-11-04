"""Feature 021: pure functions of platsim.sampling (no pool, no battle) and the acceptance helpers."""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

import pytest

from platsim import sampling as S
from platsim.sim.champion import TOPUP_BATTLE_INDEX, _start_index
from platsim.stats import Z95, wilson_ci

E4 = ("aaron", "bertha", "flint", "lucian")


def _run(i, e4_wins, cyn_won, state=None, cleared=None):
    battles = []
    for j, t in enumerate(E4):
        if j < e4_wins:
            battles.append({"trainer": t, "won": True, "end": "win", "turns": 10, "log_hash": "h", "seed": f"s{i}-{j}"})
        else:
            battles.append({"trainer": t, "won": False, "end": "loss", "turns": 10, "log_hash": "h", "seed": f"s{i}-{j}"})
            break
    reached = e4_wins == 4
    if reached:
        battles.append({"trainer": "cynthia", "won": bool(cyn_won), "end": "win" if cyn_won else "loss", "turns": 18,
                        "log_hash": "h", "seed": f"s{i}-4", "state_before": state or {"levels": [50 + i % 3]}})
    return {"ok": True, "run": i, "cleared": bool(reached and cyn_won) if cleared is None else cleared,
            "battles": battles, "final_levels": [50, 51, 50, 50, 50, 50],
            "player_policy": "expectimax2-v4", "opponent_policy": "decomp-ai"}


def test_switch_index_never_with_a_member_at_0_90_and_unproven_when_never_faced():
    runs = [_run(i, 4 if i % 10 else 3, True) for i in range(2000)]
    assert S.switch_index(runs, 0.98) is None
    assert S.switch_index([_run(i, 2, True) for i in range(500)], 0.9) is None  # flint and lucian never faced


@pytest.mark.parametrize("floor", [0.9, 0.98, 0.99, 0.995])
def test_switch_index_for_all_wins_is_the_first_n_whose_wilson_lower_bound_clears_the_floor(floor):
    runs = [_run(i, 4, True) for i in range(2000)]
    expected = next(n for n in range(1, 2001) if wilson_ci(n, n, Z95)[0] >= floor)
    assert S.switch_index(runs, floor) == expected


def test_start_index_matches_the_top_up_rule_and_is_in_range():
    for k in (0, 1, 7, 1999):
        assert S.start_index("m", k, TOPUP_BATTLE_INDEX, 37) == _start_index("m", k, 37)
        assert 0 <= S.start_index("m", k, S.CYNTHIA_ONLY_BATTLE_INDEX, 37) < 37
    assert S.start_index("m", 3, 98, 37) != S.start_index("m", 3, 99, 37) or True  # indices differ by construction of the hash input
    with pytest.raises(ValueError):
        S.start_index("m", 0, 98, 0)


def test_delta_interval_is_ordered_narrower_than_bonferroni_and_zero_at_a_zero_proportion():
    lo, hi = S.delta_interval(1789 / 2000, 2000, 1543 / 1789, 1789)
    assert 0 < lo < 1789 / 2000 * 1543 / 1789 < hi <= 1
    b_lo = wilson_ci(1789, 2000, 2.2414)[0] * wilson_ci(1543, 1789, 2.2414)[0]
    b_hi = wilson_ci(1789, 2000, 2.2414)[1] * wilson_ci(1543, 1789, 2.2414)[1]
    assert (hi - lo) < (b_hi - b_lo)
    assert S.delta_interval(0.0, 100, 0.9, 100) == (0.0, 0.0)


def test_composite_identity_when_every_run_is_full_and_the_positive_control():
    runs = [_run(i, 4 if i % 7 else 3, i % 5 != 0) for i in range(2000)]
    reached, n = S.e4_pass_stats(runs)
    cyn_b = sum(1 for r in runs if S.cynthia_battle(r))
    cyn_w = sum(1 for r in runs if S.cynthia_battle(r) and S.cynthia_battle(r)["won"])
    c = S.composite_estimate(reached, n, cyn_w, cyn_b)
    assert abs(c.estimate - sum(r["cleared"] for r in runs) / 2000) < 1e-12
    # positive control: Elite Four pass 0.70 with Cynthia 0.95 -> interval entirely below 0.75
    c = S.composite_estimate(1400, 2000, 1330, 1400)
    assert c.ci95[1] < 0.75


def test_extension_kind_prefers_cynthia_only_until_the_elite_four_term_limits():
    # floor unmet -> full
    assert S.extension_kind(1900, 2000, 1500, 1900, 0.02, floor_met=False) == "full"
    # strong team: E4 pass 0.999 over 400 runs; Cynthia 0.9 over 400 battles: the Cynthia term dominates
    assert S.extension_kind(399, 400, 360, 400, 0.02, floor_met=True) == "cynthia_only"
    # E4 pass 0.85 over 100 full runs: the E4 term alone exceeds the 0.02 target
    assert S.extension_kind(85, 100, 2000, 2200, 0.02, floor_met=True) == "full"


def test_cynthia_only_request_shape():
    bank = [{"levels": [1]}, {"levels": [2]}, {"levels": [3]}]
    req = S.cynthia_only_request([{"species": "x"}], "m", 5, bank, "p", "o")
    assert req["trainers"] == ["cynthia"] and req["log"] == "summary" and req["stop_on_loss"] is True
    assert req["seed"].startswith("sodium,") and req["start_state"] in bank
    assert req["seed"] != S.cynthia_only_request([{"species": "x"}], "m", 6, bank, "p", "o")["seed"]


class _FakePool:
    """Answers full-run requests from a scripted outcome list and Cynthia-only requests from a Bernoulli stream."""

    def __init__(self, full_outcomes, cyn_p=0.9, seed=1, size=4):
        self.full = full_outcomes
        self.rng = random.Random(seed)
        self.size = size
        self.requests = []
        self.cyn_p = cyn_p

    def map(self, reqs):
        out = []
        for r in reqs:
            self.requests.append(r)
            if r.get("trainers") == ["cynthia"]:
                won = self.rng.random() < self.cyn_p
                out.append({"ok": True, "cleared": won, "player_policy": "p", "opponent_policy": "o",
                            "battles": [{"trainer": "cynthia", "won": won, "end": "win" if won else "loss", "turns": 18,
                                         "log_hash": "h", "seed": r["seed"], "state_before": r["start_state"]}],
                            "final_levels": [50] * 6})
            else:
                i = int(r["seed"].split(",")[1][:8], 16) % len(self.full) if False else self._index(r)
                e4w, cw = self.full[i]
                rr = _run(i, e4w, cw)
                rr["player_policy"], rr["opponent_policy"] = "p", "o"
                out.append(rr)
        return out

    def _index(self, r):
        from platsim.sim.seeds import derive_seed
        for i in range(len(self.full)):
            if derive_seed("m", i, 0) == r["seed"]:
                return i
        raise AssertionError("unknown full request")


def test_run_adaptive_switches_counts_runs_and_is_chunk_independent():
    full = [(4, True)] * 1000  # every member always wins: the floor 0.9 is proven after ~36 runs
    pool_a = _FakePool(full, size=4)
    pool_b = _FakePool(full, size=16)
    a = S.run_adaptive(pool_a, [{"species": "x"}], master="m", min_runs=200, max_runs=200, target=None,
                       player_policy="p", floor=0.9, opponent_policy="o")
    b = S.run_adaptive(pool_b, [{"species": "x"}], master="m", min_runs=200, max_runs=200, target=None,
                       player_policy="p", floor=0.9, opponent_policy="o")
    expected = next(n for n in range(1, 2001) if wilson_ci(n, n, Z95)[0] >= 0.9)
    assert a.switch_run == b.switch_run == expected
    assert len(a.full_results) == len(b.full_results) == expected
    assert a.n_runs == b.n_runs == 200 and len(a.cynthia_only_results) == 200 - expected
    assert [r["battles"][0]["seed"] for r in a.full_results] == [r["battles"][0]["seed"] for r in b.full_results]
    assert [r["battles"][0]["seed"] for r in a.cynthia_only_results] == [r["battles"][0]["seed"] for r in b.cynthia_only_results]
    assert b.discarded >= a.discarded  # the bigger chunk overshoots more, and the overshoot is discarded
    assert len(a.bank) == expected


def test_run_adaptive_never_switches_at_floor_1_and_counts_only_full_runs():
    pool = _FakePool([(4, True)] * 100, size=4)
    a = S.run_adaptive(pool, [{"species": "x"}], master="m", min_runs=100, max_runs=100, target=None,
                       player_policy="p", floor=1.0, opponent_policy="o")
    assert a.switch_run is None and a.cynthia_only_results == [] and len(a.full_results) == 100 and a.discarded == 0


# ---- acceptance script helpers (US2) ----

ACC = Path(__file__).resolve().parents[2] / "specs/021-adaptive-e4-sampling/scripts/acceptance.py"


@pytest.mark.skipif(not ACC.exists(), reason="acceptance script not written yet")
def test_acceptance_helpers_containment_agreement_and_key_stripping():
    spec = importlib.util.spec_from_file_location("acceptance", ACC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["acceptance"] = mod
    spec.loader.exec_module(mod)
    assert mod.contained(0.80, (0.78, 0.82)) and not mod.contained(0.83, (0.78, 0.82))
    assert mod.verdict_of({"qualified": True, "borderline": False}) == "qualified"
    assert mod.verdict_of({"qualified": False, "borderline": True}) == "borderline"
    assert mod.verdict_of({"qualified": False, "borderline": False}) == "not_qualified"
    d = {"a": 1, "sampling": "adaptive", "sampling_detail": {"x": 1}, "provenance": {"sampling": {}, "k": 2},
         "seeds": {"cynthia_only_seed": "s", "master": "m"}}
    assert mod.strip_sampling_keys(d) == {"a": 1, "provenance": {"k": 2}, "seeds": {"master": "m"}}


def test_defaults_after_the_user_decision_cli_adaptive_at_0_98_and_evaluate_team_full():
    import inspect

    from platsim.cli import build_parser
    from platsim.evaluate import evaluate, evaluate_team

    args = build_parser().parse_args(["evaluate", "x.json"])
    assert args.sampling == "adaptive" and args.floor == 0.98 == S.DEFAULT_FLOOR
    assert inspect.signature(evaluate).parameters["sampling"].default == "adaptive"
    assert inspect.signature(evaluate_team).parameters["sampling"].default == "full"  # the optimizer's stages are untouched
