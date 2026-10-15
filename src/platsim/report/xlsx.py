"""`result.xlsx` (T055), exactly the sheets of contracts/spreadsheet.md:
Team, Evaluation, Resources, Provenance, Divergences (in that order).

The Evaluation sheet reports Cynthia's conditional win rate P(win | reached Cynthia), its CI and
battle count (full runs + top-up, task T057) on rows separate from the full-gauntlet clear rate,
which comes from full runs only (research.md R8 "Champion share").
"""

from __future__ import annotations

import json

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from .csv_report import NOT_RECORDED, TEAM_HEADERS, NameFn, _identity, no_qualifying_text, team_rows
from .json_report import EvaluationReport

SHEET_NAMES = ("Team", "Evaluation", "Resources", "Candidates", "Provenance", "Divergences")
# 007 (contracts/candidate-report.md): one row per provenance.optimizer.candidate_tests entry
CANDIDATE_HEADERS = ("Slot", "Species", "Kind", "Moves", "Item", "Mode", "Levels", "Round reached", "Runs (round)",
                     "Cleared (round)", "Paired runs", "Rate (alternative)", "Rate (current)", "Alternative only",
                     "Current only", "p", "p (Holm)", "Verdict", "Confirmed", "Adopted", "Not modelled")
RESOURCE_HEADERS = ["Resource", "Kind", "Used by", "Copies used", "Copies available"]
DIVERGENCE_HEADERS = [
    "ID",
    "Area",
    "Description",
    "Decomp ref",
    "Showdown ref",
    "Resolution",
    "Impact",
    "Test",
]
PER_TRAINER_HEADERS = ["Trainer", "Win rate", "95% CI low", "95% CI high", "Battles"]
LOSS_CAUSE_HEADERS = ["Trainer", "Opponent mon", "Losses"]
BOLD = Font(bold=True)
WARN = Font(bold=True, color="C00000")


def _header(ws: Worksheet, headers: list[str]) -> None:
    ws.append(headers)
    for cell in ws[ws.max_row]:
        cell.font = BOLD


def _kv(ws: Worksheet, key: str, value, font: Font | None = None) -> None:
    ws.append([key, value])
    ws.cell(ws.max_row, 1).font = font or BOLD


def _or_nr(v):
    return NOT_RECORDED if v is None else v


def _status(r: EvaluationReport) -> str:
    if r.no_qualifying is not None:
        return "no qualifying team"
    if r.qualified:
        return "qualified"
    if r.borderline:
        return "borderline"
    return "not qualified"


def _warnings(ws: Worksheet, r: EvaluationReport) -> None:
    for w in r.warnings:
        _kv(ws, "WARNING", w, WARN)


def _team_sheet(ws: Worksheet, r: EvaluationReport, name_of: NameFn) -> None:
    _header(ws, TEAM_HEADERS)
    for row in team_rows(r, name_of):
        ws.append(row)


def _evaluation_sheet(ws: Worksheet, r: EvaluationReport) -> None:
    _warnings(ws, r)
    if r.no_qualifying is not None:
        _kv(ws, "Result", no_qualifying_text(r), WARN)
    _kv(ws, "Status", _status(r))
    _kv(ws, "Qualified", r.qualified)
    _kv(ws, "Borderline", r.borderline)
    _kv(ws, "Threshold (min clear rate)", r.threshold)
    _kv(ws, "Budget preset", r.budget_preset)
    _kv(ws, "Objective", r.objective)
    _kv(ws, "Runs (full gauntlets)", r.n_runs)
    _kv(ws, "Clear rate (full gauntlet)", r.clear_rate)
    _kv(ws, "Clear rate 95% CI low", r.clear_ci95[0])
    _kv(ws, "Clear rate 95% CI high", r.clear_ci95[1])
    _kv(ws, "Champion win rate P(win | reached Cynthia)", _or_nr(r.champion_rate))
    _kv(ws, "Champion 95% CI low", r.champion_ci95[0] if r.champion_ci95 else NOT_RECORDED)
    _kv(ws, "Champion 95% CI high", r.champion_ci95[1] if r.champion_ci95 else NOT_RECORDED)
    _kv(ws, "Champion battles (full runs + top-up)", r.champion_battles)
    _kv(ws, "Expected average final level", _or_nr(r.expected_avg_final_level))
    _kv(
        ws,
        "Expected final levels",
        "/".join(f"{x:.1f}" for x in r.expected_final_levels) or NOT_RECORDED,
    )
    _kv(ws, "Final level gap (max)", _or_nr(r.final_level_gap_max))
    ws.append([])
    ws.append(["Clear rate per trainer (full runs only)"])
    ws.cell(ws.max_row, 1).font = BOLD
    _header(ws, PER_TRAINER_HEADERS)
    for trainer, s in r.per_battle.items():
        ws.append([trainer, s.rate, s.ci95[0], s.ci95[1], s.battles])
    ws.append([])
    ws.append(["Top loss causes (opponent mons present at losses)"])
    ws.cell(ws.max_row, 1).font = BOLD
    _header(ws, LOSS_CAUSE_HEADERS)
    for c in r.loss_causes:
        ws.append([c.trainer, c.opponent_mon, c.losses])


