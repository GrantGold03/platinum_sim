"""Feature 019: fast-mode tests of the pure functions in specs/019-e4-sampling-spike/scripts (no pool, no battle)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from platsim.stats import Z95, wilson_ci

SCRIPTS = Path(__file__).resolve().parents[2] / "specs/019-e4-sampling-spike/scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses with postponed annotations look the module up here (Python 3.14)
    spec.loader.exec_module(mod)
    return mod


E = _load("e4_estimator")
C = _load("common")


def test_wilson_bounds_match_platsim_stats_at_both_levels():
    assert E.wilson_bounds(90, 100, 0.95) == wilson_ci(90, 100, Z95)
    assert E.wilson_bounds(90, 100, 0.975) == wilson_ci(90, 100, E.Z975)
    lo95, hi95 = E.wilson_bounds(90, 100, 0.95)
    lo975, hi975 = E.wilson_bounds(90, 100, 0.975)
    assert lo975 < lo95 and hi975 > hi95  # the 97.5% interval is wider


def test_product_interval_is_ordered_and_wider_than_the_naive_95_product():
    e4 = E.wilson_bounds(1789, 2000, 0.975)
    cyn = E.wilson_bounds(1543, 1789, 0.975)
    lo, hi = E.product_interval(e4, cyn)
    assert lo < hi
    n_lo, n_hi = E.product_interval(E.wilson_bounds(1789, 2000, 0.95), E.wilson_bounds(1543, 1789, 0.95))
    assert lo < n_lo and hi > n_hi
    d_lo, d_hi = E.delta_interval(1789 / 2000, 2000, 1543 / 1789, 1789)
    assert (d_hi - d_lo) < (hi - lo)  # delta is narrower than Bonferroni (informational only)


def test_verdict_rule_reproduces_hand_cases_and_the_gap_rule():
    # above and tight: qualified
    assert E.verdict(0.90, (0.885, 0.915), "standard", 0.75, 3.0) == ("above", "qualified")
    # straddling: borderline
    assert E.verdict(0.76, (0.74, 0.78), "standard", 0.75, 3.0) == ("borderline", "borderline")
    # below
    assert E.verdict(0.70, (0.68, 0.72), "standard", 0.75, 3.0) == ("below", "not_qualified")
    # above but too wide for the 0.02 target: not qualified (half-width only)
    assert E.verdict(0.90, (0.86, 0.94), "standard", 0.75, 3.0) == ("above", "not_qualified")
    # gap rule and the quick preset never qualify
    assert E.verdict(0.90, (0.885, 0.915), "standard", 0.75, 11.0)[1] == "not_qualified"
    assert E.verdict(0.90, (0.885, 0.915), "quick", 0.75, 3.0)[1] == "not_qualified"


def test_disagreement_kind_and_runs_needed():
    assert E.disagreement_kind("above", "qualified", "above", "qualified") == "agree"
    assert E.disagreement_kind("above", "qualified", "borderline", "borderline") == "threshold"
    assert E.disagreement_kind("above", "qualified", "above", "not_qualified") == "half-width only"
    rn = E.runs_needed_for_half_width(0.03, 2000, 0.02)
    assert rn == 4500  # (0.03/0.02)^2 * 2000
    assert E.runs_needed_for_half_width(0.015, 2000, 0.02) == 2000


def _synthetic(n, cyn_reached, cyn_wins_full, champ_battles, champ_wins, **kw):
    clear = cyn_wins_full / n
    s = C.StoredEvaluation(
        dir="<synthetic>", n_runs=n, clear_rate=clear, clear_ci95=wilson_ci(cyn_wins_full, n),
        per_battle={"aaron": {"battles": n, "rate": 1.0}, "bertha": {"battles": n, "rate": 1.0},
                    "flint": {"battles": n, "rate": 1.0}, "lucian": {"battles": n, "rate": cyn_reached / n},
                    "cynthia": {"battles": cyn_reached, "rate": (cyn_wins_full / cyn_reached) if cyn_reached else 0.0}},
        champion_rate=(champ_wins / champ_battles) if champ_battles else None, champion_battles=champ_battles,
        champion_ci95=wilson_ci(champ_wins, champ_battles) if champ_battles else None,
        budget_preset=kw.get("preset", "standard"), threshold=0.75, qualified=kw.get("qualified", False),
        borderline=kw.get("borderline", False), final_level_gap_max=2.0, champion_status=kw.get("status", "met"))
    return s


def test_positive_control_elite_four_below_threshold_gives_below_not_qualified():
    c = E.composite(E.control_case(), "topup")
    assert c.threshold_verdict == "below" and c.full_verdict == "not_qualified"
    # a naive Cynthia-only rule would have said above
    assert E.threshold_verdict(wilson_ci(1901, 2001), 0.75) == "above"


def test_not_estimable_is_reported_not_guessed():
    s = _synthetic(2000, 0, 0, 0, 0, status="no_reach")
    c = E.composite(s, "topup")
    assert c.not_estimable and c.disagreement_kind == "n/a" and not c.agreement
    c2 = E.composite(s, "fullrun")
    assert c2.not_estimable


def test_fullrun_identity_equals_stored_clear_rate_and_topup_agrees_on_a_strong_team():
    s = _synthetic(2000, 1999, 1889, 2001, 1891, qualified=True)
    f = E.composite(s, "fullrun")
    assert abs(f.estimate - s.clear_rate) < 1e-9
    t = E.composite(s, "topup")
    assert t.contains_stored and t.agreement and t.threshold_verdict == "above"
    assert t.half_width_ratio > 1.0  # the composite interval is wider by construction


def test_dedup_marks_a_repeated_result_once():
    a = _synthetic(2000, 1900, 1700, 2001, 1800)
    b = _synthetic(2000, 1900, 1700, 2001, 1800)
    a.dir, b.dir = "x", "y"
    a.team_key = b.team_key = (("garchomp", 52),)
    a.master_seed = b.master_seed = "m"
    out = C.dedup([a, b])
    assert out[0].duplicate_of is None and out[1].duplicate_of == "x"


# ---- replay (US2) ----

R = _load("e4_replay")


def _run(i, e4_wins, cyn_won, state=None, turns=10):
    """A synthetic recorded run: e4_wins = number of Elite Four members beaten (0..4, in order); cyn_won None = not reached."""
    battles = []
    order = ["aaron", "bertha", "flint", "lucian"]
    for j, t in enumerate(order):
        if j < e4_wins:
            battles.append({"trainer": t, "won": True, "end": "win", "turns": turns, "log_hash": "h"})
        else:
            battles.append({"trainer": t, "won": False, "end": "loss", "turns": turns, "log_hash": "h"})
            break
    reached = e4_wins == 4
    if reached:
        battles.append({"trainer": "cynthia", "won": bool(cyn_won), "end": "win" if cyn_won else "loss", "turns": 18,
                        "log_hash": "h", "state_before": state or {"levels": [50 + i % 3]}})
    return {"run": i, "seed": f"s{i}", "cleared": bool(reached and cyn_won), "battles": battles, "final_levels": [50, 51, 50, 50, 50, 50]}


def test_switch_never_happens_when_a_member_sits_at_0_90():
    runs = [_run(i, 4 if i % 10 else 3, True) for i in range(2000)]  # Lucian lost in 10% of runs
    assert R.switch_point(runs, 0.98) is None
    c = R.composite_after(runs, None)
    assert c["cynthia_only_runs"] == 0 and abs(c["estimate"] - sum(r["cleared"] for r in runs) / 2000) < 1e-12


def test_switch_point_for_all_wins_is_the_first_n_whose_wilson_lower_bound_clears_the_floor():
    runs = [_run(i, 4, True) for i in range(2000)]
    for floor in (0.98, 0.99, 0.995):
        expected = next(n for n in range(1, 2001) if wilson_ci(n, n, Z95)[0] >= floor)
        assert R.switch_point(runs, floor) == expected
        assert 100 < expected < 1000


def test_composite_after_counts_unvalued_and_reproduces_the_full_rate_at_k_equal_n():
    runs = [_run(i, 4 if i % 5 else 2, i % 7 != 0) for i in range(100)]
    c_full = R.composite_after(runs, 100)
    assert abs(c_full["estimate"] - sum(r["cleared"] for r in runs) / 100) < 1e-12 and c_full["unvalued"] == 0
    c = R.composite_after(runs, 20)
    assert c["unvalued"] == sum(1 for r in runs[20:] if R.cynthia_battle(r) is None)
    assert c["cynthia_only_runs"] == 80 and c["cynthia_only_share"] == 0.8


def test_banked_states_counts_distinct_states_and_orders_are_deterministic():
    runs = [_run(i, 4, True) for i in range(30)]
    assert R.banked_states(runs, 30) == 3  # levels 50/51/52 cycle
    assert R.banked_states(runs, 1) == 1
    o1, o2 = R.orders(30, 3, "x"), R.orders(30, 3, "x")
    assert o1 == o2 and o1[0] == list(range(30)) and o1[1] != o1[0]
