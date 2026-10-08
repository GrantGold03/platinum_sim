"""T071: `platsim evaluate` end to end (quickstart V7; spec User Story 2, SC-003, Constitution III/IV).

- An illegal team exits 2 and names its violations; nothing is simulated.
- Determinism: the same team, seed and run count give byte-identical result.json, also with a
  different worker count (fast check: `quick` budget, PLATSIM_EVALUATE_FAST_N runs, default 40).
- V7: `platsim evaluate tests/fixtures/reference_team.json --runs N --seed fixed` twice (16 and 7
  workers by default): identical result.json, and the clear-rate CI half-width <= 0.02.
  N = PLATSIM_EVALUATE_N, default 2,000 (the task's count). PLATSIM_EVALUATE_WORKERS sets the first
  run's pool size (default os.cpu_count()). Run with `-s` to see the printed result table and times.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from platsim import pins
from platsim.legality.validator import validate

FIX = pins.REPO_ROOT / "tests" / "fixtures"
REFERENCE = FIX / "reference_team.json"
ILLEGAL = FIX / "illegal_trade_evo.json"


def _evaluate(out, *args: str) -> tuple[subprocess.CompletedProcess, float]:
    cmd = [sys.executable, "-m", "platsim.cli", "evaluate", *args, "--out", str(out)]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=pins.REPO_ROOT, capture_output=True, text=True)
    return p, time.perf_counter() - t0


def test_illegal_fixture_exits_2(tmp_path):
    p, _ = _evaluate(tmp_path / "out", str(ILLEGAL), "--runs", "5")
    assert p.returncode == 2, p.stderr[-2000:]
    assert "SPECIES_TRADE_EVOLUTION" in p.stderr and "ILLEGAL" in p.stderr
    assert not (tmp_path / "out").exists()  # nothing simulated, nothing written
    # positive control: the same check accepts the legal reference team
    assert validate(str(REFERENCE)) == []


def test_egg_move_team_exits_2_without_the_flag(tmp_path):
    """The V8 optimize result (Luxray egg moves) is illegal by default: evaluate refuses it with
    EGG_MOVE_NOT_ALLOWED and simulates nothing; validate accepts it with the flag."""
    v8 = FIX / "t076_v8_team.json"
    p, _ = _evaluate(tmp_path / "out", str(v8), "--runs", "5")
    assert p.returncode == 2, p.stderr[-2000:]
    assert "EGG_MOVE_NOT_ALLOWED" in p.stderr and not (tmp_path / "out").exists()
    from platsim.legality.models import LegalityOptions

    assert validate(str(v8), options=LegalityOptions(allow_egg_moves=True)) == []


def _same_json(a, b) -> None:
    ja, jb = (a / "result.json").read_text(), (b / "result.json").read_text()
    assert ja == jb, f"result.json differs between {a} and {b}"


def test_determinism_fast(tmp_path):
    n = os.environ.get("PLATSIM_EVALUATE_FAST_N", "40")
    common = [str(REFERENCE), "--runs", n, "--seed", "t071-fast", "--budget", "quick"]
    p1, _ = _evaluate(tmp_path / "a", *common, "--workers", "8")
    assert p1.returncode == 0, p1.stderr[-3000:]
    p2, _ = _evaluate(tmp_path / "b", *common, "--workers", "3")
    assert p2.returncode == 0, p2.stderr[-3000:]
    _same_json(tmp_path / "a", tmp_path / "b")
    r = json.loads((tmp_path / "a" / "result.json").read_text())
    assert r["n_runs"] == int(n) and r["budget_preset"] == "quick" and not r["qualified"]
    assert r["player_policy"] == "expectimax2-v2" and r["opponent_policy"] == "decomp-ai"
    # Code version (platsim/version.py): which code produced the result; equal across worker counts
    # (the byte-identical check above covers them).
    from platsim import version

    assert r["sim_code_hash"] == version.sim_code_hash() and r["platsim_code_hash"] == version.platsim_code_hash()
    assert r["repo_commit"] == version.repo_commit() and isinstance(r["repo_dirty"], bool)
    assert r["node_version"].startswith("v") and r["python_version"].count(".") == 2
    for k in ("decomp_commit", "showdown_commit", "divergence_ledger_version", "seeds"):
        assert r[k]
    assert r["provenance"]["worker"]["decomp_data_hash"].startswith("sha256:")
    # Legality options the team was validated under (both off by default)
    assert r["provenance"]["legality_options"] == {"allow_egg_moves": False, "allow_trade_evolutions": False}
    for f in ("result.json", "result.xlsx", "result.csv", "team.txt"):
        assert (tmp_path / "a" / f).is_file()
    # team.txt is a Showdown export that re-imports to a legal team
    assert validate(str(tmp_path / "a" / "team.txt")) == []


def test_v7_reference_team_2000_runs(tmp_path):
    n = int(os.environ.get("PLATSIM_EVALUATE_N", "2000"))
    w1 = os.environ.get("PLATSIM_EVALUATE_WORKERS", str(os.cpu_count() or 1))
    common = [str(REFERENCE), "--runs", str(n), "--seed", "fixed"]
    p1, t1 = _evaluate(tmp_path / "a", *common, "--workers", w1)
    assert p1.returncode == 0, p1.stderr[-3000:]
    print(f"\nV7 run 1 ({w1} workers, {t1:.0f}s):\n{p1.stdout}\n{p1.stderr[-1500:]}")
    p2, t2 = _evaluate(tmp_path / "b", *common, "--workers", "7")
    assert p2.returncode == 0, p2.stderr[-3000:]
    print(f"V7 run 2 (7 workers, {t2:.0f}s)")
    _same_json(tmp_path / "a", tmp_path / "b")
    r = json.loads((tmp_path / "a" / "result.json").read_text())
    lo, hi = r["clear_ci95"]
    assert r["n_runs"] >= n
    assert (hi - lo) / 2 <= 0.02, (r["n_runs"], lo, hi)
    assert r["seeds"]["master"] == "fixed" and r["budget_preset"] == "standard"
    assert r["decomp_commit"] == pins.DECOMP_COMMIT and r["showdown_commit"] == pins.SHOWDOWN_COMMIT
    assert set(r["per_battle"]) <= {"aaron", "bertha", "flint", "lucian", "cynthia"}
    assert r["per_battle"]["aaron"]["battles"] == r["n_runs"]
    assert r["champion_battles"] > max(s["battles"] for t, s in r["per_battle"].items() if t != "cynthia")
    assert r["provenance"]["champion"]["status"] == "met"
    assert len(r["expected_final_levels"]) == 6
