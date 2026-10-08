"""T058: `platsim optimize` end to end with the `quick` budget (spec User Story 1, SC-001, SC-002, SC-004;
contracts/cli.md; Constitution III/IV).

Runs the optimizer twice on the same six species and seed, with different worker counts and output
directories (so the second run cannot resume from the first's state.json), and asserts:
- result.json is byte-identical across the two runs (determinism independent of worker count);
- the report carries every provenance field (Constitution IV) and the `quick` label (research R8);
- the optimized team passes the independent validator (or the run is an explicit "no qualifying team"
  report, SC-001), and team.txt re-imports to the same team.

Slow (two full quick optimizations with expectimax2-v2; about 20-40 min each on 16 workers).
PLATSIM_OPTIMIZE_WORKERS sets the first run's pool size (default os.cpu_count()); the second uses 7.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from platsim.legality.models import import_team
from platsim.legality.validator import _showdown_key, validate
from platsim.report.json_report import QUICK_WARNING

SPECIES = ["infernape", "staraptor", "luxray", "garchomp", "gyarados", "gardevoir"]
PROVENANCE = ("n_runs", "clear_rate", "clear_ci95", "per_battle", "champion_rate", "champion_ci95", "champion_battles",
              "opponent_policy", "player_policy", "seeds", "decomp_commit", "showdown_commit",
              "divergence_ledger_version", "budget_preset", "threshold", "objective", "qualified", "borderline")


def _optimize(out, workers: str) -> tuple[subprocess.CompletedProcess, float]:
    cmd = [sys.executable, "-m", "platsim.cli", "optimize", *SPECIES, "--budget", "quick", "--seed", "t058",
           "--workers", workers, "--out", str(out)]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p, time.perf_counter() - t0


def test_optimize_quick_deterministic_and_legal(tmp_path):
    w1 = os.environ.get("PLATSIM_OPTIMIZE_WORKERS", str(os.cpu_count()))
    p1, t1 = _optimize(tmp_path / "a", w1)
    print(f"\nrun 1 ({w1} workers, {t1:.0f}s) exit {p1.returncode}\n{p1.stdout}\n{p1.stderr[-3000:]}")
    assert p1.returncode == 0, p1.stderr[-3000:]
    p2, t2 = _optimize(tmp_path / "b", "7")
    print(f"run 2 (7 workers, {t2:.0f}s) exit {p2.returncode}")
    assert p2.returncode == 0, p2.stderr[-3000:]

    j1 = (tmp_path / "a" / "result.json").read_bytes()
    j2 = (tmp_path / "b" / "result.json").read_bytes()
    assert j1 == j2, "result.json differs between two runs with the same seed"

    r = json.loads(j1)
    for k in PROVENANCE:
        assert k in r, k
    assert r["budget_preset"] == "quick" and not r["qualified"]
    assert QUICK_WARNING in r["warnings"]
    assert r["seeds"]["master"] and r["seeds"]["scheme"]
    opt = r["provenance"]["optimizer"]
    assert opt["budget_preset"]["name"] == "quick"
    assert opt["policy_per_stage"]["screen"] == "greedy-v1" and opt["policy_per_stage"]["confirm"] == "expectimax2-v2"
    assert r["player_policy"] == "expectimax2-v2" and r["opponent_policy"] == "decomp-ai"
    for name in ("result.xlsx", "result.csv", "team.txt", "state.json"):
        assert (tmp_path / "a" / name).is_file(), name

    if r["no_qualifying"] is not None:  # SC-001: an explicit report, never a failing team
        assert r["team"] is None and r["no_qualifying"]["best_levels"]
        return
    team = r["team"]
    assert validate({"builds": team["builds"]}) == []
    assert r["final_level_gap_max"] <= 10
    assert r["clear_rate"] >= r["threshold"]
    sets = import_team((tmp_path / "a" / "team.txt").read_text(), key_of=_showdown_key)
    assert len(sets) == 6
    for s, b in zip(sets, team["builds"]):
        assert s.level == b["start_level"]
        assert s.ability == b["ability"]
        assert [m.removeprefix("MOVE_").lower() for m in s.moves] == [m["move"] for m in b["moves"]]
        assert (s.item or None) == (f"ITEM_{b['held_item'].upper()}" if b["held_item"] else None)
        assert s.species.removeprefix("SPECIES_").lower() == b["species"]
        assert dict(s.ivs) == b["ivs"] and dict(s.evs) == b["evs"]
