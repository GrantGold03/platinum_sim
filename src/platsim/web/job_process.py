"""Run one web job in its own process group, so Cancel can stop it within seconds (002 research R1).

The optimizer cannot be stopped from inside: it swallows exceptions raised by the progress
callback (optimizer/run.py `_Progress`), and `WorkerPool.close()` lets every queued battle finish
first. So each job runs in a `spawn` child that calls `os.setsid()`. The child and its Node
workers then share one process group, and cancel signals the whole group.

Parent-death guard (analysis U1): in its own session the child no longer gets the terminal's
Ctrl-C. If the server dies without running its shutdown hook (kill -9, a crash), the child kills
its own group. On Linux this uses PR_SET_PDEATHSIG, plus a getppid() poll as a fallback.
PDEATHSIG fires when the parent *thread* that started the child exits, so `run_in_process` must
be called from the long-lived JobRunner thread.

`run_optimization` itself is unchanged; the same request goes to the same function.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import queue
import signal
import sys
import threading
import time
import traceback
from typing import Callable

from platsim.optimizer.api import InvalidRequest, OptimizeRequest, OptimizeResult, Progress

POLL_S = 0.2
TERM_GRACE_S = 5.0
SETSID_WAIT_S = 2.0
PR_SET_PDEATHSIG = 1


class JobCancelled(BaseException):
    """The job was stopped by cancel (or by server shutdown). A BaseException, so that no
    `except Exception` on the way up swallows it."""


def _kill_own_group(*_args) -> None:
    os.killpg(os.getpgrp(), signal.SIGKILL)


def _guard_parent(parent_pid: int) -> None:
    if sys.platform.startswith("linux"):
        try:
            import ctypes

            libc = ctypes.CDLL(None, use_errno=True)
            libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0)
        except (OSError, AttributeError):
            pass
    signal.signal(signal.SIGTERM, _kill_own_group)
    if os.getppid() != parent_pid:  # the parent died before the guard was in place
        _kill_own_group()

    def watch() -> None:
        while True:
            time.sleep(1.0)
            if os.getppid() != parent_pid:
                _kill_own_group()

    threading.Thread(target=watch, name="parent-watch", daemon=True).start()


def _child_main(runner, req: OptimizeRequest, q, parent_pid: int) -> None:
    os.setsid()
    _guard_parent(parent_pid)
    try:
        result = runner(req, lambda p: q.put(("progress", p)))
        q.put(("result", result))
    except InvalidRequest as e:
        q.put(("invalid", str(e), dict(e.reasons)))
    except BaseException as e:  # noqa: BLE001 - report everything to the parent
        q.put(("error", f"{type(e).__name__}: {e}", traceback.format_exc(limit=8)))
    finally:
        q.close()
        q.join_thread()


class ChildError(RuntimeError):
    def __init__(self, message: str, tb: str = ""):
        super().__init__(message)
        self.child_traceback = tb


def _signal_group(proc, sig) -> bool:
    """Signal the child's process group. If the child hasn't called setsid() yet, there is no
    group to signal (ProcessLookupError): poll briefly, then signal the child alone."""
    end = time.monotonic() + SETSID_WAIT_S
    while True:
        try:
            if os.getpgid(proc.pid) == proc.pid:
                os.killpg(proc.pid, sig)
                return True
        except ProcessLookupError:
            return False  # already gone
        if time.monotonic() >= end or not proc.is_alive():
            try:
                os.kill(proc.pid, sig)
            except ProcessLookupError:
                pass
            return False
        time.sleep(0.1)


def stop_process_group(proc) -> None:
    """SIGTERM the group (the child's handler turns that into SIGKILL for the whole group), then
    SIGKILL it after a grace period if anything is left."""
    _signal_group(proc, signal.SIGTERM)
    proc.join(TERM_GRACE_S)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if proc.is_alive():
        proc.kill()
    proc.join(TERM_GRACE_S)


def run_in_process(runner: Callable, req: OptimizeRequest, on_progress: Callable[[Progress], None],
                   cancel_event: threading.Event, on_start: Callable[[int], None] | None = None) -> OptimizeResult:
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    proc = ctx.Process(target=_child_main, args=(runner, req, q, os.getpid()), name="platsim-web-job")
    proc.start()
    if on_start:
        on_start(proc.pid)
    try:
        while True:
            try:
                msg = q.get(timeout=POLL_S)
            except queue.Empty:
                msg = None
                if not proc.is_alive():
                    try:  # the child may have exited right after its last message
                        msg = q.get(timeout=POLL_S)
                    except queue.Empty:
                        raise ChildError(f"worker process exited with code {proc.exitcode}") from None
            if msg is not None:
                kind = msg[0]
                if kind == "progress":
                    on_progress(msg[1])
                elif kind == "result":  # a finished job wins over a late cancel
                    proc.join(TERM_GRACE_S)
                    return msg[1]
                elif kind == "invalid":
                    proc.join(TERM_GRACE_S)
                    raise InvalidRequest(msg[1], msg[2])
                elif kind == "error":
                    proc.join(TERM_GRACE_S)
                    raise ChildError(msg[1], msg[2])
            if cancel_event.is_set():
                stop_process_group(proc)
                raise JobCancelled()
    finally:
        if proc.is_alive():
            stop_process_group(proc)
        q.close()
