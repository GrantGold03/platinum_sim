"""`platsim bench`: time the battle player on the fixed seed set (feature 015, contracts/bench-tool.md).

Two halves. The single-process half runs `node sim/bench.mjs --json`, which owns the request set, the
policy counters (ms per decision, trainer-AI calls and draws) and the two result digests. The pool half
builds the same requests here and times them through the optimizer's `WorkerPool`, reporting wall time,
gauntlets/s, the workers' `sim_code_hash` and `digest_logs` computed from the pool's results with the same
line format. When both halves ran, the two `digest_logs` must agree (the pool ran the same battles with the
same decisions), otherwise the command prints both and exits 1.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from platsim.sim.pool import WorkerPool
from platsim.evaluate import DEFAULT_PLAYER_POLICY

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCH_MJS = REPO_ROOT / "sim" / "bench.mjs"
TEAM_FILES = {
    "bench": ("tests/fixtures/policy_benchmark_team.json", "team"),
    "ref": ("tests/fixtures/reference_team.json", "builds"),
}
LEAGUE = ["aaron", "bertha", "flint", "lucian", "cynthia"]
DEFAULT_POLICY = DEFAULT_PLAYER_POLICY  # 018: the one default strong player


class BenchError(Exception):
    pass


def load_team(name: str) -> list[dict]:
    if name not in TEAM_FILES:
        raise BenchError(f"unknown bench team {name!r} (known: {', '.join(TEAM_FILES)})")
    rel, key = TEAM_FILES[name]
    return json.loads((REPO_ROOT / rel).read_text())[key]


def bench_requests(*, block: str = "a", n: int = 20, teams=("bench", "ref"), trainers=None,
                   policy: str = DEFAULT_POLICY, battle_style: str = "set") -> list[dict]:
    """The fixed set, as worker requests: same seeds and teams as `benchRequests` in sim/bench.mjs."""
    out = []
    for tn in teams:
        team = load_team(tn)
        for i in range(n):
            req = {"op": "gauntlet", "team": team, "seed": f"prof-{block}-{tn}-{i}", "player_policy": policy,
                   "opponent_policy": "decomp-ai", "stop_on_loss": False}
            if trainers:
                req["trainers"] = list(trainers)
            if battle_style != "set":  # 023: the Set requests are unchanged
                req["battle_style"] = battle_style
            out.append(req)
    return out


def log_line(result: dict, seed: str) -> str:
    battles = ";".join(f"{b['trainer']}:{b['end']}:{b['turns']}:{b['log_hash']}" for b in result["battles"])
    levels = ",".join(str(x) for x in result["final_levels"])
    return f"{seed}|{1 if result['cleared'] else 0}|{levels}|{battles}\n"


def digest_logs(results, seeds) -> str:
    h = hashlib.sha256()
    for r, seed in zip(results, seeds, strict=True):
        h.update(log_line(r, seed).encode("utf-8"))
    return h.hexdigest()


def run_single_node(*, policy: str, n: int, block: str, teams, trainers) -> dict:
    cmd = ["node", str(BENCH_MJS), "--json", "--policy", policy, "--n", str(n), "--block", block,
           "--teams", ",".join(teams), "--trainers", ",".join(trainers or LEAGUE)]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise BenchError(f"node sim/bench.mjs exited {proc.returncode}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def run_pool(requests: list[dict], workers: int) -> dict:
    with WorkerPool(workers) as pool:
        hello_hash = pool.sim_code_hash
        t0 = time.perf_counter()
        results = pool.map(requests)
        wall = time.perf_counter() - t0
    errors = [r for r in results if not r.get("ok")]
    if errors:
        raise BenchError(f"{len(errors)} of {len(results)} pool requests failed: {errors[0].get('error')}")
    return {
        "pool_workers": workers,
        "pool_gauntlets": len(results),
        "pool_cleared": sum(1 for r in results if r.get("cleared")),
        "pool_wall_s": round(wall, 3),
        "pool_gauntlets_per_s": round(len(results) / wall, 4),
        "pool_sim_code_hash": hello_hash,
        "pool_digest_logs": digest_logs(results, [r["seed"] for r in requests]),
    }


def _table(out: dict) -> str:
    rows = [("policy", out["policy"]),
            ("set", f"block {out['block']}, n {out['n']}, teams {','.join(out['teams'])}, trainers {','.join(out['trainers'])}")]
    if "gauntlets_per_s" in out:
        rows += [("single: gauntlets/s", out["gauntlets_per_s"]), ("single: wall", f"{out['wall_s']} s"),
                 ("single: ms/decision", out.get("ms_per_decision")), ("single: AI calls/decision", out.get("ai_calls_per_decision")),
                 ("single: AI draws", out.get("ai_draws")),
                 ("single: interpreter steps", out.get("interp_steps")), ("single: interpreter dispatches", out.get("interp_dispatches")),
                 ("single: digest_full", out["digest_full"]),
                 ("single: digest_logs", out["digest_logs"]), ("single: sim_code_hash", out["sim_code_hash"])]
    if "pool_gauntlets_per_s" in out:
        rows += [(f"pool ({out['pool_workers']} workers): gauntlets/s", out["pool_gauntlets_per_s"]),
                 ("pool: wall", f"{out['pool_wall_s']} s"), ("pool: cleared", f"{out['pool_cleared']}/{out['pool_gauntlets']}"),
                 ("pool: digest_logs", out["pool_digest_logs"]), ("pool: sim_code_hash", out["pool_sim_code_hash"])]
    if "digests_agree" in out:
        rows.append(("digests agree", out["digests_agree"]))
    width = max(len(k) for k, _ in rows)
    return "\n".join(f"{k.ljust(width)}  {v}" for k, v in rows)


def run(args) -> int:
    teams = args.teams
    trainers = args.trainers or LEAGUE
    workers = args.workers or os.cpu_count() or 1
    out: dict = {"policy": args.policy, "block": args.block, "n": args.n, "teams": list(teams), "trainers": list(trainers)}
    try:
        if not args.no_single:
            print("platsim bench: single process (node sim/bench.mjs) ...", file=sys.stderr)
            single = run_single_node(policy=args.policy, n=args.n, block=args.block, teams=teams, trainers=trainers)
            out.update({k: v for k, v in single.items() if k not in ("policy", "block", "n", "teams", "trainers")})
        requests = bench_requests(block=args.block, n=args.n, teams=teams, trainers=args.trainers, policy=args.policy)
        print(f"platsim bench: {len(requests)} gauntlets on {workers} workers ...", file=sys.stderr)
        out.update(run_pool(requests, workers))
    except BenchError as e:
        print(f"platsim bench: {e}", file=sys.stderr)
        return 1
    status = 0
    if "digest_logs" in out:
        out["digests_agree"] = out["digest_logs"] == out["pool_digest_logs"]
        if not out["digests_agree"]:
            print(f"platsim bench: pool digest_logs {out['pool_digest_logs']} != single-process {out['digest_logs']}",
                  file=sys.stderr)
            status = 1
    print(json.dumps(out, indent=1) if args.json else _table(out))
    return status
