"""The confirm stage's borderline extension stops at the preset cap (research R8, budget.py).

A stand-in pool returns a team that clears exactly 3 of every 4 gauntlets, so its clear-rate CI
straddles 0.75 at every n: without a cap the extension would run to max_runs (20,000).
"""

from platsim.budget import get_preset
from platsim.evaluate import OPPONENT_POLICY, run_full_gauntlets
from platsim.stats import wilson_ci


class AtThresholdPool:
    size = 16

    def __init__(self):
        self.calls = 0

    def map(self, reqs):
        out = []
        for _ in reqs:
            out.append({"ok": True, "cleared": self.calls % 4 != 0, "player_policy": "p",
                        "opponent_policy": OPPONENT_POLICY, "battles": []})
            self.calls += 1
        return out


def _run(borderline_max_runs):
    pool = AtThresholdPool()
    runs = run_full_gauntlets(pool, [], master="m", min_runs=2000, max_runs=20_000, target=0.02,
                              player_policy="p", borderline_threshold=0.75,
                              borderline_max_runs=borderline_max_runs)
    return pool, runs


def test_standard_cap_stops_at_4000_and_stays_borderline():
    cap = get_preset("standard").borderline_max_runs
    assert cap == 4000
    pool, runs = _run(cap)
    n = len(runs.results)
    wins = sum(r["cleared"] for r in runs.results)
    assert n == cap == pool.calls  # stopped at the cap, not at max_runs
    lo, hi = wilson_ci(wins, n)
    assert lo < 0.75 <= hi  # still undecided -> reported borderline (not qualified) by evaluate_team


def test_positive_control_without_cap_runs_to_max_runs():
    pool, runs = _run(None)
    assert len(runs.results) == 20_000  # the old behaviour this change prevents


def test_quick_preset_has_no_extension_and_thorough_cap():
    assert get_preset("quick").borderline_max_runs is None
    assert get_preset("thorough").borderline_max_runs == 10_000
