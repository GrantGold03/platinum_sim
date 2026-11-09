"""024 acceptance (spec FR-008, FR-009; research R8).

usage: uv run python specs/024-variable-power-moves/scripts/acceptance.py --side main|branch [--workers 16] [--runs 2000]

`--side main` runs BEFORE any code change on the branch (its code equals `main`): the B2 quick optimize into
runs/024-evidence/b2-main, the identity evaluations (reference team, 014 b2-main team; 200 runs, quick, seed 024-ident)
into runs/024-evidence/ident-main/{ref,b2main}, and the candidate snapshot (the optimizer's own member_candidates call
for the six B2 species at the job's reference level) into specs/024-variable-power-moves/evidence/b2-candidates-main.json.
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

EVIDENCE = REPO / "runs" / "024-evidence"
SPEC_EVIDENCE = REPO / "specs" / "024-variable-power-moves" / "evidence"
B2_SPECIES = ["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"]
B2_SEED = "014-b2"
IDENT_RUNS = "200"
IDENT_SEED = "024-ident"
VARIABLE = {"MOVE_RETURN", "MOVE_GRASS_KNOT", "MOVE_LOW_KICK", "MOVE_GYRO_BALL"}
# Fields that change with every feature (code version, ledger) and are removed before the identity comparison (FR-008).
VOLATILE = ("sim_code_hash", "platsim_code_hash", "repo_commit", "repo_dirty", "divergence_ledger_version",
            "divergence_ledger_file_version", "divergences")
VOLATILE_PROV = ("divergence_ledger_version",)  # under provenance.worker


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
    w = (d.get("provenance") or {}).get("worker") or {}
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


def snapshot(b2_dir: Path) -> None:
    from platsim.availability.ledger import build_ledger
    from platsim.legality.models import LegalityOptions
    from platsim.optimizer import candidates as C

    st = json.loads((b2_dir / "state.json").read_text())
    ref_level = st["stages"]["prune"]["ref_level"]
    led = build_ledger().with_options(LegalityOptions())
    consts = C.resolve_species(B2_SPECIES, led)
    snap = {}
    for c in consts:
        for v in C.variants(c, led):
            mc = C.member_candidates(c, v, ref_level, led, team=tuple(consts))
            snap[f"{c}|{v.key}"] = {
                "call": {"species": c, "variant": v.key, "ref_level": ref_level, "legality": LegalityOptions().to_dict(),
                         "k": C.K_MOVESETS, "team": list(consts)},
                "movesets": [list(m) for m in mc.movesets], "setup_moveset": list(mc.setup_moveset) if mc.setup_moveset else None,
                "ranked_prefix": [list(m) for m in mc.ranked[:210]], "pool": list(mc.pool),
                "level": mc.ref_level}
    SPEC_EVIDENCE.mkdir(parents=True, exist_ok=True)
    (SPEC_EVIDENCE / "b2-candidates-main.json").write_text(json.dumps(snap, indent=1))
    log(f"snapshot: {len(snap)} member variants at ref_level {ref_level}")


def winner_row(d: Path) -> dict:
    res = json.loads((d / "result.json").read_text())
    st = json.loads((d / "state.json").read_text())
    builds = res["team"]["builds"]
    return {"dir": d.name, "species": [b["species"] for b in builds],
            "moves": [[m["move"] for m in b["moves"]] for b in builds],
            "items": [b.get("held_item") for b in builds], "levels": [b["start_level"] for b in builds],
            "variable_members": [b["species"] for b in builds if any(m["move"] in VARIABLE for m in b["moves"])],
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
          f"wall {out['b2_wall_s']} s variable members {out['b2']['variable_members']}", flush=True)
    out["identity_runs"] = identity(a.side, a.workers)
    if a.side == "main":
        snapshot(b2)
    else:
        main_row = winner_row(EVIDENCE / "b2-main")
        out["b2_main"] = main_row
        out["identity"] = compare_identity()
        for name, r in out["identity"].items():
            print(f"identity {name}: identical without volatile fields {r['identical_without_volatile']}"
                  + (f" differing {r['differing_keys']}" if r["differing_keys"] else ""), flush=True)
        eq = [sys.executable, str(REPO / "specs/024-variable-power-moves/scripts/equal_levels.py"),
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
        out["pass"] = eqr["verdict"] != "B" and level_diff <= 1.0
        print(f"equal levels at {eqr['levels']}: n {eqr['n']} A(branch) {eqr['a_rate']:.4f} B(main) {eqr['b_rate']:.4f} "
              f"only A {eqr['a_only']} / only B {eqr['b_only']} p {eqr['p_value']:.3g} verdict {eqr['verdict']}; "
              f"winners' expected avg final level branch {out['b2']['expected_avg_final_level']:.2f} vs main "
              f"{main_row['expected_avg_final_level']:.2f} (diff {level_diff:+.2f}); FR-009 pass {out['pass']}", flush=True)
    out["end"] = eastern_now()
    (EVIDENCE / f"acceptance-{a.side}.json").write_text(json.dumps(out, indent=1))
    print(f"end {out['end']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
