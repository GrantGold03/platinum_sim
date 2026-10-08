"""T059 (+T067/T068): web page and HTTP API (contracts/http-api.md) with FastAPI's TestClient.

The optimizer is replaced by a STUB runner (create_app(runner=...)). The stub writes real report
files through platsim.report.write_all from a SYNTHETIC EvaluationReport: its moves, abilities,
items, rates and commits are made-up placeholders ("synthetic_move_1", ...), not game facts. The
species keys it receives are the ones the API accepted.

Species availability is real: the catalogue is built from the availability ledger and the legality
validator's source rule (~35 s once per session). Game facts used here:
- Garchomp's name: pokeplatinum/res/pokemon/garchomp/data.json:132 ("name": "GARCHOMP").
- Munchlax exclusion: project rule src/platsim/availability/ledger.py:171 (EXCLUDED_SPECIES).
- The post-game-only species are derived from the ledger here (positive control: the set is non-empty).
"""

from __future__ import annotations

import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from platsim.legality.models import Build, MoveChoice, TeamCandidate
from platsim.optimizer.api import OptimizeRequest, OptimizeResult, Progress
from platsim.report import write_all
from platsim.report.json_report import BattleStat, EvaluationReport
from platsim.web import app as webapp
from platsim.web.species_catalog import build_catalog

RESULT_NAMES = ("result.json", "result.xlsx", "result.csv", "team.txt")


@pytest.fixture(scope="module")
def ledger():
    from platsim.availability.ledger import build_ledger

    return build_ledger()


@pytest.fixture(scope="module")
def catalog(ledger):
    return build_catalog(ledger)


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
    while time.monotonic() < end:
        job = client.get(f"/api/jobs/{jid}").json()
        if job["status"] in statuses:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {jid} did not reach {statuses}: {job}")


def test_page_is_served(tmp_path, catalog):
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    for needle in ('id="search"', 'id="show-excluded"', 'id="slots"', 'id="min-clear"', 'value="75"', 'id="seed"',
                   ">Optimize<", "/static/app.js", 'name="viewport"'):
        assert needle in r.text, needle
    assert client.get("/static/app.js").status_code == 200
    assert "prefers-color-scheme: dark" in client.get("/static/style.css").text


def test_species_search(tmp_path, catalog, ledger):
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    res = client.get("/api/species", params={"q": "gar"}).json()
    assert len(res) <= 25
    gar = next(s for s in res if s["key"] == "garchomp")  # data.json:132 "GARCHOMP"
    assert gar["name"] == "Garchomp" and gar["available"] is True and "reason" not in gar
    assert set(gar) >= {"key", "name", "types", "available"}
    assert len(client.get("/api/species", params={"q": ""}).json()) == 25

    # Munchlax: project rule (ledger.py:171), shown with its reason; hidden when excluded=0.
    m = client.get("/api/species", params={"q": "munchlax"}).json()
    assert m and m[0]["key"] == "munchlax" and m[0]["available"] is False
    assert m[0]["reason_code"] == "excluded" and "FR-006a" in m[0]["reason"]
    assert client.get("/api/species", params={"q": "munchlax", "excluded": 0}).json() == []

    # Post-game-only species, derived from the ledger: every acquisition entry is post_game.
    from platsim.availability.ledger import POST
    from platsim.web.species_catalog import ACQUIRE_KINDS

    phases: dict[str, set] = {}
    for c in ledger.entries:
        if c.entry.kind in ACQUIRE_KINDS:
            phases.setdefault(c.entry.subject, set()).add(c.phase)
    post_only = [s for s in catalog.species if phases.get(s.const) == {POST} and not s.available]
    assert post_only, "positive control: the ledger has post-game-only species"
    for s in post_only[:5]:
        hit = next(x for x in client.get("/api/species", params={"q": s.key}).json() if x["key"] == s.key)
        assert hit["available"] is False and "post-game" in hit["reason"], hit
    assert sum(1 for s in post_only if s.reason_code == "post_game") >= 1


def test_post_validation(tmp_path, catalog):
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    team = _available_team(catalog)
    r = client.post("/api/jobs", json={"species": team[:5]})
    assert r.status_code == 422 and "exactly 6" in r.json()["detail"]
    r = client.post("/api/jobs", json={"species": team[:5] + ["munchlax"]})
    assert r.status_code == 422 and "munchlax" in r.json()["reasons"]
    r = client.post("/api/jobs", json={"species": team[:5] + ["not_a_species"]})
    assert r.status_code == 422 and r.json()["reasons"] == {"not_a_species": "unknown species"}
    r = client.post("/api/jobs", json={"species": team, "min_clear": 1.5})
    assert r.status_code == 422
    r = client.post("/api/jobs", json={"species": team, "budget": "nope"})
    assert r.status_code == 422
    assert not any(tmp_path.iterdir()), "an invalid request must not create a job"


