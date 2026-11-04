"""Feature 022 acceptance (research R7): four blocks, each selectable with --blocks.

  b2quick : two `platsim optimize` runs (the 014 B2 request, quick, seed 014-b2) with --sampling full and adaptive;
            species / moves / items / levels, containment both ways, verdicts, the 010 equal-levels comparison (018's
            script by path), the runner-up records, wall times (confirm stage from state.json timing, whole run).
  confirm : the confirmation call as `_confirm` makes it, on the 014 b2-main and bench-010 B3 teams, full then adaptive.
  resume  : the b2quick adaptive request, killed once the confirm stage is under way, resumed, compared byte for byte.
  pairing : b2-main vs b2-branch under full and adaptive; the full-kind McNemar counts must match exactly.

usage: uv run python specs/022-confirm-adaptive-sampling/scripts/acceptance.py [--blocks b2quick,confirm,resume,pairing]
         [--workers 16] [--floor 0.98] [--out runs/022-evidence/acceptance.json]
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "specs" / "019-e4-sampling-spike" / "scripts"))
from common import assert_idle, code_hashes, eastern_now  # noqa: E402  (feature 019 helpers)

EVIDENCE = REPO / "runs" / "022-evidence"
B2_SPECIES = ["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"]
B2_SEED = "014-b2"
EQUAL_LEVELS = REPO / "specs" / "018-expectimax2-v4" / "scripts" / "equal_levels.py"
TEAMS = {"b2main": "runs/014-evidence/b2-main/result.json", "b2branch": "runs/014-evidence/b2-branch/result.json",
         "b3": "runs/bench-010/B3/result.json"}


def verdict_of(d: dict) -> str:
    if d.get("qualified"):
        return "qualified"
    return "borderline" if d.get("borderline") else "not_qualified"


def contained(x: float, ci) -> bool:
    return ci[0] <= x <= ci[1]


def team_key(result: dict) -> list:
    return [(b["species"], [m["move"] for m in b["moves"]], b.get("held_item"), b["start_level"]) for b in result["team"]["builds"]]


def optimize(sampling: str, out: Path, workers: int, floor: float, extra=()) -> tuple[subprocess.CompletedProcess, float]:
    cmd = [sys.executable, "-m", "platsim.cli", "optimize", *B2_SPECIES, "--budget", "quick", "--seed", B2_SEED,
           "--workers", str(workers), "--sampling", sampling, "--floor", str(floor), "--out", str(out), *extra]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    return p, time.perf_counter() - t0


def block_b2quick(a) -> dict:
    out = {"start": eastern_now()}
    runs = {}
    for sampling in ("full", "adaptive"):
        d = EVIDENCE / f"b2quick-{sampling}"
        if a.reuse and (d / "result.json").exists():
            wall = json.loads((d / "state.json").read_text())["timing"].get("total_s_this_session")
        else:
            p, wall = optimize(sampling, d, a.workers, a.floor, ("--force-new",))
            if p.returncode != 0:
                raise SystemExit(f"b2quick {sampling} failed: {p.stderr[-2000:]}")
        res = json.loads((d / "result.json").read_text())
        st = json.loads((d / "state.json").read_text())
        att = st["stages"]["confirm_attempts"][-1]
        runs[sampling] = {"dir": str(d), "wall_s": wall, "confirm_s": st["timing"].get("confirm"), "team": team_key(res),
                          "levels": [b["start_level"] for b in res["team"]["builds"]], "clear_rate": res["clear_rate"],
                          "ci95": res["clear_ci95"], "verdict": verdict_of(res), "avg_final": res["expected_avg_final_level"],
                          "attempts": len(st["stages"]["confirm_attempts"]), "attempt": att,
                          "comparison": st["stages"]["confirm"].get("comparison"), "sampling": res["sampling"]}
        print(f"b2quick {sampling}: wall {wall:.0f}s confirm {st['timing'].get('confirm')}s clear {res['clear_rate']:.4f} "
              f"{res['clear_ci95']} {verdict_of(res)} levels {runs[sampling]['levels']} attempts {runs[sampling]['attempts']} "
              f"mix full/cyn {att.get('full_runs')}/{att.get('cynthia_only_runs')} switch {att.get('switch_run')}", flush=True)
    f, ad = runs["full"], runs["adaptive"]
    same_build = [(t[0], t[1], t[2]) for t in f["team"]] == [(t[0], t[1], t[2]) for t in ad["team"]]
    same_levels = f["levels"] == ad["levels"]
    # containment is judged at EQUAL levels: the first confirm attempt is always at the level search's levels on both
    # sides; later attempts may sit at different levels after a bump, so comparing final results would mix levels
    fa = json.loads((Path(f["dir"]) / "state.json").read_text())["stages"]["confirm_attempts"][0]
    aa = json.loads((Path(ad["dir"]) / "state.json").read_text())["stages"]["confirm_attempts"][0]
    assert fa["levels"] == aa["levels"], "first attempts at different levels"
    cont = contained(aa["clear_rate"], fa["ci95"]) and contained(fa["clear_rate"], aa["ci95"])
    out["first_attempt"] = {"levels": fa["levels"], "full": {"clear_rate": fa["clear_rate"], "ci95": fa["ci95"], "borderline": fa["borderline"], "passes": fa["passes_confirm_checks"]},
                            "adaptive": {"clear_rate": aa["clear_rate"], "ci95": aa["ci95"], "borderline": aa["borderline"], "passes": aa["passes_confirm_checks"],
                                         "switch_run": aa.get("switch_run"), "cynthia_only_runs": aa.get("cynthia_only_runs")},
                            "contained_both_ways": cont}
    note = None
    if not same_levels:
        note = "levels differ: a borderline flip with a confirm bump; passes while containment holds at equal levels (clarification)" if cont else "levels differ and containment broken at equal levels: FAIL"
    # 010 equal-levels comparison: A = adaptive result, B = full result, both at A's levels, reference player v2, 500 runs
    eq = subprocess.run([sys.executable, str(EQUAL_LEVELS), f["dir"], ad["dir"], "500"], cwd=REPO, capture_output=True, text=True)
    out.update({"full": f, "adaptive": ad, "same_build": same_build, "same_levels": same_levels, "contained_both_ways_at_equal_levels": cont,
                "verdicts_agree": f["verdict"] == ad["verdict"], "note": note,
                "ratio_confirm": (f["confirm_s"] / ad["confirm_s"]) if f["confirm_s"] and ad["confirm_s"] else None,
                "ratio_whole": f["wall_s"] / ad["wall_s"], "equal_levels_stdout": eq.stdout[-3000:], "equal_levels_exit": eq.returncode,
                "pass": same_build and cont and (same_levels or note.startswith("levels differ: a borderline")), "end": eastern_now()})
    print(f"b2quick: same build {same_build}, same levels {same_levels}, first attempt at {fa['levels']}: full {fa['clear_rate']:.4f} {[round(x, 4) for x in fa['ci95']]} "
          f"borderline {fa['borderline']} vs adaptive {aa['clear_rate']:.4f} {[round(x, 4) for x in aa['ci95']]} borderline {aa['borderline']}; contained both ways at equal levels {cont}, final verdicts {f['verdict']}/{ad['verdict']}, "
          f"ratio confirm {out['ratio_confirm']}, whole {out['ratio_whole']:.2f}x; equal-levels exit {eq.returncode}; pass {out['pass']}", flush=True)
    return out


def load_team_candidate(name: str):
    from platsim.evaluate import load_and_validate

    d = json.loads((REPO / TEAMS[name]).read_text())["team"]
    tmp = EVIDENCE / "teams"
    tmp.mkdir(parents=True, exist_ok=True)
    path = tmp / f"{name}.json"
    path.write_text(json.dumps(d))
    return load_and_validate(path, None, ())


def block_confirm(a) -> dict:
    from platsim.budget import get_preset
    from platsim.evaluate import DEFAULT_MAX_RUNS, evaluate_team
    from platsim.sim.pool import WorkerPool

    preset = get_preset("standard")
    max_runs = max(DEFAULT_MAX_RUNS, 4 * preset.confirm_min)
    out = {"start": eastern_now(), "teams": {}}
    with WorkerPool(a.workers) as pool:
        for name in ("b2main", "b3"):
            team, led = load_team_candidate(name)
            row = {}
            for sampling in ("full", "adaptive"):
                t0 = time.perf_counter()
                rep, ev = evaluate_team(team, led, pool, runs=preset.confirm_min, seed="022-acc|confirm", budget="standard",
                                        threshold=0.75, max_runs=max_runs, extend_borderline=True,
                                        borderline_max_runs=preset.borderline_max_runs, sampling=sampling, floor=a.floor)
                wall = time.perf_counter() - t0
                d = rep.to_dict()
                (EVIDENCE / "confirm").mkdir(parents=True, exist_ok=True)
                (EVIDENCE / "confirm" / f"{name}-{sampling}.result.json").write_text(json.dumps(d, indent=1))
                row[sampling] = {"clear_rate": d["clear_rate"], "ci95": d["clear_ci95"], "n_runs": d["n_runs"], "verdict": verdict_of(d),
                                 "wall_s": wall, "detail": d.get("sampling_detail")}
            f, ad = row["full"], row["adaptive"]
            row["contained"] = contained(ad["clear_rate"], f["ci95"])
            row["agree"] = f["verdict"] == ad["verdict"]
            row["ratio"] = f["wall_s"] / ad["wall_s"]
            out["teams"][name] = row
            sd = ad["detail"] or {}
            print(f"confirm {name}: full {f['clear_rate']:.4f} {f['ci95']} n {f['n_runs']} {f['verdict']} {f['wall_s']:.0f}s | adaptive "
                  f"{ad['clear_rate']:.4f} {ad['ci95']} n {ad['n_runs']} {ad['verdict']} {ad['wall_s']:.0f}s | contained {row['contained']} "
                  f"agree {row['agree']} ratio {row['ratio']:.2f}x | mix full/cyn {sd.get('full_runs')}/{sd.get('cynthia_only_runs')} "
                  f"switch {sd.get('switch_run')} ext {sd.get('extension')} borderline_ext {sd.get('borderline_extended')}", flush=True)
    out["pass"] = all(r["contained"] and r["agree"] for r in out["teams"].values())
    out["end"] = eastern_now()
    return out


def block_resume(a) -> dict:
    out = {"start": eastern_now()}
    d = EVIDENCE / "b2quick-resume"
    cmd = [sys.executable, "-m", "platsim.cli", "optimize", *B2_SPECIES, "--budget", "quick", "--seed", B2_SEED,
           "--workers", str(a.workers), "--sampling", "adaptive", "--floor", str(a.floor), "--out", str(d)]
    if d.exists():
        import shutil
        shutil.rmtree(d)
    proc = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    killed_at = None
    t0 = time.perf_counter()
    while proc.poll() is None and time.perf_counter() - t0 < 1800:
        time.sleep(5)
        try:
            st = json.loads((d / "state.json").read_text())
        except (OSError, ValueError):
            continue
        stages = st.get("stages", {})
        if "level_search" in stages and "confirm" not in stages:
            time.sleep(10)  # let the confirmation attempt get under way
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
                killed_at = "during the confirmation attempt (checkpoint granularity: per attempt)"
            break
    proc.wait(timeout=120)
    if killed_at is None:
        out.update({"killed": False, "note": "the run finished before the kill point; resume not exercised"})
    else:
        p2, _ = optimize("adaptive", d, a.workers, a.floor)
        if p2.returncode != 0:
            raise SystemExit(f"resume failed: {p2.stderr[-2000:]}")
        ref = EVIDENCE / "b2quick-adaptive" / "result.json"
        same = ref.exists() and (d / "result.json").read_bytes() == ref.read_bytes()
        out.update({"killed": True, "killed_at": killed_at, "identical_to_uninterrupted": same})
    out["pass"] = bool(out.get("identical_to_uninterrupted"))
    out["end"] = eastern_now()
    print(f"resume: killed {out.get('killed')} ({out.get('killed_at')}); identical to the uninterrupted run: {out.get('identical_to_uninterrupted')}", flush=True)
    return out


def block_pairing(a) -> dict:
    from platsim.evaluate import DEFAULT_PLAYER_POLICY, run_full_gauntlets, worker_team
    from platsim.optimizer.pairing import paired_outcomes
    from platsim.optimizer.run import paired_outcomes_full
    from platsim.sampling import run_adaptive
    from platsim.sim.pool import WorkerPool
    from platsim.stats import mcnemar_exact

    out = {"start": eastern_now()}
    master = "022-pair|confirm"
    with WorkerPool(a.workers) as pool:
        teams = {n: worker_team(*load_team_candidate(n)) for n in ("b2main", "b2branch")}
        full = {n: run_full_gauntlets(pool, t, master=master, min_runs=2000, max_runs=2000, target=None,
                                      player_policy=DEFAULT_PLAYER_POLICY).results for n, t in teams.items()}
        ad = {n: run_adaptive(pool, t, master=master, min_runs=2000, max_runs=2000, target=None,
                              player_policy=DEFAULT_PLAYER_POLICY, floor=a.floor) for n, t in teams.items()}
    pf = paired_outcomes_full(full["b2main"], full["b2branch"])
    pa = paired_outcomes(ad["b2main"].full_results, ad["b2main"].cynthia_only_results,
                         ad["b2branch"].full_results, ad["b2branch"].cynthia_only_results)
    nf = pa.full_pairs
    c_full_restricted = mcnemar_exact(pf.a_flags[:nf], pf.b_flags[:nf]) if nf else None
    c_ad_full_part = mcnemar_exact(pa.a_flags[:nf], pa.b_flags[:nf]) if nf else None
    exact = (c_full_restricted is not None and (c_full_restricted.a_only, c_full_restricted.b_only)
             == (c_ad_full_part.a_only, c_ad_full_part.b_only))
    c_all = mcnemar_exact(pa.a_flags, pa.b_flags) if pa.pairs else None
    c_full_all = mcnemar_exact(pf.a_flags, pf.b_flags)
    out.update({"switch": {n: r.switch_run for n, r in ad.items()}, "full_pairs": nf, "cynthia_only_pairs": pa.cynthia_only_pairs,
                "excluded": pa.excluded,
                "full_method_counts_on_full_pairs": [c_full_restricted.a_only, c_full_restricted.b_only] if c_full_restricted else None,
                "adaptive_counts_on_full_pairs": [c_ad_full_part.a_only, c_ad_full_part.b_only] if c_ad_full_part else None,
                "exact_equality": exact,
                "adaptive_all_pairs": {"a_only": c_all.a_only, "b_only": c_all.b_only, "p": c_all.p_value, "verdict": c_all.verdict} if c_all else None,
                "full_all_pairs": {"a_only": c_full_all.a_only, "b_only": c_full_all.b_only, "p": c_full_all.p_value, "verdict": c_full_all.verdict},
                "pass": exact, "end": eastern_now()})
    print(f"pairing: switch {out['switch']}; full pairs {nf}, Cynthia-only pairs {pa.cynthia_only_pairs}, excluded {pa.excluded}; "
          f"counts on full pairs full {out['full_method_counts_on_full_pairs']} vs adaptive {out['adaptive_counts_on_full_pairs']} exact {exact}; "
          f"all pairs adaptive {out['adaptive_all_pairs']} vs full {out['full_all_pairs']}", flush=True)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", default="b2quick,confirm,resume,pairing")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--floor", type=float, default=0.98)
    ap.add_argument("--out", default=str(EVIDENCE / "acceptance.json"))
    ap.add_argument("--reuse", action="store_true", help="b2quick: reuse existing optimize directories (deterministic) instead of rerunning")
    a = ap.parse_args(argv)
    assert_idle()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = {"hashes": code_hashes()}
    fns = {"b2quick": block_b2quick, "confirm": block_confirm, "resume": block_resume, "pairing": block_pairing}
    for name in a.blocks.split(","):
        results[name] = fns[name](a)
        Path(a.out).write_text(json.dumps(results, indent=1, default=str))
    passed = all(results[n].get("pass") for n in a.blocks.split(","))
    print(json.dumps({n: results[n].get("pass") for n in a.blocks.split(",")}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
