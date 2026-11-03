"""Feature 020: record 2,000 full gauntlets per lead for one team (six leads, identical seeds) through the pool.

Reuses the feature-019 helpers by path and `platsim.evaluate.run_full_gauntlets` unchanged (research R7, R8).

usage: uv run python specs/020-lead-spike/scripts/lead_runs.py --team b2main|b2branch|b2v2 [--leads 0,1,2,3,4,5] [--runs 2000] [--workers 16] [--out-dir runs/020-evidence]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "specs" / "019-e4-sampling-spike" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import assert_idle, code_hashes, eastern_now  # noqa: E402  (feature 019 helpers)
from lead_analysis import rotate  # noqa: E402

from platsim.evaluate import DEFAULT_PLAYER_POLICY, OPPONENT_POLICY, run_full_gauntlets  # noqa: E402
from platsim.sim.pool import WorkerPool  # noqa: E402
from platsim.sim.seeds import derive_seed  # noqa: E402

TEAMS = {
    "b2main": "runs/014-evidence/b2-main/result.json",
    "b2branch": "runs/014-evidence/b2-branch/result.json",
    "b2v2": "runs/018-evidence/b2-expectimax2-v2/result.json",
}


def load_team(name: str) -> list[dict]:
    return json.loads((REPO / TEAMS[name]).read_text())["team"]["builds"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True, choices=sorted(TEAMS))
    ap.add_argument("--leads", default="0,1,2,3,4,5")
    ap.add_argument("--runs", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out-dir", default=str(REPO / "runs" / "020-evidence"))
    a = ap.parse_args(argv)
    assert_idle()
    team = load_team(a.team)
    master = f"020-lead-{a.team}"
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for lead in [int(x) for x in a.leads.split(",")]:
        order_indices = [lead] + [j for j in range(len(team)) if j != lead]
        rotated = rotate(team, lead)
        start = eastern_now()
        t0 = time.perf_counter()
        with WorkerPool(a.workers) as pool:
            sim_hash = pool.sim_code_hash
            full = run_full_gauntlets(pool, rotated, master=master, min_runs=a.runs, max_runs=a.runs, target=None,
                                      player_policy=DEFAULT_PLAYER_POLICY, log="summary")
        wall = time.perf_counter() - t0
        results = full.results
        if len(results) != a.runs:
            raise SystemExit(f"lead {lead}: expected {a.runs} results, got {len(results)}")
        header = {"header": True, "team": a.team, "lead_index": lead, "lead_species": team[lead]["species"],
                  "order": [m["species"] for m in rotated], "order_indices": order_indices,
                  "builds": [(m["species"], m["start_level"]) for m in team], "master": master, "runs": a.runs,
                  "workers": a.workers, "player_policy": results[0]["player_policy"],
                  "opponent_policy": results[0]["opponent_policy"], "requested_opponent": OPPONENT_POLICY,
                  "pool_sim_code_hash": sim_hash, **code_hashes(), "start": start, "end": eastern_now(),
                  "wall_s": round(wall, 1), "gauntlets_per_s": round(a.runs / wall, 2)}
        path = out_dir / f"{a.team}-lead{lead}.jsonl"
        with path.open("w") as f:
            f.write(json.dumps(header) + "\n")
            for i, r in enumerate(results):
                f.write(json.dumps({"run": i, "seed": derive_seed(master, i, 0), "cleared": bool(r["cleared"]),
                                    "battles": [{k: b[k] for k in ("trainer", "won", "end", "turns", "log_hash")} for b in r["battles"]],
                                    "final_levels": r["final_levels"]}) + "\n")
        wins = sum(bool(r["cleared"]) for r in results)
        per = {}
        for r in results:
            for b in r["battles"]:
                d = per.setdefault(b["trainer"], [0, 0]); d[0] += 1; d[1] += bool(b["won"])
        print(json.dumps({"team": a.team, "lead": lead, "species": team[lead]["species"], "cleared": wins,
                          "clear_rate": wins / a.runs, "per_trainer": {t: round(v[1] / v[0], 4) for t, v in per.items()},
                          "wall_s": round(wall, 1), "gauntlets_per_s": round(a.runs / wall, 2), "file": str(path)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
