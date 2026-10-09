"""Fake optimizer runners for the web tests (002 T021, T022, T024, T030).

They live in a plain importable module, not a test module, so a `spawn` child process can
unpickle them by name. `tests/conftest.py` puts this directory on sys.path, and a spawn child
inherits it.
"""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

from platsim.optimizer.api import OptimizeRequest, OptimizeResult, Progress

# Released by thread-mode tests; never used across processes. Tests call HOLD.clear() first.
HOLD = threading.Event()

BEST = {"clear_rate": 0.5, "levels": [50] * 6}


def _write_reports(req: OptimizeRequest) -> OptimizeResult:
    from platsim.report import write_all

    from _web_helpers import _synthetic_report

    write_all(_synthetic_report(req.species), req.out_dir)
    return OptimizeResult(out_dir=req.out_dir, qualified=True)


def sleepy_runner(req: OptimizeRequest, progress=None) -> OptimizeResult:
    """Starts a `sleep 300` (a stand-in for the Node workers), records its pid in child.pid, then
    reports progress, including best_so_far, every 0.2 s for up to 120 s. It only finishes if
    nobody cancels it."""
    out = Path(req.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    child = subprocess.Popen(["sleep", "300"])
    (out / "child.pid").write_text(str(child.pid))
    end = time.monotonic() + 120
    i = 0
    while time.monotonic() < end:
        if progress:
            progress(Progress("screen", i, 1000, best_so_far=dict(BEST)))
        i += 1
        time.sleep(0.2)
    child.kill()
    return _write_reports(req)


def instant_runner(req: OptimizeRequest, progress=None) -> OptimizeResult:
    """Writes the synthetic reports and returns at once (the cancel/done race case)."""
    return _write_reports(req)


def two_beat_runner(req: OptimizeRequest, progress=None) -> OptimizeResult:
    """Two progress updates in the same stage, 1.1 s apart (more than the 1 s resolution of stored
    times), then waits on HOLD before finishing."""
    if progress:
        progress(Progress("screen", 1, 10))
    time.sleep(1.1)
    if progress:
        progress(Progress("screen", 2, 10))
    assert HOLD.wait(30), "HOLD was never set"
    return _write_reports(req)


def seed_switch_runner(req: OptimizeRequest, progress=None) -> OptimizeResult:
    """Behaviour by seed: "fail" raises; "hold" waits on HOLD; anything else finishes at once."""
    if req.seed == "fail":
        raise RuntimeError("synthetic failure")
    if req.seed == "hold":
        if progress:
            progress(Progress("screen", 1, 10))
        assert HOLD.wait(30), "HOLD was never set"
    return _write_reports(req)


def evaluate_runner(req: OptimizeRequest, progress=None) -> OptimizeResult:
    """A real, short battle evaluation: 40 runs of the reference team (T024)."""
    from platsim import cli
    from platsim.pins import REPO_ROOT

    rc = cli.main(["evaluate", str(REPO_ROOT / "tests/fixtures/reference_team.json"), "--runs", "40",
                   "--seed", "web-proc", "--budget", "quick", "--workers", "4", "--out", str(req.out_dir)])
    assert rc == 0, f"evaluate exited {rc}"
    return OptimizeResult(out_dir=req.out_dir, qualified=False)
