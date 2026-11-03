"""Feature 019, US2: replay the adaptive Elite Four rule offline over a recording (research R3).

For a run order, full runs are consumed until every Elite Four member's Wilson 95% lower bound (battles faced and
won so far) is at or above the floor; the remaining runs are Cynthia-only, valued by their recorded Cynthia outcome
when the recording reached her (runs that lost earlier are counted as "unvalued"). The composite estimate and its
Bonferroni interval come from `e4_estimator`.

usage: uv run python specs/019-e4-sampling-spike/scripts/e4_replay.py --recording FILE [--floors 0.98,0.99,0.995] [--orders 200] [--seed 019-replay] --out FILE
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CHAMPION, E4  # noqa: E402
from e4_estimator import product_interval, threshold_verdict, verdict, wilson_bounds  # noqa: E402

from platsim.stats import Z95, wilson_ci  # noqa: E402


def load_recording(path: str | Path) -> tuple[dict, list[dict]]:
    lines = Path(path).read_text().splitlines()
    header = json.loads(lines[0])
    runs = [json.loads(line) for line in lines[1:]]
    for i, r in enumerate(runs):
        if r["run"] != i:
            raise ValueError(f"run index {r['run']} at line {i + 2}")
    return header, runs


def cynthia_battle(run: dict) -> dict | None:
    for b in run["battles"]:
        if b["trainer"] == CHAMPION:
            return b
    return None


def switch_point(runs_in_order: list[dict], floor: float) -> int | None:
    """First k (count of full runs) after which every Elite Four member's Wilson 95% lower bound >= floor."""
    faced = {t: 0 for t in E4}
    won = {t: 0 for t in E4}
    for k, r in enumerate(runs_in_order, start=1):
        for b in r["battles"]:
            t = b["trainer"]
            if t in faced:
                faced[t] += 1
                won[t] += bool(b["won"])
        if all(faced[t] > 0 and wilson_ci(won[t], faced[t], Z95)[0] >= floor for t in E4):
            return k
    return None


def composite_after(runs_in_order: list[dict], k: int | None, preset: str = "standard", threshold: float = 0.75) -> dict:
    n = len(runs_in_order)
    k = n if k is None else k
    full, rest = runs_in_order[:k], runs_in_order[k:]
    reached = sum(1 for r in full if cynthia_battle(r) is not None)
    cyn_b = cyn_w = 0
    for r in full:
        b = cynthia_battle(r)
        if b is not None:
            cyn_b += 1
            cyn_w += bool(b["won"])
    unvalued = 0
    for r in rest:
        b = cynthia_battle(r)
        if b is None:
            unvalued += 1
        else:
            cyn_b += 1
            cyn_w += bool(b["won"])
    e4_pass = reached / k
    cyn_rate = cyn_w / cyn_b if cyn_b else 0.0
    est = e4_pass * cyn_rate
    iv = product_interval(wilson_bounds(reached, k, 0.975), wilson_bounds(cyn_w, cyn_b, 0.975)) if cyn_b else (0.0, 0.0)
    gap = level_gap(runs_in_order)
    tv, full_v = verdict(est, iv, preset, threshold, gap)
    return {"k": k, "cynthia_only_runs": n - k, "cynthia_only_share": (n - k) / n, "unvalued": unvalued,
            "e4_pass_k": e4_pass, "cyn_battles": cyn_b, "cyn_rate": cyn_rate, "estimate": est,
            "interval_bonferroni": iv, "threshold_verdict": tv, "full_verdict": full_v}


def level_gap(runs: list[dict]) -> float | None:
    gaps = [max(r["final_levels"]) - min(r["final_levels"]) for r in runs if r["cleared"]]
    return max(gaps) if gaps else None


def banked_states(runs_in_order: list[dict], k: int | None) -> int:
    k = len(runs_in_order) if k is None else k
    seen = set()
    for r in runs_in_order[:k]:
        b = cynthia_battle(r)
        if b is not None and "state_before" in b:
            seen.add(json.dumps(b["state_before"], sort_keys=True))
    return len(seen)


def orders(n: int, count: int, seed: str = "019-replay") -> list[list[int]]:
    rng = random.Random(seed)
    out = [list(range(n))]
    for _ in range(count):
        perm = list(range(n))
        rng.shuffle(perm)
        out.append(perm)
    return out


