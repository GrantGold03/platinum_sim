"""EvaluationReport (T055): the machine-readable result of `platsim evaluate` / `platsim optimize`.

Fields follow specs/001-champion-team-optimizer/data-model.md ("EvaluationReport") exactly. A few
display-only fields are added because contracts/spreadsheet.md asks for columns the data model does
not carry (all optional, all defaulting to "not recorded" in the spreadsheet rather than invented):

- `objective`: the optimizer's objective, stated in output (Constitution IV, FR-016).
- `obtained_from[6]`, `held_item_sources[6]`: display text for the Team sheet's "Obtained from"
  and "Held item source" columns (Build.source is only an availability ref).
- `resources`: the Resources sheet rows (who uses each single-copy TM / limited item, copies used,
  copies available).
- `divergences`: the ledger entries that apply to this run (Divergences sheet).
- `no_qualifying`: set instead of `team` when no team met the threshold (spec.md Edge Cases,
  SC-001): best clear rate reached and at which levels. A failing team is never reported as the
  result.
- `provenance`: extra run provenance (worker hello data hash, run-count rule, Cynthia top-up
  details, ...); free-form dict, written to result.json and the Provenance sheet.
- `warnings`: human-readable warnings. `budget_preset == "quick"` always adds QUICK_WARNING
  (research.md R8: `quick` is labelled in every output and never `qualified`).

Invariants checked in `__post_init__` (so a writer never emits a contradictory report):
`quick` is never `qualified`; `qualified` and `borderline` are exclusive; exactly one of `team`
and `no_qualifying` is set; a no-qualifying report is not `qualified`; CIs are (lo, hi) with
0 <= lo <= hi <= 1.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from platsim.legality.models import TeamCandidate

from platsim.budget import PRESETS as _PRESETS

# Single source of truth: platsim.budget (research.md R8).
BUDGET_PRESETS = frozenset(_PRESETS)
QUALIFYING_PRESETS = frozenset(n for n, p in _PRESETS.items() if p.qualifying)
DIVERGENCE_AREAS = frozenset({"data", "mechanics", "ai", "exp"})
DIVERGENCE_RESOLUTIONS = frozenset({"corrected", "accepted"})

QUICK_WARNING = (
    "QUICK BUDGET: this result used the 'quick' simulation preset (research.md R8). Its run counts "
    "have no confidence-interval target, it does not meet SC-003, and it can never be 'qualified'. "
    "For testing only."
)

DEFAULT_OBJECTIVE = (
    "Among teams whose full-gauntlet clear rate meets the threshold (FR-015), minimise the expected "
    "average level of the six members after the Champion is defeated, with final level gap <= 10 "
    "(FR-016)."
)

CI = tuple[float, float]


def _ci(value: Any, name: str) -> CI:
    if value is None:
        raise ValueError(f"{name} is required")
    lo, hi = (float(x) for x in value)
    if not 0.0 <= lo <= hi <= 1.0:
        raise ValueError(f"{name} must satisfy 0 <= lo <= hi <= 1, got {value!r}")
    return (lo, hi)


@dataclass
class BattleStat:
    rate: float
    ci95: CI
    battles: int

    def __post_init__(self) -> None:
        self.ci95 = _ci(self.ci95, "per_battle.ci95")

    def to_dict(self) -> dict[str, Any]:
        return {"rate": self.rate, "ci95": list(self.ci95), "battles": self.battles}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BattleStat:
        return cls(rate=d["rate"], ci95=d["ci95"], battles=d["battles"])


@dataclass
class LossCause:
    """One opponent mon present at losses ("top opponent mons present at losses")."""

    trainer: str
    opponent_mon: str
    losses: int

    def to_dict(self) -> dict[str, Any]:
        return {"trainer": self.trainer, "opponent_mon": self.opponent_mon, "losses": self.losses}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LossCause:
        return cls(trainer=d["trainer"], opponent_mon=d["opponent_mon"], losses=d["losses"])


@dataclass
class ResourceLine:
    """Resources sheet row: a single-copy TM or limited item."""

    resource: str
    kind: str  # "tm" | "hm" | "item" | free text
    used_by: list[str]
    copies_used: int
    copies_available: int | str  # int or "unlimited"

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "kind": self.kind,
            "used_by": list(self.used_by),
            "copies_used": self.copies_used,
            "copies_available": self.copies_available,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ResourceLine:
        return cls(
            resource=d["resource"],
            kind=d["kind"],
            used_by=list(d["used_by"]),
            copies_used=d["copies_used"],
            copies_available=d["copies_available"],
        )


@dataclass
class DivergenceEntry:
    """data-model.md DivergenceEntry."""

    id: str
    area: str
    description: str
    decomp_ref: str
    showdown_ref: str
    resolution: str
    impact: str
    test_id: str

    def __post_init__(self) -> None:
        if self.area not in DIVERGENCE_AREAS:
            raise ValueError(f"unknown divergence area {self.area!r}")
        if self.resolution not in DIVERGENCE_RESOLUTIONS:
            raise ValueError(f"unknown divergence resolution {self.resolution!r}")

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DivergenceEntry:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__})


@dataclass
class NoQualifying:
    """'No qualifying team found' (spec.md Edge Cases): best clear rate reached, at which levels."""

    best_clear_rate: float
    best_clear_ci95: CI
    best_n_runs: int
    best_levels: list[int]
    species: list[str]
    message: str = "No qualifying team found"

    def __post_init__(self) -> None:
        self.best_clear_ci95 = _ci(self.best_clear_ci95, "no_qualifying.best_clear_ci95")

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "best_clear_rate": self.best_clear_rate,
            "best_clear_ci95": list(self.best_clear_ci95),
            "best_n_runs": self.best_n_runs,
            "best_levels": list(self.best_levels),
            "species": list(self.species),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NoQualifying:
        return cls(
            best_clear_rate=d["best_clear_rate"],
            best_clear_ci95=d["best_clear_ci95"],
            best_n_runs=d["best_n_runs"],
            best_levels=list(d["best_levels"]),
            species=list(d["species"]),
            message=d.get("message", "No qualifying team found"),
        )


@dataclass
class EvaluationReport:
    team: TeamCandidate | None
    n_runs: int
    clear_rate: float
    clear_ci95: CI
    per_battle: dict[str, BattleStat]
    champion_rate: float | None
    champion_ci95: CI | None
    champion_battles: int
    budget_preset: str
    expected_final_levels: list[float]
    expected_avg_final_level: float | None
    final_level_gap_max: float | None
    loss_causes: list[LossCause]
    threshold: float
    qualified: bool
    borderline: bool
    player_policy: str
    opponent_policy: str
    seeds: dict[str, Any]  # {"master": int, "scheme": str}
    decomp_commit: str
    showdown_commit: str
    divergence_ledger_version: str
    # --- display / variant fields (see module docstring) ---
    objective: str = DEFAULT_OBJECTIVE
    obtained_from: list[str] = field(default_factory=list)
    held_item_sources: list[str | None] = field(default_factory=list)
    resources: list[ResourceLine] = field(default_factory=list)
    divergences: list[DivergenceEntry] = field(default_factory=list)
    no_qualifying: NoQualifying | None = None
    warnings: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.budget_preset not in BUDGET_PRESETS:
            raise ValueError(f"unknown budget_preset {self.budget_preset!r}")
        if self.qualified and self.budget_preset not in QUALIFYING_PRESETS:
            raise ValueError(f"budget preset {self.budget_preset!r} can never be qualified (R8)")
        if self.qualified and self.borderline:
            raise ValueError("a report cannot be both qualified and borderline")
        if (self.team is None) == (self.no_qualifying is None):
            raise ValueError("exactly one of team and no_qualifying must be set")
        if self.no_qualifying is not None and self.qualified:
            raise ValueError("a no-qualifying-team report cannot be qualified")
        self.clear_ci95 = _ci(self.clear_ci95, "clear_ci95")
        if self.champion_ci95 is not None:
            self.champion_ci95 = _ci(self.champion_ci95, "champion_ci95")
        if self.budget_preset == "quick" and QUICK_WARNING not in self.warnings:
            self.warnings = [QUICK_WARNING, *self.warnings]
        if self.team is not None:
            n = len(self.team.builds)
            for name in ("obtained_from", "held_item_sources"):
                v = getattr(self, name)
                if v and len(v) != n:
                    raise ValueError(f"{name} has {len(v)} entries for {n} team members")
            if self.expected_final_levels and len(self.expected_final_levels) != n:
                raise ValueError("expected_final_levels must have one entry per team member")

    @property
    def is_quick(self) -> bool:
        return self.budget_preset == "quick"

    def to_dict(self) -> dict[str, Any]:
        return {
            "warnings": list(self.warnings),
            "budget_preset": self.budget_preset,
            "qualified": self.qualified,
            "borderline": self.borderline,
            "threshold": self.threshold,
            "objective": self.objective,
            "no_qualifying": self.no_qualifying.to_dict() if self.no_qualifying else None,
            "team": self.team.to_dict() if self.team else None,
            "n_runs": self.n_runs,
            "clear_rate": self.clear_rate,
            "clear_ci95": list(self.clear_ci95),
            "per_battle": {t: s.to_dict() for t, s in self.per_battle.items()},
            "champion_rate": self.champion_rate,
            "champion_ci95": list(self.champion_ci95) if self.champion_ci95 else None,
            "champion_battles": self.champion_battles,
            "expected_final_levels": list(self.expected_final_levels),
            "expected_avg_final_level": self.expected_avg_final_level,
            "final_level_gap_max": self.final_level_gap_max,
            "loss_causes": [c.to_dict() for c in self.loss_causes],
            "player_policy": self.player_policy,
            "opponent_policy": self.opponent_policy,
            "seeds": dict(self.seeds),
            "decomp_commit": self.decomp_commit,
            "showdown_commit": self.showdown_commit,
            "divergence_ledger_version": self.divergence_ledger_version,
            "obtained_from": list(self.obtained_from),
            "held_item_sources": list(self.held_item_sources),
            "resources": [r.to_dict() for r in self.resources],
            "divergences": [d.to_dict() for d in self.divergences],
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EvaluationReport:
        return cls(
            team=TeamCandidate.from_dict(d["team"]) if d.get("team") else None,
            n_runs=d["n_runs"],
            clear_rate=d["clear_rate"],
            clear_ci95=d["clear_ci95"],
            per_battle={t: BattleStat.from_dict(s) for t, s in d["per_battle"].items()},
            champion_rate=d["champion_rate"],
            champion_ci95=d["champion_ci95"],
            champion_battles=d["champion_battles"],
            budget_preset=d["budget_preset"],
            expected_final_levels=list(d["expected_final_levels"]),
            expected_avg_final_level=d["expected_avg_final_level"],
            final_level_gap_max=d["final_level_gap_max"],
            loss_causes=[LossCause.from_dict(c) for c in d["loss_causes"]],
            threshold=d["threshold"],
            qualified=d["qualified"],
            borderline=d["borderline"],
            player_policy=d["player_policy"],
            opponent_policy=d["opponent_policy"],
            seeds=dict(d["seeds"]),
            decomp_commit=d["decomp_commit"],
            showdown_commit=d["showdown_commit"],
            divergence_ledger_version=d["divergence_ledger_version"],
            objective=d.get("objective", DEFAULT_OBJECTIVE),
            obtained_from=list(d.get("obtained_from", [])),
            held_item_sources=list(d.get("held_item_sources", [])),
            resources=[ResourceLine.from_dict(r) for r in d.get("resources", [])],
            divergences=[DivergenceEntry.from_dict(x) for x in d.get("divergences", [])],
            no_qualifying=NoQualifying.from_dict(d["no_qualifying"])
            if d.get("no_qualifying")
            else None,
            warnings=list(d.get("warnings", [])),
            provenance=dict(d.get("provenance", {})),
        )

    def to_json(self, **kwargs: Any) -> str:
        kwargs.setdefault("indent", 2)
        kwargs.setdefault("ensure_ascii", False)
        return json.dumps(self.to_dict(), **kwargs)

    @classmethod
    def from_json(cls, text: str) -> EvaluationReport:
        return cls.from_dict(json.loads(text))


def write_json(report: EvaluationReport, path: Path) -> None:
    Path(path).write_text(report.to_json() + "\n", encoding="utf-8")
