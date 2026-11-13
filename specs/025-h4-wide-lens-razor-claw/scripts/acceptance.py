"""025 acceptance (spec FR-006, FR-009, FR-010; research R8), adapted from feature 024's script.

usage: uv run python specs/025-h4-wide-lens-razor-claw/scripts/acceptance.py --side main|branch [--workers 16] [--runs 2000]

`--side main` runs BEFORE any code change on the branch (its code equals `main`): the B2 quick optimize into
runs/025-evidence/b2-main, the identity evaluations (reference team, 014 b2-main team; 200 runs, quick, seed 025-ident)
into runs/025-evidence/ident-main/{ref,b2main}, and the candidate snapshot (the optimizer's own member_candidates call
for the six B2 species at the job's reference level) into specs/025-h4-wide-lens-razor-claw/evidence/candidates-main.json.
`--side branch` runs the same B2 quick and identity evaluations into b2-branch / ident-branch, the equal-levels paired
check (scripts/equal_levels.py, 2,000 pairs, expectimax2-v4), compares the identity reports with the code-version and
ledger fields removed, lists the members carrying a variable-power move, applies the FR-009 pass rule and prints the table.
Every result records the code hashes. Refuses to run while workers or pytest run (assert_idle). Exit 1 on a failed step.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "specs" / "019-e4-sampling-spike" / "scripts"))
from common import assert_idle, eastern_now  # noqa: E402  (feature 019 helpers)

EVIDENCE = REPO / "runs" / "025-evidence"
SPEC_EVIDENCE = REPO / "specs" / "025-h4-wide-lens-razor-claw" / "evidence"
B2_SPECIES = ["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"]
B2_SEED = "014-b2"
IDENT_RUNS = "200"
IDENT_SEED = "025-ident"
VARIABLE = {"return", "grass_knot", "low_kick", "gyro_ball"}  # result.json uses move keys (024)
NEW_ITEMS = {"wide_lens", "razor_claw"}  # 025: result.json uses item keys
# Fields that change with every feature (code version, ledger) and are removed before the identity comparison (FR-008).
VOLATILE = ("sim_code_hash", "platsim_code_hash", "repo_commit", "repo_dirty", "divergence_ledger_version",
            "divergence_ledger_file_version", "divergences")
VOLATILE_PROV = ("divergence_ledger_version",)  # under provenance.worker
VOLATILE_PROV_TOP = ("divergence_ledger_file_version", "member_defaults")  # under provenance (member_defaults is new in 025)


def log(m: str) -> None:
    print(f"acceptance: {m}", file=sys.stderr, flush=True)


def run(cmd: list[str]) -> tuple[subprocess.CompletedProcess, float]:
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    return p, time.perf_counter() - t0


def optimize(out: Path, workers: int) -> float:
    cmd = [sys.executable, "-m", "platsim.cli", "optimize", *B2_SPECIES, "--budget", "quick", "--seed", B2_SEED,
           "--workers", str(workers), "--force-new", "--out", str(out)]
    log(f"optimize -> {out.name}")
    p, wall = run(cmd)
    if p.returncode != 0:
        raise SystemExit(f"optimize {out.name} failed: {p.stderr[-2000:]}")
    return wall


def b2main_team_path() -> Path:
    src = REPO / "runs" / "014-evidence" / "b2-main" / "result.json"
    path = EVIDENCE / "teams" / "b2main.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json.loads(src.read_text())["team"]))
    return path


def identity(side: str, workers: int) -> dict:
    teams = {"ref": REPO / "tests" / "fixtures" / "reference_team.json", "b2main": b2main_team_path()}
    out = {}
    for name, team in teams.items():
        d = EVIDENCE / f"ident-{side}" / name
        cmd = [sys.executable, "-m", "platsim.cli", "evaluate", str(team), "--runs", IDENT_RUNS, "--budget", "quick",
               "--seed", IDENT_SEED, "--workers", str(workers), "--out", str(d)]
        log(f"evaluate {name} -> ident-{side}/{name}")
        p, wall = run(cmd)
        if p.returncode != 0:
            raise SystemExit(f"evaluate {name} ({side}) failed: {p.stderr[-2000:]}")
        out[name] = {"dir": str(d), "wall_s": round(wall, 1)}
    return out


def strip_volatile(d: dict) -> dict:
    d = json.loads(json.dumps(d))
    removed = {}
    for k in VOLATILE:
        if k in d:
            removed[k] = d.pop(k)
    prov = d.get("provenance") or {}
    for k in VOLATILE_PROV_TOP:
        if k in prov:
            removed[f"provenance.{k}"] = prov.pop(k)
    w = prov.get("worker") or {}
    for k in VOLATILE_PROV:
        if k in w:
            removed[f"provenance.worker.{k}"] = w.pop(k)
    return d, removed


def compare_identity() -> dict:
    out = {}
    for name in ("ref", "b2main"):
        a = json.loads((EVIDENCE / "ident-main" / name / "result.json").read_text())
        b = json.loads((EVIDENCE / "ident-branch" / name / "result.json").read_text())
        sa, ra = strip_volatile(a)
        sb, rb = strip_volatile(b)
        same = json.dumps(sa, sort_keys=True) == json.dumps(sb, sort_keys=True)
        diffs = []
        if not same:
            for k in sorted(set(sa) | set(sb)):
                if sa.get(k) != sb.get(k):
                    diffs.append(k)
        out[name] = {"identical_without_volatile": same, "differing_keys": diffs,
                     "removed_main": {k: (v if not isinstance(v, list) else f"<{len(v)} entries>") for k, v in ra.items()},
                     "removed_branch": {k: (v if not isinstance(v, list) else f"<{len(v)} entries>") for k, v in rb.items()}}
    return out


BENCH = ("B1", "B2", "B3", "B4", "B5")


def _record(mc, call: dict) -> dict:
    return {"call": call, "movesets": [list(m) for m in mc.movesets],
            "setup_moveset": list(mc.setup_moveset) if mc.setup_moveset else None,
            "ranked": [list(m) for m in mc.ranked], "pool": list(mc.pool), "pruned": dict(mc.pruned),
            "scores": {k: v for k, v in mc.scores.items()},
            "items": {"|".join(ms): list(its) for ms, its in mc.items.items()}, "level": mc.ref_level,
            "extras": getattr(mc, "extras", 0), "variable_offered": list(getattr(mc, "variable_offered", []))}


def snapshot(b2_dir: Path, out_name: str = "candidates-main.json") -> None:
    """The optimizer's own member_candidates call for B2's six species at the job's reference level, and for every B1-B5
    member at its recorded level (the 014 benchmark), with every list the attribution needs (FR-006)."""
    from platsim.availability.ledger import build_ledger
    from platsim.legality.models import LegalityOptions
    from platsim.optimizer import candidates as C

    led = build_ledger().with_options(LegalityOptions())
    legality = LegalityOptions().to_dict()
    snap = {}
    st = json.loads((b2_dir / "state.json").read_text())
    ref_level = st["stages"]["prune"]["ref_level"]
    consts = C.resolve_species(B2_SPECIES, led)
    for c in consts:
        for v in C.variants(c, led):
            call = {"species": c, "variant": v.key, "ref_level": ref_level, "legality": legality, "k": C.K_MOVESETS, "team": list(consts)}
            snap[f"B2quick|{c}|{v.key}"] = _record(C.member_candidates(c, v, ref_level, led, team=tuple(consts)), call)
    for b in BENCH:
        builds = json.loads((REPO / "runs" / "bench-010" / b / "result.json").read_text())["team"]["builds"]
        names = [x["species"] for x in builds]
        bconsts = C.resolve_species(names, led)
        for (x, c) in zip(builds, bconsts):
            v = C.variants(c, led)[0]
            lvl = int(x["start_level"])
            call = {"species": c, "variant": v.key, "ref_level": lvl, "legality": legality, "k": C.K_MOVESETS, "team": list(bconsts)}
            snap[f"{b}|{c}|{v.key}"] = _record(C.member_candidates(c, v, lvl, led, team=tuple(bconsts)), call)
    SPEC_EVIDENCE.mkdir(parents=True, exist_ok=True)
    (SPEC_EVIDENCE / out_name).write_text(json.dumps(snap, indent=1))
    log(f"snapshot: {len(snap)} member variants -> {out_name}")


def winner_row(d: Path) -> dict:
    res = json.loads((d / "result.json").read_text())
    st = json.loads((d / "state.json").read_text())
    builds = res["team"]["builds"]
    return {"dir": d.name, "species": [b["species"] for b in builds],
            "moves": [[m["move"] for m in b["moves"]] for b in builds],
            "items": [b.get("held_item") for b in builds], "levels": [b["start_level"] for b in builds],
            "variable_members": [b["species"] for b in builds if any(m["move"] in VARIABLE for m in b["moves"])],
            "new_item_members": {b["species"]: b.get("held_item") for b in builds if b.get("held_item") in NEW_ITEMS},
            "clear_rate": res["clear_rate"], "clear_ci95": res["clear_ci95"], "n_runs": res["n_runs"],
            "qualified": res["qualified"], "borderline": res["borderline"],
            "expected_avg_final_level": res["expected_avg_final_level"],
            "confirm_attempts": len(st["stages"].get("confirm_attempts") or []),
            "sim_code_hash": res["sim_code_hash"], "platsim_code_hash": res["platsim_code_hash"], "repo_commit": res.get("repo_commit")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--side", choices=("main", "branch"), required=True)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--runs", type=int, default=2000, help="equal-levels paired gauntlets (branch side)")
    a = ap.parse_args(argv)
    assert_idle()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out = {"side": a.side, "start": eastern_now()}
    print(f"start {out['start']} side {a.side}", flush=True)
    b2 = EVIDENCE / f"b2-{a.side}"
    out["b2_wall_s"] = round(optimize(b2, a.workers), 1)
    out["b2"] = winner_row(b2)
    print(f"b2-{a.side}: {out['b2']['species']} levels {out['b2']['levels']} clear {out['b2']['clear_rate']:.4f} "
          f"{[round(x, 4) for x in out['b2']['clear_ci95']]} n {out['b2']['n_runs']} attempts {out['b2']['confirm_attempts']} "
          f"wall {out['b2_wall_s']} s new-item members {out['b2']['new_item_members']}", flush=True)
    out["identity_runs"] = identity(a.side, a.workers)
    if a.side == "main":
        snapshot(b2)
    else:
        main_row = winner_row(EVIDENCE / "b2-main")
        out["b2_main"] = main_row
        # FR-003 (025): the capped list follows today's rule from the base options; report the overlap with the main run
        sm = json.loads((EVIDENCE / "b2-main" / "state.json").read_text())["stages"]["screen"]
        sb = json.loads((b2 / "state.json").read_text())["stages"]["screen"]
        main_keys = {json.dumps(c, sort_keys=True) for c in sm["candidates"]}
        branch_keys = [json.dumps(c, sort_keys=True) for c in sb["candidates"]]
        out["screen"] = {"main_candidates": len(sm["candidates"]), "branch_candidates": len(sb["candidates"]),
                         "overlap": sum(1 for k in branch_keys if k in main_keys), "extras_screened": sb.get("extras_screened")}
        print(f"screen: main {len(sm['candidates'])} teams, branch {len(sb['candidates'])} (extras {sb.get('extras_screened')}); "
              f"overlap {out['screen']['overlap']} of {len(sm['candidates'])}", flush=True)
        # FR-006: the attributed diff of every snapshot member through scripts/attribution.py
        import importlib.util
        spec = importlib.util.spec_from_file_location("attribution025", REPO / "specs/025-h4-wide-lens-razor-claw/scripts/attribution.py")
        attribution = importlib.util.module_from_spec(spec); sys.modules["attribution025"] = attribution; spec.loader.exec_module(attribution)
        snapshot(b2, out_name="candidates-branch.json")
        main_snap = json.loads((SPEC_EVIDENCE / "candidates-main.json").read_text())
        diff = attribution.attribute_snapshot(main_snap)
        out["attributed_diff"] = diff
        n_defect = sum(1 for recs in diff.values() for r in recs if r["cause"] == "defect")
        for key, recs in diff.items():
            counts = {}
            for r in recs:
                counts[r["cause"]] = counts.get(r["cause"], 0) + 1
            print(f"diff {key}: {counts if counts else 'identical'}", flush=True)
            for r in recs:
                if r["cause"] == "defect":
                    print(f"DEFECT {key}: {r}", flush=True)
        out["defects"] = n_defect
        eq = [sys.executable, str(REPO / "specs/025-h4-wide-lens-razor-claw/scripts/equal_levels.py"),
              str(EVIDENCE / "b2-main"), str(b2), str(a.runs)]
        log("equal levels")
        p, wall = run(eq)
        if p.returncode != 0:
            raise SystemExit(f"equal_levels failed: {p.stderr[-2000:]}")
        eqr = json.loads(p.stdout.strip().splitlines()[-1])
        eqr["wall_s"] = round(wall, 1)
        out["equal_levels"] = eqr
        level_diff = out["b2"]["expected_avg_final_level"] - main_row["expected_avg_final_level"]
        out["level_diff_branch_minus_main"] = round(level_diff, 3)
        out["pass"] = eqr["verdict"] != "B" and level_diff <= 1.0 and n_defect == 0
        print(f"equal levels at {eqr['levels']}: n {eqr['n']} A(branch) {eqr['a_rate']:.4f} B(main) {eqr['b_rate']:.4f} "
              f"only A {eqr['a_only']} / only B {eqr['b_only']} p {eqr['p_value']:.3g} verdict {eqr['verdict']}; "
              f"winners' expected avg final level branch {out['b2']['expected_avg_final_level']:.2f} vs main "
              f"{main_row['expected_avg_final_level']:.2f} (diff {level_diff:+.2f}); defects {n_defect}; FR-010 pass {out['pass']}", flush=True)
    out["end"] = eastern_now()
    (EVIDENCE / f"acceptance-{a.side}.json").write_text(json.dumps(out, indent=1))
    print(f"end {out['end']}", flush=True)
    return 0 if out.get("pass", True) else 1


if __name__ == "__main__":
    sys.exit(main())
