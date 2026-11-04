"""Feature 021 acceptance (research R11): adaptive against full, paired on the same seeds, on six teams; two controls.

usage: uv run python specs/021-adaptive-e4-sampling/scripts/acceptance.py [--teams ref,b2main,b2branch,b2v2,b3]
         [--runs 2000] [--workers 16] [--floor 0.99] [--alt-floor 0.98] [--budget standard] [--out FILE]
       uv run python specs/021-adaptive-e4-sampling/scripts/acceptance.py --control [--workers 16]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "specs" / "019-e4-sampling-spike" / "scripts"))
from common import assert_idle, code_hashes, eastern_now  # noqa: E402  (feature 019 helpers)

EVIDENCE = REPO / "runs" / "021-evidence"
SAMPLING_KEYS = ("sampling", "sampling_detail")
TEAMS = {
    "bench": ("tests/fixtures/policy_benchmark_team.json", None),
    "ref": ("tests/fixtures/reference_team.json", None),
    "b2main": ("runs/014-evidence/b2-main/result.json", "team"),
    "b2branch": ("runs/014-evidence/b2-branch/result.json", "team"),
    "b2v2": ("runs/018-evidence/b2-expectimax2-v2/result.json", "team"),
    "b3": ("runs/bench-010/B3/result.json", "team"),
}


# ---- pure helpers (tested in tests/unit/test_sampling.py) ----

def contained(x: float, ci: tuple[float, float]) -> bool:
    return ci[0] <= x <= ci[1]


def verdict_of(d: dict) -> str:
    if d.get("qualified"):
        return "qualified"
    return "borderline" if d.get("borderline") else "not_qualified"


def strip_sampling_keys(d: dict) -> dict:
    out = {k: v for k, v in d.items() if k not in SAMPLING_KEYS}
    if "provenance" in out:
        out["provenance"] = {k: v for k, v in out["provenance"].items() if k != "sampling"}
    if "seeds" in out:
        out["seeds"] = {k: v for k, v in out["seeds"].items() if k != "cynthia_only_seed"}
    return out


def row_for(team: str, full: dict, adaptive: dict, wall_full: float, wall_adaptive: float, floor: float) -> dict:
    sd = adaptive.get("sampling_detail") or {}
    hw_full = (full["clear_ci95"][1] - full["clear_ci95"][0]) / 2
    hw_ad = (adaptive["clear_ci95"][1] - adaptive["clear_ci95"][0]) / 2
    return {"team": team, "floor": floor,
            "full_estimate": full["clear_rate"], "full_ci95": full["clear_ci95"], "full_n": full["n_runs"],
            "adaptive_estimate": adaptive["clear_rate"], "adaptive_ci95": adaptive["clear_ci95"], "adaptive_n": adaptive["n_runs"],
            "contained": contained(adaptive["clear_rate"], tuple(full["clear_ci95"])),
            "verdict_full": verdict_of(full), "verdict_adaptive": verdict_of(adaptive),
            "agree": verdict_of(full) == verdict_of(adaptive),
            "hw_ratio": (hw_ad / hw_full) if hw_full else None,
            "switch_run": sd.get("switch_run"), "full_runs": sd.get("full_runs"), "cynthia_only_runs": sd.get("cynthia_only_runs"),
            "cynthia_only_share": (sd.get("cynthia_only_runs", 0) / adaptive["n_runs"]) if adaptive.get("n_runs") else None,
            "discarded": sd.get("discarded"), "extension": sd.get("extension"),
            "wall_full_s": wall_full, "wall_adaptive_s": wall_adaptive,
            "ratio": (wall_full / wall_adaptive) if wall_adaptive else None}


def fmt_row(r: dict) -> str:
    return (f"{r['team']:<9} floor {r['floor']:<5} full {r['full_estimate']:.4f} [{r['full_ci95'][0]:.4f}, {r['full_ci95'][1]:.4f}] n {r['full_n']}  "
            f"adaptive {r['adaptive_estimate']:.4f} [{r['adaptive_ci95'][0]:.4f}, {r['adaptive_ci95'][1]:.4f}] n {r['adaptive_n']}  "
            f"contained {r['contained']}  verdicts {r['verdict_full']}/{r['verdict_adaptive']} agree {r['agree']}  "
            f"hw x{r['hw_ratio']:.2f}  switch {r['switch_run']}  full/cyn {r['full_runs']}/{r['cynthia_only_runs']} "
            f"(share {r['cynthia_only_share']:.3f})  discarded {r['discarded']}  ext {r['extension']}  "
            f"wall {r['wall_full_s']:.0f}s/{r['wall_adaptive_s']:.0f}s = {r['ratio']:.2f}x")


# ---- team loading ----

def load_team_candidate(name: str):
    """(TeamCandidate, ledger) through the same loader `evaluate` uses. The policy benchmark fixture (`bench`) cannot be
    evaluated this way: its builds carry placeholder sources ("reference-fixture") that the report writer refuses
    (`report/sources.py`), and it fails in-game legality (15 violations); it exists for the simulator-side benchmark
    tools, which never write reports. It is therefore not in the default team list."""
    from platsim.evaluate import load_and_validate

    rel, key = TEAMS[name]
    path = REPO / rel
    if key:
        d = json.loads(path.read_text())[key]
        tmp = EVIDENCE / "teams"
        tmp.mkdir(parents=True, exist_ok=True)
        path = tmp / f"{name}.json"
        path.write_text(json.dumps(d))
    return load_and_validate(path, None, ())


def run_one(team, led, pool, *, runs: int, seed: str, budget: str, sampling: str, floor: float, out: Path):
    from platsim.evaluate import evaluate_team
    from platsim.legality.validator import showdown_name
    from platsim.report import write_all

    t0 = time.perf_counter()
    report, ev = evaluate_team(team, led, pool, runs=runs, seed=seed, budget=budget, sampling=sampling, floor=floor)
    wall = time.perf_counter() - t0
    out.mkdir(parents=True, exist_ok=True)
    write_all(report, out, showdown_name)
    return json.loads((out / "result.json").read_text()), wall, ev


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teams", default="ref,b2main,b2branch,b2v2,b3",
                    help="bench (the policy benchmark fixture) is excluded: not evaluable through the report writers")
    ap.add_argument("--runs", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--floor", type=float, default=0.99)
    ap.add_argument("--alt-floor", type=float, default=0.98, help="rerun adaptive at this floor when the switch run is > 1000 or absent")
    ap.add_argument("--budget", default="standard")
    ap.add_argument("--seed", default="021-acc")
    ap.add_argument("--out", default=str(EVIDENCE / "acceptance.json"))
    ap.add_argument("--control", action="store_true")
    a = ap.parse_args(argv)
    assert_idle()
    from platsim.sim.pool import WorkerPool

    if a.control:
        return control(a)
    rows, alt_rows = [], []
    start = eastern_now()
    with WorkerPool(a.workers) as pool:
        for name in a.teams.split(","):
            team, led = load_team_candidate(name)
            full, wf, _ = run_one(team, led, pool, runs=a.runs, seed=a.seed, budget=a.budget, sampling="full",
                                  floor=a.floor, out=EVIDENCE / name / "full")
            ad, wa, _ = run_one(team, led, pool, runs=a.runs, seed=a.seed, budget=a.budget, sampling="adaptive",
                                floor=a.floor, out=EVIDENCE / name / "adaptive")
            r = row_for(name, full, ad, wf, wa, a.floor)
            rows.append(r)
            print(fmt_row(r), flush=True)
            if r["switch_run"] is None or r["switch_run"] > 1000:
                ad2, wa2, _ = run_one(team, led, pool, runs=a.runs, seed=a.seed, budget=a.budget, sampling="adaptive",
                                      floor=a.alt_floor, out=EVIDENCE / name / f"adaptive-{a.alt_floor}")
                r2 = row_for(name, full, ad2, wf, wa2, a.alt_floor)
                alt_rows.append(r2)
                print("  alt: " + fmt_row(r2), flush=True)
    summary = {"all_contained": all(r["contained"] for r in rows), "all_agree": all(r["agree"] for r in rows),
               "ratios": {r["team"]: r["ratio"] for r in rows}, "start": start, "end": eastern_now(), **code_hashes()}
    print(json.dumps(summary))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"summary": summary, "rows": rows, "alt_rows": alt_rows}, indent=1))
    return 0 if summary["all_contained"] and summary["all_agree"] else 1


def control(a) -> int:
    from platsim.sim.champion import champion_topup
    from platsim.sim.pool import WorkerPool
    from platsim.evaluate import worker_team

    team, led = load_team_candidate("ref")
    out = {"start": eastern_now()}
    with WorkerPool(a.workers) as pool:
        # 1. floor 1.0 equals full apart from the sampling keys
        full, _, _ = run_one(team, led, pool, runs=200, seed="021-ctl", budget="quick", sampling="full", floor=1.0,
                             out=EVIDENCE / "control" / "full")
        ad, _, _ = run_one(team, led, pool, runs=200, seed="021-ctl", budget="quick", sampling="adaptive", floor=1.0,
                           out=EVIDENCE / "control" / "adaptive-floor1")
        same = json.dumps(strip_sampling_keys(full), sort_keys=True) == json.dumps(strip_sampling_keys(ad), sort_keys=True)
        out["floor_1_identical_after_strip"] = same
        out["floor_1_switch_run"] = (ad.get("sampling_detail") or {}).get("switch_run")
        print(f"control 1: adaptive floor 1.0 vs full, identical after removing the sampling keys: {same}; switch_run {out['floor_1_switch_run']}")
        # 2. Cynthia-only sampling runs vs the top-up on the same bank
        ad2, _, ev = run_one(team, led, pool, runs=200, seed="021-ctl", budget="quick", sampling="adaptive", floor=0.9,
                             out=EVIDENCE / "control" / "adaptive-floor09")
        cyn = ev.cynthia_only_results
        n_s = len(cyn)
        w_s = sum(bool(r["battles"][0]["won"]) for r in cyn)
        wteam = worker_team(team, led)
        # the top-up's own draws (seed index 99, its start_index rule) on the same bank, at the same count
        from platsim.sim.champion import CHAMPION, TOPUP_BATTLE_INDEX, _start_index
        from platsim.sim.seeds import derive_seed

        bank = [b["state_before"] for r in ev.results for b in r["battles"] if b["trainer"] == CHAMPION]
        reqs = [{"op": "gauntlet", "team": wteam, "seed": derive_seed("021-ctl", k, TOPUP_BATTLE_INDEX),
                 "player_policy": ev.results[0]["player_policy"], "opponent_policy": ev.results[0]["opponent_policy"],
                 "trainers": [CHAMPION], "start_state": bank[_start_index("021-ctl", k, len(bank))],
                 "stop_on_loss": True, "log": "none"} for k in range(n_s)]
        resps = pool.map(reqs)
        n_t = len(resps)
        w_t = sum(bool(r["battles"][0]["won"]) for r in resps)
        del champion_topup  # not used; the explicit draws above are the control
        p_s = w_s / n_s if n_s else None
        p_t = w_t / n_t if n_t else None
        if p_s is not None and p_t is not None:
            p = (w_s + w_t) / (n_s + n_t)
            se = math.sqrt(max(p * (1 - p), 1e-9) * (1 / n_s + 1 / n_t))
            z = abs(p_s - p_t) / se if se else 0.0
        else:
            z = None
        out.update({"sampling_runs": n_s, "sampling_wins": w_s, "topup_battles": n_t, "topup_wins": w_t,
                    "p_sampling": p_s, "p_topup": p_t, "z": z, "within_noise": (z is not None and z < 1.96)})
        print(f"control 2: Cynthia-only sampling {w_s}/{n_s} = {p_s} vs top-up {w_t}/{n_t} = {p_t}; z {z}; within noise: {out['within_noise']}")
    out["end"] = eastern_now()
    (EVIDENCE / "control.json").write_text(json.dumps(out, indent=1))
    return 0 if same and out["within_noise"] else 1


if __name__ == "__main__":
    sys.exit(main())
