"""002 T024: the process boundary does not change results (analysis V1, Constitution IV).

A real 40-run `evaluate` of tests/fixtures/reference_team.json, once in a spawned child (the web
job path, job_process.run_in_process) and once in this process. The two result.json files must be
byte-identical. Positive control: the run really happened (n_runs == 40, per_battle not empty).
"""

from __future__ import annotations

import json
import threading
import time

import _fake_runners
import pytest

from platsim.optimizer.api import OptimizeRequest
from platsim.web import job_process

pytestmark = pytest.mark.battle_sim  # 012: every test here starts the battle worker


def test_child_process_matches_in_process(tmp_path):
    species = ("infernape",) * 6  # unused by evaluate_runner; OptimizeRequest needs six
    t0 = time.monotonic()
    req_a = OptimizeRequest(species=species, out_dir=tmp_path / "child")
    res_a = job_process.run_in_process(_fake_runners.evaluate_runner, req_a, lambda p: None, threading.Event())
    t1 = time.monotonic()
    req_b = OptimizeRequest(species=species, out_dir=tmp_path / "inproc")
    _fake_runners.evaluate_runner(req_b)
    t2 = time.monotonic()
    print(f"\nchild {t1 - t0:.1f}s, in-process {t2 - t1:.1f}s")

    a = (res_a.out_dir / "result.json").read_bytes()
    b = (tmp_path / "inproc" / "result.json").read_bytes()
    r = json.loads(a)
    assert r["n_runs"] == 40 and r["per_battle"], "positive control: a real evaluation ran"
    assert a == b, "result.json differs between the child process and in-process runs"
