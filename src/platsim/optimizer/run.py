"""Optimizer orchestration (T065; spec User Story 1, FR-015-FR-019, SC-001-SC-004; research.md R8).

`run_optimization(OptimizeRequest, progress) -> OptimizeResult` (the interface in optimizer/api.py).

OBJECTIVE (stated in every result, Constitution IV): among teams whose full-gauntlet clear rate meets
the threshold (FR-015), minimise the expected average level of the six members after the Champion is
defeated, with final level gap <= 10 (FR-016).

Stages (each checkpointed in <out>/state.json; a re-run with the same request resumes from it, only if the
code fingerprint matches - see _State; `--force-new` starts over)
-------------------------------------------------------------------------------------------------
0. resolve: species names -> SPECIES_* (candidates.resolve_species; InvalidRequest = CLI exit 2).
1. prune / candidates (candidates.py, resources.py): source variants, legal move pools, R8 dominance
   pruning, coverage-ranked movesets, held items; team-wide TM/item/source copy limits (a candidate
   that breaks one is never generated: resources.repair falls back to the member's next-best set).
   Pass A uses move legality at Lv 100 to build a calibration baseline.
2. calibrate (greedy-v1): the lowest uniform level U_g at which the baseline clears >= 50% with
   greedy-v1 (bisection; `rounds[0]` runs per point; seeds derive_seed(f"{seed}|calibrate", i, 0)),
   so the screen is run where candidates differ. Pass B then rebuilds the candidates with move legality
   at ref = U_g - 5 (heuristic: expectimax2-v2 needs fewer levels than greedy-v1, R7, and the level
   search will go below U_g; moves are kept legal there). Screening vector: max(U_g, member minimum).
3. ability_screen (abilities.choose_ability, T060, greedy-v1, FR-008c) on the pass-B baseline, per
   member; the result applies to every candidate with that member's source variant. A finalist member
   whose variant was not tested is screened again on the finalist team.
4. screen (screen.py, greedy-v1): successive halving over up to N_CANDIDATES teams = the baseline,
   every single-member variation (moveset x item x source variant), then seeded random combinations;
   rounds and the top-third rule from the budget preset; finalists = best two.
5. level_search (levels.py, expectimax2-v2): bisection on the uniform level, then the alternatives stage (007),
   then the balanced per-member descent; each point PASS/FAIL by the sequential rule in levels.py.
   alternatives (007, optimizer/alternatives.py, played by move_classes.ALT_POLICY = expectimax2-v3): per
   member, status-move alternatives at the current team's first failing neighbour U - 1; successive
   halving, then the top 3 vs the current team (McNemar exact, Holm), the winner confirmed on a fresh
   block and adopted only if both are significant (FR-008: not "better" without support).
6. confirm (evaluate.evaluate_team, the `platsim evaluate` path): the winner at its final levels,
   >= `confirm_min` expectimax2-v2 runs, more until the CI target is met and, for qualifying presets,
   more while the CI straddles the threshold (up to 4 x confirm_min); Cynthia top-up (T057); loss causes.
   If the confirmed rate misses the threshold or is borderline, every start level is raised by 1; if
   only the final gap (> 10) fails, the lowest members are raised by 1; the confirm is repeated at most
   MAX_CONFIRM_BUMPS times; then "no qualifying team". The runner-up is played on the SAME seeds at the same levels (raised to its floors if needed)
   and compared by McNemar exact (FR-019). It replaces the winner only if significantly better AND it
   passes the same confirm checks; otherwise the comparison is reported (possibly "indistinguishable").
7. report: the independent validator runs on the final team (any violation is a hard error,
   Constitution III); result.json / result.xlsx / result.csv / team.txt via report.write_all.

Determinism (SC-004): every stage consumes worker results in request order and stops at the first index
that meets its rule; every seed is derived from the request seed; result.json contains no wall-clock
time or path. So identical requests give identical results for any worker count. Timings go to
state.json only.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time
from dataclasses import replace
from pathlib import Path

from platsim import pins, version
from platsim.budget import get_preset
from platsim.legality import movesources as MS
from platsim.optimizer import candidates as C
from platsim.optimizer import move_classes as MC
from platsim.optimizer import resources as R
from platsim.optimizer.api import InvalidRequest, OptimizeRequest, OptimizeResult, Progress, ProgressCallback
from platsim.optimizer.levels import LevelSearch, Point, team_key
from platsim.optimizer.screen import ScreenResult, successive_halving
from platsim.sim.seeds import SCHEME, derive_seed
from platsim.stats import mcnemar_exact, wilson_ci

STATE_VERSION = 4  # 2: balanced descent (levels.py); 3: strong player expectimax2-v2; 4: 007 alternatives stage
CALIBRATION_TARGET = 0.5
REF_MARGIN = 5
N_CANDIDATES = 81
MAX_CONFIRM_BUMPS = 2
POLICY = "expectimax2-v2"  # v1 until the policy-reversal fix (sim/policy/expectimax2.mjs VERSIONS)
SCREEN_POLICY = "greedy-v1"
OPPONENT = "decomp-ai"


def _log(msg: str) -> None:
    print(f"platsim optimize: {msg}", file=sys.stderr, flush=True)


def job_fingerprint(consts: list[str], req: OptimizeRequest) -> dict:
    fp = {"species": list(consts), "min_clear": req.min_clear, "seed": str(req.seed), "budget": req.budget,
          "legality_options": req.legality.to_dict(compact=True), "state_version": STATE_VERSION}
    if req.required_hms:  # 006 FR-009: only when set, so default fingerprints (and resume) are unchanged
        fp["required_hms"] = list(req.required_hms)
    fp["candidates"] = req.candidates  # 007 (state version 4)
    if req.alternatives_round is not None:
        fp["alternatives_round"] = req.alternatives_round
    if req.alternatives_members is not None:
        fp["alternatives_members"] = req.alternatives_members
    return fp


def default_out_dir(fp: dict) -> Path:
    h = hashlib.sha256(json.dumps(fp, sort_keys=True).encode()).hexdigest()[:12]
    return pins.REPO_ROOT / "runs" / f"optimize-{h}"


class _State:
    """<out>/state.json: the job fingerprint (request), the code fingerprint (platsim/version.py:
    sim + platsim code hashes, node/python versions, pinned commits, data hash, ledger version) and the
    stage checkpoints. A resume is refused when the job differs, or when any behaviour field of the code
    fingerprint differs (version.BEHAVIOUR_KEYS), so one result never mixes code versions. With
    `force_new` the old checkpoint and result files are moved to <out>/superseded-N/ and the job starts
    over."""

    def __init__(self, path: Path, fp: dict, code: dict, force_new: bool = False):
        self.path = path
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            problem = None
            if data.get("fingerprint") != fp:
                problem = (f"{path.parent} holds a different optimize job ({data.get('fingerprint')})")
            else:
                diff = version.fingerprint_diff(data.get("code"), code)
                if diff:
                    what = ("it records no code fingerprint (written before code versioning)" if not data.get("code")
                            else "; ".join(f"{k}: checkpoint {a!r}, now {b!r}" for k, (a, b) in diff.items()))
                    problem = (f"{path} was produced by different code/data, refusing to resume and mix versions: "
                               f"{what}")
            if problem and not force_new:
                raise InvalidRequest(f"{problem}. Re-run with --force-new to start over in this directory (the old "
                                     "checkpoint and results are moved to a superseded-N/ subdirectory), or use "
                                     "another --out.")
            if force_new:
                moved = _supersede(path.parent)
                _log(f"--force-new: previous checkpoint and results moved to {moved}")
            else:
                self.data = data
                if any(data["code"].get(k) != code.get(k) for k in ("repo_commit", "repo_dirty")):
                    _log(f"note: repo commit/dirty state differs from the checkpoint ({data['code'].get('repo_commit')}, "
                         f"dirty={data['code'].get('repo_dirty')}); code hashes match, resuming")
                _log(f"resuming from {path} (stages done: {sorted(self.data.get('stages', {}))})")
                return
        self.data = {"fingerprint": fp, "code": code, "stages": {}, "level_points": {}, "timing": {}}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.part")
        tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def stage(self, name: str):
        return self.data["stages"].get(name)

    def done(self, name: str, value, seconds: float | None = None) -> None:
        self.data["stages"][name] = value
        if seconds is not None:
            self.data["timing"][name] = round(seconds, 1)
        self.save()


def _supersede(out: Path) -> Path:
    """Move state.json and the result files of `out` into a fresh out/superseded-N/ (nothing is deleted)."""
    n = 1
    while (out / f"superseded-{n}").exists():
        n += 1
    dest = out / f"superseded-{n}"
    dest.mkdir(parents=True)
    for name in ("state.json", "result.json", "result.xlsx", "result.csv", "team.txt"):
        if (out / name).exists():
            os.replace(out / name, dest / name)
    return dest


class _Progress:
    def __init__(self, cb: ProgressCallback | None):
        self.cb = cb

    def __call__(self, stage: str, runs_done: int = 0, runs_planned: int | None = None, best=None, detail: str = "",
                 **extra) -> None:
        if detail:
            _log(f"[{stage}] {detail}")
        if self.cb:
            try:
                self.cb(Progress(stage, runs_done, runs_planned, best, detail, dict(extra)))
            except Exception as e:  # noqa: BLE001 - a broken UI callback must not kill the job
                _log(f"progress callback failed: {e!r}")


# ---------------------------------------------------------------------------------------------
# helpers


def _apply_abilities(specs, abilities: dict) -> tuple:
    out = []
    for slot, s in enumerate(specs):
        a = abilities.get(f"{slot}|{s.variant}")
        if a:
            s = replace(s, ability=a["ability"], ability_reason=a["reason"])
        else:
            s = replace(s, ability=None, ability_reason=None)
        out.append(s)
    return tuple(out)


def _member_options(mcs: dict) -> list[tuple[str, tuple, str | None]]:
    """(variant key, moveset, item) choices of one member, the baseline first."""
    out = []
    for vkey, mc in mcs.items():
        for ms in mc.movesets:
            for item in mc.items[ms]:
                out.append((vkey, ms, item))
    return out


def _build_cands(consts, led, ref_level: int) -> list[dict]:
    out = []
    for c in consts:
        out.append({v.key: C.member_candidates(c, v, ref_level, led, team=tuple(consts)) for v in C.variants(c, led)})
    return out


def _baseline(cands, consts) -> tuple:
    specs = []
    for c, mcs in zip(consts, cands):
        vkey, mc = next(iter(mcs.items()))
        ms = mc.movesets[0]
        specs.append(R.MemberSpec(c, vkey, ms, mc.items[ms][0]))
    return tuple(specs)


def _ranked(cands, specs) -> list:
    return [cands[i][s.variant].ranked for i, s in enumerate(specs)]


def _summary(p: Point | None) -> dict | None:
    if p is None:
        return None
    lo, hi = wilson_ci(p.wins, p.n) if p.n else (0.0, 1.0)
    return {"levels": p.levels, "clear_rate": round(p.rate, 4), "ci95": [round(lo, 4), round(hi, 4)], "runs": p.n,
            "avg_final_level": round(p.avg_final, 2) if p.avg_final is not None else None}


def _check(results: list[dict]) -> None:
    for r in results:
        if not r.get("ok"):
            raise RuntimeError(f"gauntlet failed: {r.get('error')}")


def _paired(pool, team: list[dict], master: str, n: int, policy: str) -> list[bool]:
    reqs = [{"op": "gauntlet", "team": team, "seed": derive_seed(master, i, 0), "player_policy": policy,
             "opponent_policy": OPPONENT, "stop_on_loss": True, "log": "none"} for i in range(n)]
    rs = pool.map(reqs)
    _check(rs)
    for r in rs:
        if (r["player_policy"], r["opponent_policy"]) != (policy, OPPONENT):
            raise RuntimeError(f"worker ran {r['player_policy']}/{r['opponent_policy']}")
    return [bool(r["cleared"]) for r in rs]


# ---------------------------------------------------------------------------------------------
# main


def run_optimization(req: OptimizeRequest, progress: ProgressCallback | None = None) -> OptimizeResult:
    from platsim.availability.ledger import build_ledger
    from platsim.sim.pool import WorkerPool

    t_start = time.perf_counter()
    prog = _Progress(progress)
    try:
        preset = get_preset(req.budget)
    except ValueError as e:
        raise InvalidRequest(str(e)) from e
    if not 0.0 < float(req.min_clear) <= 1.0:
        raise InvalidRequest(f"min_clear must be in (0, 1], got {req.min_clear}")
    if req.workers is not None and req.workers < 1:
        raise InvalidRequest(f"workers must be >= 1, got {req.workers}")
    prog("resolve", detail=f"resolving {list(req.species)}")
    # Every legality / candidate query below reads the options from this ledger view (Ledger.with_options).
    led = build_ledger().with_options(req.legality)
    consts = C.resolve_species(req.species, led)
    if req.required_hms:  # 006 FR-005: refuse an impossible HM requirement before any battle
        missing = MS.unlearnable_moves(consts, req.required_hms, led)
        if missing:
            reasons = {k: MS.unlearnable_text(k) for k in missing}
            raise InvalidRequest("required HMs no team member can learn: " + "; ".join(reasons.values()), reasons)
    fp = job_fingerprint(consts, req)
    out = Path(req.out_dir) if req.out_dir else default_out_dir(fp)
    # The pool starts first: its hello (agreed by every worker) gives the sim code hash and data
    # fingerprint that the checkpoint must match before anything is resumed.
    pool = WorkerPool(req.workers)
    try:
        state = _State(out / "state.json", fp, version.code_fingerprint(pool.hello), force_new=req.force_new)
        if state.stage("report") and (out / "result.json").is_file():
            prog("done", detail=f"already complete: {out}")
            return OptimizeResult(out, bool(state.stage("report")["qualified"]))
        state.save()
        qualified = _run(req, preset, led, consts, out, state, pool, prog)
    finally:
        pool.close()
    state.data["timing"]["total_s_this_session"] = round(time.perf_counter() - t_start, 1)
    state.save()
    prog("done", detail=f"wrote {out} (qualified={qualified})")
    return OptimizeResult(out, qualified)


def _run(req, preset, led, consts, out: Path, state: _State, pool, prog) -> bool:
    from platsim.evaluate import run_full_gauntlets, worker_team
    from platsim.legality.validator import validate

    seed = str(req.seed)
    thr = float(req.min_clear)
    hello = pool.hello
    for need, key in ((POLICY, "policies"), (SCREEN_POLICY, "policies"), (MC.ALT_POLICY, "policies"), (OPPONENT, "opponent_policies")):
        if need not in hello[key]:
            raise RuntimeError(f"worker does not offer {need!r} ({key}: {hello[key]})")

    def wteam(specs, levels):
        r = R.realize(specs, levels, led, required_hms=req.required_hms)
        if isinstance(r, R.Refusal):
            return None
        return worker_team(r.team, led)

    # -- 1-2: candidates pass A + calibration ---------------------------------------------------
    t0 = time.perf_counter()
    prog("prune", detail="building candidates (pass A, move legality at Lv 100)")
    cands_a = _build_cands(consts, led, 100)
    base_a = R.repair(_baseline(cands_a, consts), [100] * 6, led, _ranked(cands_a, _baseline(cands_a, consts)), required_hms=req.required_hms)
    if isinstance(base_a, R.Refusal):
        raise InvalidRequest(f"no legal team can be formed: {base_a.reason}")
    base_a = base_a[0]
    cal = state.stage("calibrate")
    if cal is None:
        floors_a = [R.member_floor(s, led) for s in base_a]
        lo_u = max(1, max(floors_a) - 10)
        n_cal = preset.screening_rounds[0]
        points = {}

        def rate(u: int) -> float:
            levels = [max(u, f) for f in floors_a]
            team = wteam(base_a, levels)
            res = _paired(pool, team, f"{seed}|calibrate", n_cal, SCREEN_POLICY)
            points[str(u)] = {"levels": levels, "runs": n_cal, "cleared": sum(res)}
            prog("calibrate", runs_done=len(points) * n_cal, detail=f"greedy-v1 at U={u}: {sum(res)}/{n_cal} cleared")
            return sum(res) / n_cal

        lo, hi = lo_u - 1, 100  # invariant: rate(hi) >= target or hi == 100
        if rate(100) >= CALIBRATION_TARGET:
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if rate(mid) >= CALIBRATION_TARGET:
                    hi = mid
                else:
                    lo = mid
        cal = {"u_greedy": hi, "target": CALIBRATION_TARGET, "runs_per_point": n_cal, "points": points,
               "baseline_a": R.spec_to_json(base_a), "floors_a": floors_a,
               "seeds": f"derive_seed('{seed}|calibrate', i, 0)", "policy": SCREEN_POLICY}
        state.done("calibrate", cal, time.perf_counter() - t0)
    u_g = cal["u_greedy"]
    ref = max(1, u_g - REF_MARGIN)
    prog("prune", detail=f"building candidates (pass B, move legality at Lv {ref}; screening level {u_g})")
    cands = _build_cands(consts, led, ref)
    screen_levels = [max(u_g, max(mc.ref_level for mc in mcs.values())) for mcs in cands]
    b = R.repair(_baseline(cands, consts), screen_levels, led, _ranked(cands, _baseline(cands, consts)), required_hms=req.required_hms)
    if isinstance(b, R.Refusal):
        raise InvalidRequest(f"no legal team can be formed: {b.reason}")
    baseline, base_notes = b
    if state.stage("prune") is None:
        state.done("prune", {"ref_level": ref, "screen_levels": screen_levels,
                             "members": [{k: mc.summary() for k, mc in mcs.items()} for mcs in cands],
                             "baseline": R.spec_to_json(baseline), "baseline_repairs": base_notes})

    # -- 3: abilities ----------------------------------------------------------------------------
    from platsim.optimizer.abilities import choose_ability

    abilities = state.stage("ability_screen")
    if abilities is None:
        t0 = time.perf_counter()
        abilities = {}
        team = R.realize(baseline, screen_levels, led, required_hms=req.required_hms).team
        for slot, s in enumerate(baseline):
            prog("ability_screen", runs_done=slot, runs_planned=6, detail=f"slot {slot + 1} {C.display_name(s.species)}")
            ch = choose_ability(pool, team.builds, slot, seed=seed, budget=preset.name, ledger=led)
            abilities[f"{slot}|{s.variant}"] = {"ability": ch.ability, "reason": ch.reason, "stats": ch.stats,
                                                "tested_on": "pass-B baseline at the screening levels"}
        state.done("ability_screen", abilities, time.perf_counter() - t0)

    # -- 4: screen -------------------------------------------------------------------------------
    scr = state.stage("screen")
    if scr is None:
        t0 = time.perf_counter()
        opts = [_member_options(mcs) for mcs in cands]
        base_idx = []
        for slot, s in enumerate(baseline):
            k = (s.variant, s.moves, s.item)
            base_idx.append(opts[slot].index(k) if k in opts[slot] else None)
        combos: list[tuple] = [tuple(base_idx)]
        for slot in range(6):
            for j in range(len(opts[slot])):
                if j != base_idx[slot]:
                    c = list(base_idx)
                    c[slot] = j
                    combos.append(tuple(c))
        rng = random.Random(int(hashlib.sha256(f"{seed}|screen-candidates".encode()).hexdigest(), 16))
        tries = 0
        while len(combos) < 4 * N_CANDIDATES and tries < 20 * N_CANDIDATES:
            tries += 1
            c = tuple(rng.randrange(len(o)) for o in opts)
            if c not in combos:
                combos.append(c)
        teams_specs, seen, dropped = [], set(), []
        for c in combos:
            if len(teams_specs) >= N_CANDIDATES:
                break
            if c == tuple(base_idx):
                specs = baseline
            else:
                specs = tuple(baseline[s] if j is None else R.MemberSpec(consts[s], *opts[s][j]) for s, j in enumerate(c))
            specs = _apply_abilities(specs, abilities)
            rr = R.repair(specs, screen_levels, led, _ranked(cands, specs), required_hms=req.required_hms)
            if isinstance(rr, R.Refusal):
                dropped.append({"combo": list(c), "reason": rr.reason})
                continue
            specs = rr[0]
            key = json.dumps(R.spec_to_json(specs))
            if key in seen:
                continue
            real = R.realize(specs, screen_levels, led, required_hms=req.required_hms)
            v = validate(real.team, led, required_hms=req.required_hms)
            if v:  # the optimizer is not trusted (Constitution III): never screened
                dropped.append({"combo": list(c), "reason": "validator: " + "; ".join(x.message for x in v[:3])})
                continue
            seen.add(key)
            teams_specs.append(specs)
        prog("screen", detail=f"{len(teams_specs)} candidate teams at levels {screen_levels}")
        wteams = [worker_team(R.realize(s, screen_levels, led, required_hms=req.required_hms).team, led) for s in teams_specs]
        res = successive_halving(pool, wteams, seed=seed, rounds=preset.screening_rounds,
                                 progress=lambda d, p, best, sc, r: prog(
                                     "screen", runs_done=d, runs_planned=p,
                                     best={"candidate": best, "cleared": sc[0], "runs": sc[2]},
                                     detail=f"round {r}: best candidate {best} cleared {sc[0]}/{sc[2]}"))
        scr = {"levels": screen_levels, "candidates": [R.spec_to_json(s) for s in teams_specs],
               "labels": [[m.label() for m in s] for s in teams_specs], "dropped": dropped,
               "result": res.to_dict(), "policy": SCREEN_POLICY, "seeds": f"derive_seed('{seed}|screen', i, 0)",
               "finalists": res.order[:2]}
        state.done("screen", scr, time.perf_counter() - t0)
    res = ScreenResult.from_dict(scr["result"])
    finalists = [R.spec_from_json(scr["candidates"][i]) for i in scr["finalists"]]

    # ability re-screen for finalist members whose variant was not tested
    for fi, specs in enumerate(finalists):
        for slot, s in enumerate(specs):
            k = f"{slot}|{s.variant}"
            if k not in abilities:
                team = R.realize(specs, screen_levels, led, required_hms=req.required_hms).team
                ch = choose_ability(pool, team.builds, slot, seed=seed, budget=preset.name, ledger=led)
                abilities[k] = {"ability": ch.ability, "reason": ch.reason, "stats": ch.stats,
                                "tested_on": f"finalist {fi + 1} at the screening levels"}
                state.done("ability_screen", abilities)
        finalists[fi] = _apply_abilities(specs, abilities)

    # -- 5: level search -------------------------------------------------------------------------
    margin = preset.ci_half_width if preset.ci_half_width is not None else 0.02
    memo = state.data["level_points"]
    ls_state = state.data["stages"].setdefault("level_search", {})
    t0 = time.perf_counter()

    def make_search(specs) -> LevelSearch:
        floors = [R.member_floor(s, led) for s in specs]

        def on_point(p: Point) -> None:
            state.save()
            prog("level_search", runs_done=p.n, best=_summary(p),
                 detail=f"levels {p.levels}: {p.wins}/{p.n} cleared -> {p.decision}"
                        + (f", avg final {p.avg_final:.2f}" if p.avg_final else ""))

        return LevelSearch(pool, lambda lv: wteam(specs, lv), floors, seed=seed, budget=preset.name, threshold=thr,
                           margin=margin, key=team_key(R.spec_to_json(specs)), memo=memo, on_point=on_point,
                           on_batch=lambda lv, n, w: prog("level_search", runs_done=n,
                                                          detail=f"levels {lv}: {w}/{n} so far"))

    winner = finalists[0]
    search = make_search(winner)
    u, pt = search.bisect_uniform(u_g)
    ls_state["bisection"] = {"start_u": u_g, "u": u, "point": _summary(pt), "floors": search.floors}
    state.save()
    if u is None:
        best = max(search.points, key=lambda p: (p.rate, -sum(p.levels)))
        return _no_qualifying(req, preset, led, consts, out, state, hello, best, winner,
                              "U = 100 (every member at Lv 100 or its floor) does not pass the level-search rule")

    levels = list(pt.levels)
    # 007 alternatives stage (replaces the setup check; optimizer/alternatives.py, spec FR-007/FR-008/FR-017):
    # status-move alternatives per member, played by ALT_POLICY near the clear threshold.
    from platsim.optimizer import alternatives as ALT
    from platsim.optimizer.levels import MAX_GAP

    alt_state = ls_state.setdefault("alternatives", {})
    if not alt_state.get("done"):
        lo_bound = max(1, max(search.floors) - MAX_GAP)
        cmp_levels = search.vector(u - 1) if u - 1 >= lo_bound else list(levels)
        alt_state["levels"] = cmp_levels
        alt_state["level_rule"] = "U - 1 (first failing neighbour)" if u - 1 >= lo_bound else "bisection levels (U - 1 below the bound)"
        alt_state["round_size"] = req.alternatives_round or ALT.DEFAULT_ROUND
        alt_state["policy"] = MC.ALT_POLICY

        def save(records):
            alt_state["records"] = records
            state.save()

        winner, records = ALT.run_stage(
            pool=pool, specs=winner, cands=cands, levels=cmp_levels, led=led, seed=seed, n_full=preset.ability_screen,
            round_size=alt_state["round_size"], wteam=wteam, members=req.alternatives_members, save=save,
            done=alt_state.get("records"),
            progress=lambda slot, r, n, alive: prog("alternatives", detail=f"slot {slot + 1}: round {r}, {alive} of {n} alternatives kept"))
        alt_state.update({"records": records, "winner": R.spec_to_json(winner), "done": True})
        state.save()
    else:
        winner = R.spec_from_json(alt_state["winner"])
    search = make_search(winner)
    p0 = search.test(levels)
    if not p0.passed:  # an adopted alternative must still pass at the bisection levels
        u2, p0 = search.bisect_uniform(u)
        if u2 is None:
            best = max(search.points, key=lambda p: (p.rate, -sum(p.levels)))
            return _no_qualifying(req, preset, led, consts, out, state, hello, best, winner, "no passing level vector")
        levels = list(p0.levels)
    if "descent" not in ls_state:
        levels, best_pt, trace = search.descend(levels, p0)
        ls_state["descent"] = {"levels": levels, "point": _summary(best_pt), "trace": trace}
        state.data["timing"]["level_search"] = round(time.perf_counter() - t0, 1)
        state.save()
    levels = ls_state["descent"]["levels"]

    # -- 6: confirm ------------------------------------------------------------------------------
    return _confirm(req, preset, led, consts, out, state, pool, prog, winner, finalists, levels, cands, abilities,
                    hello, wteam)


def _confirm_ok(rep, preset, thr) -> bool:
    if rep.no_qualifying is not None or rep.n_runs == 0:
        return False
    hw = (rep.clear_ci95[1] - rep.clear_ci95[0]) / 2
    return (rep.clear_rate >= thr and not rep.borderline and rep.final_level_gap_max is not None
            and rep.final_level_gap_max <= 10 and (preset.ci_half_width is None or hw <= preset.ci_half_width))


def _confirm(req, preset, led, consts, out, state, pool, prog, winner, finalists, levels, cands, abilities, hello, wteam) -> bool:
    from platsim.evaluate import DEFAULT_MAX_RUNS, evaluate_team, run_full_gauntlets
    from platsim.stats import mcnemar_exact

    seed, thr = str(req.seed), float(req.min_clear)
    master = f"{seed}|confirm"
    extend = preset.ci_half_width is not None
    max_runs = max(DEFAULT_MAX_RUNS, 4 * preset.confirm_min) if extend else preset.confirm_min
    attempts = []
    t0 = time.perf_counter()
    rep = ev = real = None
    lv = list(levels)
    for bump in range(MAX_CONFIRM_BUMPS + 1):
        real = R.realize(winner, lv, led, required_hms=req.required_hms)
        if isinstance(real, R.Refusal):
            raise RuntimeError(f"winner not buildable at {lv}: {real.reason}")
        prog("confirm", runs_planned=preset.confirm_min, detail=f"winner at levels {lv} ({POLICY}, >= {preset.confirm_min} runs)")
        rep, ev = evaluate_team(real.team, led, pool, runs=preset.confirm_min, seed=master, player_policy=POLICY,
                                budget=preset.name, threshold=thr, max_runs=max_runs, extend_borderline=extend,
                                borderline_max_runs=preset.borderline_max_runs,
                                on_batch=lambda n, w: prog("confirm", runs_done=n, runs_planned=preset.confirm_min,
                                                           best={"levels": lv, "clear_rate": round(w / n, 4)},
                                                           detail=f"{w}/{n} cleared"))
        ok = _confirm_ok(rep, preset, thr)
        attempts.append({"levels": list(lv), "runs": rep.n_runs, "clear_rate": rep.clear_rate, "ci95": list(rep.clear_ci95),
                         "borderline": rep.borderline, "final_level_gap_max": rep.final_level_gap_max,
                         "expected_avg_final_level": rep.expected_avg_final_level, "passes_confirm_checks": ok})
        state.data["stages"]["confirm_attempts"] = attempts
        state.save()
        if ok or bump == MAX_CONFIRM_BUMPS or all(x >= 100 for x in lv):
            break
        gap_only = (rep.clear_rate >= thr and not rep.borderline and rep.final_level_gap_max is not None
                    and rep.final_level_gap_max > 10)
        if gap_only:  # raise the lowest members (the gap, not the rate, failed)
            low = min(lv)
            lv = [min(100, x + 1) if x == low else x for x in lv]
        else:
            lv = [min(100, x + 1) for x in lv]
    if not _confirm_ok(rep, preset, thr):
        best = Point(attempts[-1]["levels"], rep.n_runs, round(rep.clear_rate * rep.n_runs), rep.final_level_gap_max,
                     rep.expected_avg_final_level, "fail")
        return _no_qualifying(req, preset, led, consts, out, state, hello, best, winner,
                              "the confirm stage did not meet the threshold / CI / gap checks", attempts=attempts)
    # runner-up, paired on the same seeds and run count
    comparison = None
    chosen, chosen_real, chosen_rep = winner, real, rep
    if len(finalists) > 1 and finalists[1] != finalists[0]:
        ru = finalists[1]
        ru_lv = [max(a, R.member_floor(s, led) or 100) for a, s in zip(lv, ru)]
        ru_real = R.realize(ru, ru_lv, led, required_hms=req.required_hms)
        if isinstance(ru_real, R.Refusal):
            comparison = {"result": f"runner-up not buildable at {ru_lv}: {ru_real.reason}"}
        else:
            from platsim.evaluate import worker_team

            prog("confirm", detail=f"runner-up at levels {ru_lv}, {len(ev.results)} paired runs")
            full2 = run_full_gauntlets(pool, worker_team(ru_real.team, led), master=master, min_runs=len(ev.results),
                                       max_runs=len(ev.results), target=None, player_policy=POLICY)
            a = [bool(r["cleared"]) for r in ev.results]
            b = [bool(r["cleared"]) for r in full2.results]
            cmp = mcnemar_exact(a, b)
            comparison = {"runner_up": R.spec_to_json(ru), "runner_up_labels": [m.label() for m in ru],
                          "levels_winner": lv, "levels_runner_up": ru_lv, "n_paired": cmp.n,
                          "clear_rate_winner": cmp.a_rate, "clear_rate_runner_up": cmp.b_rate,
                          "winner_only": cmp.a_only, "runner_up_only": cmp.b_only, "p_value": cmp.p_value,
                          "test": "McNemar exact (two-sided), alpha 0.05",
                          "verdict": {"A": "winner better", "B": "runner-up better"}.get(cmp.verdict, "indistinguishable")}
            if cmp.verdict == "B":
                rep2, _ = evaluate_team(ru_real.team, led, pool, runs=len(ev.results), seed=master, player_policy=POLICY,
                                        budget=preset.name, threshold=thr, max_runs=len(ev.results), full=full2)
                if _confirm_ok(rep2, preset, thr):
                    chosen, chosen_real, chosen_rep = ru, ru_real, rep2
                    comparison["switched_to_runner_up"] = True
                    lv = ru_lv
                else:
                    comparison["switched_to_runner_up"] = False
                    comparison["note"] = "runner-up better on clear rate but failed the confirm checks"
    state.data["stages"]["confirm"] = {"attempts": attempts, "comparison": comparison}
    state.data["timing"]["confirm"] = round(time.perf_counter() - t0, 1)
    state.save()
    return _report(req, preset, led, out, state, chosen, chosen_real, chosen_rep, lv, comparison, abilities)


def _optimizer_provenance(req, preset, state: _State, extra: dict | None = None) -> dict:
    st = state.data["stages"]
    d = {
        "objective": "minimise expected average final level after Cynthia among teams with clear rate >= threshold "
                     "and final gap <= 10 (FR-016)",
        "request": {"species": state.data["fingerprint"]["species"], "min_clear": req.min_clear,
                    "seed": str(req.seed), "budget": preset.name, "legality_options": req.legality.to_dict(),
                    **({"required_hms": list(req.required_hms)} if req.required_hms else {}),
                    "candidates": req.candidates,
                    **({"alternatives_round": req.alternatives_round} if req.alternatives_round is not None else {}),
                    **({"alternatives_members": req.alternatives_members} if req.alternatives_members is not None else {})},
        "candidate_mode": req.candidates,
        "budget_preset": {"name": preset.name, "screening_rounds": list(preset.screening_rounds),
                          "ability_screen": preset.ability_screen, "confirm_min": preset.confirm_min,
                          "ci_half_width": preset.ci_half_width, "qualifying": preset.qualifying},
        "policy_per_stage": {"calibrate": SCREEN_POLICY, "ability_screen": SCREEN_POLICY, "screen": SCREEN_POLICY,
                             "level_search": POLICY, "alternatives": MC.ALT_POLICY, "confirm": POLICY,
                             "opponent": OPPONENT},
        "seeds": {"scheme": SCHEME, "calibrate": f"{req.seed}|calibrate", "screen": f"{req.seed}|screen",
                  "ability_screen": "abilities.screen_master(seed, slot)", "level_search": f"{req.seed}|levels",
                  "alternatives": f"{req.seed}|alternatives", "alternatives_confirm": f"{req.seed}|alternatives-confirm|<slot>",
                  "confirm": f"{req.seed}|confirm",
                  "candidate_sampling": f"random.Random(sha256('{req.seed}|screen-candidates'))"},
        "stages": {k: st.get(k) for k in ("calibrate", "prune", "ability_screen", "screen", "level_search", "confirm")},
        "level_points": [state.data["level_points"][k] for k in sorted(state.data["level_points"])],
        "heuristics": "candidate generation, coverage scoring and item choice are heuristics over candidates "
                      "(optimizer/candidates.py docstring); legality comes from legality/movesources.py and the ledger "
                      "and is re-checked by the independent validator",
    }
    if extra:
        d.update(extra)
    return d


def load_move_name(const: str) -> str:
    from platsim.decomp.moves import load_moves

    return load_moves()[const].name


def _candidate_provenance(state: _State, specs) -> dict:
    """007 FR-013 / contracts/candidate-report.md: every offered alternative and its outcome, the moves and
    items left out with their reasons, the item tie rule and the assumptions."""
    from platsim.legality.models import default_ivs
    from platsim.optimizer import item_classes as IC

    st = state.data["stages"]
    alt = (st.get("level_search") or {}).get("alternatives") or {}
    tests = [r for r in alt.get("records") or [] if not r.get("member_done")]
    members = (st.get("prune") or {}).get("members") or []
    excluded_moves, excluded_items = {}, {}
    for slot, s in enumerate(specs):
        summ = members[slot].get(s.variant) if slot < len(members) else None
        if summ:
            excluded_moves[str(slot + 1)] = summ.get("excluded") or {}
            excluded_items[str(slot + 1)] = summ.get("excluded_items") or {}
    hp_type, hp_power = C.hidden_power(default_ivs())
    return {"candidate_tests": tests, "excluded_moves": excluded_moves, "excluded_items": excluded_items,
            "item_tie_rule": IC.ITEM_TIE_RULE, "alternatives_levels": alt.get("levels"),
            "alternatives_level_rule": alt.get("level_rule"), "alternatives_round_size": alt.get("round_size"),
            "assumptions": {"friendship": C.FRIENDSHIP, "ivs": default_ivs()["hp"],
                            "hidden_power": f"{hp_type.removeprefix('TYPE_').title()} {hp_power}"}}


def _report(req, preset, led, out, state, specs, real, rep, levels, comparison, abilities) -> bool:
    from platsim.legality.validator import format_violations, showdown_name, validate
    from platsim.report import write_all

    finals = [round(x) for x in rep.expected_final_levels] if rep.expected_final_levels else None
    v = validate(real.team, led, finals, required_hms=req.required_hms)
    if v:
        raise RuntimeError("the optimized team FAILED the independent legality validator (Constitution III):\n"
                           + format_violations(v))
    from platsim.report.sources import team_sources

    rep.obtained_from, rep.held_item_sources, rep.held_item_source_refs = team_sources(real.team, led)
    rep.resources = R.resource_lines(real, led)
    final_specs = R.place_required_hms(specs, levels, led, req.required_hms)[0] if req.required_hms else specs
    rep.provenance["optimizer"] = _optimizer_provenance(req, preset, state, {
        "final_levels_start": list(levels), "runner_up_comparison": comparison,
        "final_team_labels": [m.label() for m in final_specs], **_candidate_provenance(state, specs)})
    for s in final_specs:  # 007 contract: a required HM the player does not model is carried anyway (FR-014)
        for m in MC.not_modelled(MC.ALT_POLICY, s.moves, None):
            rep.warnings.append(f"{C.display_name(s.species)} carries {load_move_name(m)}, which {MC.ALT_POLICY} does not model; "
                                "its in-battle effect is applied by the engine but the player does not plan around it.")
    rep.provenance["validator"] = {"violations": 0, "final_levels_checked": finals}
    if req.required_hms:  # 006 FR-008: the constraint the result was made under
        rep.provenance["required_hms"] = list(req.required_hms)
    if comparison and comparison.get("verdict") == "indistinguishable":
        rep.warnings.append("Winner and runner-up are statistically indistinguishable on paired runs; "
                            "the winner is the screening winner.")
    paths = write_all(rep, out, showdown_name)
    state.done("report", {"qualified": rep.qualified, "paths": {k: str(p.name) for k, p in paths.items()}})
    return rep.qualified


def _no_qualifying(req, preset, led, consts, out, state, hello, best: Point, specs, why: str, attempts=None) -> bool:
    from platsim.evaluate import _divergences, code_version_fields
    from platsim.legality.validator import showdown_name
    from platsim.report import write_all
    from platsim.report.json_report import EvaluationReport, NoQualifying

    n = max(best.n, 1)
    ci = wilson_ci(best.wins, n)
    divs, _ = _divergences()
    nq = NoQualifying(best_clear_rate=best.wins / n, best_clear_ci95=ci, best_n_runs=best.n, best_levels=list(best.levels),
                      species=[C.display_name(c) for c in consts],
                      message=f"No qualifying team found ({why})")
    rep = EvaluationReport(
        team=None, n_runs=best.n, clear_rate=best.wins / n, clear_ci95=ci, per_battle={}, champion_rate=None,
        champion_ci95=None, champion_battles=0, budget_preset=preset.name, expected_final_levels=[],
        expected_avg_final_level=best.avg_final, final_level_gap_max=best.gap, loss_causes=[],
        threshold=float(req.min_clear), qualified=False, borderline=False, player_policy=POLICY,
        opponent_policy=OPPONENT, seeds={"master": str(req.seed), "scheme": SCHEME},
        decomp_commit=hello["decomp_commit"], showdown_commit=hello["showdown_commit"],
        divergence_ledger_version=hello["divergence_ledger_version"], **code_version_fields(hello),
        divergences=divs, no_qualifying=nq,
        warnings=[f"No qualifying team: {why}. Best clear rate {best.wins}/{best.n} at start levels {best.levels}."],
        provenance={"legality_options": req.legality.to_dict(), "optimizer": _optimizer_provenance(req, preset, state, {
            "best_team_labels": [m.label() for m in specs], "best_team": R.spec_to_json(specs),
            "confirm_attempts": attempts}), **({"required_hms": list(req.required_hms)} if req.required_hms else {})},
    )
    write_all(rep, out, showdown_name)
    state.done("report", {"qualified": False, "no_qualifying": True})
    return False


__all__ = ["run_optimization", "default_out_dir", "job_fingerprint"]
