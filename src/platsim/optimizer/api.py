"""Public boundary between the optimizer (T060-T066) and its callers (CLI T066, web T067).

The optimizer implements `run_optimization`. The web app depends only on this module, so it can be
built and tested with a stub before the optimizer exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from platsim.budget import DEFAULT_PRESET
from platsim.evaluate import DEFAULT_PLAYER_POLICY
from platsim.sampling import DEFAULT_FLOOR, FLOOR_MAX, FLOOR_MIN
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
    # 006: HMs that must be carried in some member's final moveset (move keys, HM-number order).
    # Part of the fingerprint and reports only when non-empty, so default jobs are unchanged.
    required_hms: tuple[str, ...] = ()
    # 018: the strong player for the level search, the setup check and the confirmation runs (the screening
    # stages keep greedy-v1). Part of the job fingerprint; named in the result's provenance.
    player_policy: str = DEFAULT_PLAYER_POLICY
    # 022: the confirmation stage's sampling ("full", the reference, or "adaptive": feature 021's method) and its floor.
    # The level search and the setup check keep full gauntlets. In the fingerprint only when non-default.
    sampling: str = "full"
    floor: float = DEFAULT_FLOOR
    # 023: the battle style of every stage's battles ("set": Showdown's behaviour; "shift": the game's default).
    # In the fingerprint only when non-default; named in the result's provenance. Default shift since the user's
    # decision of 2026-11-04 (specs/023-shift-battle-style/validation-log.md T022).
    battle_style: str = "shift"

    def __post_init__(self) -> None:
        if self.battle_style not in ("set", "shift"):
            raise InvalidRequest(f"battle_style must be set or shift, got {self.battle_style!r}",
                                 {"battle_style": self.battle_style})
        if self.sampling not in ("full", "adaptive"):
            raise InvalidRequest(f"sampling must be full or adaptive, got {self.sampling!r}", {"sampling": self.sampling})
        if not FLOOR_MIN <= self.floor <= FLOOR_MAX:
            raise InvalidRequest(f"floor must be in [{FLOOR_MIN}, {FLOOR_MAX}], got {self.floor}", {"floor": self.floor})
        if self.required_hms:
            from platsim.legality.movesources import normalize_hms

            try:
                object.__setattr__(self, "required_hms", normalize_hms(self.required_hms))
            except KeyError as e:
                raise InvalidRequest(str(e.args[0]), {"required_hms": str(e.args[0])}) from None


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
