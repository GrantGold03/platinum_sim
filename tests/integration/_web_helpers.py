"""Shared helpers for the web tests (002 T004). A plain module, not a conftest: tests import it by
name (`tests/conftest.py` puts this directory on sys.path), and so can a `spawn` child.

The STUB runner writes real report files through platsim.report.write_all from a SYNTHETIC
EvaluationReport: its moves, abilities, items, rates and commits are made-up placeholders
("synthetic_move_1", ...), not game facts.
"""

from __future__ import annotations

import json
import shutil
import threading
import time
from pathlib import Path

from platsim.legality.models import Build, MoveChoice, TeamCandidate
from platsim.optimizer.api import OptimizeRequest, OptimizeResult, Progress
from platsim.report import write_all
from platsim.report.json_report import BattleStat, EvaluationReport
from platsim.web import app as webapp

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "web_final_defaults"
FIXTURE_ID = "job-20261008T000000Z-f1f1f1"
RESULT_NAMES = ("result.json", "result.xlsx", "result.csv", "team.txt")


def _synthetic_report(species: tuple[str, ...]) -> EvaluationReport:
    builds = [
        Build(species=sp, source=f"avail:synthetic:{i}", start_level=40 + i,
              moves=[MoveChoice(f"synthetic_move_{i}_{j}", "level_up", f"Lv {30 + j}") for j in range(4)],
              ability=f"synthetic_ability_{i}", ability_reason="single_ability", held_item=f"synthetic_item_{i}")
        for i, sp in enumerate(species)
    ]
    return EvaluationReport(
        team=TeamCandidate(builds=builds), n_runs=100, clear_rate=0.8, clear_ci95=(0.71, 0.87),
        per_battle={"synthetic_trainer": BattleStat(0.9, (0.8, 0.95), 100)}, champion_rate=0.85,
        champion_ci95=(0.8, 0.9), champion_battles=120, budget_preset="standard",
        expected_final_levels=[45.0 + i for i in range(6)], expected_avg_final_level=47.5, final_level_gap_max=5.0,
        loss_causes=[], threshold=0.75, qualified=True, borderline=False, player_policy="synthetic-player",
        opponent_policy="synthetic-opponent", seeds={"master": 1, "scheme": "synthetic"},
        decomp_commit="synthetic-decomp", showdown_commit="synthetic-showdown", divergence_ledger_version="synthetic-1",
        obtained_from=[f"Synthetic source {i}" for i in range(6)],
        held_item_sources=[f"Synthetic item source {i}" for i in range(6)],
    )


class StubRunner:
    """Records call order; each call blocks until `release` is set (tests that need to observe the
    queued/running states), reports progress, then writes real result files."""

    def __init__(self, block: bool = False):
        self.calls: list[OptimizeRequest] = []
        self.release = threading.Event()
        self.started = threading.Event()
        if not block:
            self.release.set()

    def __call__(self, req: OptimizeRequest, progress=None) -> OptimizeResult:
        self.calls.append(req)
        self.started.set()
        if progress:
            progress(Progress(stage="screen", runs_done=10, runs_planned=40,
                              best_so_far={"clear_rate": 0.5, "levels": [40] * 6}))
        assert self.release.wait(30), "stub was never released"
        if progress:
            progress(Progress(stage="confirm", runs_done=40, runs_planned=40))
        write_all(_synthetic_report(req.species), req.out_dir)
        return OptimizeResult(out_dir=req.out_dir, qualified=True)


def _available_team(catalog) -> list[str]:
    keys = [s.key for s in catalog.species if s.available][:6]
    assert len(keys) == 6
    return keys


def _wait(client, jid, statuses, timeout=20.0) -> dict:
    end = time.monotonic() + timeout
    job = None
    while time.monotonic() < end:
        job = client.get(f"/api/jobs/{jid}").json()
        if job["status"] in statuses:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {jid} did not reach {statuses}: {job}")


def copy_fixture_run(dest_dir, job_id: str = FIXTURE_ID, created: str | None = None, drop_keys=()) -> str:
    """Copy the frozen final-defaults run to <dest_dir>/<job_id>/ as a finished web job, with
    `result_paths` pointing at the copy. `drop_keys` removes top-level result.json keys (for the
    "older run" cases); the other report files stay byte-identical."""
    d = Path(dest_dir) / job_id
    d.mkdir(parents=True, exist_ok=True)
    for name in RESULT_NAMES:
        shutil.copyfile(FIXTURE_DIR / name, d / name)
    if drop_keys:
        r = json.loads((d / "result.json").read_text(encoding="utf-8"))
        for k in drop_keys:
            r.pop(k, None)
        (d / "result.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
    job = json.loads((FIXTURE_DIR / "job.json").read_text(encoding="utf-8"))
    job["id"] = job_id
    if created:
        job["created"] = job["started"] = created
    job["result_paths"] = {"json": str(d / "result.json"), "xlsx": str(d / "result.xlsx"),
                           "csv": str(d / "result.csv"), "team": str(d / "team.txt")}
    (d / "job.json").write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    return job_id


def make_app(runs_dir, catalog, runner=None, **kw):
    return webapp.create_app(runner=runner if runner is not None else StubRunner(), runs_dir=runs_dir,
                             catalog=catalog, **kw)
