"""Feature 019, US2: record per-run, per-battle outcomes for N full gauntlets of one team through the worker pool.

Reuses `platsim.evaluate.run_full_gauntlets` unchanged (stop_on_loss on, log "summary" so every Cynthia battle carries
its `state_before`). Output: JSON lines, a header line then one line per run in index order (contracts/scripts.md).

usage: uv run python specs/019-e4-sampling-spike/scripts/record_runs.py --team ref|b3|file:<team.json> [--runs 2000] [--workers 16] --out FILE
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CHAMPION, REPO, assert_idle, code_hashes, eastern_now  # noqa: E402

from platsim.evaluate import DEFAULT_PLAYER_POLICY, OPPONENT_POLICY, run_full_gauntlets  # noqa: E402
from platsim.sim.pool import WorkerPool  # noqa: E402
from platsim.sim.seeds import derive_seed  # noqa: E402

TEAMS = {
    "ref": ("tests/fixtures/reference_team.json", "builds"),
    "b3": ("runs/bench-010/B3/result.json", "team.builds"),
    "b2v2": ("runs/018-evidence/b2-expectimax2-v2/result.json", "team.builds"),
}


def load_team(spec: str) -> tuple[str, list[dict]]:
    if spec.startswith("file:"):
        path, name = Path(spec[5:]), Path(spec[5:]).stem
        d = json.loads(path.read_text())
    else:
        rel, key = TEAMS[spec]
        name, d = spec, json.loads((REPO / rel).read_text())
        for k in key.split("."):
            d = d[k]
        return name, d
    if "builds" in d:
        return name, d["builds"]
    return name, d["team"]["builds"]


def slim_battle(b: dict) -> dict:
    out = {k: b[k] for k in ("trainer", "won", "end", "turns", "log_hash")}
    if b["trainer"] == CHAMPION and "state_before" in b:
        out["state_before"] = b["state_before"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True)
    ap.add_argument("--runs", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--master", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    assert_idle()
    name, team = load_team(a.team)
    master = a.master or f"019-record-{name}"
    start = eastern_now()
    t0 = time.perf_counter()
    with WorkerPool(a.workers) as pool:
        sim_hash = pool.sim_code_hash
        full = run_full_gauntlets(pool, team, master=master, min_runs=a.runs, max_runs=a.runs, target=None,
                                  player_policy=DEFAULT_PLAYER_POLICY, log="summary")
    wall = time.perf_counter() - t0
    results = full.results
    if len(results) != a.runs:
        raise SystemExit(f"expected {a.runs} results, got {len(results)}")
    for i, r in enumerate(results):
        for b in r["battles"]:
            if b["trainer"] == CHAMPION and "state_before" not in b:
                raise SystemExit(f"run {i}: Cynthia battle without state_before")
    header = {"header": True, "team": name, "builds": [(b["species"], b["start_level"]) for b in team], "master": master,
              "runs": a.runs, "workers": a.workers, "player_policy": results[0]["player_policy"],
              "opponent_policy": results[0]["opponent_policy"], "requested_opponent": OPPONENT_POLICY,
              "pool_sim_code_hash": sim_hash, **code_hashes(), "start": start, "end": eastern_now(),
              "wall_s": round(wall, 1), "gauntlets_per_s": round(a.runs / wall, 2)}
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        f.write(json.dumps(header) + "\n")
        for i, r in enumerate(results):
            f.write(json.dumps({"run": i, "seed": derive_seed(master, i, 0), "cleared": bool(r["cleared"]),
                                "battles": [slim_battle(b) for b in r["battles"]],
                                "final_levels": r["final_levels"]}) + "\n")
    cleared = sum(bool(r["cleared"]) for r in results)
    per = {}
    for r in results:
        for b in r["battles"]:
            d = per.setdefault(b["trainer"], [0, 0]); d[0] += 1; d[1] += bool(b["won"])
    print(json.dumps({**header, "cleared": cleared, "clear_rate": cleared / a.runs,
                      "per_trainer": {t: {"battles": v[0], "rate": round(v[1] / v[0], 4)} for t, v in per.items()}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
