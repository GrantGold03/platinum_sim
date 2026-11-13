"""025 T018: equal-levels paired comparison (the 010 rule) of the pre-feature and branch B2 optimizer winners.

usage: uv run python specs/025-h4-wide-lens-razor-claw/scripts/equal_levels.py <b_dir> <a_dir> <runs> [--self]
B = the first dir's final team (today's code), A = the second dir's (the branch); both are set to A's start levels, validated,
and played by expectimax2-v4 on the same seeds (master '025-equal|B2', today's default battle style). Prints one JSON line
last: n, a_rate, b_rate, a_only, b_only, p_value, verdict (A = branch better, B = today's better), mean final levels, levels,
wall_s. --self plays B against itself (pairing control; exit 1 unless 0 discordant pairs). Adapted from the 018 script.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from platsim.evaluate import DEFAULT_PLAYER_POLICY, final_level_stats, load_and_validate, run_full_gauntlets, worker_team
from platsim.sim.pool import WorkerPool
from platsim.stats import mcnemar_exact

REFERENCE_PLAYER = DEFAULT_PLAYER_POLICY  # expectimax2-v4
b_dir, a_dir, runs = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
self_check = "--self" in sys.argv

b_team = json.loads((b_dir / "result.json").read_text())["team"]
a_team = json.loads((a_dir / "result.json").read_text())["team"]
if self_check:
    a_team = b_team
levels = [b["start_level"] for b in a_team["builds"]]


def at_levels(team: dict, name: str):
    t = json.loads(json.dumps(team))
    for b, lv in zip(t["builds"], levels, strict=True):
        b["start_level"] = lv
    path = a_dir / f"equal_{name}.json"  # beside the branch result, under runs/
    path.write_text(json.dumps(t))
    return load_and_validate(path)  # raises InvalidTeamInput (with violations) if illegal at these levels


(a_valid, led), (b_valid, _) = at_levels(a_team, "a"), at_levels(b_team, "b")
print(f"levels {levels}; A(branch) moves {[[m['move'] for m in b['moves']] for b in a_team['builds']]}; "
      f"B(today) moves {[[m['move'] for m in b['moves']] for b in b_team['builds']]}; player {REFERENCE_PLAYER}", file=sys.stderr)
t0 = time.time()
pool = WorkerPool(None)
try:
    kw = dict(master="025-equal|B2", min_runs=runs, max_runs=runs, target=None, player_policy=REFERENCE_PLAYER)
    ra = run_full_gauntlets(pool, worker_team(a_valid, led), **kw).results
    rb = run_full_gauntlets(pool, worker_team(b_valid, led), **kw).results
finally:
    pool.close()
cmp = mcnemar_exact([bool(r["cleared"]) for r in ra], [bool(r["cleared"]) for r in rb])
_, avg_a, _ = final_level_stats(ra, len(levels))
_, avg_b, _ = final_level_stats(rb, len(levels))
out = {"n": cmp.n, "a_rate": round(cmp.a_rate, 4), "b_rate": round(cmp.b_rate, 4), "a_only": cmp.a_only, "b_only": cmp.b_only,
       "p_value": cmp.p_value, "verdict": cmp.verdict, "mean_final_level_a": avg_a, "mean_final_level_b": avg_b,
       "levels": levels, "player": REFERENCE_PLAYER, "wall_s": round(time.time() - t0, 1)}
print(json.dumps(out))
if self_check:
    ok = cmp.a_only == 0 and cmp.b_only == 0
    print(f"pairing control: {'0 discordant pairs, OK' if ok else 'DISCORDANT PAIRS FOUND'}", file=sys.stderr)
    sys.exit(0 if ok else 1)
