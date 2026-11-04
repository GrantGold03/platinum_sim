"""Feature 022: a quick optimize whose confirmation stage uses adaptive sampling (floor 0.9 so the switch happens at the
quick confirm count), at two worker counts: byte-identical result.json; the confirm attempt and provenance carry the
sampling fields. About 20 minutes on 16 workers (two quick optimizations, like test_optimize_small.py)."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from platsim import pins

SPECIES = ["infernape", "staraptor", "luxray", "garchomp", "gyarados", "gardevoir"]


def _optimize(out, workers: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "platsim.cli", "optimize", *SPECIES, "--budget", "quick", "--seed", "t022",
           "--sampling", "adaptive", "--floor", "0.9", "--workers", workers, "--out", str(out)]
    return subprocess.run(cmd, cwd=pins.REPO_ROOT, capture_output=True, text=True)


@pytest.mark.battle_sim
def test_quick_optimize_with_adaptive_confirmation_is_deterministic_and_records_the_mix(tmp_path):
    w1 = os.environ.get("PLATSIM_OPTIMIZE_WORKERS") or str(os.cpu_count() or 8)
    p1 = _optimize(tmp_path / "a", w1)
    assert p1.returncode == 0, p1.stderr[-3000:]
    p2 = _optimize(tmp_path / "b", "3")
    assert p2.returncode == 0, p2.stderr[-3000:]
    j1, j2 = (tmp_path / "a" / "result.json").read_bytes(), (tmp_path / "b" / "result.json").read_bytes()
    assert j1 == j2, "result.json differs between worker counts under adaptive confirmation"
    r = json.loads(j1)
    assert r["sampling"] == "adaptive"
    prov = r["provenance"]["optimizer"]
    assert prov["sampling_per_stage"]["confirm"] == "adaptive" and prov["sampling_per_stage"]["level_search"] == "full"
    st = json.loads((tmp_path / "a" / "state.json").read_text())
    att = st["stages"]["confirm_attempts"][-1]
    assert att["sampling"] == "adaptive" and att["switch_run"] is not None and att["cynthia_only_runs"] > 0
    assert att["full_runs"] + att["cynthia_only_runs"] == att["runs"]
    comp = st["stages"]["confirm"]["comparison"]
    if comp and "pairs" in comp:
        assert comp["pairs"] == comp["full_pairs"] + comp["cynthia_only_pairs"]
