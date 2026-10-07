"""`team.txt` (T055): the team in Showdown export format, via `models.export_team` (T027), as the
constitution's "Interface" rule requires.

A no-qualifying-team report has no team to export (spec.md Edge Cases: never return a team that
fails the threshold). Its team.txt then contains only NO_TEAM_LINE plus the summary; that text is
deliberately not a Showdown set, so `import_team` rejects it instead of importing a failing team.
"""

from __future__ import annotations

from pathlib import Path

from platsim.legality.models import export_team

from .csv_report import NameFn, _identity, no_qualifying_text
from .json_report import EvaluationReport

NO_TEAM_LINE = "NO QUALIFYING TEAM FOUND - no Showdown team is exported."


def team_text(report: EvaluationReport, name_of: NameFn = _identity) -> str:
    if report.team is None:
        return f"{NO_TEAM_LINE}\n{no_qualifying_text(report)}\n"
    return export_team(report.team, name_of)


def write_team_txt(report: EvaluationReport, path: Path, name_of: NameFn = _identity) -> None:
    Path(path).write_text(team_text(report, name_of), encoding="utf-8")
