"""Report writers (T055). `write_all` is the single entry point used by `platsim optimize`
(T066), `platsim evaluate` (T070) and the web job runner."""

from __future__ import annotations

from pathlib import Path

from .csv_report import NameFn, _identity, write_csv
from .json_report import EvaluationReport, write_json
from .team_txt import write_team_txt
from .xlsx import write_xlsx

OUTPUT_FILES = {
    "json": "result.json",
    "xlsx": "result.xlsx",
    "csv": "result.csv",
    "team": "team.txt",
}


def write_all(
    report: EvaluationReport, out_dir: Path, name_of: NameFn = _identity
) -> dict[str, Path]:
    """Write result.json, result.xlsx, result.csv and team.txt into `out_dir` (created if
    missing). `name_of(kind, key)` maps generated-data keys to display names for the
    spreadsheet/CSV/team.txt; result.json always keeps keys. Returns {kind: path}."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {k: out / v for k, v in OUTPUT_FILES.items()}
    write_json(report, paths["json"])
    write_xlsx(report, paths["xlsx"], name_of)
    write_csv(report, paths["csv"], name_of)
    write_team_txt(report, paths["team"], name_of)
    return paths


__all__ = ["EvaluationReport", "OUTPUT_FILES", "write_all"]
