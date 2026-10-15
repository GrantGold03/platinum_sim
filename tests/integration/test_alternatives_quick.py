"""007 T036: the alternatives stage end to end — a SMOKE TEST, not a reference (outside the 100 h budget).

`quick` budget, benchmark team B4 (tests/fixtures/bench_007.json), `--candidates reference` with the
test-only options alternatives_round=5 and alternatives_members=2. Two runs with the same seed and
different worker counts must give byte-identical result.json (SC-005); every generated alternative is
recorded (SC-003); excluded moves carry reasons (FR-002/003); the validator passes (Constitution III).
Slow: two quick optimizations (tens of minutes each on 16 workers).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from platsim.legality.validator import validate
from platsim.pins import REPO_ROOT

TEAM = json.loads((REPO_ROOT / "tests" / "fixtures" / "bench_007.json").read_text())["teams"]["B4"]["species"]
SCRIPT = """
import sys
from pathlib import Path
from platsim.optimizer.api import OptimizeRequest, run_optimization
req = OptimizeRequest(species=tuple(sys.argv[1].split(',')), seed='t036', budget='quick', workers=int(sys.argv[2]),
                      out_dir=Path(sys.argv[3]), candidates='reference', alternatives_round=5, alternatives_members=2)
run_optimization(req)
"""


def _run(out, workers):
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, "-c", SCRIPT, ",".join(TEAM), str(workers), str(out)], capture_output=True, text=True,
                       cwd=REPO_ROOT)
    return p, time.perf_counter() - t0


def test_alternatives_stage_quick_smoke(tmp_path):
    p1, t1 = _run(tmp_path / "a", os.cpu_count())
    print(f"\nrun 1 ({os.cpu_count()} workers) {t1:.0f}s exit {p1.returncode}\n{p1.stderr[-2000:]}")
    assert p1.returncode == 0, p1.stderr[-3000:]
    p2, t2 = _run(tmp_path / "b", 7)
    print(f"run 2 (7 workers) {t2:.0f}s exit {p2.returncode}")
    assert p2.returncode == 0, p2.stderr[-3000:]
    j1 = (tmp_path / "a" / "result.json").read_bytes()
    assert j1 == (tmp_path / "b" / "result.json").read_bytes(), "result.json differs between two runs with the same seed"

    r = json.loads(j1)
    opt = r["provenance"]["optimizer"]
    assert opt["candidate_mode"] == "reference" and opt["request"]["alternatives_round"] == 5
    assert opt["policy_per_stage"]["alternatives"] == "expectimax2-v3"
    state = json.loads((tmp_path / "a" / "state.json").read_text())
    alt = state["stages"]["level_search"]["alternatives"]
    members = [x for x in alt["records"] if x.get("member_done")]
    assert [m["slot"] for m in members] == [1, 2]
    tests = opt["candidate_tests"]
    for m in members:
        assert sum(1 for t in tests if t["slot"] == m["slot"]) == m["alternatives"]  # SC-003
    assert all("verdict" in t for t in tests)
    assert any(t["verdict"] == "dropped in screening" for t in tests)
    assert opt["excluded_moves"]["1"] and all(isinstance(v, str) and v for v in opt["excluded_moves"]["1"].values())
    print(f"alternatives: {len(tests)} recorded, {sum(1 for t in tests if t.get('n_paired'))} tested in full, "
          f"{sum(1 for t in tests if t.get('adopted'))} adopted; levels {alt['levels']} ({alt['level_rule']})")
    if r.get("no_qualifying") is None:
        assert validate({"builds": r["team"]["builds"]}, required_hms=()) == []
