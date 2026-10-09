"""What the result panel shows for a finished job (002 data-model ResultView).

Built from the job's own result.json and result.csv. The report files are only read, never
changed (FR-030). Fields the page no longer shows (nature, IVs, EVs, ability choice code,
held-item source, Cynthia win rate, policies, objective, commit hashes) are not sent at all.
"""

from __future__ import annotations

import csv
import functools
import json
from pathlib import Path

TRAINER_ORDER = ("aaron", "bertha", "flint", "lucian", "cynthia")
TIE = "(no significant difference)"


@functools.cache
def _species_abilities() -> dict[str, list[str]]:
    from platsim.decomp.species import load_species

    return {k: [a for a in s.abilities if a] for k, s in load_species().items()}


def _ability_name(const: str) -> str:
    from platsim.legality.validator import showdown_name

    return showdown_name("ability", const)


def _ability(build: dict, csv_value: str) -> str:
    if build.get("ability_reason") != "tie_default":
        return csv_value
    chosen = build.get("ability")
    others = [a for a in _species_abilities().get(build.get("species"), []) if a != chosen]
    if not others:
        return f"{csv_value} {TIE}"
    return "/".join([csv_value, *(_ability_name(a) for a in others)]) + f" {TIE}"


def _verdict(d: dict) -> str:
    if d.get("qualified"):
        return "qualified"
    return "borderline" if d.get("borderline") else "not_qualified"


def build_result_view(job: dict) -> dict | None:
    """{summary, per_trainer, team} for a done job, or None when its files can't be read."""
    paths = job.get("result_paths") or {}
    try:
        d = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
        with Path(paths["csv"]).open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except (KeyError, TypeError, OSError, ValueError):
        return None

    summary = {
        "verdict": _verdict(d),
        "clear_rate": d.get("clear_rate"),
        "clear_ci95": d.get("clear_ci95"),
        "n_runs": d.get("n_runs"),
        "avg_final_level": d.get("expected_avg_final_level"),
        "level_gap": d.get("final_level_gap_max"),
        "threshold": d.get("threshold"),
        "budget": d.get("budget_preset"),
        "legality_options": (d.get("provenance") or {}).get("legality_options"),
        "warnings": d.get("warnings") or [],
        "no_qualifying": d.get("no_qualifying"),
        "platsim_version": job.get("platsim_version"),
    }

    pb = d.get("per_battle") or {}
    keys = [k for k in TRAINER_ORDER if k in pb] + [k for k in pb if k not in TRAINER_ORDER]
    per_trainer = [{"trainer": k, "label": k.capitalize(), "rate": pb[k].get("rate"), "ci95": pb[k].get("ci95"),
                    "battles": pb[k].get("battles")} for k in keys]

    builds = ((d.get("team") or {}).get("builds")) or []
    team = []
    for i, row in enumerate(rows):
        b = builds[i] if i < len(builds) else {}
        key = b.get("species") or ""
        team.append({
            "slot": row.get("Slot"),
            "species_key": key,
            "species": row.get("Species"),
            "sprite": f"/api/sprites/{key}/front.png",
            "start_level": row.get("Start level"),
            "final_level": row.get("Final level (expected)"),
            "ability": _ability(b, row.get("Ability") or ""),
            "held_item": row.get("Held item"),
            "obtained_from": row.get("Obtained from"),
            "moves": [{"name": row.get(f"Move {n}") or "", "source": row.get(f"Move {n} source") or ""}
                      for n in range(1, 5)],
        })
    return {"summary": summary, "per_trainer": per_trainer, "team": team}
