"""Local web page and HTTP API (T067, contracts/http-api.md).

- Binds to 127.0.0.1 only (`serve`). There is no host option.
- The only optimizer interface used is `platsim.optimizer.api` (run_optimization, OptimizeRequest,
  Progress, InvalidRequest). `create_app(runner=...)` takes any callable with the same signature,
  which is how tests inject a fast stub.
- Single-job FIFO queue: one background thread runs one job at a time (the optimizer uses every
  worker); later jobs wait in submission order.
- Job state lives in `<runs_dir>/<id>/job.json` (data-model.md Job), rewritten on every state change
  and on progress updates. The optimizer writes its result files into the same directory.
- Restart: jobs found `queued` are re-queued in creation order. Jobs found `running` are marked
  `failed` with reason "interrupted by a server restart". They are NOT resumed: OptimizeRequest has
  no resume flag, so the web runner cannot ask the optimizer to continue from its checkpoint.
  Submit the job again (same species and seed give the same result, spec US1 scenario 4).
- Result files (result.json / result.xlsx / result.csv / team.txt) return 409 until the job is done.
"""

from __future__ import annotations

import csv
import json
import os
import queue
import re
import secrets
import threading
import time
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from platsim.budget import DEFAULT_PRESET, PRESETS
from platsim.optimizer.api import InvalidRequest, OptimizeRequest, OptimizeResult, Progress, run_optimization
from platsim.pins import REPO_ROOT

