"""Feature 023: `platsim evaluate --battle-style shift` end to end (spec US1, FR-001, FR-005, FR-009; SC-001).

- Shift at a small count on the reference team with 8 and 3 workers: byte-identical result.json; the style is in the
  report, its provenance and the summary line.
- The same request with `--battle-style set` equals the same request without the flag (the default is Set until the
  owner's decision).
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from platsim import pins

REFERENCE = pins.REPO_ROOT / "tests" / "fixtures" / "reference_team.json"
pytestmark = pytest.mark.battle_sim


def _evaluate(out, *args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "platsim.cli", "evaluate", str(REFERENCE), "--runs", "40", "--seed", "t023", "--budget", "quick",
           "--sampling", "full", *args, "--out", str(out)]
    return subprocess.run(cmd, cwd=pins.REPO_ROOT, capture_output=True, text=True)


def _result(d) -> str:
    return (d / "result.json").read_text()


def test_shift_is_deterministic_across_worker_counts_and_named_in_the_report(tmp_path):
    p1 = _evaluate(tmp_path / "a", "--battle-style", "shift", "--workers", "8")
    assert p1.returncode == 0, p1.stderr[-3000:]
    p2 = _evaluate(tmp_path / "b", "--battle-style", "shift", "--workers", "3")
    assert p2.returncode == 0, p2.stderr[-3000:]
    assert _result(tmp_path / "a") == _result(tmp_path / "b"), "result.json differs between worker counts"
    r = json.loads(_result(tmp_path / "a"))
    assert r["battle_style"] == "shift" and r["provenance"]["battle_style"] == "shift"
    assert any(line.startswith("runs ") and "style shift" in line for line in p1.stdout.splitlines())
    assert r["n_runs"] == 40 and r["opponent_policy"] == "decomp-ai"


def test_set_flag_equals_the_default_and_names_set(tmp_path):
    p1 = _evaluate(tmp_path / "s", "--battle-style", "set", "--workers", "8")
    assert p1.returncode == 0, p1.stderr[-3000:]
    p2 = _evaluate(tmp_path / "d", "--workers", "8")
    assert p2.returncode == 0, p2.stderr[-3000:]
    assert _result(tmp_path / "s") == _result(tmp_path / "d")
    r = json.loads(_result(tmp_path / "s"))
    assert r["battle_style"] == "set" and r["provenance"]["battle_style"] == "set"
    assert any(line.startswith("runs ") and "style set" in line for line in p1.stdout.splitlines())
