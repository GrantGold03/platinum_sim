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
- Legality options (legality/models.LegalityOptions): POST /api/jobs takes one JSON boolean per
  option field (`allow_egg_moves`, `allow_trade_evolutions`, `allow_post_game_pokemon`,
  `allow_post_game_items`, `allow_unobtainable_pokemon`; default false), stored in the job's
  `options` and passed to the optimizer as OptimizeRequest.legality. GET /api/species takes
  `trade_evolutions`, `post_game_pokemon`, `post_game_items` and `unobtainable_pokemon` (0/1) to
  report availability under those rules (egg moves never change availability).
- 002 redesign: with `isolate` (the default for the real optimizer), each job runs in a spawned child
  with its own process group (web/job_process.py), so POST /api/jobs/{id}/cancel stops it and its Node
  workers within seconds. Server shutdown (lifespan hook, atexit) stops the running job and records it
  as failed ("server stopped while running"). The child also kills its own group if the server dies.
"""

from __future__ import annotations

import json
import os
import queue
import re
import secrets
import threading
import time
import atexit
import traceback
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import Body, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from platsim.budget import DEFAULT_PRESET, PRESETS
from platsim.legality.models import LegalityOptions
from platsim.web.display_text import clean
from platsim.optimizer.api import InvalidRequest, OptimizeRequest, OptimizeResult, Progress, run_optimization
from platsim.pins import REPO_ROOT
from platsim.web import job_process
from platsim.web.eta import StageHistory, eta_seconds
from platsim.web.result_view import build_result_view
from platsim.web.sprites import league_trainers, sprite_png, trainer_sprite_png

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


def _platsim_version() -> str | None:
    """The installed platsim version, recorded on a job when it starts running (002 R5): a job
    queued across an upgrade shows the version it actually ran with."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("platsim")
    except PackageNotFoundError:
        return None


