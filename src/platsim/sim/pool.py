"""Pool of long-lived `node sim/worker.mjs` processes (T052, contracts/worker-protocol.md).

- `WorkerPool(workers=W)` starts W workers (default `os.cpu_count()`) and sends each a `hello`.
  The reported `showdown_commit` and `decomp_commit` must equal `platsim.pins`, and every worker
  must report the same provenance (data hash, ledger version, policies); otherwise `PinMismatch`
  is raised and all workers are stopped.
- `submit(request)` returns a `concurrent.futures.Future` for the worker's response dict;
  `map(requests)` returns the responses in request order. The pool assigns its own wire ids and
  routes each response back by id; the caller's own `id` (if any) is put back on the response.
- Each worker has one request in flight at a time (the worker is single-threaded anyway), served
  by one Python thread that reads the shared FIFO job queue.
- A worker that dies (EOF on stdout or a broken stdin pipe) is restarted (with a new `hello`
  check) and its in-flight request is re-run once. A second crash on the same request fails that
  request with `WorkerCrashed`.
- An `ai_unimplemented` response stops the job: the pool raises `AiUnimplemented` for that
  request and for every request still queued, and refuses new submissions. Errors of kind
  `invalid_team` / `internal` are returned as normal `ok: false` responses.
- `close()` (or leaving the `with` block) stops the workers by closing their stdin.
"""

from __future__ import annotations

import itertools
import json
import os
import queue
import subprocess
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field

from platsim import pins

WORKER_SCRIPT = pins.REPO_ROOT / "sim" / "worker.mjs"
# Fields that must agree across every worker of one pool (provenance, Constitution IV).
_PROVENANCE = ("showdown_commit", "decomp_commit", "decomp_data_hash", "divergence_ledger_version",
               "divergence_patches_applied", "policies", "opponent_policies", "pp_restore_between_battles")


class PoolError(RuntimeError):
    pass


class PinMismatch(pins.PinError):
    """A worker's hello does not match the pinned commits (or the other workers)."""


class WorkerCrashed(PoolError):
    pass


class AiUnimplemented(PoolError):
    """The trainer-AI interpreter reached a command that is not implemented. Stops the job."""

    def __init__(self, detail: str, request_id):
        super().__init__(f"ai_unimplemented (request {request_id!r}): {detail}")
        self.detail = detail
        self.request_id = request_id


@dataclass
class _Job:
    request: dict
    future: Future = field(default_factory=Future)


