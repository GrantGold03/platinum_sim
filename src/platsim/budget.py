"""Simulation budget presets (FR-018, SC-003, research.md R8 "Budget presets" table).

This module is the one place the preset numbers live. The CI half-width target applies to both
the gauntlet clear rate and Cynthia's P(win | reached Cynthia) (task T057).

| Preset     | Screening rounds | Ability screen | Confirm (per finalist)        | CI half-width target |
|------------|------------------|----------------|-------------------------------|----------------------|
| standard   | 100 -> 200 -> 400 | 200           | >= 2,000, more until target   | 0.02                 |
| thorough   | 200 -> 400 -> 800 | 400           | >= 5,000, more until target   | 0.015                |
| quick      | 50 -> 100 -> 200  | 100           | 500                           | none (never qualifies) |

Borderline cap (total runs while the CI straddles the threshold; then `borderline`, not qualified):
standard 4,000, thorough 10,000, quick none.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetPreset:
    name: str
    screening_rounds: tuple[int, ...]
    ability_screen: int
    confirm_min: int
    ci_half_width: float | None  # None: no CI target (quick); results are labelled quick
    qualifying: bool  # only standard/thorough can produce a `qualified` result (R8)
    # Total-run cap while the clear-rate CI still straddles the threshold (optimizer confirm). A team still
    # undecided at the cap is `borderline`, which never qualifies. None: no borderline extension.
    borderline_max_runs: int | None = None


PRESETS: dict[str, BudgetPreset] = {
    "standard": BudgetPreset("standard", (100, 200, 400), 200, 2000, 0.02, True, 4000),
    "thorough": BudgetPreset("thorough", (200, 400, 800), 400, 5000, 0.015, True, 10000),
    "quick": BudgetPreset("quick", (50, 100, 200), 100, 500, None, False),
}
DEFAULT_PRESET = "standard"


def get_preset(name: str) -> BudgetPreset:
    try:
        return PRESETS[name]
    except KeyError:
        raise ValueError(f"unknown budget preset {name!r} (known: {', '.join(PRESETS)})") from None


__all__ = ["BudgetPreset", "DEFAULT_PRESET", "PRESETS", "get_preset"]
