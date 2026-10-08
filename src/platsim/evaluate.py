"""`platsim evaluate TEAM` (T070; spec User Story 2, FR-002, FR-013, FR-015-FR-019, SC-003, SC-004;
contracts/cli.md; research.md R8).

Pipeline:
1. Read TEAM (JSON TeamCandidate / {"team": [...]} or Showdown export text) with
   `validator.load_team`, then run the independent legality validator. Any violation: exit 2 and
   print every violation (Constitution III). Nothing is simulated for an illegal team.
2. Full gauntlets through the worker pool (`sim/pool.py`): run i uses request seed
   `derive_seed(master, i, 0)`; the worker derives battle b's seed as `deriveSeed(request seed, 0, b)`
   (sim/gauntlet.mjs). `stop_on_loss` true, `log` "summary" (gives `state_before`, needed by the
   Cynthia top-up and the loss-cause replays). Opponent policy `decomp-ai` (FR-010).
3. Run count: at least `--runs` (default 2,000). If the budget preset has a CI target (R8:
   standard 0.02, thorough 0.015) and the gauntlet clear-rate Wilson half-width is above it, more runs
   are added (FR-018 "when uncertain, run more") up to `--max-runs`. Runs are consumed in index order
   and the count stops at the FIRST n >= --runs that meets the target, so the result does not depend
   on batch size or worker count. `quick` never adds runs.
4. Statistics (`stats.py`): Wilson 95% CIs for the gauntlet and per trainer (full runs only).
   Expected final levels = per-member mean of `final_levels` over CLEARED runs (the level after
   beating Cynthia, FR-016); `final_level_gap_max` = the largest (max - min) final level over cleared
   runs. Both are None/empty when no run cleared.
5. Cynthia: `champion.champion_topup` (T057) with the budget preset target; her rate is
   P(win | reached Cynthia) (FR-017).
6. Loss causes (`report/losses.py`, T069): every lost battle is replayed alone with `log: "full"`
   and must reproduce its `log_hash`.
7. Reports: `report.write_all` -> result.json / result.xlsx / result.csv / team.txt.

`qualified` / `borderline` (FR-015, R8): `borderline` when the clear-rate CI straddles the threshold
(lo < threshold <= hi). `qualified` when not borderline, the preset is qualifying, clear rate >=
threshold, its half-width <= the preset target, and `final_level_gap_max` <= 10. Evaluate does not add
runs to resolve a borderline result (that is the optimizer's confirm stage).

result.json is a pure function of (team, runs, seed, policies, budget, threshold, pinned data, code version):
it contains no wall-clock time or output path, so two runs with the same inputs write identical JSON.
The code version (sim_code_hash, platsim_code_hash, repo_commit, repo_dirty, node_version,
python_version; platsim/version.py) is recorded so results from different code are told apart.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from platsim import pins
from platsim.budget import get_preset
from platsim.report.json_report import BattleStat, DivergenceEntry, EvaluationReport
from platsim.sim.seeds import SCHEME, derive_seed
from platsim.stats import runs_needed, wilson_ci, wilson_half_width

DEFAULT_RUNS = 2000
DEFAULT_PLAYER_POLICY = "expectimax2-v2"  # research.md R8 "Policy per stage": every reported rate
OPPONENT_POLICY = "decomp-ai"  # FR-010
GAUNTLET = ("aaron", "bertha", "flint", "lucian", "cynthia")  # FR-009, sim/gauntlet.mjs default order
MAX_LEVEL_GAP = 10  # FR-016
MIN_BATCH = 64
DEFAULT_MAX_RUNS = 20_000
DIVERGENCES = pins.REPO_ROOT / "data" / "divergences.json"


class UsageError(ValueError):
    """A bad option value (exit 2)."""


class InvalidTeamInput(ValueError):
    """The team file cannot be read or is illegal (exit 2). `violations` lists the reasons."""

    def __init__(self, message: str, violations=()):
        super().__init__(message)
        self.violations = list(violations)


def _log(msg: str) -> None:
    print(f"platsim evaluate: {msg}", file=sys.stderr, flush=True)


def load_and_validate(path: Path, legality=None):
    """(TeamCandidate, ledger view with the legality options) or raise InvalidTeamInput."""
    from platsim.availability.ledger import build_ledger
    from platsim.legality.validator import load_team, validate

    led = build_ledger().with_options(legality)
    try:
        team, finals, read = load_team(path, led)
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        raise InvalidTeamInput(f"cannot read {path}: {e}") from e
    violations = list(read)
    if team is not None:
        violations += validate(team, led, finals)
    if team is None or violations:
        raise InvalidTeamInput(f"{path}: ILLEGAL - {len(violations)} violation(s)", violations)
    return team, led


def _legality_of(led):
    from platsim.legality.movesources import options_of

    return options_of(led)


def worker_team(team, led) -> list[dict]:
    """Builds as worker requests: Build.to_dict() plus `is_traded` from the source option (an NPC trade
    mon is not originally the player's, so it gets boosted exp, FR-008a)."""
    from platsim.legality import movesources as MS
    from platsim.legality.validator import _resolve, _species_index

    out = []
    for b in team.builds:
        d = b.to_dict()
        species = _resolve(_species_index(), b.species) or b.species  # key or SPECIES_* -> SPECIES_*
        opts = MS.source_options(species, led) if species in MS.by_constant() else []
        opt = next((o for o in opts if o.id == b.source), None)
        d["is_traded"] = bool(opt and opt.fixed_mon and opt.fixed_mon.get("is_traded"))
        out.append(d)
    return out


@dataclass
class _Runs:
    results: list[dict]
    extended: bool
    target_met: bool | None


def run_full_gauntlets(pool, team: list[dict], *, master: str, min_runs: int, max_runs: int,
                       target: float | None, player_policy: str, borderline_threshold: float | None = None,
                       borderline_max_runs: int | None = None, log: str = "summary", on_batch=None) -> _Runs:
    """Full gauntlets for run indices 0, 1, ... (see module doc, step 3).

    `borderline_threshold` (optimizer confirm stage, research R8 "Qualification rule"): after the CI
    target is met, while the clear-rate Wilson interval still straddles the threshold
    (lo < threshold <= hi), more runs are added up to `max_runs`, stopping at the FIRST n where it no
    longer straddles, or at `borderline_max_runs` total runs (if given, and never above `max_runs`): a
    team still straddling there is left `borderline` (not qualified) instead of being run toward
    `max_runs`. Runs are consumed in index order, so the result is independent of batching and
    worker count. `on_batch(n, wins)` is called after each batch (progress only)."""
    def req(i: int) -> dict:
        return {"op": "gauntlet", "team": team, "seed": derive_seed(master, i, 0), "player_policy": player_policy,
                "opponent_policy": OPPONENT_POLICY, "stop_on_loss": True, "log": log}

    def check(rs: list[dict]) -> None:
        for i, r in enumerate(rs):
            if not r.get("ok"):
                raise RuntimeError(f"gauntlet failed: {r.get('error')}")
            if (r["player_policy"], r["opponent_policy"]) != (player_policy, OPPONENT_POLICY):
                raise RuntimeError(f"worker ran {r['player_policy']}/{r['opponent_policy']}, "
                                   f"requested {player_policy}/{OPPONENT_POLICY}")

    t0 = time.perf_counter()
    results: list[dict] = []
    chunk = max(MIN_BATCH, pool.size * 8)
    for start in range(0, min_runs, chunk):  # chunks only for progress output; order is preserved
        rs = pool.map([req(i) for i in range(start, min(min_runs, start + chunk))])
        check(rs)
        results += rs
        dt = time.perf_counter() - t0
        _log(f"full gauntlets {len(results)}/{min_runs} ({len(results) / dt:.2f}/s, "
             f"cleared {sum(r['cleared'] for r in results)})")
        if on_batch:
            on_batch(len(results), sum(bool(r["cleared"]) for r in results))
    wins = sum(bool(r["cleared"]) for r in results)
    n = len(results)
    extended = False
    while target is not None and wilson_half_width(wins, n) > target and n < max_runs:
        extended = True
        p_hat = wins / n
        size = min(max(runs_needed(p_hat, target) - n, MIN_BATCH), max_runs - n)
        _log(f"clear-rate half-width {wilson_half_width(wins, n):.4f} > {target}: adding up to {size} runs")
        rs = pool.map([req(i) for i in range(n, n + size)])
        check(rs)
        for r in rs:  # consume in order; stop at the first n meeting the target
            results.append(r)
            n += 1
            wins += bool(r["cleared"])
            if wilson_half_width(wins, n) <= target:
                break
        if on_batch:
            on_batch(n, wins)

    def straddles(w: int, k: int) -> bool:
        lo, hi = wilson_ci(w, k)
        return lo < borderline_threshold <= hi

    if borderline_threshold is not None:
        cap = max_runs if borderline_max_runs is None else min(max_runs, borderline_max_runs)
        while straddles(wins, n) and n < cap:
            extended = True
            size = min(max(n // 2, MIN_BATCH), cap - n)
            _log(f"clear-rate CI straddles the threshold {borderline_threshold} at n={n}: adding up to {size} runs")
            rs = pool.map([req(i) for i in range(n, n + size)])
            check(rs)
            for r in rs:
                results.append(r)
                n += 1
                wins += bool(r["cleared"])
                if not straddles(wins, n):
                    break
            if on_batch:
                on_batch(n, wins)
        if straddles(wins, n):
            _log(f"clear-rate CI still straddles the threshold {borderline_threshold} at the borderline cap "
                 f"n={n}: borderline (not qualified)")
    return _Runs(results, extended, None if target is None else wilson_half_width(wins, n) <= target)


def per_battle_stats(results: list[dict]) -> dict[str, BattleStat]:
    fought: dict[str, list[int]] = {}
    for r in results:
        for b in r["battles"]:
            fought.setdefault(b["trainer"], [0, 0])
            fought[b["trainer"]][0] += 1
            fought[b["trainer"]][1] += bool(b["won"])
    order = [t for t in GAUNTLET if t in fought] + sorted(t for t in fought if t not in GAUNTLET)
    return {t: BattleStat(rate=fought[t][1] / fought[t][0], ci95=wilson_ci(fought[t][1], fought[t][0]),
                          battles=fought[t][0]) for t in order}


def final_level_stats(results: list[dict], n_members: int):
    cleared = [r["final_levels"] for r in results if r["cleared"]]
    if not cleared:
        return [], None, None
    means = [sum(fl[i] for fl in cleared) / len(cleared) for i in range(n_members)]
    avg = sum(sum(fl) / len(fl) for fl in cleared) / len(cleared)
    gap = max(max(fl) - min(fl) for fl in cleared)
    return means, avg, float(gap)


def _divergences() -> tuple[list[DivergenceEntry], str | None]:
    if not DIVERGENCES.is_file():
        return [], None
    d = json.loads(DIVERGENCES.read_text(encoding="utf-8"))
    return [DivergenceEntry.from_dict(e) for e in d["entries"]], d.get("version")


def code_version_fields(hello: dict) -> dict:
    """EvaluationReport code-version fields (platsim/version.py) from the pool's agreed hello."""
    from platsim.version import CODE_KEYS, code_fingerprint

    fp = code_fingerprint(hello)
    return {k: fp[k] for k in CODE_KEYS}


def default_out_dir(team_path: Path, master: str, runs: int, policy: str) -> Path:
    h = hashlib.sha256(team_path.read_bytes() + f"|{master}|{runs}|{policy}".encode()).hexdigest()[:8]
    return pins.REPO_ROOT / "runs" / f"evaluate-{time.strftime('%Y%m%d-%H%M%S')}-{h}"


def evaluate(team_path: Path, *, runs: int = DEFAULT_RUNS, seed: str = "0", workers: int | None = None,
             player_policy: str = DEFAULT_PLAYER_POLICY, budget: str = "standard", threshold: float = 0.75,
             max_runs: int = DEFAULT_MAX_RUNS, out_dir: Path | None = None, pool=None,
             legality=None) -> tuple[EvaluationReport, dict]:
    """Run the evaluation and write the reports. Returns (report, {kind: path}). `legality`
    (models.LegalityOptions, default both off) selects egg moves / trade evolutions."""
    from platsim.legality.validator import showdown_name
    from platsim.report import write_all
    from platsim.sim.pool import WorkerPool

    if runs < 1:
        raise UsageError(f"--runs must be >= 1, got {runs}")
    if not 0.0 <= threshold <= 1.0:
        raise UsageError(f"--min-clear must be in [0, 1], got {threshold}")
    try:
        preset = get_preset(budget)
    except ValueError as e:
        raise UsageError(str(e)) from e
    master = str(seed)
    team, led = load_and_validate(team_path, legality)
    _log(f"{team_path}: legal; {runs} runs, seed {master!r}, player {player_policy}, opponent {OPPONENT_POLICY}, "
         f"budget {preset.name}")

    own_pool = pool is None
    if own_pool:
        pool = WorkerPool(workers)
    try:
        report, _ = evaluate_team(team, led, pool, runs=runs, seed=master, player_policy=player_policy,
                                  budget=preset.name, threshold=threshold, max_runs=max_runs)
    finally:
        if own_pool:
            pool.close()
    out = Path(out_dir) if out_dir else default_out_dir(team_path, master, runs, player_policy)
    paths = write_all(report, out, showdown_name)
    _log(f"wrote {out}")
    return report, paths


@dataclass
class TeamEvaluation:
    report: EvaluationReport
    results: list[dict]  # full gauntlet responses in run order
    timing: dict  # seconds per phase (NOT written to result.json: it would break determinism)


def evaluate_team(team, led, pool, *, runs: int = DEFAULT_RUNS, seed: str = "0", player_policy: str = DEFAULT_PLAYER_POLICY,
                  budget: str = "standard", threshold: float = 0.75, max_runs: int = DEFAULT_MAX_RUNS,
                  extend_borderline: bool = False, borderline_max_runs: int | None = None, full: _Runs | None = None,
                  on_batch=None) -> tuple[EvaluationReport, TeamEvaluation]:
    """The evaluation of an already validated TeamCandidate on an open pool (steps 2-6 of the module
    doc); used by `evaluate` and by the optimizer's confirm stage (T065). `extend_borderline` adds runs
    while the clear-rate CI straddles the threshold (R8; up to `max_runs`). `full` reuses full-gauntlet
    results already computed with the same team, seed and policy (they are not re-run)."""
    from platsim.report.losses import collect_loss_causes
    from platsim.sim.champion import champion_topup

    preset = get_preset(budget)
    master = str(seed)
    wteam = worker_team(team, led)
    hello = pool.hello
    for need, key in ((player_policy, "policies"), (OPPONENT_POLICY, "opponent_policies")):
        if need not in hello[key]:
            raise UsageError(f"policy {need!r} is not offered by the worker (known: {hello[key]})")
    t0 = time.perf_counter()
    if full is None:
        full = run_full_gauntlets(pool, wteam, master=master, min_runs=runs, max_runs=max(max_runs, runs),
                                  target=preset.ci_half_width, player_policy=player_policy,
                                  borderline_threshold=threshold if extend_borderline else None,
                                  borderline_max_runs=borderline_max_runs,
                                  on_batch=on_batch)
    t_full = time.perf_counter() - t0
    results = full.results
    n = len(results)
    wins = sum(bool(r["cleared"]) for r in results)
    _log(f"full runs: {n} in {t_full:.1f}s; cleared {wins}/{n}; Cynthia top-up ...")
    t1 = time.perf_counter()
    champ = champion_topup(pool, wteam, results, master_seed=master, budget=preset.name)
    t_champ = time.perf_counter() - t1
    _log(f"Cynthia: status {champ.status}, {champ.battles} battles ({champ.topup_battles} top-up) in "
         f"{t_champ:.1f}s; replaying lost battles for loss causes ...")
    t2 = time.perf_counter()
    causes = collect_loss_causes(pool.map, wteam, results, GAUNTLET)
    t_loss = time.perf_counter() - t2

    clear_ci = wilson_ci(wins, n)
    hw = wilson_half_width(wins, n)
    means, avg, gap = final_level_stats(results, len(wteam))
    divs, div_file_version = _divergences()
    borderline = clear_ci[0] < threshold <= clear_ci[1]
    target = preset.ci_half_width
    qualified = (not borderline and preset.qualifying and wins / n >= threshold and target is not None
                 and hw <= target and gap is not None and gap <= MAX_LEVEL_GAP)
    warnings = []
    if full.target_met is False:
        warnings.append(f"Clear-rate CI half-width {hw:.4f} is above the {preset.name} target {target} after "
                        f"{n} runs (cap --max-runs {max_runs}); the target is NOT met.")
    if champ.status != "met":
        warnings.append(f"Cynthia top-up status {champ.status!r}: her CI/count target is NOT met.")
    if not means:
        warnings.append("No run cleared the gauntlet: expected final levels are not defined.")
    provenance = {
        # LegalityOptions the team was validated under (the ledger view's options).
        "legality_options": _legality_of(led).to_dict(),
        "worker": {k: hello.get(k) for k in ("decomp_commit", "showdown_commit", "decomp_data_hash",
                                             "divergence_ledger_version", "divergence_patches_applied",
                                             "pp_restore_between_battles")},
        "divergence_ledger_file_version": div_file_version,
        "runs_requested": runs,
        "runs_extended_for_ci_target": full.extended,
        **({"runs_extended_while_borderline": True, "borderline_max_runs": borderline_max_runs} if extend_borderline else {}),
        "clear_ci_half_width": hw,
        "clear_ci_target": target,
        "stop_on_loss": True,
        "log_mode": "summary",
        "trainers": list(GAUNTLET),
        "champion": champ.to_dict(),
        "loss_cause_method": "lost battles replayed alone with log 'full'; log_hash checked (report/losses.py)",
        "final_levels_from": "cleared runs only",
        "qualification_rule": (f"not borderline, budget qualifying, clear_rate >= threshold, half-width <= target, "
                               f"final_level_gap_max <= {MAX_LEVEL_GAP}"),
    }
    report = EvaluationReport(
        team=team, n_runs=n, clear_rate=wins / n, clear_ci95=clear_ci, per_battle=per_battle_stats(results),
        champion_rate=champ.rate, champion_ci95=champ.ci95, champion_battles=champ.battles,
        budget_preset=preset.name, expected_final_levels=means, expected_avg_final_level=avg,
        final_level_gap_max=gap, loss_causes=causes, threshold=threshold, qualified=qualified,
        borderline=borderline, player_policy=player_policy, opponent_policy=OPPONENT_POLICY,
        seeds={"master": master, "scheme": SCHEME,
               "full_run_request_seed": "derive_seed(master, run, 0); battle b: derive_seed(request_seed, 0, b)",
               "champion_topup_seed": "derive_seed(master, k, 99)",
               "loss_cause_replay_seed": "the lost battle's own seed"},
        decomp_commit=hello["decomp_commit"], showdown_commit=hello["showdown_commit"],
        divergence_ledger_version=hello["divergence_ledger_version"], **code_version_fields(hello),
        divergences=divs, warnings=warnings, provenance=provenance,
    )
    from platsim.report.sources import team_sources

    report.obtained_from, report.held_item_sources, report.held_item_source_refs = team_sources(team, led)
    _log(f"timing: full runs {t_full:.1f}s ({n / max(t_full, 1e-9):.2f} gauntlets/s), Cynthia top-up {t_champ:.1f}s, "
         f"loss replays {t_loss:.1f}s")
    return report, TeamEvaluation(report, results, {"full_runs_s": t_full, "champion_topup_s": t_champ,
                                                    "loss_replays_s": t_loss})


def summary_text(r: EvaluationReport) -> str:
    lines = [f"runs {r.n_runs}  player {r.player_policy}  opponent {r.opponent_policy}  budget {r.budget_preset}",
             f"gauntlet clear rate {r.clear_rate:.4f}  95% CI [{r.clear_ci95[0]:.4f}, {r.clear_ci95[1]:.4f}]  "
             f"half-width {(r.clear_ci95[1] - r.clear_ci95[0]) / 2:.4f}"]
    for t, s in r.per_battle.items():
        lines.append(f"  {t:8s} {s.rate:.4f}  [{s.ci95[0]:.4f}, {s.ci95[1]:.4f}]  battles {s.battles}")
    if r.champion_rate is not None:
        lines.append(f"Cynthia P(win | reached) {r.champion_rate:.4f}  [{r.champion_ci95[0]:.4f}, "
                     f"{r.champion_ci95[1]:.4f}]  battles {r.champion_battles}")
    if r.expected_final_levels:
        lines.append("expected final levels " + " / ".join(f"{x:.2f}" for x in r.expected_final_levels)
                     + f"  avg {r.expected_avg_final_level:.2f}  gap max {r.final_level_gap_max}")
    lines.append(f"threshold {r.threshold}  qualified {r.qualified}  borderline {r.borderline}")
    for c in r.loss_causes[:10]:
        lines.append(f"  loss cause: {c.trainer} {c.opponent_mon} {c.losses}")
    lines += [f"WARNING: {w}" for w in r.warnings]
    return "\n".join(lines)


__all__ = ["DEFAULT_PLAYER_POLICY", "DEFAULT_RUNS", "InvalidTeamInput", "TeamEvaluation", "UsageError", "evaluate",
           "code_version_fields", "evaluate_team", "load_and_validate", "run_full_gauntlets",
           "summary_text", "worker_team"]
