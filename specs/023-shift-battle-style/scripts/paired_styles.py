"""023 T019: paired comparison of the Shift and Set battle styles on the same seeds (spec FR-012, research R8).

usage: uv run python specs/023-shift-battle-style/scripts/paired_styles.py
           [--teams ref,b2main,b2branch,b3] [--runs 2000] [--workers 16] [--policy expectimax2-v4]
           [--out runs/023-evidence/pairs] [--self] [--b2quick]

Every team plays the seeds derive_seed("023-pairs|<team>", i, 0), i < runs, under battle_style set and shift with the
same player and decomp-ai, stop_on_loss, log 'summary' (so per-battle records carry the Shift offers), through one
worker pool. Per team: clear rate and Wilson interval per style, McNemar exact (A = shift, B = set), per-trainer pass
rates per style, offers / switches / outcomes of prompted battles under Shift, gauntlets/s per style and the wall
ratio. Each (team, style, policy, runs) outcome list is cached under <out> while the pool's sim_code_hash matches.
`--self` plays Shift twice on the first team and requires 0 discordant pairs (pairing control). `--b2quick` runs the
B2 quick optimize (garchomp infernape staraptor rotom floatzel weavile, --budget quick --seed 014-b2) under each style
into runs/023-evidence/b2quick-<style>/ and reports winner, levels, the confirmation's clear rate and wall. Exit 1 on
any failed request or a failed control. Measurements must run alone (assert_idle).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OPPONENT = "decomp-ai"
TEAM_NAMES = ("ref", "b2main", "b2branch", "b3")
STYLES = ("shift", "set")
EVIDENCE = REPO / "runs" / "023-evidence"
B2_SPECIES = ["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"]
B2_SEED = "014-b2"

sys.path.insert(0, str(REPO / "specs" / "019-e4-sampling-spike" / "scripts"))
from common import assert_idle, eastern_now  # noqa: E402  (feature 019 helpers)


def _load_018():
    """The 018 pairing script's team loaders (registered in sys.modules before exec: the 019 lesson)."""
    path = REPO / "specs" / "018-expectimax2-v4" / "scripts" / "paired_policies.py"
    spec = importlib.util.spec_from_file_location("paired_policies_018", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["paired_policies_018"] = mod
    spec.loader.exec_module(mod)
    return mod


def team_requests(name: str, out: Path) -> list[dict]:
    p018 = _load_018()
    if name == "b3":
        from platsim.evaluate import load_and_validate, worker_team

        src = REPO / "runs" / "bench-010" / "B3" / "result.json"
        path = EVIDENCE / "teams" / "b3.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(json.loads(src.read_text())["team"]))
        team, led = load_and_validate(path)
        return worker_team(team, led)
    return p018.load_team_requests(name, out)


def cache_valid(entry: dict, sim_code_hash: str, n: int) -> bool:
    return bool(entry) and entry.get("sim_code_hash") == sim_code_hash and entry.get("n") == n and len(entry.get("cleared", [])) == n


def run_side(pool, team: str, team_reqs: list[dict], style: str, policy: str, n: int, out: Path, log, suffix: str = "") -> dict:
    from platsim.sim.seeds import derive_seed

    cache = out / f"{team}__{style}__{policy}__{n}{suffix}.json"
    if cache.exists():
        entry = json.loads(cache.read_text())
        if cache_valid(entry, pool.sim_code_hash, n):
            log(f"cache hit {cache.name}")
            return entry
        log(f"cache {cache.name} ignored (sim_code_hash or n differs); recomputing")
    master = f"023-pairs|{team}"
    reqs = [{"op": "gauntlet", "id": f"{style}-{i}", "team": team_reqs, "seed": derive_seed(master, i, 0),
             "player_policy": policy, "opponent_policy": OPPONENT, "stop_on_loss": True, "log": "summary",
             "battle_style": style} for i in range(n)]
    t0 = time.perf_counter()
    rs = pool.map(reqs)
    wall = time.perf_counter() - t0
    bad = [r for r in rs if not r.get("ok")]
    if bad:
        raise RuntimeError(f"{len(bad)} failed requests for {style} on {team}; first: {bad[0].get('error')}")
    for r in rs:
        if (r["player_policy"], r["opponent_policy"], r.get("battle_style", "set")) != (policy, OPPONENT, style):
            raise RuntimeError(f"worker ran {r['player_policy']}/{r['opponent_policy']}/{r.get('battle_style', 'set')}")
    per_trainer: dict[str, list[int]] = {}
    offers = switches = prompted = prompted_won = 0
    for r in rs:
        saw_offer = False
        for b in r["battles"]:
            pt = per_trainer.setdefault(b["trainer"], [0, 0])
            pt[0] += 1
            pt[1] += bool(b["won"])
            sh = b.get("shift")
            if sh:
                offers += sh["offers"]
                switches += sh["switches"]
                if sh["offers"]:
                    saw_offer = True
                    prompted += 1
                    prompted_won += bool(b["won"])
        _ = saw_offer
    entry = {"team": team, "style": style, "policy": policy, "master": master, "n": n,
             "cleared": [bool(r["cleared"]) for r in rs], "battles_seed_0": [r["battles"][0]["seed"] for r in rs],
             "per_trainer": {k: {"battles": v[0], "won": v[1], "rate": round(v[1] / v[0], 4)} for k, v in per_trainer.items()},
             "offers": offers, "switches": switches, "prompted_battles": prompted, "prompted_battles_won": prompted_won,
             "wall_s": round(wall, 3), "gauntlets_per_s": round(n / wall, 4), "sim_code_hash": pool.sim_code_hash}
    cache.write_text(json.dumps(entry))
    log(f"{style} on {team}: {sum(entry['cleared'])}/{n} cleared, {wall:.1f} s, {n / wall:.2f} gauntlets/s, offers {offers}, switches {switches}")
    return entry


def summary_row(team: str, a: dict, b: dict) -> dict:
    from platsim.stats import mcnemar_exact, wilson_ci

    cmp = mcnemar_exact(a["cleared"], b["cleared"])
    return {"team": team, "a": a["style"], "b": b["style"], "policy": a["policy"], "n": cmp.n,
            "a_cleared": sum(a["cleared"]), "b_cleared": sum(b["cleared"]),
            "a_rate": round(cmp.a_rate, 4), "b_rate": round(cmp.b_rate, 4),
            "a_ci95": [round(x, 4) for x in wilson_ci(sum(a["cleared"]), cmp.n)],
            "b_ci95": [round(x, 4) for x in wilson_ci(sum(b["cleared"]), cmp.n)],
            "a_only": cmp.a_only, "b_only": cmp.b_only, "p_value": cmp.p_value, "verdict": cmp.verdict,
            "a_per_trainer": a["per_trainer"], "b_per_trainer": b["per_trainer"],
            "a_offers": a["offers"], "a_switches": a["switches"], "a_prompted_battles": a["prompted_battles"],
            "a_prompted_battles_won": a["prompted_battles_won"],
            "a_gauntlets_per_s": a["gauntlets_per_s"], "b_gauntlets_per_s": b["gauntlets_per_s"],
            "wall_ratio_a_over_b": round(a["wall_s"] / b["wall_s"], 3) if b["wall_s"] else None,
            "master": a["master"], "sim_code_hash": a["sim_code_hash"], "date": eastern_now()}


def row_text(r: dict) -> str:
    pt = lambda d: " ".join(f"{k[:3]} {v['rate']:.3f}" for k, v in d.items())  # noqa: E731
    return (f"{r['team']}: n {r['n']}  shift {r['a_rate']:.4f} [{r['a_ci95'][0]:.4f}, {r['a_ci95'][1]:.4f}]  "
            f"set {r['b_rate']:.4f} [{r['b_ci95'][0]:.4f}, {r['b_ci95'][1]:.4f}]  only shift {r['a_only']} / only set {r['b_only']}  "
            f"p {r['p_value']:.3g}  verdict {r['verdict']}\n"
            f"    per trainer shift: {pt(r['a_per_trainer'])}\n    per trainer set:   {pt(r['b_per_trainer'])}\n"
            f"    offers {r['a_offers']}, switches {r['a_switches']}, prompted battles {r['a_prompted_battles']} "
            f"(won {r['a_prompted_battles_won']}); speed shift {r['a_gauntlets_per_s']:.2f} / set {r['b_gauntlets_per_s']:.2f} gauntlets/s, "
            f"wall ratio shift/set {r['wall_ratio_a_over_b']}")


def b2quick(workers: int, log) -> dict:
    out = {}
    for style in STYLES:
        d = EVIDENCE / f"b2quick-{style}"
        cmd = [sys.executable, "-m", "platsim.cli", "optimize", *B2_SPECIES, "--budget", "quick", "--seed", B2_SEED,
               "--workers", str(workers), "--battle-style", style, "--force-new", "--out", str(d)]
        log(f"b2quick {style}: {' '.join(cmd[2:])}")
        t0 = time.perf_counter()
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        wall = time.perf_counter() - t0
        if p.returncode != 0:
            raise SystemExit(f"b2quick {style} failed: {p.stderr[-2000:]}")
        res = json.loads((d / "result.json").read_text())
        st = json.loads((d / "state.json").read_text())
        attempts = st.get("stages", {}).get("confirm_attempts") or []
        out[style] = {"species": [b["species"] for b in res["team"]["builds"]],
                      "levels": [b["start_level"] for b in res["team"]["builds"]],
                      "clear_rate": res["clear_rate"], "clear_ci95": res["clear_ci95"], "n_runs": res["n_runs"],
                      "qualified": res["qualified"], "borderline": res["borderline"],
                      "expected_avg_final_level": res["expected_avg_final_level"],
                      "confirm_attempts": len(attempts), "wall_s": round(wall, 1), "battle_style": res.get("battle_style")}
        print(f"b2quick {style}: {out[style]['species']} levels {out[style]['levels']} clear {res['clear_rate']:.4f} "
              f"{[round(x, 4) for x in res['clear_ci95']]} n {res['n_runs']} attempts {len(attempts)} wall {wall:.0f} s", flush=True)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--teams", default=",".join(TEAM_NAMES))
    ap.add_argument("--runs", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--policy", default="expectimax2-v4")
    ap.add_argument("--out", type=Path, default=EVIDENCE / "pairs")
    ap.add_argument("--self", action="store_true", dest="self_check", help="pairing control: Shift twice on the first team")
    ap.add_argument("--b2quick", action="store_true", help="also run the B2 quick optimize under each style")
    ap.add_argument("--no-idle-check", action="store_true")
    args = ap.parse_args(argv)
    from platsim.sim.pool import WorkerPool

    if not args.no_idle_check:
        assert_idle()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(f"paired_styles: {m}", file=sys.stderr, flush=True)  # noqa: E731
    print(f"start {eastern_now()}", flush=True)
    rows = []
    control_ok = True
    with WorkerPool(args.workers) as pool:
        log(f"pool {pool.size} workers, sim_code_hash {pool.sim_code_hash}")
        teams = args.teams.split(",")
        for team in teams:
            team_reqs = team_requests(team, out)
            a = run_side(pool, team, team_reqs, "shift", args.policy, args.runs, out, log)
            b = run_side(pool, team, team_reqs, "set", args.policy, args.runs, out, log)
            if a["battles_seed_0"] != b["battles_seed_0"]:
                raise RuntimeError(f"pairing broken on {team}: first-battle seeds differ between sides")
            row = summary_row(team, a, b)
            rows.append(row)
            print(row_text(row), flush=True)
        if args.self_check:
            team = teams[0]
            team_reqs = team_requests(team, out)
            a = run_side(pool, team, team_reqs, "shift", args.policy, args.runs, out, log)
            a2 = run_side(pool, team, team_reqs, "shift", args.policy, args.runs, out, log, suffix="__self2")
            disc = sum(x != y for x, y in zip(a["cleared"], a2["cleared"]))
            control_ok = disc == 0
            print(f"pairing control ({team}, shift twice): {disc} discordant pairs, {'OK' if control_ok else 'FAILED'}", flush=True)
            rows.append({"team": team, "control": "shift-vs-shift", "discordant": disc, "ok": control_ok})
    if args.b2quick:
        rows.append({"b2quick": b2quick(args.workers, log)})
    summary = out / "summary.json"
    existing = json.loads(summary.read_text()) if summary.exists() else []
    summary.write_text(json.dumps(existing + rows, indent=1))
    print(f"end {eastern_now()}", flush=True)
    return 0 if control_ok else 1


if __name__ == "__main__":
    sys.exit(main())
