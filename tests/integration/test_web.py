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

import pytest
from fastapi.testclient import TestClient

from _web_helpers import RESULT_NAMES, StubRunner, _available_team, _wait
from platsim.legality.models import LegalityOptions
from platsim.web import app as webapp


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
    assert job["species"] == team and job["options"] == {"min_clear": 0.8, "seed": "fixed", "budget": "standard",
                                                           "allow_egg_moves": False, "allow_trade_evolutions": False}
    req = stub.calls[0]
    assert req.species == tuple(team) and req.min_clear == 0.8 and req.seed == "fixed" and req.out_dir == tmp_path / jid
    assert req.legality == LegalityOptions()  # both optional rules off by default
    assert "table" not in job and len(job["team"]) == 6  # 002: shaped view replaces the CSV table
    assert all(len(m["moves"]) == 4 and all(mv["source"] for mv in m["moves"]) for m in job["team"])
    assert job["summary"]["verdict"] == "qualified" and job["summary"]["n_runs"] == 100
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


def test_legality_options_page_search_and_jobs(tmp_path, catalog):
    """Two unchecked checkboxes; species search reflects trade evolutions; POST fields reach the
    optimizer request (OptimizeRequest.legality) and the job's options."""
    stub = StubRunner()
    client = TestClient(webapp.create_app(runner=stub, runs_dir=tmp_path, catalog=catalog))
    page = client.get("/").text
    for cid in ("allow-egg-moves", "allow-trade-evolutions"):
        tag = page[page.index(f'id="{cid}"') - 7:page.index(f'id="{cid}"') + 60]
        assert 'type="checkbox"' in tag and "checked" not in tag, tag
    js = client.get("/static/app.js").text
    assert "allow_egg_moves" in js and "allow_trade_evolutions" in js and "trade_evolutions=" in js

    off = client.get("/api/species", params={"q": "alakazam"}).json()
    assert off[0]["key"] == "alakazam" and off[0]["available"] is False and off[0]["reason_code"] == "trade_evolution"
    on = client.get("/api/species", params={"q": "alakazam", "trade_evolutions": 1}).json()
    assert on[0]["available"] is True and on[0]["trade_evolution"] is True
    assert client.get("/api/species", params={"q": "alakazam", "excluded": 0}).json() == []
    gar = client.get("/api/species", params={"q": "garchomp", "trade_evolutions": 1}).json()[0]  # control
    assert gar["available"] is True and "trade_evolution" not in gar

    team = _available_team(catalog)[:5] + ["alakazam"]
    r = client.post("/api/jobs", json={"species": team})
    assert r.status_code == 422 and "alakazam" in r.json()["reasons"]
    r = client.post("/api/jobs", json={"species": team, "allow_trade_evolutions": "yes"})
    assert r.status_code == 422 and "allow_trade_evolutions" in r.json()["detail"]
    assert not any(tmp_path.iterdir())
    r = client.post("/api/jobs", json={"species": team, "allow_trade_evolutions": True, "allow_egg_moves": True})
    assert r.status_code == 201, r.json()
    job = _wait(client, r.json()["id"], {"done", "failed"})
    assert job["status"] == "done", job
    assert job["options"]["allow_egg_moves"] is True and job["options"]["allow_trade_evolutions"] is True
    assert stub.calls[-1].legality == LegalityOptions(allow_egg_moves=True, allow_trade_evolutions=True)


def test_budget_and_species_icons(tmp_path, catalog):
    """002 T015: species items carry their icon URL (FR-004); the chosen budget reaches the job (FR-005)."""
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    gar = next(s for s in client.get("/api/species", params={"q": "garch"}).json() if s["key"] == "garchomp")
    assert gar["sprite_icon"] == "/api/sprites/garchomp/icon.png"
    assert client.get(gar["sprite_icon"]).status_code == 200
    team = _available_team(catalog)
    a = client.post("/api/jobs", json={"species": team, "budget": "thorough"}).json()["id"]
    b = client.post("/api/jobs", json={"species": team}).json()["id"]
    for jid, budget in ((a, "thorough"), (b, "standard")):
        _wait(client, jid, {"done", "failed"})
        assert json.loads((tmp_path / jid / "job.json").read_text())["options"]["budget"] == budget


