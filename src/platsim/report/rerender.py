"""Re-render an existing run's report with the current source-selection code, without re-simulating.

`rerender(run_dir, out_dir)` reads `<run_dir>/result.json`, re-selects every member's species source
and move sources with the current preference order (optimizer/resources.realize, which ranks with
legality/movesources.option_sort_key / move_source_key), re-checks the team with the independent
validator, recomputes the display text (report/sources.team_sources) and the Resources sheet, and
writes result.json / result.xlsx / result.csv / team.txt into `out_dir`.

What may change: Build.source, MoveChoice source_kind/detail/availability_ref, obtained_from,
held_item_sources(+refs), resources. What may NOT change (checked, else RerenderError): every
battle-relevant field (`Build.showdown_set()`: species, level, ability, item, nature, IVs, EVs,
moves) and whether a member is an NPC-trade Pokemon (`is_traded`, which changes exp, FR-008a; a
trade source is kept as its own variant and a non-trade one never becomes a trade). Every battle
number (clear rate, CIs, per-battle stats, final levels, loss causes, seeds, commits, code hashes of
the producing run) is copied unchanged. Provenance gets a `rerender` block naming the source run,
the sha256 of its result.json, and the code (platsim_code_hash, repo commit/dirty) that re-rendered.

The source run directory is never written to.

Legality options: sources are re-selected under the run's own `provenance.legality_options`
(models.LegalityOptions). A run written before the options existed has none and was produced with
egg moves allowed and trade evolutions forbidden (models.LEGACY_LEGALITY), so that is used.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from platsim.report import OUTPUT_FILES, write_all
from platsim.report.json_report import EvaluationReport


class RerenderError(RuntimeError):
    pass


def default_out_dir(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    return run_dir.parent / f"{run_dir.name}-rerendered"


def rerender(run_dir: Path, out_dir: Path | None = None) -> tuple[EvaluationReport, dict[str, Path], list[str]]:
    from platsim.availability.ledger import build_ledger
    from platsim.evaluate import worker_team
    from platsim.legality.validator import _resolve, _species_index, format_violations, showdown_name, validate
    from platsim.optimizer import resources as R
    from platsim.pins import DECOMP_COMMIT
    from platsim.report.sources import build_option, team_sources
    from platsim.version import local_fingerprint

    run_dir = Path(run_dir)
    out = Path(out_dir) if out_dir is not None else default_out_dir(run_dir)
    src_json = run_dir / OUTPUT_FILES["json"]
    if not src_json.is_file():
        raise RerenderError(f"no {OUTPUT_FILES['json']} in {run_dir}")
    if out.resolve() == run_dir.resolve():
        raise RerenderError("the output directory must differ from the run directory (the original is never overwritten)")
    if any((out / name).exists() for name in OUTPUT_FILES.values()):
        raise RerenderError(f"{out} already holds report files; choose another --out")
    raw = src_json.read_bytes()
    rep = EvaluationReport.from_json(raw.decode("utf-8"))
    if rep.team is None:
        raise RerenderError("the run has no team (no qualifying team): nothing to re-render")
    if rep.decomp_commit != DECOMP_COMMIT:
        raise RerenderError(f"run used decomp {rep.decomp_commit}, this checkout pins {DECOMP_COMMIT}: sources would "
                            "come from different game data")

    from platsim.legality.models import LEGACY_LEGALITY, LegalityOptions

    recorded = rep.provenance.get("legality_options")
    legality = LegalityOptions.from_dict(recorded) if recorded is not None else LEGACY_LEGALITY
    led = build_ledger().with_options(legality)
    old = rep.team
    specs, levels = [], []
    for b in old.builds:
        species = _resolve(_species_index(), b.species) or b.species
        opt = build_option(b, led)
        if opt is None:
            raise RerenderError(f"{b.species}: recorded source {b.source!r} is not a source option under the current code")
        moves = tuple(_resolve_move(m.move) for m in b.moves)
        variant = opt.id if opt.kind == "npc_trade" else "own"  # trade vs non-trade is never changed here
        specs.append(R.MemberSpec(species, variant, moves, b.held_item, b.ability, b.ability_reason))
        levels.append(b.start_level)
    real = R.realize(tuple(specs), levels, led)
    if isinstance(real, R.Refusal):
        raise RerenderError(f"cannot re-select sources: {real.reason}")
    new = real.team
    for b0, b1 in zip(old.builds, new.builds):
        if b0.showdown_set() != b1.showdown_set():
            raise RerenderError(f"battle-relevant fields changed for {b0.species}: {b0.showdown_set()} -> {b1.showdown_set()}")
    if [w["is_traded"] for w in worker_team(old, led)] != [w["is_traded"] for w in worker_team(new, led)]:
        raise RerenderError("NPC-trade status changed (exp boost, FR-008a): refusing")
    finals = [round(x) for x in rep.expected_final_levels] if rep.expected_final_levels else None
    v = validate(new, led, finals, required_hms=tuple(rep.provenance.get("required_hms") or ()))  # 006
    if v:
        raise RerenderError("re-selected team FAILED the independent legality validator:\n" + format_violations(v))

    changes = []
    for b0, b1 in zip(old.builds, new.builds):
        if b0.source != b1.source:
            changes.append(f"{b0.species}: source {b0.source} -> {b1.source}")
        for m0, m1 in zip(b0.moves, b1.moves):
            if (m0.source_kind, m0.detail) != (m1.source_kind, m1.detail):
                changes.append(f"{b0.species} {m0.move}: {m0.detail} -> {m1.detail}")
    rep.team = new
    rep.obtained_from, rep.held_item_sources, rep.held_item_source_refs = team_sources(new, led)
    rep.resources = R.resource_lines(real, led)
    fp = local_fingerprint()
    rep.provenance = dict(rep.provenance)
    rep.provenance["rerender"] = {
        "from_run_dir": str(run_dir),
        "from_result_json_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "rerendered_by": {"platsim_code_hash": fp["platsim_code_hash"], "repo_commit": fp["repo_commit"],
                          "repo_dirty": fp["repo_dirty"], "python_version": fp["python_version"]},
        "what_changed": "source text only: Build.source, move sources, obtained_from, held_item_sources(+refs), "
                        "resources. Battle numbers, seeds, commits and the producing run's code hashes are copied "
                        "unchanged (no battle was re-simulated).",
        "source_preference": "legality/movesources.py 'Source preference' (option_sort_key, move_source_key)",
        "legality_options": legality.to_dict(),
        "legality_options_from": "the run's provenance" if recorded is not None else
                                 "not recorded (run predates the options): legacy behaviour, egg moves allowed",
        "checks": ["showdown_set identical per member", "is_traded identical per member",
                   "independent validator: 0 violations"],
        "changes": changes,
    }
    paths = write_all(rep, out, showdown_name)
    return rep, paths, changes


def _resolve_move(move: str) -> str:
    from platsim.legality.validator import _move_index, _resolve

    const = _resolve(_move_index(), move)
    if const is None:
        raise RerenderError(f"unknown move {move!r}")
    return const


__all__ = ["RerenderError", "default_out_dir", "rerender"]