HOST = "127.0.0.1"  # contracts/http-api.md: local only
DEFAULT_RUNS_DIR = REPO_ROOT / "runs"
STATIC_DIR = Path(__file__).resolve().parent / "static"
JOB_FILE = "job.json"
# Result files: URL name -> (file name inside the job directory, media type).
RESULT_FILES = {
    "result.json": ("result.json", "application/json"),
    "result.xlsx": ("result.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "result.csv": ("result.csv", "text/csv; charset=utf-8"),
    "team.txt": ("team.txt", "text/plain; charset=utf-8"),
}
RESULT_KIND = {"result.json": "json", "result.xlsx": "xlsx", "result.csv": "csv", "team.txt": "team"}
ID_RE = re.compile(r"^job-\d{8}T\d{6}Z-[0-9a-f]{6}$")
PROGRESS_WRITE_INTERVAL = 0.5  # seconds between job.json rewrites for progress-only updates

Runner = Callable[[OptimizeRequest, Callable[[Progress], None] | None], OptimizeResult]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _jsonable(x: Any) -> Any:
    return json.loads(json.dumps(x, default=str))


class JobStore:
    """Jobs in memory, mirrored to <runs_dir>/<id>/job.json. All access goes through `lock`."""

    def __init__(self, runs_dir: Path):
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.jobs: dict[str, dict] = {}
        self.order: list[str] = []  # creation order
        self._last_write: dict[str, float] = {}

    def path(self, job_id: str) -> Path:
        return self.runs_dir / job_id

    def save(self, job: dict) -> None:
        d = self.path(job["id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / (JOB_FILE + ".part")
        tmp.write_text(json.dumps(job, indent=2, default=str) + "\n", encoding="utf-8")
        os.replace(tmp, d / JOB_FILE)
        self._last_write[job["id"]] = time.monotonic()

    def new_id(self) -> str:
        while True:
            jid = f"job-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}"
            if jid not in self.jobs and not self.path(jid).exists():
                return jid

    def create(self, species: tuple[str, ...], options: dict) -> dict:
        with self.lock:
            jid = self.new_id()
            job = {
                "id": jid,
                "status": "queued",
                "species": list(species),
                "options": options,
                "progress": {"stage": "queued", "runs_done": 0, "runs_planned": None, "best_so_far": None,
                             "detail": ""},
                "result_paths": None,
                "qualified": None,
                "error": None,
                "created": _now(),
                "started": None,
                "finished": None,
            }
            self.jobs[jid] = job
            self.order.append(jid)
            self.save(job)
            return job

    def update(self, job_id: str, force_write: bool = True, **fields: Any) -> dict:
        with self.lock:
            job = self.jobs[job_id]
            job.update(fields)
            if force_write or time.monotonic() - self._last_write.get(job_id, 0) >= PROGRESS_WRITE_INTERVAL:
                self.save(job)
            return job

    def get(self, job_id: str) -> dict | None:
        with self.lock:
            j = self.jobs.get(job_id)
            return json.loads(json.dumps(j, default=str)) if j else None

    def queued_ids(self) -> list[str]:
        with self.lock:
            return [j for j in self.order if self.jobs[j]["status"] == "queued"]

    def load_existing(self) -> list[str]:
        """Read job.json files left by a previous server. Returns ids to re-queue (creation order)."""
        found = []
        for f in sorted(self.runs_dir.glob(f"*/{JOB_FILE}")):
            try:
                job = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(job, dict) or job.get("id") != f.parent.name or not ID_RE.match(job["id"]):
                continue
            found.append(job)
        found.sort(key=lambda j: (j.get("created") or "", j["id"]))
        requeue = []
        with self.lock:
            for job in found:
                if job.get("status") == "running":
                    job.update(status="failed", finished=_now(),
                               error="interrupted by a server restart while running; the web runner does not resume "
                                     "jobs (OptimizeRequest has no resume option). Submit it again: the same species "
                                     "and seed give the same result.")
                    self.jobs[job["id"]] = job
                    self.save(job)
                else:
                    self.jobs[job["id"]] = job
                if job.get("status") == "queued":
                    requeue.append(job["id"])
                self.order.append(job["id"])
        return requeue


class JobRunner:
    """One background thread; FIFO over job ids."""

    def __init__(self, store: JobStore, runner: Runner):
        self.store = store
        self.runner = runner
        self.q: queue.Queue[str | None] = queue.Queue()
        self.thread: threading.Thread | None = None
        self.current: str | None = None

    def start(self) -> None:
        if self.thread is None:
            self.thread = threading.Thread(target=self._loop, name="platsim-web-jobs", daemon=True)
            self.thread.start()

    def submit(self, job_id: str) -> None:
        self.q.put(job_id)

    def stop(self) -> None:
        self.q.put(None)

    def _loop(self) -> None:
        while True:
            jid = self.q.get()
            if jid is None:
                return
            try:
                self.run_one(jid)
            except Exception:  # never let the worker thread die
                traceback.print_exc()

    def run_one(self, jid: str) -> None:
        store = self.store
        job = store.get(jid)
        if job is None or job["status"] != "queued":
            return
        self.current = jid
        opts = job["options"]
        req = OptimizeRequest(species=tuple(job["species"]), min_clear=float(opts["min_clear"]), seed=str(opts["seed"]),
                              budget=str(opts["budget"]), out_dir=store.path(jid))
        store.update(jid, status="running", started=_now(),
                     progress={**job["progress"], "stage": "starting"})
        last_stage = ["starting"]

        def on_progress(p: Progress) -> None:
            prog = _jsonable(asdict(p))
            stage_changed = prog.get("stage") != last_stage[0]
            last_stage[0] = prog.get("stage")
            store.update(jid, force_write=stage_changed, progress=prog)

        try:
            result = self.runner(req, on_progress)
            out = Path(result.out_dir)
            paths = {RESULT_KIND[name]: str(out / fname) for name, (fname, _) in RESULT_FILES.items()}
            missing = [p for p in paths.values() if not Path(p).is_file()]
            if missing:
                raise RuntimeError(f"optimizer finished but did not write: {', '.join(missing)}")
            final_progress = {**store.get(jid)["progress"], "stage": "done"}
            store.update(jid, status="done", finished=_now(), result_paths=paths, qualified=bool(result.qualified),
                         progress=final_progress)
        except InvalidRequest as e:
            store.update(jid, status="failed", finished=_now(), error=str(e),
                         progress={**store.get(jid)["progress"], "stage": "failed"},
                         invalid_reasons=dict(e.reasons))
        except Exception as e:
            store.update(jid, status="failed", finished=_now(), error=f"{type(e).__name__}: {e}",
                         progress={**store.get(jid)["progress"], "stage": "failed"},
                         traceback=traceback.format_exc(limit=8))
        finally:
            self.current = None


class CatalogHolder:
    """The species catalogue is built once (the ledger takes ~35 s); a warm-up thread builds it
    at startup and the API answers 503 until it is ready."""

    def __init__(self, catalog=None, builder: Callable[[], Any] | None = None):
        self.catalog = catalog
        self.error: str | None = None
        self._builder = builder
        self._lock = threading.Lock()

    def warm(self) -> None:
        if self.catalog is not None:
            return

        def build() -> None:
            with self._lock:
                if self.catalog is not None:
                    return
                try:
                    if self._builder is None:
                        from platsim.web.species_catalog import build_catalog

                        self.catalog = build_catalog()
                    else:
                        self.catalog = self._builder()
                except Exception as e:  # surfaced through the API
                    self.error = f"{type(e).__name__}: {e}"
                    traceback.print_exc()

        threading.Thread(target=build, name="platsim-web-catalog", daemon=True).start()

    def require(self):
        if self.catalog is not None:
            return self.catalog
        if self.error:
            raise HTTPException(500, detail=f"species data failed to load: {self.error}")
        raise HTTPException(503, detail="species data is loading (first start takes about a minute); retry shortly")


def _read_table(csv_path: Path) -> dict | None:
    try:
        with csv_path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
    except OSError:
        return None
    if not rows:
        return None
    return {"headers": rows[0], "rows": rows[1:]}


SUMMARY_KEYS = ("qualified", "borderline", "threshold", "objective", "n_runs", "clear_rate", "clear_ci95",
                "champion_rate", "champion_ci95", "expected_avg_final_level", "final_level_gap_max", "budget_preset",
                "warnings", "no_qualifying", "player_policy", "opponent_policy", "seeds", "decomp_commit",
                "showdown_commit", "divergence_ledger_version", "sim_code_hash", "platsim_code_hash", "repo_commit",
                "repo_dirty", "node_version", "python_version")


def _read_summary(json_path: Path) -> dict | None:
    try:
        d = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {k: d.get(k) for k in SUMMARY_KEYS}


def create_app(runner: Runner = run_optimization, runs_dir: Path | str = DEFAULT_RUNS_DIR, catalog=None,
               catalog_builder: Callable[[], Any] | None = None, start_worker: bool = True) -> FastAPI:
    """Build the app. `runner` defaults to the real optimizer; `catalog` (a SpeciesCatalog) may be
    passed pre-built, otherwise it is built in a background thread. `start_worker=False` leaves
    the job thread stopped (tests drive `app.state.jobs.run_one` themselves)."""
    app = FastAPI(title="platsim", docs_url=None, redoc_url=None, openapi_url=None)
    store = JobStore(Path(runs_dir))
    jobs = JobRunner(store, runner)
    holder = CatalogHolder(catalog, catalog_builder)
    app.state.store, app.state.jobs, app.state.catalog = store, jobs, holder

    for jid in store.load_existing():
        jobs.submit(jid)
    holder.warm()
    if start_worker:
        jobs.start()

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html; charset=utf-8")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/api/species")
    def species(q: str = "", excluded: int = 1, limit: int = 25) -> list[dict]:
        cat = holder.require()
        limit = max(1, min(int(limit), 25))
        return [s.to_json() for s in cat.search(q, include_excluded=bool(excluded), limit=limit)]

    @app.post("/api/jobs", status_code=201)
    def submit(payload: Any = Body(...)) -> JSONResponse:
        cat = holder.require()
        if not isinstance(payload, dict):
            return JSONResponse({"detail": "request body must be a JSON object", "reasons": {}}, status_code=422)
        try:
            keys = cat.resolve_team(payload.get("species"))
            options = _options(payload)
        except InvalidRequest as e:
            return JSONResponse({"detail": str(e), "reasons": e.reasons}, status_code=422)
        job = store.create(keys, options)
        jobs.submit(job["id"])
        return JSONResponse({"id": job["id"]}, status_code=201)

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        with store.lock:
            return [_view(store, jobs, j) for j in reversed(store.order)][:50]

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = _job_or_404(store, job_id)
        view = _view(store, jobs, job_id)
        if job["status"] == "done" and job.get("result_paths"):
            view["summary"] = _read_summary(Path(job["result_paths"]["json"]))
            view["table"] = _read_table(Path(job["result_paths"]["csv"]))
        return view

    @app.get("/api/jobs/{job_id}/{name}")
    def get_result(job_id: str, name: str) -> FileResponse:
        if name not in RESULT_FILES:
            raise HTTPException(404, detail=f"unknown result file {name!r}; one of {', '.join(RESULT_FILES)}")
        job = _job_or_404(store, job_id)
        if job["status"] != "done":
            raise HTTPException(409, detail=f"job {job_id} is {job['status']}; results are available when it is done")
        path = Path(job["result_paths"][RESULT_KIND[name]])
        if not path.is_file():
            raise HTTPException(404, detail=f"{name} is missing from {path.parent}")
        fname, media = RESULT_FILES[name]
        disp = "attachment" if name in ("result.xlsx", "result.csv") else "inline"
        return FileResponse(path, media_type=media, filename=f"{job_id}-{fname}", content_disposition_type=disp)

    return app


def _options(payload: dict) -> dict:
    min_clear = payload.get("min_clear", 0.75)
    try:
        min_clear = float(min_clear)
    except (TypeError, ValueError):
        raise InvalidRequest(f"min_clear must be a number, got {min_clear!r}") from None
    if not 0 < min_clear <= 1:
        raise InvalidRequest(f"min_clear must be in (0, 1], got {min_clear}")
    seed = payload.get("seed", "default")
    if seed is None or str(seed).strip() == "":
        seed = "default"
    budget = payload.get("budget") or DEFAULT_PRESET
    if budget not in PRESETS:
        raise InvalidRequest(f"unknown budget {budget!r} (known: {', '.join(PRESETS)})")
    return {"min_clear": min_clear, "seed": str(seed), "budget": budget}


def _job_or_404(store: JobStore, job_id: str) -> dict:
    job = store.get(job_id) if ID_RE.match(job_id) else None
    if job is None:
        raise HTTPException(404, detail=f"no job {job_id!r}")
    return job


def _view(store: JobStore, jobs: JobRunner, job_id: str) -> dict:
    job = store.get(job_id)
    view = {k: v for k, v in job.items() if k != "traceback"}
    if job["status"] == "queued":
        q = store.queued_ids()
        view["queue_position"] = q.index(job_id) + 1 if job_id in q else None
        view["running_job"] = jobs.current
    if job["status"] == "done":
        view["downloads"] = {name: f"/api/jobs/{job_id}/{name}" for name in RESULT_FILES}
    return view


def serve(port: int = 8000, runs_dir: Path | str = DEFAULT_RUNS_DIR) -> int:
    import uvicorn

    app = create_app(runs_dir=runs_dir)
    print(f"platsim web: http://{HOST}:{port}/  (runs in {Path(runs_dir).resolve()})", flush=True)
    uvicorn.run(app, host=HOST, port=port, log_level="info")
    return 0