def test_running_view_fields(tmp_path, catalog):
    """002 T022 (thread mode): elapsed_s / eta_s / stage_started / platsim_version while running;
    stage_started survives same-stage updates (P3-01, P4-03); verdict stored when done (P3-02)."""
    import importlib.metadata
    import time

    import _fake_runners

    _fake_runners.HOLD.clear()
    client = TestClient(webapp.create_app(runner=_fake_runners.two_beat_runner, runs_dir=tmp_path, catalog=catalog))
    jid = client.post("/api/jobs", json={"species": _available_team(catalog)}).json()["id"]
    first = None
    end = time.monotonic() + 10
    while time.monotonic() < end:  # first "screen" update (runs_done 1)
        job = client.get(f"/api/jobs/{jid}").json()
        if job["progress"].get("stage") == "screen" and job["progress"].get("runs_done") == 1:
            first = job
            break
        time.sleep(0.02)
    assert first, "never saw the first screen update"
    job = _wait(client, jid, {"running"})
    end = time.monotonic() + 10
    while time.monotonic() < end and job["progress"].get("runs_done") != 2:
        time.sleep(0.05)
        job = client.get(f"/api/jobs/{jid}").json()
    assert job["progress"]["runs_done"] == 2
    assert job["progress"]["stage_started"] == first["progress"]["stage_started"]  # carried forward, not reset
    assert "eta_s" in job and job["elapsed_s"] > 0
    assert job["platsim_version"] == importlib.metadata.version("platsim")
    _fake_runners.HOLD.set()
    done = _wait(client, jid, {"done", "failed"})
    assert done["status"] == "done", done
    stored = json.loads((tmp_path / jid / "job.json").read_text())
    assert stored["verdict"] == "qualified"
    assert done["elapsed_s"] == client.get(f"/api/jobs/{jid}").json()["elapsed_s"]  # fixed once finished


def test_job_list_labels_and_cap(tmp_path, catalog):
    """002 T030: GET /api/jobs newest first with labels (FR-015); failed / cancelled views (FR-016);
    the list is capped at 50 (SC-005)."""
    import time

    import _fake_runners
    from _web_helpers import copy_fixture_run

    _fake_runners.HOLD.clear()
    runs = tmp_path / "a"
    client = TestClient(webapp.create_app(runner=_fake_runners.seed_switch_runner, isolate=False, runs_dir=runs,
                                          catalog=catalog))
    team = _available_team(catalog)
    ids = {}
    for seed in ("ok1", "ok2", "fail"):
        ids[seed] = client.post("/api/jobs", json={"species": team, "seed": seed}).json()["id"]
        _wait(client, ids[seed], {"done", "failed"})
        time.sleep(1.05)  # distinct `created` seconds keep "newest first" unambiguous
    ids["hold"] = client.post("/api/jobs", json={"species": team, "seed": "hold"}).json()["id"]
    _wait(client, ids["hold"], {"running"})
    ids["queued"] = client.post("/api/jobs", json={"species": team, "seed": "q"}).json()["id"]
    r = client.post(f"/api/jobs/{ids['queued']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    _fake_runners.HOLD.set()
    _wait(client, ids["hold"], {"done", "failed"})

    listed = client.get("/api/jobs").json()
    order = [j["id"] for j in listed]
    assert order == [ids["queued"], ids["hold"], ids["fail"], ids["ok2"], ids["ok1"]]
    by_id = {j["id"]: j for j in listed}
    assert by_id[ids["ok1"]]["label"].endswith("· qualified")
    assert by_id[ids["fail"]]["label"].endswith("· failed")
    assert by_id[ids["queued"]]["label"].endswith("· cancelled")
    names = [catalog.get(k).name for k in team]
    assert by_id[ids["ok1"]]["label"].startswith(", ".join(names))
    failed = client.get(f"/api/jobs/{ids['fail']}").json()
    assert "synthetic failure" in failed["error"] and "team" not in failed
    assert client.get(f"/api/jobs/{ids['queued']}").json()["error"] == "cancelled by user"

    # Cap: 51 finished copies of the fixture run, each in a folder named by its id.
    big = tmp_path / "big"
    for i in range(51):
        copy_fixture_run(big, job_id=f"job-20261008T{i // 60:02d}{i % 60:02d}00Z-{i:06x}",
                         created=f"2026-10-08T{i // 60:02d}:{i % 60:02d}:00Z")
    listed = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=big, catalog=catalog)).get("/api/jobs").json()
    assert len(listed) == 50 and listed[0]["id"] == "job-20261008T005000Z-000032"
    assert all(j["label"].endswith("· qualified") for j in listed)