def _resources_sheet(ws: Worksheet, r: EvaluationReport) -> None:
    _header(ws, RESOURCE_HEADERS)
    if r.resources:
        for line in r.resources:
            ws.append(
                [
                    line.resource,
                    line.kind,
                    ", ".join(line.used_by),
                    line.copies_used,
                    line.copies_available,
                ]
            )
    elif r.team is not None:
        # Only TeamCandidate.resource_use is known: show it, and say what is missing.
        for key, used in r.team.resource_use.items():
            ws.append([key, NOT_RECORDED, NOT_RECORDED, used, NOT_RECORDED])


def _provenance_sheet(ws: Worksheet, r: EvaluationReport) -> None:
    _warnings(ws, r)
    _kv(ws, "Decomp commit", r.decomp_commit)
    _kv(ws, "Showdown commit", r.showdown_commit)
    _kv(ws, "Divergence ledger version", r.divergence_ledger_version)
    _kv(ws, "Sim code hash (sim/)", _or_nr(r.sim_code_hash))
    _kv(ws, "Platsim code hash (src/platsim/)", _or_nr(r.platsim_code_hash))
    _kv(ws, "Repo commit", _or_nr(r.repo_commit))
    _kv(ws, "Repo dirty (uncommitted changes)", _or_nr(r.repo_dirty))
    _kv(ws, "Node version", _or_nr(r.node_version))
    _kv(ws, "Python version", _or_nr(r.python_version))
    _kv(ws, "Player policy", r.player_policy)
    _kv(ws, "Opponent policy", r.opponent_policy)
    _kv(ws, "Master seed", _or_nr(r.seeds.get("master")))
    _kv(ws, "Seed derivation scheme", _or_nr(r.seeds.get("scheme")))
    _kv(ws, "Budget preset", r.budget_preset)
    _kv(ws, "Runs (full gauntlets)", r.n_runs)
    _kv(ws, "Champion battles (full runs + top-up)", r.champion_battles)
    for key, value in r.provenance.items():
        _kv(ws, key, value if isinstance(value, (str, int, float, bool)) else json.dumps(value, sort_keys=True))


def candidate_rows(r: EvaluationReport) -> list[list]:
    """The Candidates sheet rows: provenance.optimizer.candidate_tests, in order (empty for evaluate)."""
    tests = ((r.provenance or {}).get("optimizer") or {}).get("candidate_tests") or []
    out = []
    for t in tests:
        out.append([t.get("slot"), t.get("species"), t.get("kind"), "/".join(t.get("moves") or []), t.get("item"),
                    t.get("mode"), ",".join(map(str, t.get("levels") or [])), t.get("round_reached"), t.get("round_runs"),
                    t.get("round_cleared"), t.get("n_paired"), t.get("rate_alt"), t.get("rate_current"), t.get("alt_only"),
                    t.get("current_only"), t.get("p_value"), t.get("p_holm"), t.get("verdict"), t.get("confirmed"),
                    t.get("adopted"), ", ".join(t.get("not_modelled") or [])])
    return out


def _candidates_sheet(ws: Worksheet, r: EvaluationReport) -> None:
    _header(ws, CANDIDATE_HEADERS)
    for row in candidate_rows(r):
        ws.append(row)


def _divergences_sheet(ws: Worksheet, r: EvaluationReport) -> None:
    _header(ws, DIVERGENCE_HEADERS)
    for d in r.divergences:
        ws.append(
            [
                d.id,
                d.area,
                d.description,
                d.decomp_ref,
                d.showdown_ref,
                d.resolution,
                d.impact,
                d.test_id,
            ]
        )


def write_xlsx(report: EvaluationReport, path: Path, name_of: NameFn = _identity) -> None:
    wb = Workbook()
    team_ws = wb.active
    team_ws.title = SHEET_NAMES[0]
    _team_sheet(team_ws, report, name_of)
    _evaluation_sheet(wb.create_sheet(SHEET_NAMES[1]), report)
    _resources_sheet(wb.create_sheet(SHEET_NAMES[2]), report)
    _candidates_sheet(wb.create_sheet(SHEET_NAMES[3]), report)
    _provenance_sheet(wb.create_sheet(SHEET_NAMES[4]), report)
    _divergences_sheet(wb.create_sheet(SHEET_NAMES[5]), report)
    wb.save(Path(path))
