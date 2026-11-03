"""Feature 020: fast-mode tests of specs/020-lead-spike/scripts/lead_analysis.py (no pool, no battle)."""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "specs/020-lead-spike/scripts/lead_analysis.py"
spec = importlib.util.spec_from_file_location("lead_analysis", SCRIPT)
LA = importlib.util.module_from_spec(spec)
sys.modules["lead_analysis"] = LA
spec.loader.exec_module(LA)

TEAM = [{"species": s, "start_level": 50 + i} for i, s in enumerate(["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"])]


def _recording(lead, cleared_flags, seeds=None, finals=None):
    order_indices = [lead] + [j for j in range(6) if j != lead]
    runs = []
    for i, c in enumerate(cleared_flags):
        battles = [{"trainer": t, "won": True, "end": "win", "turns": 10, "log_hash": "h"} for t in ("aaron", "bertha", "flint", "lucian")]
        battles.append({"trainer": "cynthia", "won": bool(c), "end": "win" if c else "loss", "turns": 18, "log_hash": "h"})
        fl = finals[i] if finals else [TEAM[order_indices[k]]["start_level"] + (1 if k == 0 else 0) for k in range(6)]
        runs.append({"run": i, "seed": (seeds[i] if seeds else f"s{i}"), "cleared": bool(c), "battles": battles, "final_levels": fl})
    return {"header": {"lead_index": lead, "lead_species": TEAM[lead]["species"], "order_indices": order_indices, "runs": len(runs)},
            "runs": runs, "path": f"<lead{lead}>"}


def test_rotate_keeps_relative_order_and_lead_0_is_identity():
    assert LA.rotate(TEAM, 0) == TEAM
    r = LA.rotate(TEAM, 3)
    assert [m["species"] for m in r] == ["rotom", "garchomp", "infernape", "staraptor", "floatzel", "weavile"]


def test_check_paired_raises_on_differing_seed_lists():
    a = _recording(0, [True] * 5)
    b = _recording(1, [True] * 5, seeds=[f"x{i}" for i in range(5)])
    with pytest.raises(ValueError):
        LA.check_paired(a, b)
    LA.check_paired(a, _recording(2, [False] * 5))  # same default seeds: fine


def test_lead_row_reconciles_rates_level_mapping_and_lead_gain():
    rec = _recording(3, [True, True, False, True])
    starts = [m["start_level"] for m in TEAM]
    row = LA.lead_row(rec, starts, rec["header"]["order_indices"])
    assert row["cleared"] == 3 and row["clear_rate"] == 0.75 and row["lead_index"] == 3
    assert row["per_trainer"]["cynthia"]["rate"] == 0.75 and row["per_trainer"]["aaron"]["rate"] == 1.0
    # the lead (rotom, start 53) gained 1 level in every cleared run; the others 0; mapped back to member order
    assert row["expected_final_levels"] == [50, 51, 52, 54, 54, 55]
    assert row["lead_gain"] == 1.0


def test_choose_best_picks_highest_and_breaks_ties_to_lowest_index():
    recs = {0: _recording(0, [True, False, False]), 1: _recording(1, [True, True, False]), 2: _recording(2, [True, True, False])}
    assert LA.choose_best(recs, 3) == (1, True)
    recs[2] = _recording(2, [True, True, True])
    assert LA.choose_best(recs, 3) == (2, False)


def _bernoulli_recordings(rates, n=2000, seed=20):
    rng = random.Random(seed)
    return {i: _recording(i, [rng.random() < p for _ in range(n)]) for i, p in enumerate(rates)}


def test_positive_control_ten_point_advantage_is_supported_on_the_held_out_half():
    recs = _bernoulli_recordings([0.75, 0.75, 0.75, 0.85, 0.75, 0.75])
    rows = {i: LA.lead_row(r, [m["start_level"] for m in TEAM], r["header"]["order_indices"]) for i, r in recs.items()}
    s = LA.split_sample(recs, rows)
    assert s["chosen_lead"] == 3 and s["held_out"]["verdict"] == "A" and s["supported_gain"]
    assert s["control_discordant"] == 0
    # informational: a 5-point advantage, printed only
    recs5 = _bernoulli_recordings([0.75, 0.75, 0.75, 0.80, 0.75, 0.75], seed=21)
    rows5 = {i: LA.lead_row(r, [m["start_level"] for m in TEAM], r["header"]["order_indices"]) for i, r in recs5.items()}
    s5 = LA.split_sample(recs5, rows5)
    print(f"5-point informational case: held-out p {s5['held_out']['p']:.3g} verdict {s5['held_out']['verdict']}")


def test_negative_control_identical_leads_show_no_gain():
    base = [i % 4 != 0 for i in range(2000)]
    recs = {i: _recording(i, base) for i in range(6)}
    rows = {i: LA.lead_row(r, [m["start_level"] for m in TEAM], r["header"]["order_indices"]) for i, r in recs.items()}
    s = LA.split_sample(recs, rows)
    assert s["first_listed_already_best"] and s["chosen_lead"] == 0 and s["tied"]
    assert s["held_out"]["verdict"] == "indistinguishable" and s["held_out"]["only_chosen"] == 0 and not s["supported_gain"]


def test_screening_and_level_gains():
    recs = _bernoulli_recordings([0.75, 0.75, 0.75, 0.85, 0.75, 0.75])
    sc = LA.screening(recs)
    assert set(sc["choices"]) == {200, 400, 1000} and set(sc["agree"]) == {200, 400}
    rows = {i: LA.lead_row(r, [m["start_level"] for m in TEAM], r["header"]["order_indices"]) for i, r in recs.items()}
    lg = LA.level_gains(rows, 3)
    assert lg["chosen_gain"] == 1.0 and lg["others_mean_gain"] == 1.0 and lg["difference"] == 0.0
