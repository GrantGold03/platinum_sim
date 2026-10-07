"""T052: src/platsim/sim/pool.py over real `node sim/worker.mjs` processes.

Opponents are `placeholder-default` (the decomp trainer AI, T045-T047, is not wired in yet); the
player uses `greedy-v1` (T049). Run with `-s` to see timings.
"""

import json
import signal
import time

import pytest

from platsim import pins
from platsim.sim import pool as pool_mod
from platsim.sim.pool import AiUnimplemented, PinMismatch, WorkerCrashed, WorkerPool
from platsim.sim.seeds import derive_seed

from test_worker import TEAM  # tests/integration is on sys.path (pytest rootdir/prepend import)


def gauntlet(i, master="pool"):
    return {"op": "gauntlet", "team": TEAM, "seed": derive_seed(master, i, 0), "player_policy": "greedy-v1",
            "stop_on_loss": False, "log": "summary"}


def test_64_gauntlets_on_4_workers_match_single_worker():
    reqs = [gauntlet(i) | {"id": f"r{i}"} for i in range(64)]
    t0 = time.perf_counter()
    with WorkerPool(4) as p4:
        multi = p4.map(reqs)
        assert p4.restarts == 0
        assert p4.hello["showdown_commit"] == pins.SHOWDOWN_COMMIT
        assert "greedy-v1" in p4.hello["policies"]
    t4 = time.perf_counter() - t0
    t0 = time.perf_counter()
    single = pool_mod.run_single(reqs)
    t1 = time.perf_counter() - t0
    print(f"64 gauntlets: 4 workers {t4:.2f}s, 1 worker {t1:.2f}s")
    assert [r["id"] for r in multi] == [f"r{i}" for i in range(64)]  # caller ids routed back in order
    assert all(r["ok"] and r["player_policy"] == "greedy-v1" for r in multi)
    assert json.dumps(multi, sort_keys=True) == json.dumps(single, sort_keys=True)
    # Positive control: the comparison can fail - other seeds give other battles.
    other = pool_mod.run_single([gauntlet(i, master="other") for i in range(4)])
    assert [r["battles"][0]["log_hash"] for r in other] != [r["battles"][0]["log_hash"] for r in multi[:4]]


def test_killed_worker_is_restarted_and_its_request_completes():
    req = gauntlet(7)
    (expected,) = pool_mod.run_single([req])
    with WorkerPool(1) as p:
        w = p.workers[0]
        old_pid = w.proc.pid
        w.proc.send_signal(signal.SIGSTOP)  # freeze it so the request is certainly in flight
        fut = p.submit(req)
        deadline = time.monotonic() + 10
        while w.in_flight is None:
            assert time.monotonic() < deadline, "request never reached the worker"
            time.sleep(0.01)
        w.proc.kill()
        got = fut.result(timeout=60)
        assert p.restarts == 1
        assert w.proc.pid != old_pid
        assert got == expected
        # The restarted slot keeps serving.
        assert p.map([gauntlet(8)])[0]["ok"]


def test_hello_mismatch_raises(monkeypatch):
    monkeypatch.setattr(pins, "SHOWDOWN_COMMIT", "0" * 40)
    with pytest.raises(PinMismatch, match="showdown_commit"):
        WorkerPool(2)


def test_hello_mismatch_decomp_raises(monkeypatch):
    monkeypatch.setattr(pins, "DECOMP_COMMIT", "f" * 40)
    with pytest.raises(PinMismatch, match="decomp_commit"):
        WorkerPool(1)


# A stand-in worker speaking the protocol, for failure kinds the real worker cannot produce yet.
FAKE = """
const rl = require('readline').createInterface({ input: process.stdin });
rl.on('line', (l) => {
  const r = JSON.parse(l);
  const out = (o) => process.stdout.write(JSON.stringify({ id: r.id, ...o }) + '\\n');
  if (r.op === 'hello') return out({ ok: true, showdown_commit: %(sd)s, decomp_commit: %(pp)s });
  if (r.mode === 'ai') return out({ ok: false, error: { kind: 'ai_unimplemented', detail: 'AI command 0x2a' } });
  if (r.mode === 'crash') process.exit(3);
  setTimeout(() => out({ ok: true, echo: r.n }), r.delay || 0);
});
"""


def fake_cmd():
    return ["node", "-e", FAKE % {"sd": json.dumps(pins.SHOWDOWN_COMMIT), "pp": json.dumps(pins.DECOMP_COMMIT)}]


def test_ai_unimplemented_stops_the_job():
    with WorkerPool(1, command=fake_cmd()) as p:
        assert p.map([{"op": "x", "n": 1}])[0] == {"ok": True, "echo": 1}  # positive control
        reqs = [{"op": "x", "n": 2, "delay": 200}, {"op": "x", "mode": "ai", "id": "bad"},
                {"op": "x", "n": 3}, {"op": "x", "n": 4}]
        futs = [p.submit(r) for r in reqs]
        assert futs[0].result(timeout=10)["echo"] == 2
        with pytest.raises(AiUnimplemented, match="0x2a") as ei:
            futs[1].result(timeout=10)
        assert ei.value.request_id == "bad"
        for f in futs[2:]:  # queued behind it: stopped, not run
            with pytest.raises(AiUnimplemented):
                f.result(timeout=10)
        with pytest.raises(AiUnimplemented):
            p.submit({"op": "x", "n": 5})


def test_request_that_crashes_twice_fails_with_workercrashed():
    with WorkerPool(1, command=fake_cmd()) as p:
        with pytest.raises(WorkerCrashed, match="twice"):
            p.submit({"op": "x", "mode": "crash"}).result(timeout=30)
        assert p.restarts == 2
        assert p.map([{"op": "x", "n": 9}])[0]["echo"] == 9  # the slot still works
