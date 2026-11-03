"""Shared helpers for the feature-019 scripts (no package change; imported by path)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[3]
EVIDENCE = REPO / "runs" / "019-evidence"

# The ten stored evaluations named in the spec (each has >= 2,000 runs).
SPEC_DIRS = [
    "runs/t076/v7-w16", "runs/final-defaults", "runs/bench-007-baseline/B5",
    "runs/bench-010/B1", "runs/bench-010/B2", "runs/bench-010/B3", "runs/bench-010/B4", "runs/bench-010/B5",
    "runs/t076/v8", "runs/job-20261008T235244Z-2d8f18",
]
E4 = ("aaron", "bertha", "flint", "lucian")
CHAMPION = "cynthia"


@dataclass
class StoredEvaluation:
    dir: str
    n_runs: int
    clear_rate: float
    clear_ci95: tuple[float, float]
    per_battle: dict  # trainer -> {"battles": int, "rate": float}
    champion_rate: float | None
    champion_battles: int
    champion_ci95: tuple[float, float] | None
    budget_preset: str
    threshold: float
    qualified: bool
    borderline: bool
    final_level_gap_max: float | None
    champion_status: str | None
    team_key: tuple = field(default_factory=tuple)
    master_seed: str | None = None
    duplicate_of: str | None = None

    @property
    def cynthia_battles(self) -> int:
        return int(self.per_battle[CHAMPION]["battles"])

    @property
    def cynthia_full_rate(self) -> float:
        return float(self.per_battle[CHAMPION]["rate"])


def load_stored(dir_: str | Path) -> StoredEvaluation:
    p = REPO / dir_ if not Path(dir_).is_absolute() else Path(dir_)
    r = json.loads((p / "result.json").read_text())
    pb = {k: {"battles": int(v["battles"]), "rate": float(v["rate"])} for k, v in r["per_battle"].items()}
    n = int(r["n_runs"])
    if pb[CHAMPION]["battles"] > n:
        raise ValueError(f"{dir_}: Cynthia battles {pb[CHAMPION]['battles']} > n_runs {n}")
    cb = int(r.get("champion_battles") or 0)
    if cb and cb < pb[CHAMPION]["battles"]:
        raise ValueError(f"{dir_}: champion_battles {cb} < full-run Cynthia battles {pb[CHAMPION]['battles']}")
    builds = (r.get("team") or {}).get("builds") or []
    team_key = tuple((b.get("species"), b.get("start_level")) for b in builds)
    seeds = r.get("seeds") or {}
    champ = (r.get("provenance") or {}).get("champion") or {}
    return StoredEvaluation(
        dir=str(dir_), n_runs=n, clear_rate=float(r["clear_rate"]), clear_ci95=tuple(r["clear_ci95"]), per_battle=pb,
        champion_rate=r.get("champion_rate"), champion_battles=cb,
        champion_ci95=tuple(r["champion_ci95"]) if r.get("champion_ci95") else None,
        budget_preset=r["budget_preset"], threshold=float(r.get("threshold", 0.75)), qualified=bool(r["qualified"]),
        borderline=bool(r.get("borderline", False)), final_level_gap_max=r.get("final_level_gap_max"),
        champion_status=champ.get("status") if isinstance(champ, dict) else None,
        team_key=team_key, master_seed=seeds.get("master"))


def dedup(stored: list[StoredEvaluation]) -> list[StoredEvaluation]:
    """Mark later entries that repeat an earlier result (same team, master seed, run count and clear rate)."""
    seen: dict[tuple, str] = {}
    for s in stored:
        key = (s.team_key, s.master_seed, s.n_runs, round(s.clear_rate, 6))
        if key in seen:
            s.duplicate_of = seen[key]
        else:
            seen[key] = s.dir
    return stored


def assert_idle() -> None:
    """Refuse to start a measurement while any Node worker or pytest is running (project rule)."""
    offenders = []
    for args in (["pgrep", "-a", "-x", "node"], ["pgrep", "-a", "pytest"]):
        out = subprocess.run(args, capture_output=True, text=True).stdout.strip()
        if out:
            offenders.append(out)
    if offenders:
        raise SystemExit("machine not idle:\n" + "\n".join(offenders))


def eastern_now() -> str:
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %-I:%M:%S %p %Z")


def code_hashes() -> dict:
    from platsim import version
    return {"sim_code_hash": version.sim_code_hash(), "platsim_code_hash": version.platsim_code_hash()}