def _parse_time(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def _verdict_of(result_json: Path) -> str | None:
    """qualified / borderline / not_qualified from a result.json; None if it can't be read."""
    try:
        d = json.loads(Path(result_json).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if d.get("qualified"):
        return "qualified"
    return "borderline" if d.get("borderline") else "not_qualified"


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
                                     "jobs (OptimizeRequest has no resume option). Submit it again: the same Pokémon "
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
    """One background thread; FIFO over job ids. With `isolate`, each job runs in its own process
    group (job_process.run_in_process) and can be cancelled."""

    def __init__(self, store: JobStore, runner: Runner, isolate: bool = False, history: StageHistory | None = None):
        self.store = store
        self.runner = runner
        self.isolate = isolate
        self.history = history
        self.q: queue.Queue[str | None] = queue.Queue()
        self.thread: threading.Thread | None = None
        self.current: str | None = None
        self.current_pid: int | None = None
        self.cancel_events: dict[str, threading.Event] = {}
        self.shutting_down = False

    def start(self) -> None:
        if self.thread is None:
            self.thread = threading.Thread(target=self._loop, name="platsim-web-jobs", daemon=True)
            self.thread.start()

    def submit(self, job_id: str) -> None:
        self.q.put(job_id)

    def stop(self) -> None:
        self.q.put(None)

    def shutdown(self, timeout: float = 10.0) -> None:
        """Stop the running job and the job thread (server shutdown). The running job is recorded as
        failed ("server stopped while running"); queued jobs stay queued for the next start."""
        self.shutting_down = True
        for ev in list(self.cancel_events.values()):
            ev.set()
        self.stop()
        t = self.thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout)
        if t is not None and t.is_alive():  # the join timed out: record it and kill the group ourselves
            jid, pid = self.current, self.current_pid
            if pid:
                try:
                    os.killpg(pid, 9)
                except OSError:
                    pass
            if jid:
                with self.store.lock:
                    job = self.store.get(jid)
                    if job and job["status"] == "running":
                        self.store.update(jid, status="failed", finished=_now(), error="server stopped while running")

    def cancel(self, jid: str) -> tuple[int, dict]:
        """(HTTP status, body) for POST /api/jobs/{id}/cancel (contracts/http-api.md)."""
        with self.store.lock:
            job = self.store.get(jid)
            if job is None:
                return 404, {"detail": f"no job {jid!r}"}
            if job["status"] == "queued":
                self.store.update(jid, status="cancelled", finished=_now(), error="cancelled by user",
                                  progress={**job["progress"], "stage": "cancelled"})
                return 200, {"id": jid, "status": "cancelled"}
            if job["status"] == "running":
                at = _now()
                self.store.update(jid, cancel_requested=at)
                ev = self.cancel_events.get(jid)
                if ev is not None:
                    ev.set()
                return 202, {"id": jid, "status": "running", "cancel_requested": at}
            return 409, {"detail": f"job {jid} is {job['status']}"}

    def _set_pid(self, pid: int) -> None:
        self.current_pid = pid

    def _loop(self) -> None:
        while True:
            jid = self.q.get()
            if jid is None or self.shutting_down:
                return
            try:
                self.run_one(jid)
            except Exception:  # never let the worker thread die
                traceback.print_exc()

    def run_one(self, jid: str) -> None:
        store = self.store
        event = threading.Event()  # exists before the job is visible as running (analysis P4-05)
        # The queued -> running step happens under the store lock, so a cancel can't land between
        # the check and the write and be lost (analysis P4-05).
        with store.lock:
            job = store.get(jid)
            if job is None or job["status"] != "queued":
                return
            self.cancel_events[jid] = event
            self.current = jid
            opts = job["options"]
            legality = _legality(opts)
            req = OptimizeRequest(species=tuple(job["species"]), min_clear=float(opts["min_clear"]),
                                  seed=str(opts["seed"]), budget=str(opts["budget"]), out_dir=store.path(jid),
                                  legality=legality)
            started = _now()
            # stage_started and seen_stages are web-side fields: a Progress update replaces the whole
            # progress dict, so they are carried forward here (002 T005, analysis P3-01 / P4-09).
            track = {"stage": "starting", "stage_started": started, "seen_stages": ["starting"]}
            store.update(jid, status="running", started=started, platsim_version=_platsim_version(),
                         progress={**job["progress"], "stage": "starting", "stage_started": started,
                                   "seen_stages": ["starting"]})

        def on_progress(p: Progress) -> None:
            prog = _jsonable(asdict(p))
            stage = prog.get("stage")
            stage_changed = stage != track["stage"]
            if stage_changed:
                track["stage"], track["stage_started"] = stage, _now()
                if stage not in track["seen_stages"]:
                    track["seen_stages"] = [*track["seen_stages"], stage]
            prog["stage_started"] = track["stage_started"]
            prog["seen_stages"] = list(track["seen_stages"])
            store.update(jid, force_write=stage_changed, progress=prog)

        try:
            if self.isolate:
                result = job_process.run_in_process(self.runner, req, on_progress, event, on_start=self._set_pid)
            else:
                result = self.runner(req, on_progress)
            out = Path(result.out_dir)
            paths = {RESULT_KIND[name]: str(out / fname) for name, (fname, _) in RESULT_FILES.items()}
            missing = [p for p in paths.values() if not Path(p).is_file()]
            if missing:
                raise RuntimeError(f"optimizer finished but did not write: {', '.join(missing)}")
            final_progress = {**store.get(jid)["progress"], "stage": "done"}
            store.update(jid, status="done", finished=_now(), result_paths=paths, qualified=bool(result.qualified),
                         verdict=_verdict_of(Path(paths["json"])), progress=final_progress)
        except job_process.JobCancelled:
            status, why = (("failed", "server stopped while running") if self.shutting_down
                           else ("cancelled", "cancelled by user"))
            store.update(jid, status=status, finished=_now(), error=why,
                         progress={**store.get(jid)["progress"], "stage": status})
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
            self.current_pid = None
            self.cancel_events.pop(jid, None)
            if self.history is not None:
                self.history.refresh()


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
            raise HTTPException(500, detail=f"Pokémon data failed to load: {clean(self.error)}")
        raise HTTPException(503, detail="Pokémon data is loading (first start takes about a minute); retry shortly")


def create_app(runner: Runner = run_optimization, runs_dir: Path | str = DEFAULT_RUNS_DIR, catalog=None,
               catalog_builder: Callable[[], Any] | None = None, start_worker: bool = True,
               isolate: bool | None = None) -> FastAPI:
    """Build the app. `runner` defaults to the real optimizer; `catalog` (a SpeciesCatalog) may be
    passed pre-built, otherwise it is built in a background thread. `start_worker=False` leaves
    the job thread stopped (tests drive `app.state.jobs.run_one` themselves). `isolate=None` runs
    the real optimizer in a child process and test stubs in the job thread."""
    if isolate is None:
        isolate = runner is run_optimization
    store = JobStore(Path(runs_dir))
    jobs = JobRunner(store, runner, isolate=isolate, history=StageHistory.load(runs_dir))
    holder = CatalogHolder(catalog, catalog_builder)
    atexit.register(jobs.shutdown)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        await run_in_threadpool(jobs.shutdown)

    app = FastAPI(title="platsim", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
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
    def species(q: str = "", excluded: int = 1, limit: int = 25, trade_evolutions: int = 0, post_game_pokemon: int = 0,
                post_game_items: int = 0, unobtainable_pokemon: int = 0) -> list[dict]:
        cat = holder.require()
        limit = max(1, min(int(limit), 25))
        opts = LegalityOptions(allow_trade_evolutions=bool(trade_evolutions),
                               allow_post_game_pokemon=bool(post_game_pokemon),
                               allow_post_game_items=bool(post_game_items),
                               allow_unobtainable_pokemon=bool(unobtainable_pokemon))
        return [cat.to_json(s, opts) for s in cat.search(q, include_excluded=bool(excluded), limit=limit, options=opts)]

    @app.post("/api/jobs", status_code=201)
    def submit(payload: Any = Body(...)) -> JSONResponse:
        cat = holder.require()
        if not isinstance(payload, dict):
            return JSONResponse({"detail": "request body must be a JSON object", "reasons": {}}, status_code=422)
        try:
            options = _options(payload)
            keys = cat.resolve_team(payload.get("species"), _legality(options))
        except InvalidRequest as e:
            return JSONResponse({"detail": clean(str(e)), "reasons": {k: clean(v) for k, v in e.reasons.items()}},
                                status_code=422)
        job = store.create(keys, options)
        jobs.submit(job["id"])
        return JSONResponse({"id": job["id"]}, status_code=201)

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        with store.lock:
            return [_view(store, jobs, j, holder) for j in reversed(store.order)][:50]

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = _job_or_404(store, job_id)
        view = _view(store, jobs, job_id, holder)
        if job["status"] == "done" and job.get("result_paths"):
            view.update(build_result_view(job) or {})
        return view

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str) -> JSONResponse:
        _job_or_404(store, job_id)
        code, body = jobs.cancel(job_id)
        return JSONResponse(body, status_code=code)

    @app.get("/api/sprites/{species}/{kind}.png")
    def sprite(species: str, kind: str) -> Response:
        data = sprite_png(species, kind)
        if data is None:
            raise HTTPException(404, detail=f"no {kind!r} sprite for {species!r}")
        return Response(data, media_type="image/png", headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/league")
    def league() -> JSONResponse:
        """003 FR-020: the first-run Elite Four and Champion, in battle order, with party pokemon keys
        only (no levels, moves or items)."""
        body = [{"trainer": k, "name": name, "sprite": f"/api/trainer-sprites/{k}.png", "party": list(party)}
                for k, (name, _cls, party) in league_trainers().items()]
        return JSONResponse(body, headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/trainer-sprites/{trainer}.png")
    def trainer_sprite(trainer: str) -> Response:
        data = trainer_sprite_png(trainer)
        if data is None:
            raise HTTPException(404, detail=f"no trainer sprite for {trainer!r}")
        return Response(data, media_type="image/png", headers={"Cache-Control": "max-age=86400"})

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
    flags = {}
    for k in LegalityOptions().to_dict():
        v = payload.get(k, False)
        if v is None:
            v = False
        if not isinstance(v, bool):
            raise InvalidRequest(f"{k} must be true or false, got {v!r}")
        flags[k] = v
    return {"min_clear": min_clear, "seed": str(seed), "budget": budget, **flags}


def _legality(options: dict) -> LegalityOptions:
    """The legality rules of a job's stored options (its other keys are min_clear, seed and budget)."""
    return LegalityOptions.from_dict({k: options[k] for k in LegalityOptions().to_dict() if k in options})


def _job_or_404(store: JobStore, job_id: str) -> dict:
    job = store.get(job_id) if ID_RE.match(job_id) else None
    if job is None:
        raise HTTPException(404, detail=f"no job {job_id!r}")
    return job


_VERDICT_CACHE: dict[str, str] = {}


def _label(job: dict, holder: CatalogHolder | None) -> str:
    """"<6 species names> · <verdict or status>" (FR-015). The page adds the local time."""
    cat = holder.catalog if holder is not None else None
    names = []
    for k in job.get("species") or []:
        info = cat.get(k) if cat is not None else None
        names.append(info.name if info is not None else k)
    what = job["status"]
    if what == "done":
        what = job.get("verdict") or _VERDICT_CACHE.get(job["id"])
        if what is None:  # older jobs: read once from result.json; unreadable -> "done" (P5-03)
            what = _verdict_of(Path((job.get("result_paths") or {}).get("json") or "")) or "done"
            _VERDICT_CACHE[job["id"]] = what
    label = f"{', '.join(names)} · {what.replace('_', ' ')}"
    # 003 T042a: a run re-rendered from an older one (new source text, same battles) says so.
    return label + " (re-rendered)" if job.get("rerendered_from") else label


def _view(store: JobStore, jobs: JobRunner, job_id: str, holder: CatalogHolder | None = None) -> dict:
    job = store.get(job_id)
    view = {k: v for k, v in job.items() if k != "traceback"}
    # Recorded messages may come from the optimizer or validator: shown text only (003 FR-001, FR-002).
    view["error"] = clean(view.get("error"))
    if view.get("invalid_reasons"):
        view["invalid_reasons"] = {k: clean(v) for k, v in view["invalid_reasons"].items()}
    view["label"] = _label(job, holder)
    view.setdefault("platsim_version", None)
    started, finished = _parse_time(job.get("started")), _parse_time(job.get("finished"))
    now = time.time()
    view["elapsed_s"] = (finished - started) if (started and finished) else (now - started) if started else None
    if job["status"] == "running":
        p = job.get("progress") or {}
        stage_t = _parse_time(p.get("stage_started")) or started or now
        view["eta_s"] = (eta_seconds(jobs.history, job["options"].get("budget", DEFAULT_PRESET), p.get("stage"),
                                     p.get("runs_done"), p.get("runs_planned"), now - stage_t, p.get("seen_stages"))
                         if jobs.history is not None else None)
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
