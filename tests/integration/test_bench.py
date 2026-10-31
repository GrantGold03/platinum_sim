"""Feature 015: `platsim bench` end to end on one small set (contracts/bench-tool.md).

Starts the battle worker (pool half) and `node sim/bench.mjs` (single half): marked `battle_sim`.
"""

import json

import pytest

from platsim.cli import main


@pytest.mark.battle_sim
def test_bench_single_and_pool_agree_on_one_gauntlet(capsys):
    rc = main(["bench", "--policy", "greedy-v1", "--n", "1", "--teams", "bench", "--trainers", "aaron",
               "--workers", "2", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out
    assert out["gauntlets"] == 1 and out["pool_gauntlets"] == 1
    assert out["pool_workers"] == 2
    assert out["digests_agree"] is True
    assert out["digest_logs"] == out["pool_digest_logs"]
    assert out["sim_code_hash"] == out["pool_sim_code_hash"]
    assert out["decisions"] is None  # greedy has no expectimax counters
    assert out["gauntlets_per_s"] > 0 and out["pool_gauntlets_per_s"] > 0
    assert len(out["digest_full"]) == 64


@pytest.mark.battle_sim
def test_bench_no_single_reports_pool_only(capsys):
    rc = main(["bench", "--policy", "greedy-v1", "--n", "1", "--teams", "ref", "--trainers", "aaron",
               "--workers", "1", "--no-single", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out
    assert "digest_logs" not in out and "digests_agree" not in out
    assert out["pool_gauntlets"] == 1 and out["pool_workers"] == 1
    assert len(out["pool_digest_logs"]) == 64
