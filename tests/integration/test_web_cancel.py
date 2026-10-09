"""002 T021: cancelling jobs that run in their own process group (FR-011, FR-012, SC-004).

`sleepy_runner` starts a `sleep 300` as a stand-in for the Node workers. Cancel must stop the job
process AND that grandchild within 10 s. Positive control: both are alive before the cancel.
"""

from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

import _fake_runners
from _web_helpers import _available_team, _wait
from platsim.web import app as webapp


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:  # a zombie still answers kill(0); treat it as gone
        with open(f"/proc/{pid}/stat") as f:
            return f.read().split(") ", 1)[1][0] != "Z"
    except OSError:
        return False


def _wait_for(pred, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.05)
    return pred()


@pytest.fixture
def app_factory(tmp_path, catalog):
    made = []

    def make(runner):
        app = webapp.create_app(runner=runner, isolate=True, catalog=catalog, runs_dir=tmp_path)
        made.append(app)
        return TestClient(app)

    yield make
    for app in made:  # teardown: no job process or sleep outlives the test
        app.state.jobs.shutdown(timeout=15)


def test_cancel_running_then_queued(tmp_path, catalog, app_factory):
    client = app_factory(_fake_runners.sleepy_runner)
    team = _available_team(catalog)
    a = client.post("/api/jobs", json={"species": team, "seed": "a"}).json()["id"]
    b = client.post("/api/jobs", json={"species": team, "seed": "b"}).json()["id"]
    c = client.post("/api/jobs", json={"species": team, "seed": "c"}).json()["id"]
    _wait(client, a, {"running"})
    pid_file = tmp_path / a / "child.pid"
    assert _wait_for(pid_file.exists, 60), "the job process never started its sleep"
    sleep_pid = int(pid_file.read_text())
    job_pid = client.app.state.jobs.current_pid
    assert job_pid and _alive(job_pid) and _alive(sleep_pid), "positive control: both alive before cancel"

    # A queued job: cancelled at once, never runs.
    r = client.post(f"/api/jobs/{c}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert client.get(f"/api/jobs/{c}").json()["error"] == "cancelled by user"

    t0 = time.monotonic()
    r = client.post(f"/api/jobs/{a}/cancel")
    assert r.status_code == 202
    job = _wait(client, a, {"cancelled", "failed", "done"}, timeout=10)
    elapsed = time.monotonic() - t0
    assert job["status"] == "cancelled" and job["error"] == "cancelled by user", job
    assert elapsed <= 10, elapsed
    assert _wait_for(lambda: not _alive(sleep_pid) and not _alive(job_pid), 10 - elapsed), "processes outlived cancel"

    # The next queued job starts; the cancelled-while-queued one never does.
    assert _wait(client, b, {"running"})["status"] == "running"
    assert client.get(f"/api/jobs/{c}").json()["status"] == "cancelled"
    assert not (tmp_path / c / "child.pid").exists()

    assert client.post(f"/api/jobs/{a}/cancel").status_code == 409
    assert client.post("/api/jobs/job-20000101T000000Z-abcdef/cancel").status_code == 404


def test_cancel_race_with_finish(tmp_path, catalog, app_factory):
    client = app_factory(_fake_runners.instant_runner)
    jid = client.post("/api/jobs", json={"species": _available_team(catalog)}).json()["id"]
    _wait(client, jid, {"running", "done"})
    client.post(f"/api/jobs/{jid}/cancel")
    job = _wait(client, jid, {"done", "cancelled", "failed"}, timeout=60)
    assert job["status"] in ("done", "cancelled"), job
    if job["status"] == "done":
        assert (tmp_path / jid / "result.json").is_file()
