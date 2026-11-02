"""018 T016: paired comparison of two player policies on the same seeds (specs/018-expectimax2-v4/contracts/python-and-cli.md).

usage: uv run python specs/018-expectimax2-v4/scripts/paired_policies.py --a <policy> --b <policy>
           [--teams bench,ref,b2main,b2branch] [--runs 2000] [--workers N] [--out runs/018-evidence/pairs] [--self]

Both policies play every team on the seeds derive_seed("018-pairs|<team>", i, 0), i < runs, against decomp-ai with
stop_on_loss, through one worker pool. Per team: McNemar exact on the discordant pairs (A = --a, B = --b), Wilson
intervals, throughput; one text block and one row appended to <out>/summary.json. Each (team, policy, runs) outcome
list is cached under <out> and reused while the pool's sim_code_hash matches, so the reference side is played once per
team over the whole ladder. `--self` plays --a twice (two independent pool passes) on the first team and requires
0 discordant pairs (pairing control). Exit 1 on any failed request or a failed control.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OPPONENT = "decomp-ai"
TEAM_NAMES = ("bench", "ref", "b2main", "b2branch")


def safe_name(policy: str) -> str:
    """A filesystem-safe, injective-enough rendering of a policy name (candidate names carry ? & =)."""
    s = policy.replace("?", "_Q_").replace("&", "__").replace("=", "-")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)


def cache_valid(entry: dict, sim_code_hash: str, n: int) -> bool:
    return bool(entry) and entry.get("sim_code_hash") == sim_code_hash and entry.get("n") == n \
        and len(entry.get("cleared", [])) == n


def summary_row(team: str, a: dict, b: dict) -> dict:
    from platsim.stats import mcnemar_exact, wilson_ci

    cmp = mcnemar_exact(a["cleared"], b["cleared"])
    return {
        "team": team, "a": a["policy"], "b": b["policy"], "n": cmp.n,
        "a_cleared": sum(a["cleared"]), "b_cleared": sum(b["cleared"]),
        "a_rate": round(cmp.a_rate, 4), "b_rate": round(cmp.b_rate, 4),
        "a_ci95": [round(x, 4) for x in wilson_ci(sum(a["cleared"]), cmp.n)],
        "b_ci95": [round(x, 4) for x in wilson_ci(sum(b["cleared"]), cmp.n)],
        "a_only": cmp.a_only, "b_only": cmp.b_only, "p_value": cmp.p_value, "verdict": cmp.verdict,
        "a_gauntlets_per_s": a["gauntlets_per_s"], "b_gauntlets_per_s": b["gauntlets_per_s"],
        "master": a["master"], "sim_code_hash": a["sim_code_hash"], "date": datetime.now().isoformat(timespec="seconds"),
    }


def row_text(r: dict) -> str:
    return (f"{r['team']}: n {r['n']}  A {r['a']} {r['a_rate']:.4f} [{r['a_ci95'][0]:.4f}, {r['a_ci95'][1]:.4f}]  "
            f"B {r['b']} {r['b_rate']:.4f} [{r['b_ci95'][0]:.4f}, {r['b_ci95'][1]:.4f}]  only A {r['a_only']} / only B {r['b_only']}  "
            f"p {r['p_value']:.3g}  verdict {r['verdict']}  speed A {r['a_gauntlets_per_s']:.2f} B {r['b_gauntlets_per_s']:.2f} gauntlets/s")


def load_team_requests(name: str, out: Path) -> list[dict]:
    """The worker-shaped team for a fixed-team name (research R3)."""
    from platsim.evaluate import load_and_validate, worker_team

    if name == "bench":
        return json.loads((REPO / "tests/fixtures/policy_benchmark_team.json").read_text())["team"]
    if name == "ref":
        team, led = load_and_validate(REPO / "tests/fixtures/reference_team.json")
        return worker_team(team, led)
    if name in ("b2main", "b2branch"):
        res = json.loads((REPO / "runs/014-evidence" / f"b2-{name[2:]}" / "result.json").read_text())
        path = out / "teams" / f"{name}.json"  # beside the pairs cache, never /tmp
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(res["team"]))
        team, led = load_and_validate(path)
        return worker_team(team, led)
    raise SystemExit(f"unknown team {name} (known: {', '.join(TEAM_NAMES)})")


def run_side(pool, team: str, team_reqs: list[dict], policy: str, n: int, out: Path, log, suffix: str = "") -> dict:
    from platsim.sim.seeds import derive_seed

    cache = out / f"{team}__{safe_name(policy)}__{n}{suffix}.json"
    if cache.exists():
        entry = json.loads(cache.read_text())
        if cache_valid(entry, pool.sim_code_hash, n):
            log(f"cache hit {cache.name} ({entry['gauntlets_per_s']:.2f} gauntlets/s when recorded)")
            return entry
        log(f"cache {cache.name} ignored: sim_code_hash {entry.get('sim_code_hash')} != pool {pool.sim_code_hash} or n differs; recomputing")
    master = f"018-pairs|{team}"
    reqs = [{"op": "gauntlet", "id": f"{policy}-{i}", "team": team_reqs, "seed": derive_seed(master, i, 0),
             "player_policy": policy, "opponent_policy": OPPONENT, "stop_on_loss": True, "log": "none"} for i in range(n)]
    t0 = time.perf_counter()
    rs = pool.map(reqs)
    wall = time.perf_counter() - t0
    bad = [r for r in rs if not r.get("ok")]
    if bad:
        raise RuntimeError(f"{len(bad)} failed requests for {policy} on {team}; first: {bad[0].get('error')}")
    for r in rs:
        if (r["player_policy"], r["opponent_policy"]) != (policy, OPPONENT):
            raise RuntimeError(f"worker ran {r['player_policy']}/{r['opponent_policy']}, requested {policy}/{OPPONENT}")
    entry = {"team": team, "policy": policy, "master": master, "n": n,
             "cleared": [bool(r["cleared"]) for r in rs], "battles_seed_0": [r["battles"][0]["seed"] for r in rs],
             "wall_s": round(wall, 3), "gauntlets_per_s": round(n / wall, 4), "sim_code_hash": pool.sim_code_hash,
             "hello": {k: pool.hello.get(k) for k in ("decomp_commit", "showdown_commit", "node_version")}}
    cache.write_text(json.dumps(entry))
    log(f"{policy} on {team}: {sum(entry['cleared'])}/{n} cleared, {wall:.1f} s, {n / wall:.2f} gauntlets/s")
    return entry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--a", required=True, help="policy A (the candidate)")
    ap.add_argument("--b", required=True, help="policy B (the reference)")
    ap.add_argument("--teams", default=",".join(TEAM_NAMES))
    ap.add_argument("--runs", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out", type=Path, default=REPO / "runs/018-evidence/pairs")
    ap.add_argument("--self", action="store_true", dest="self_check", help="pairing control: play --a twice on the first team")
    args = ap.parse_args(argv)
    from platsim.sim.pool import WorkerPool

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(f"paired_policies: {m}", file=sys.stderr, flush=True)  # noqa: E731
    teams = args.teams.split(",")[:1] if args.self_check else args.teams.split(",")
    rows = []
    with WorkerPool(args.workers) as pool:
        log(f"pool {pool.size} workers, sim_code_hash {pool.sim_code_hash}")
        for team in teams:
            team_reqs = load_team_requests(team, out)
            a = run_side(pool, team, team_reqs, args.a, args.runs, out, log)
            b = run_side(pool, team, team_reqs, args.a if args.self_check else args.b, args.runs, out, log,
                         suffix="__self2" if args.self_check else "")
            if a["battles_seed_0"] != b["battles_seed_0"]:
                raise RuntimeError(f"pairing broken on {team}: first-battle seeds differ between sides")
            row = summary_row(team, a, b)
            rows.append(row)
            print(row_text(row), flush=True)
    summary = out / "summary.json"
    existing = json.loads(summary.read_text()) if summary.exists() else []
    summary.write_text(json.dumps(existing + rows, indent=1))
    if args.self_check:
        ok = all(r["a_only"] == 0 and r["b_only"] == 0 for r in rows)
        print(f"pairing control: {'0 discordant pairs, OK' if ok else 'DISCORDANT PAIRS FOUND'}")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
