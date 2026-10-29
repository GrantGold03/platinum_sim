"""014 T015: equal-levels paired comparison (010 rule) of two optimizer results.

usage: equal_levels.py <main_out_dir> <branch_out_dir> <runs> [--self]
Both final teams are set to the branch team's start levels, validated, and played on the same seeds
(master '014-equal|B2'). A = branch, B = main. --self plays main against itself (pairing control).
"""
import json
import sys
import time
from pathlib import Path

from platsim.evaluate import final_level_stats, load_and_validate, run_full_gauntlets, worker_team
from platsim.sim.pool import WorkerPool
from platsim.stats import mcnemar_exact

main_dir, branch_dir, runs = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
self_check = "--self" in sys.argv

main_team = json.loads((main_dir / "result.json").read_text())["team"]
branch_team = json.loads((branch_dir / "result.json").read_text())["team"]
if self_check:
    branch_team = main_team
levels = [b["start_level"] for b in branch_team["builds"]]


def at_levels(team: dict, name: str):
    t = json.loads(json.dumps(team))
    for b, lv in zip(t["builds"], levels, strict=True):
        b["start_level"] = lv
    path = branch_dir / f"equal_{name}.json"  # beside the branch result, not under specs/
    path.write_text(json.dumps(t))
    return load_and_validate(path)  # raises InvalidTeamInput (with violations) if illegal at these levels


(a_team, led), (b_team, _) = at_levels(branch_team, "a"), at_levels(main_team, "b")
print(f"levels {levels}; A items {[b['held_item'] for b in branch_team['builds']]}; "
      f"B items {[b['held_item'] for b in main_team['builds']]}")
t0 = time.time()
pool = WorkerPool(None)
try:
    kw = dict(master="014-equal|B2", min_runs=runs, max_runs=runs, target=None, player_policy="expectimax2-v2")
    ra = run_full_gauntlets(pool, worker_team(a_team, led), **kw).results
    rb = run_full_gauntlets(pool, worker_team(b_team, led), **kw).results
finally:
    pool.close()
cmp = mcnemar_exact([bool(r["cleared"]) for r in ra], [bool(r["cleared"]) for r in rb])
_, avg_a, _ = final_level_stats(ra, len(levels))
_, avg_b, _ = final_level_stats(rb, len(levels))
print(f"n {cmp.n}: A(branch) {cmp.a_rate:.4f} vs B(main) {cmp.b_rate:.4f}, only {cmp.a_only}/{cmp.b_only}, "
      f"p {cmp.p_value:.4g}, verdict {cmp.verdict}")
print(f"mean final level (cleared runs): A {avg_a} vs B {avg_b}")
print(f"wall {time.time() - t0:.1f} s")
