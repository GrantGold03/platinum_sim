"""Public boundary between the optimizer (T060-T066) and its callers (CLI T066, web T067).

The optimizer implements `run_optimization`. The web app depends only on this module, so it can be
built and tested with a stub before the optimizer exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from platsim.budget import DEFAULT_PRESET
from platsim.legality.models import LegalityOptions


@dataclass(frozen=True)
class OptimizeRequest:
    species: tuple[str, ...]  # exactly six species keys (data/generated species keys, e.g. "garchomp")
    min_clear: float = 0.75  # FR-015
    seed: str = "default"
    budget: str = DEFAULT_PRESET  # platsim.budget preset name
    workers: int | None = None  # None: os.cpu_count()
    out_dir: Path | None = None  # None: runs/<job-id>/
    force_new: bool = False  # discard an existing checkpoint in out_dir (moved to superseded-N/) instead of resuming
    # Optional legality rules (egg moves, trade evolutions; both off by default). Part of the job
    # fingerprint: a checkpoint made with other options is never resumed.
    legality: LegalityOptions = field(default_factory=LegalityOptions)


@dataclass
class Progress:
    stage: str  # e.g. "prune", "ability_screen", "screen", "level_search", "confirm", "champion_topup", "report", "done"
    runs_done: int = 0
    runs_planned: int | None = None
    best_so_far: dict | None = None  # short summary (team species/levels, clear rate) for the UI
    detail: str = ""
    extra: dict = field(default_factory=dict)


ProgressCallback = Callable[[Progress], None]


@dataclass(frozen=True)
class OptimizeResult:
    out_dir: Path  # contains result.json, result.xlsx, result.csv, team.txt
    qualified: bool  # False: "no qualifying team" report (spec edge case)


class InvalidRequest(ValueError):
    """Bad input (unknown/ambiguous species, unavailable species, wrong count). Message is user-facing."""

    def __init__(self, message: str, reasons: dict[str, str] | None = None):
        super().__init__(message)
        self.reasons = reasons or {}


def run_optimization(req: OptimizeRequest, progress: ProgressCallback | None = None) -> OptimizeResult:
    """Implemented by platsim.optimizer.run (T065); imported lazily so this module stays light."""
    from platsim.optimizer.run import run_optimization as impl

    return impl(req, progress)