def test_job_lifecycle_and_results(tmp_path, catalog):
    stub = StubRunner(block=True)
    client = TestClient(webapp.create_app(runner=stub, runs_dir=tmp_path, catalog=catalog))
    team = _available_team(catalog)
    r = client.post("/api/jobs", json={"species": team, "min_clear": 0.8, "seed": "fixed"})
    assert r.status_code == 201
    jid = r.json()["id"]
    assert stub.started.wait(10)
    job = _wait(client, jid, {"running"})
    for name in RESULT_NAMES:
        assert client.get(f"/api/jobs/{jid}/{name}").status_code == 409, name
    job = _wait(client, jid, {"running"})
    assert job["progress"]["stage"] == "screen" and job["progress"]["runs_done"] == 10
    assert job["progress"]["best_so_far"]["clear_rate"] == 0.5
    stub.release.set()
    job = _wait(client, jid, {"done", "failed"})
    assert job["status"] == "done", job
    assert job["species"] == team and job["options"] == {"min_clear": 0.8, "seed": "fixed", "budget": "standard"}
    req = stub.calls[0]
    assert req.species == tuple(team) and req.min_clear == 0.8 and req.seed == "fixed" and req.out_dir == tmp_path / jid
    assert job["table"]["headers"][:3] == ["Slot", "Species", "Obtained from"]
    assert "Move 1 source" in job["table"]["headers"] and len(job["table"]["rows"]) == 6
    assert job["summary"]["qualified"] is True and job["summary"]["n_runs"] == 100
    for name in RESULT_NAMES:
        r = client.get(f"/api/jobs/{jid}/{name}")
        assert r.status_code == 200, name
        assert r.content == (tmp_path / jid / name).read_bytes()
    assert client.get(f"/api/jobs/{jid}/result.xlsx").headers["content-disposition"].startswith("attachment")
    assert json.loads((tmp_path / jid / "job.json").read_text())["status"] == "done"
    assert client.get("/api/jobs/job-20000101T000000Z-abcdef").status_code == 404
    assert client.get("/api/jobs/..%2F..%2Fetc").status_code == 404


def test_fifo_queue_two_jobs(tmp_path, catalog):
    stub = StubRunner(block=True)
    client = TestClient(webapp.create_app(runner=stub, runs_dir=tmp_path, catalog=catalog))
    team = _available_team(catalog)
    a = client.post("/api/jobs", json={"species": team, "seed": "a"}).json()["id"]
    b = client.post("/api/jobs", json={"species": list(reversed(team)), "seed": "b"}).json()["id"]
    assert stub.started.wait(10)
    _wait(client, a, {"running"})
    jb = client.get(f"/api/jobs/{b}").json()
    assert jb["status"] == "queued" and jb["queue_position"] == 1 and jb["running_job"] == a
    assert client.get(f"/api/jobs/{b}/result.csv").status_code == 409
    stub.release.set()
    assert _wait(client, a, {"done", "failed"})["status"] == "done"
    assert _wait(client, b, {"done", "failed"})["status"] == "done"
    assert [c.seed for c in stub.calls] == ["a", "b"]


def test_failed_runner_and_restart(tmp_path, catalog):
    def boom(req, progress=None):
        raise RuntimeError("synthetic optimizer failure")

    client = TestClient(webapp.create_app(runner=boom, runs_dir=tmp_path, catalog=catalog))
    jid = client.post("/api/jobs", json={"species": _available_team(catalog)}).json()["id"]
    job = _wait(client, jid, {"done", "failed"})
    assert job["status"] == "failed" and "synthetic optimizer failure" in job["error"]
    assert client.get(f"/api/jobs/{jid}/result.json").status_code == 409

    # Simulated restart: one job left "running", one "queued" by a previous server.
    runs = tmp_path / "restart"
    team = _available_team(catalog)
    for jid2, status in (("job-20260101T000000Z-aaaaaa", "running"), ("job-20260101T000001Z-bbbbbb", "queued")):
        (runs / jid2).mkdir(parents=True)
        (runs / jid2 / "job.json").write_text(json.dumps({
            "id": jid2, "status": status, "species": team, "options": {"min_clear": 0.75, "seed": "s", "budget": "standard"},
            "progress": {"stage": status, "runs_done": 0}, "result_paths": None, "error": None,
            "created": jid2[4:20]}))
    stub = StubRunner()
    client = TestClient(webapp.create_app(runner=stub, runs_dir=runs, catalog=catalog))
    j1 = client.get("/api/jobs/job-20260101T000000Z-aaaaaa").json()
    assert j1["status"] == "failed" and "restart" in j1["error"]
    assert _wait(client, "job-20260101T000001Z-bbbbbb", {"done", "failed"})["status"] == "done"
    assert len(stub.calls) == 1


def test_serve_binds_localhost(tmp_path, monkeypatch):
    import uvicorn

    from platsim import cli

    seen = {}
    monkeypatch.setattr(webapp, "create_app", lambda **kw: ("app", kw))
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(app=app, **kw))
    assert cli.main(["serve", "--port", "8765", "--runs-dir", str(tmp_path)]) == 0
    assert seen["host"] == "127.0.0.1" and seen["port"] == 8765
    assert seen["app"][1]["runs_dir"] == tmp_path
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["serve", "--host", "0.0.0.0"])
