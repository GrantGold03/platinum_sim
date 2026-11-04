"""Feature 021: `platsim evaluate --sampling adaptive` end to end at a small count on the reference team.

Floor 0.9 so the switch happens after about 36 full runs; byte-identical result.json across worker counts; the new
fields present; floor 1.0 identical to `--sampling full` once the four sampling-specific keys are removed.
PLATSIM_EVALUATE_FAST_N sets the run count (default 80).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
REFERENCE = REPO / "tests" / "fixtures" / "reference_team.json"
SAMPLING_KEYS = ("sampling", "sampling_detail")


def _evaluate(out: Path, *args: str):
    cmd = [sys.executable, "-m", "platsim.cli", "evaluate", *args, "--out", str(out)]
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    return p, out / "result.json"


def _strip(d: dict) -> dict:
    d = {k: v for k, v in d.items() if k not in SAMPLING_KEYS}
    d["provenance"] = {k: v for k, v in d.get("provenance", {}).items() if k != "sampling"}
    d["seeds"] = {k: v for k, v in d.get("seeds", {}).items() if k != "cynthia_only_seed"}
    return d


@pytest.mark.battle_sim
def test_adaptive_sampling_switches_is_deterministic_and_equals_full_at_floor_1(tmp_path):
    n = os.environ.get("PLATSIM_EVALUATE_FAST_N", "80")
    common = [str(REFERENCE), "--runs", n, "--seed", "t021", "--budget", "quick", "--sampling", "adaptive", "--floor", "0.9"]
    p1, j1 = _evaluate(tmp_path / "a", *common, "--workers", "8")
    assert p1.returncode == 0, p1.stderr[-3000:]
    p2, j2 = _evaluate(tmp_path / "b", *common, "--workers", "3")
    assert p2.returncode == 0, p2.stderr[-3000:]
    assert j1.read_bytes() == j2.read_bytes(), "adaptive result.json differs across worker counts"
    r = json.loads(j1.read_text())
    assert r["sampling"] == "adaptive" and r["n_runs"] == int(n)
    d = r["sampling_detail"]
    assert d["switch_run"] is not None and d["switch_run"] < int(n) and d["cynthia_only_runs"] > 0
    assert d["full_runs"] + d["cynthia_only_runs"] == int(n)
    for k in ("floor", "banked_states", "e4_pass_rate", "e4_pass_ci95", "cynthia_rate", "cynthia_battles",
              "composite_ci95", "extension", "statistic"):
        assert k in d, k
    assert r["provenance"]["sampling"]["method"] == "adaptive" and "cynthia_only_seed" in r["seeds"]
    assert r["champion_battles"] >= d["cynthia_only_runs"]
    assert "adaptive" in p1.stdout
    # floor 1.0: never switches; identical to full apart from the sampling keys
    p3, j3 = _evaluate(tmp_path / "c", str(REFERENCE), "--runs", n, "--seed", "t021", "--budget", "quick",
                       "--sampling", "adaptive", "--floor", "1.0", "--workers", "8")
    assert p3.returncode == 0, p3.stderr[-3000:]
    p4, j4 = _evaluate(tmp_path / "d", str(REFERENCE), "--runs", n, "--seed", "t021", "--budget", "quick",
                       "--sampling", "full", "--workers", "8")
    assert p4.returncode == 0, p4.stderr[-3000:]
    r3, r4 = json.loads(j3.read_text()), json.loads(j4.read_text())
    assert r3["sampling"] == "adaptive" and r3["sampling_detail"]["switch_run"] is None
    assert r4["sampling"] == "full" and r4["sampling_detail"] is None
    assert json.dumps(_strip(r3), sort_keys=True) == json.dumps(_strip(r4), sort_keys=True)


def test_floor_outside_range_is_a_usage_error(tmp_path):
    p, _ = _evaluate(tmp_path / "e", str(REFERENCE), "--runs", "5", "--sampling", "adaptive", "--floor", "0.5")
    assert p.returncode == 2 and "--floor" in p.stderr
