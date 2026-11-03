"""Feature 019, US3: projected wall time of the two baselines under adaptive Elite Four sampling (research R6).

Inputs: the reference team's batch-200 time-share row (wall per gauntlet at the pool, Cynthia seconds per battle,
CPU seconds per gauntlet) and the replay's switch-point distributions per floor. Model, per floor and per k:
  projected = k * w_full + (n - k + topup_method) * w_cyn
  baseline  = n * w_full + topup_today * w_cyn           (the same model with no sampling)
with w_full the measured wall per full gauntlet at 16 workers and w_cyn = w_full * (Cynthia CPU per battle / CPU per
full gauntlet). Top-ups: today max(0, n - reached + 1) (Cynthia count must exceed every other trainer's); under the
method the Cynthia-only runs already are Cynthia battles, so max(0, k - (reached_k + n - k) + 1).
The B2 quick figure is a bracket between the strong (ref) and Lucian-heavy (b3) replays: NOT a measurement.

usage: uv run python specs/019-e4-sampling-spike/scripts/projection.py [--time-share F] [--replay-ref F] [--replay-b3 F] [--baseline-eval 769] [--baseline-b2quick 350] --out F
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CHAMPION, EVIDENCE  # noqa: E402

QUICK_BATCHES = (50, 100, 200)
QUICK_CONFIRM = 500


def eval_projection(ts_row: dict, replay: dict, n: int = 2000) -> dict:
    w_full = ts_row["wall_per_gauntlet_s"]
    cpu_full = ts_row["cpu_s_per_gauntlet"]
    w_cyn = w_full * ts_row["cynthia_s_per_battle"] / cpu_full
    full = replay["full"]
    reached_full = sum(1 for r in replay["floors"][next(iter(replay["floors"]))]["rows"][:1] for _ in [0])  # placeholder, replaced below
    out = {"inputs": {"w_full_s": w_full, "w_cyn_s": w_cyn, "cpu_s_per_gauntlet": cpu_full,
                      "cynthia_s_per_battle": ts_row["cynthia_s_per_battle"], "n": n}, "floors": {}}
    # reached count in the recording = Cynthia battles of the identity order at k = n
    for floor, d in replay["floors"].items():
        ident = d["identity"]
        rows = [r for r in d["rows"][1:] if r["switch_k"] is not None]
        reached_full = d["identity"]["cyn_battles"] if ident["switch_k"] is None else None
        topup_today = None
        # baseline: full gauntlets for all n plus today's top-up
        full_identity = [r for r in d["rows"] if r["order"] == 0][0]
        k_full_reached = full_identity["cyn_battles"] if full_identity["switch_k"] is None else None
        ks = sorted(r["switch_k"] for r in rows)
        if not ks:
            out["floors"][floor] = {"switched_orders": 0, "note": "floor never reached; no saving", "ratio_model": 1.0}
            continue
        q = lambda p: ks[min(len(ks) - 1, int(p * (len(ks) - 1)))]
        proj = {}
        for label, k in (("p5", q(0.05)), ("median", q(0.5)), ("p95", q(0.95))):
            row = next(r for r in rows if r["switch_k"] == k)
            reached_k = round(row["e4_pass_k"] * k)
            topup_method = max(0, k - (reached_k + n - k) + 1)
            projected = k * w_full + (n - k + topup_method) * w_cyn
            proj[label] = {"k": k, "projected_s": projected}
        # baseline with the same model: n full gauntlets + today's top-up (Cynthia count must exceed n reached... use n - reached + 1)
        reached_n = round(full["clear_rate"] / max(1e-9, d["identity"]["cyn_rate"]) * n) if d["identity"]["cyn_rate"] else n
        topup_today = max(0, n - reached_n + 1)
        baseline = n * w_full + topup_today * w_cyn
        out["floors"][floor] = {"switched_orders": len(rows), "baseline_model_s": baseline, "topup_today": topup_today,
                                "projection": proj,
                                "ratio_model": {lbl: baseline / p["projected_s"] for lbl, p in proj.items()}}
    return out


def b2quick_bracket(ts_rows: dict, replay_ref: dict, replay_b3: dict) -> dict:
    """Saving fraction on a quick optimize, bracketed: strong team (ref replay) vs Lucian-heavy (b3 replay).
    Runs per stage: level search batches 50 -> 100 -> 200 per tested point (count unknown; one point assumed per
    batch size) and the 500-run confirmation. Cynthia-only runs in a batch of b = max(0, b - k)."""
    out = {}
    for name, replay in (("strong_ref", replay_ref), ("lucian_heavy_b3", replay_b3)):
        per_floor = {}
        for floor, d in replay["floors"].items():
            rows = [r for r in d["rows"][1:] if r["switch_k"] is not None]
            if not rows:
                per_floor[floor] = {"saving_fraction": 0.0, "note": "floor never reached"}
                continue
            ks = sorted(r["switch_k"] for r in rows)
            k = ks[len(ks) // 2]
            stages = list(QUICK_BATCHES) + [QUICK_CONFIRM]
            full_runs = sum(min(b, k) for b in stages)
            cyn_runs = sum(max(0, b - k) for b in stages)
            row = ts_rows.get("b2v2") or ts_rows.get("ref")
            w_full = row["wall_per_gauntlet_s"]
            w_cyn = w_full * row["cynthia_s_per_battle"] / row["cpu_s_per_gauntlet"]
            base = sum(stages) * w_full
            proj = full_runs * w_full + cyn_runs * w_cyn
            per_floor[floor] = {"median_k": k, "runs": stages, "full_runs": full_runs, "cynthia_only_runs": cyn_runs,
                                "ratio_model": base / proj}
        out[name] = per_floor
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--time-share", default=str(EVIDENCE / "time_share.json"))
    ap.add_argument("--replay-ref", default=str(EVIDENCE / "replay-ref.json"))
    ap.add_argument("--replay-b3", default=str(EVIDENCE / "replay-b3.json"))
    ap.add_argument("--baseline-eval", type=float, default=769.0)
    ap.add_argument("--baseline-b2quick", type=float, default=350.0)
    ap.add_argument("--out", default=str(EVIDENCE / "projection.json"))
    a = ap.parse_args(argv)
    ts = json.loads(Path(a.time_share).read_text())
    rows = {(m["team"], m["batch_size"]): m for m in ts["measurements"] if m.get("digests_equal")}
    ref200 = rows[("ref", 200)]
    ts_by_team = {t: rows[(t, 200)] for t in ("ref", "b3", "b2v2") if (t, 200) in rows}
    replay_ref = json.loads(Path(a.replay_ref).read_text())
    replay_b3 = json.loads(Path(a.replay_b3).read_text())
    ev = eval_projection(ref200, replay_ref)
    b2 = b2quick_bracket(ts_by_team, replay_ref, replay_b3)
    decision = {}
    for floor, d in ev["floors"].items():
        if "projection" in d:
            decision[floor] = {"ratio_model_p5_to_p95": [d["ratio_model"]["p95"], d["ratio_model"]["p5"]],
                               "projected_s_median": d["projection"]["median"]["projected_s"],
                               "baseline_model_s": d["baseline_model_s"],
                               "against_769s": a.baseline_eval / d["projection"]["median"]["projected_s"]}
    out = {"evaluate_reference": ev, "b2_quick_bracket": b2, "decision_figure": decision,
           "baselines": {"evaluate_reference_s": a.baseline_eval, "b2_quick_s": a.baseline_b2quick},
           "note": "B2 quick is a bracket between the strong and Lucian-heavy replays, not a measurement."}
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({"inputs": ev["inputs"]}))
    for floor, d in decision.items():
        print(f"evaluate reference, floor {floor}: model ratio (p95 of k .. p5 of k) {d['ratio_model_p5_to_p95'][0]:.2f} .. {d['ratio_model_p5_to_p95'][1]:.2f}; "
              f"projected median {d['projected_s_median']:.0f} s vs model baseline {d['baseline_model_s']:.0f} s; vs README 769 s: {d['against_769s']:.2f}x")
    for name, pf in b2.items():
        for floor, d in pf.items():
            print(f"B2 quick bracket, {name}, floor {floor}: " + (f"model ratio {d['ratio_model']:.2f} (median k {d['median_k']})" if "ratio_model" in d else d["note"]) + "  [bracket, not a measurement]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