class _Worker:
    def __init__(self, pool: WorkerPool, index: int):
        self.pool = pool
        self.index = index
        self.proc: subprocess.Popen | None = None
        self.restarts = 0
        self.in_flight: int | None = None  # wire id of the request being served (for tests/diagnostics)
        self.hello: dict | None = None
        self.thread = threading.Thread(target=self._serve, name=f"platsim-worker-{index}", daemon=True)

    # -- process ------------------------------------------------------------------------------
    def spawn(self) -> None:
        self.proc = subprocess.Popen(
            self.pool.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
            text=True, encoding="utf-8", bufsize=1, env=self.pool.env, cwd=str(pins.REPO_ROOT),
        )

    def say_hello(self) -> dict:
        resp = self.roundtrip({"op": "hello"})
        if not resp.get("ok"):
            raise PinMismatch(f"worker {self.index}: hello failed: {resp}")
        expected = {"showdown_commit": pins.SHOWDOWN_COMMIT, "decomp_commit": pins.DECOMP_COMMIT}
        bad = {k: (resp.get(k), v) for k, v in expected.items() if resp.get(k) != v}
        if bad:
            raise PinMismatch(f"worker {self.index}: hello does not match pins (got, pinned): {bad}")
        self.hello = resp
        return resp

    def stop(self, timeout: float = 10.0) -> None:
        p = self.proc
        if p is None:
            return
        try:
            if p.stdin and not p.stdin.closed:
                p.stdin.close()
        except OSError:
            pass
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
        if p.stdout:
            p.stdout.close()

    def restart(self) -> None:
        self.stop(timeout=2.0)
        self.restarts += 1
        self.spawn()
        self.pool._check_same(self.say_hello(), self.index)

    # -- one request --------------------------------------------------------------------------
    def roundtrip(self, request: dict) -> dict:
        wire_id = next(self.pool._ids)
        msg = dict(request, id=wire_id)
        self.in_flight = wire_id
        try:
            try:
                self.proc.stdin.write(json.dumps(msg) + "\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError) as e:
                raise WorkerCrashed(f"worker {self.index}: write failed: {e}") from e
            line = self.proc.stdout.readline()
            if not line:
                code = self.proc.poll()
                raise WorkerCrashed(f"worker {self.index} (pid {self.proc.pid}) exited (code {code}) "
                                    f"with request {wire_id} in flight")
            resp = json.loads(line)
            if resp.get("id") != wire_id:
                raise PoolError(f"worker {self.index}: response id {resp.get('id')!r} != request id {wire_id}")
            return resp
        finally:
            self.in_flight = None

    def _serve(self) -> None:
        while True:
            job = self.pool._jobs.get()
            if job is None:
                return
            if not job.future.set_running_or_notify_cancel():
                continue
            if self.pool._fatal is not None:
                job.future.set_exception(self.pool._fatal)
                continue
            try:
                resp = self._run_with_retry(job.request)
            except BaseException as e:  # noqa: BLE001 - every failure goes to the caller's future
                if not isinstance(e, WorkerCrashed):
                    self.pool._fail(e)
                job.future.set_exception(e)
                continue
            err = resp.get("error") if not resp.get("ok") else None
            if err and err.get("kind") == "ai_unimplemented":
                exc = AiUnimplemented(err.get("detail", ""), job.request.get("id"))
                self.pool._fail(exc)
                job.future.set_exception(exc)
                continue
            if "id" in job.request:
                resp["id"] = job.request["id"]
            else:
                resp.pop("id", None)
            job.future.set_result(resp)

    def _run_with_retry(self, request: dict) -> dict:
        try:
            return self.roundtrip(request)
        except WorkerCrashed as first:
            self.restart()
            try:
                return self.roundtrip(request)
            except WorkerCrashed as second:
                self.restart()  # keep the slot alive for the next request
                raise WorkerCrashed(f"request crashed its worker twice: {first}; then {second}") from second


class WorkerPool:
    def __init__(self, workers: int | None = None, *, command: list[str] | None = None,
                 env: dict[str, str] | None = None):
        self.size = workers or os.cpu_count() or 1
        if self.size < 1:
            raise ValueError(f"workers must be >= 1, got {workers}")
        self.command = command or ["node", str(WORKER_SCRIPT)]
        self.env = dict(os.environ if env is None else env)
        self._ids = itertools.count(1)
        self._jobs: queue.Queue[_Job | None] = queue.Queue()
        self._fatal: BaseException | None = None
        self._lock = threading.Lock()
        self._closed = False
        self.hello: dict | None = None
        self.workers = [_Worker(self, i) for i in range(self.size)]
        try:
            for w in self.workers:
                w.spawn()
            for w in self.workers:
                self._check_same(w.say_hello(), w.index)
        except BaseException:
            for w in self.workers:
                w.stop(timeout=2.0)
            raise
        for w in self.workers:
            w.thread.start()

    def _check_same(self, hello: dict, index: int) -> None:
        prov = {k: hello.get(k) for k in _PROVENANCE}
        with self._lock:
            if self.hello is None:
                self.hello = prov
            elif prov != self.hello:
                diff = {k: (prov[k], self.hello[k]) for k in _PROVENANCE if prov[k] != self.hello[k]}
                raise PinMismatch(f"worker {index} provenance differs from worker 0: {diff}")

    def _fail(self, exc: BaseException) -> None:
        with self._lock:
            if self._fatal is None:
                self._fatal = exc
        # Fail everything still queued; the sentinels for close() are put back.
        sentinels = 0
        while True:
            try:
                job = self._jobs.get_nowait()
            except queue.Empty:
                break
            if job is None:
                sentinels += 1
            elif job.future.set_running_or_notify_cancel():
                job.future.set_exception(self._fatal)
        for _ in range(sentinels):
            self._jobs.put(None)

    @property
    def restarts(self) -> int:
        return sum(w.restarts for w in self.workers)

    def submit(self, request: dict) -> Future:
        if self._closed:
            raise PoolError("pool is closed")
        if self._fatal is not None:
            raise self._fatal
        job = _Job(request)
        self._jobs.put(job)
        return job.future

    def map(self, requests, timeout: float | None = None) -> list[dict]:
        futures = [self.submit(r) for r in requests]
        return [f.result(timeout=timeout) for f in futures]

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for _ in self.workers:
            self._jobs.put(None)
        for w in self.workers:
            if w.thread.is_alive():
                w.thread.join()
            w.stop()

    def __enter__(self) -> WorkerPool:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def run_single(requests: list[dict], command: list[str] | None = None) -> list[dict]:
    """Reference path: run requests sequentially through one fresh worker (for determinism checks)."""
    with WorkerPool(1, command=command) as pool:
        return pool.map(requests)


__all__ = ["AiUnimplemented", "PinMismatch", "PoolError", "WorkerCrashed", "WorkerPool", "run_single",
           "WORKER_SCRIPT"]
