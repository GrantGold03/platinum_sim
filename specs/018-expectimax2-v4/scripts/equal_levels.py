"""018 T029: equal-levels paired comparison (feature-010 rule) of the v2 and v4 optimizer results on B2.

usage: uv run python specs/018-expectimax2-v4/scripts/equal_levels.py <v2_out_dir> <v4_out_dir> <runs> [--self]
A = the v4 optimizer's final team, B = the v2 optimizer's final team; both are set to A's start levels, validated, and
played by the reference player expectimax2-v2 on the same seeds (master '018-equal|B2'). --self plays B against itself
(pairing control; expects 0 discordant pairs). Adapted from specs/014-damage-boost-items/scripts/equal_levels.py.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from platsim.evaluate import final_level_stats, load_and_validate, run_full_gauntlets, worker_team
from platsim.sim.pool import WorkerPool
from platsim.stats import mcnemar_exact

REFERENCE_PLAYER = "expectimax2-v2"
v2_dir, v4_dir, runs = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
self_check = "--self" in sys.argv

b_team = json.loads((v2_dir / "result.json").read_text())["team"]  # B = v2 result
a_team = json.loads((v4_dir / "result.json").read_text())["team"]  # A = v4 result
if self_check:
    a_team = b_team
levels = [b["start_level"] for b in a_team["builds"]]


def at_levels(team: dict, name: str):
    t = json.loads(json.dumps(team))
    for b, lv in zip(t["builds"], levels, strict=True):
        b["start_level"] = lv
    path = v4_dir / f"equal_{name}.json"  # beside the v4 result, not under specs/
    path.write_text(json.dumps(t))
    return load_and_validate(path)  # raises InvalidTeamInput (with violations) if illegal at these levels


(a_valid, led), (b_valid, _) = at_levels(a_team, "a"), at_levels(b_team, "b")
print(f"levels {levels}; A(v4) items {[b['held_item'] for b in a_team['builds']]} species {[b['species'] for b in a_team['builds']]}; "
      f"B(v2) items {[b['held_item'] for b in b_team['builds']]} species {[b['species'] for b in b_team['builds']]}; player {REFERENCE_PLAYER}")
t0 = time.time()
pool = WorkerPool(None)
try:
    kw = dict(master="018-equal|B2", min_runs=runs, max_runs=runs, target=None, player_policy=REFERENCE_PLAYER)
    ra = run_full_gauntlets(pool, worker_team(a_valid, led), **kw).results
    rb = run_full_gauntlets(pool, worker_team(b_valid, led), **kw).results
finally:
    pool.close()
cmp = mcnemar_exact([bool(r["cleared"]) for r in ra], [bool(r["cleared"]) for r in rb])
_, avg_a, _ = final_level_stats(ra, len(levels))
_, avg_b, _ = final_level_stats(rb, len(levels))
print(f"n {cmp.n}: A(v4 result) {cmp.a_rate:.4f} vs B(v2 result) {cmp.b_rate:.4f}, only {cmp.a_only}/{cmp.b_only}, "
      f"p {cmp.p_value:.4g}, verdict {cmp.verdict}")
print(f"mean final level (cleared runs): A {avg_a} vs B {avg_b}")
print(f"wall {time.time() - t0:.1f} s")
if self_check:
    ok = cmp.a_only == 0 and cmp.b_only == 0
    print(f"pairing control: {'0 discordant pairs, OK' if ok else 'DISCORDANT PAIRS FOUND'}")
    sys.exit(0 if ok else 1)
