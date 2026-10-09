"""002 T023: no job outlives the server (analysis U1, P4-04, P5-02).

Each web job runs in its own session (setsid), so the terminal's Ctrl-C no longer reaches it.
Case A (SIGINT, a graceful stop) relies on the shutdown hook. Case B (SIGKILL, no hook can run)
relies on the child's parent-death guard. Positive control in both: the job process and its
`sleep` grandchild are alive before the signal.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from _serve_fake import FAKE_SPECIES

LAUNCHER = Path(__file__).resolve().parent / "_serve_fake.py"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
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


def _http(port, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


def _children(pid: int) -> list[int]:
    """Direct children (pgrep -P; /proc/<pid>/task/<pid>/children needs CONFIG_PROC_CHILDREN,
    which this kernel lacks)."""
    r = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True)
    return [int(x) for x in r.stdout.split()]


def _kill_all(pids) -> None:
    for p in pids:
        if p and _alive(p):
            for f in (lambda: os.killpg(p, signal.SIGKILL), lambda: os.kill(p, signal.SIGKILL)):
                try:
                    f()
                except OSError:
                    pass


def _start(runs_dir: Path, procs: dict):
    """Start the server and one job. Every pid seen goes into `procs` at once, so the test's
    cleanup can kill them even if an assertion here fails."""
    port = _free_port()
    server = subprocess.Popen([sys.executable, str(LAUNCHER), str(port), str(runs_dir)])
    procs["server"] = server
    assert _wait_for(lambda: _try(lambda: _http(port, "/api/jobs")), 30), "server never came up"
    jid = _http(port, "/api/jobs", {"species": list(FAKE_SPECIES)})["id"]
    pid_file = runs_dir / jid / "child.pid"
    assert _wait_for(pid_file.exists, 60), "the job never started its sleep"
    sleep_pid = int(pid_file.read_text())
    procs["pids"] = [sleep_pid]
    job_pids = [p for p in _children(server.pid) if _alive(p)]
    procs["pids"] += job_pids
    # The job process is the spawn child (the server's other child is multiprocessing's resource tracker).
    spawn = [p for p in job_pids if "spawn_main" in Path(f"/proc/{p}/cmdline").read_text(errors="replace")]
    assert spawn and _alive(sleep_pid), "positive control: job process and sleep alive"
    return server, jid, job_pids, sleep_pid


def _try(f):
    try:
        f()
        return True
    except OSError:
        return False


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGKILL], ids=["sigint", "sigkill"])
def test_no_job_outlives_server(tmp_path, sig):
    procs: dict = {}
    try:
        server, jid, job_pids, sleep_pid = _start(tmp_path, procs)
        t0 = time.monotonic()
        server.send_signal(sig)
        server.wait(timeout=20)
        gone = _wait_for(lambda: not _alive(sleep_pid) and not any(_alive(p) for p in job_pids), 10)
        print(f"\n{sig.name}: everything gone after {time.monotonic() - t0:.1f}s")
        assert gone, f"left running after {sig.name}: sleep={_alive(sleep_pid)} jobs={[_alive(p) for p in job_pids]}"
        if sig == signal.SIGINT:
            job = json.loads((tmp_path / jid / "job.json").read_text())
            assert job["status"] == "failed" and job["error"] == "server stopped while running", job
    finally:
        _kill_all(procs.get("pids", []))
        server = procs.get("server")
        if server is not None and server.poll() is None:
            server.kill()