def full_result(runs: list[dict], threshold: float = 0.75) -> dict:
    n = len(runs)
    wins = sum(bool(r["cleared"]) for r in runs)
    ci = wilson_ci(wins, n)
    return {"n": n, "wins": wins, "clear_rate": wins / n, "ci95": ci, "threshold_verdict": threshold_verdict(ci, threshold)}


def _dist(values: list[float]) -> dict:
    if not values:
        return {}
    v = sorted(values)
    q = lambda p: v[min(len(v) - 1, int(p * (len(v) - 1)))]
    return {"min": v[0], "p5": q(0.05), "median": statistics.median(v), "p95": q(0.95), "max": v[-1]}


def replay(runs: list[dict], floors: list[float], n_orders: int, seed: str, threshold: float = 0.75) -> dict:
    fr = full_result(runs, threshold)
    ords = orders(len(runs), n_orders, seed)
    cyn_turns = [cynthia_battle(r)["turns"] for r in runs if cynthia_battle(r)]
    full_turns = [sum(b["turns"] for b in r["battles"]) for r in runs]
    out = {"full": fr, "floors": {}, "cynthia_turns_per_battle": statistics.mean(cyn_turns) if cyn_turns else None,
           "turns_per_full_gauntlet": statistics.mean(full_turns), "orders": n_orders, "seed": seed}
    for floor in floors:
        rows = []
        for oi, perm in enumerate(ords):
            ro = [runs[i] for i in perm]
            k = switch_point(ro, floor)
            c = composite_after(ro, k, threshold=threshold)
            rows.append({"order": oi, "switch_k": k, **c, "banked_states": banked_states(ro, k),
                         "contains_full": c["interval_bonferroni"][0] <= fr["clear_rate"] <= c["interval_bonferroni"][1],
                         "verdict_agrees": c["threshold_verdict"] == fr["threshold_verdict"]})
        perms = rows[1:]
        switched = [r for r in perms if r["switch_k"] is not None]
        out["floors"][str(floor)] = {
            "identity": rows[0],
            "orders_switched": len(switched), "orders_total": len(perms),
            "switch_k": _dist([r["switch_k"] for r in switched]),
            "cynthia_only_share": _dist([r["cynthia_only_share"] for r in perms]),
            "unvalued": _dist([r["unvalued"] for r in perms]),
            "banked_states_at_switch": _dist([r["banked_states"] for r in switched]),
            "contains_full_fraction": sum(r["contains_full"] for r in perms) / len(perms),
            "verdict_agrees_fraction": sum(r["verdict_agrees"] for r in perms) / len(perms),
            "estimate": _dist([r["estimate"] for r in perms]),
            "rows": rows,
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recording", required=True)
    ap.add_argument("--floors", default="0.98,0.99,0.995")
    ap.add_argument("--orders", type=int, default=200)
    ap.add_argument("--seed", default="019-replay")
    ap.add_argument("--threshold", type=float, default=0.75)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    header, runs = load_recording(a.recording)
    res = replay(runs, [float(x) for x in a.floors.split(",")], a.orders, a.seed, a.threshold)
    res["header"] = header
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))
    fr = res["full"]
    print(f"team {header['team']}  runs {fr['n']}  full clear {fr['clear_rate']:.4f} [{fr['ci95'][0]:.4f}, {fr['ci95'][1]:.4f}] "
          f"{fr['threshold_verdict']}  Cynthia turns/battle {res['cynthia_turns_per_battle']:.2f}  turns/full gauntlet {res['turns_per_full_gauntlet']:.2f}")
    for floor, d in res["floors"].items():
        idn = d["identity"]
        print(f"floor {floor}: switched {d['orders_switched']}/{d['orders_total']} orders; switch_k {d['switch_k']}; "
              f"cynthia-only share {d['cynthia_only_share']}; unvalued {d['unvalued']}; banked {d['banked_states_at_switch']}; "
              f"contains_full {d['contains_full_fraction']:.3f}; verdict_agrees {d['verdict_agrees_fraction']:.3f}; "
              f"estimate {d['estimate']}; identity order: k {idn['switch_k']} share {idn['cynthia_only_share']:.3f} "
              f"est {idn['estimate']:.4f} [{idn['interval_bonferroni'][0]:.4f}, {idn['interval_bonferroni'][1]:.4f}] {idn['threshold_verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
