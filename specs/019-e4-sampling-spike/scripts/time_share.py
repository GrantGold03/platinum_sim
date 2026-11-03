"""Feature 019, US3: Elite Four share of wall time on the real worker pool, level-search style (research R4, R5).

Per team and batch size: the same requests run once plain and once with the timing hook loaded into every worker
(NODE_OPTIONS=--import=.../hooks/register.mjs). The pool-side `digest_logs` of both result lists must be identical
(the harness changes nothing but timing) before any share is computed from the hook's side files.

usage: uv run python specs/019-e4-sampling-spike/scripts/time_share.py [--teams ref,b3,b2v2] [--batches 50,100,200] [--workers 16] --out FILE
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CHAMPION, E4, EVIDENCE, REPO, assert_idle, code_hashes, eastern_now  # noqa: E402
from record_runs import load_team  # noqa: E402

from platsim.bench import digest_logs  # noqa: E402
from platsim.evaluate import DEFAULT_PLAYER_POLICY, OPPONENT_POLICY  # noqa: E402
from platsim.sim.pool import WorkerPool  # noqa: E402
from platsim.sim.seeds import derive_seed  # noqa: E402

HOOK = Path(__file__).resolve().parent / "hooks" / "register.mjs"
TIMING_DIR = EVIDENCE / "timing"


def requests_for(team: list[dict], name: str, n: int) -> list[dict]:
    return [{"op": "gauntlet", "team": team, "seed": derive_seed(f"019-time-{name}", i, 0),
             "player_policy": DEFAULT_PLAYER_POLICY, "opponent_policy": OPPONENT_POLICY,
             "stop_on_loss": True, "log": "summary"} for i in range(n)]


def run_pool(reqs: list[dict], workers: int, hooked: bool) -> tuple[list[dict], float]:
    env = dict(os.environ)
    if hooked:
        env["NODE_OPTIONS"] = f"--import={HOOK}"
        env["PLATSIM_TIMING_DIR"] = str(TIMING_DIR)
    t0 = time.perf_counter()
    with WorkerPool(workers, env=env) as pool:
        results = pool.map(reqs)
    wall = time.perf_counter() - t0
    for r in results:
        if not r.get("ok"):
            raise SystemExit(f"gauntlet failed: {r.get('error')}")
    return results, wall


def read_side_files() -> list[dict]:
    rows = []
    for f in sorted(TIMING_DIR.glob("*.jsonl")):
        rows += [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
        f.unlink()
    return rows


def aggregate(rows: list[dict], wall: float, workers: int, n_batch: int) -> dict:
    per = defaultdict(lambda: {"battles": 0, "turns": 0, "decisions": 0, "battle_s": 0.0})
    for r in rows:
        d = per[r["trainer"]]
        d["battles"] += 1
        d["turns"] += r["turns"]
        d["decisions"] += r["decisions"]
        d["battle_s"] += r["ns"] / 1e9
    total = sum(d["battle_s"] for d in per.values())
    e4 = sum(per[t]["battle_s"] for t in E4 if t in per)
    out = {t: {**d, "s_per_battle": d["battle_s"] / d["battles"], "turns_per_battle": d["turns"] / d["battles"],
               "decisions_per_battle": d["decisions"] / d["battles"]} for t, d in per.items()}
    return {"per_trainer": out, "battle_s_total": total, "e4_share_battle": (e4 / total) if total else None,
            "e4_share_wall": (e4 / (wall * workers)) if wall else None, "overhead_s": wall - total / workers,
            "wall_per_gauntlet_s": wall / n_batch, "cpu_s_per_gauntlet": total / n_batch,
            "cynthia_s_per_battle": out[CHAMPION]["s_per_battle"] if CHAMPION in out else None,
            "battles_recorded": len(rows)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teams", default="ref,b3,b2v2")
    ap.add_argument("--batches", default="50,100,200")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", default=str(EVIDENCE / "time_share.json"))
    a = ap.parse_args(argv)
    assert_idle()
    TIMING_DIR.mkdir(parents=True, exist_ok=True)
    for f in TIMING_DIR.glob("*.jsonl"):
        f.unlink()
    out = {"start": eastern_now(), "workers": a.workers, **code_hashes(), "measurements": []}
    for spec in a.teams.split(","):
        name, team = load_team(spec)
        for b in [int(x) for x in a.batches.split(",")]:
            reqs = requests_for(team, name, b)
            seeds = [r["seed"] for r in reqs]
            plain, wall_plain = run_pool(reqs, a.workers, hooked=False)
            hooked, wall_hooked = run_pool(reqs, a.workers, hooked=True)
            d_plain, d_hooked = digest_logs(plain, seeds), digest_logs(hooked, seeds)
            rows = read_side_files()
            m = {"team": name, "batch_size": b, "digest_plain": d_plain, "digest_hooked": d_hooked,
                 "digests_equal": d_plain == d_hooked, "wall_plain_s": wall_plain, "wall_hooked_s": wall_hooked,
                 "cleared": sum(bool(r["cleared"]) for r in plain)}
            if d_plain != d_hooked:
                out["measurements"].append(m)
                Path(a.out).write_text(json.dumps(out, indent=1))
                raise SystemExit(f"{name} batch {b}: digests differ ({d_plain[:12]} vs {d_hooked[:12]}); harness invalid")
            m.update(aggregate(rows, wall_hooked, a.workers, b))
            m["kill_flag"] = (name == "ref" and b == 200 and m["e4_share_battle"] is not None and m["e4_share_battle"] < 0.40)
            out["measurements"].append(m)
            print(f"{name} batch {b}: digests equal {m['digests_equal']}; wall plain {wall_plain:.1f}s hooked {wall_hooked:.1f}s; "
                  f"E4 share of battle time {m['e4_share_battle']:.3f}, of wall x workers {m['e4_share_wall']:.3f}; overhead {m['overhead_s']:.1f}s; "
                  f"cleared {m['cleared']}/{b}; battles recorded {m['battles_recorded']}; "
                  + "; ".join(f"{t} {v['s_per_battle']:.3f}s/{v['turns_per_battle']:.1f}t/{v['decisions_per_battle']:.1f}d" for t, v in m["per_trainer"].items()))
            Path(a.out).write_text(json.dumps(out, indent=1))
    out["end"] = eastern_now()
    Path(a.out).write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
