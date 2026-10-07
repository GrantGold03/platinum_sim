"""Team table (contracts/spreadsheet.md, sheet "Team") and its CSV form `result.csv` (T055).

`team_rows` is shared by the xlsx writer so the CSV and the Team sheet cannot drift apart.

Move sources: every move MUST carry a non-empty source (Constitution III/IV provenance). A
MoveChoice with an empty `detail` for a kind whose text comes from `detail` raises
`MissingProvenance` instead of writing a blank cell.
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path

from platsim.legality.models import STAT_KEYS, Build, MoveChoice

from .json_report import EvaluationReport

NameFn = Callable[[str, str], str]

NOT_RECORDED = "not recorded"

TEAM_HEADERS: list[str] = [
    "Slot",
    "Species",
    "Obtained from",
    "Start level",
    "Final level (expected)",
    "Ability",
    "Ability choice",
    "Held item",
    "Held item source",
    "Nature",
    "IVs",
    "EVs",
    *[f"Move {i}" for i in range(1, 5)],
    *[f"Move {i} source" for i in range(1, 5)],
]


class MissingProvenance(ValueError):
    pass


def _identity(_kind: str, value: str) -> str:
    return value


def move_source(m: MoveChoice) -> str:
    """Human-readable source text for the "Move N source" column (spreadsheet.md examples)."""
    detail = (m.detail or "").strip()
    kind = m.source_kind
    if kind == "level_up":
        text = f"Level-up {detail}" if detail else ""
    elif kind == "pre_evo_level_up":
        text = f"Pre-evolution level-up ({detail})" if detail else ""
    elif kind == "egg":
        text = f"Egg move – {detail}" if detail else "Egg move"
    elif kind == "relearner":
        text = f"Move relearner – {detail}" if detail else ""
    else:  # tm, hm, tutor: the detail already names the TM/tutor and where it comes from
        text = detail
    if not text:
        raise MissingProvenance(f"move {m.move!r} ({kind}) has no source detail")
    return text


def _stats(stats: dict[str, int]) -> str:
    return "/".join(str(stats[k]) for k in STAT_KEYS)


def _member_row(
    report: EvaluationReport, slot: int, b: Build, name_of: NameFn
) -> list[str | int | float]:
    i = slot - 1
    obtained = report.obtained_from[i] if report.obtained_from else b.source
    if b.held_item is None:
        item, item_src = "", ""
    else:
        item = name_of("item", b.held_item)
        item_src = (report.held_item_sources[i] if report.held_item_sources else None) or NOT_RECORDED
    final = (
        round(report.expected_final_levels[i], 1) if report.expected_final_levels else NOT_RECORDED
    )
    moves = [name_of("move", m.move) for m in b.moves]
    sources = [move_source(m) for m in b.moves]
    pad = [""] * (4 - len(b.moves))
    return [
        slot,
        name_of("species", b.species),
        obtained or NOT_RECORDED,
        b.start_level,
        final,
        name_of("ability", b.ability),
        b.ability_reason,
        item,
        item_src,
        name_of("nature", b.nature),
        _stats(b.ivs),
        _stats(b.evs),
        *moves,
        *pad,
        *sources,
        *pad,
    ]


def no_qualifying_text(report: EvaluationReport) -> str:
    nq = report.no_qualifying
    if nq is None:
        return ""
    lo, hi = nq.best_clear_ci95
    return (
        f"{nq.message}: best clear rate {nq.best_clear_rate:.1%} (95% CI {lo:.1%}–{hi:.1%}, "
        f"{nq.best_n_runs} runs) at levels {'/'.join(map(str, nq.best_levels))}; "
        f"threshold {report.threshold:.0%}"
    )


def team_rows(report: EvaluationReport, name_of: NameFn = _identity) -> list[list]:
    """Data rows (no header) of the Team sheet. A no-qualifying-team report gets one row whose
    "Species" cell states that no team qualified, the best clear rate and its levels (spec.md Edge
    Cases), so neither the CSV nor the sheet looks like an empty, silently failed result."""
    if report.team is None:
        return [[""] * 1 + [no_qualifying_text(report)] + [""] * (len(TEAM_HEADERS) - 2)]
    if any(len(b.moves) > 4 for b in report.team.builds):
        raise ValueError("a build has more than 4 moves")
    return [_member_row(report, s, b, name_of) for s, b in enumerate(report.team.builds, start=1)]


def write_csv(report: EvaluationReport, path: Path, name_of: NameFn = _identity) -> None:
    """Write `result.csv`: the Team sheet (same rows as `team_rows`)."""
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(TEAM_HEADERS)
        w.writerows(team_rows(report, name_of))
