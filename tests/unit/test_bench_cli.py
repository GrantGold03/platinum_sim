"""Feature 015: `platsim bench` option parsing (no worker is started here; contracts/bench-tool.md)."""

import hashlib

import pytest

from platsim.bench import bench_requests, digest_logs, log_line
from platsim.cli import build_parser

# The same vector as sim/test/bench.test.mjs: both languages must hash the same line.
VECTOR = [{"seed": "prof-a-bench-0", "cleared": True, "final_levels": [50, 51, 52, 53, 54, 55],
           "battles": [{"trainer": "aaron", "end": "win", "turns": 12, "log_hash": "sha256:aa"},
                       {"trainer": "bertha", "end": "loss", "turns": 7, "log_hash": "sha256:bb"}]}]
VECTOR_LINE = "prof-a-bench-0|1|50,51,52,53,54,55|aaron:win:12:sha256:aa;bertha:loss:7:sha256:bb\n"


def test_bench_defaults_match_the_contract():
    a = build_parser().parse_args(["bench"])
    assert (a.policy, a.n, a.block, a.teams, a.trainers, a.workers, a.no_single, a.json) == \
        ("expectimax2-v2", 20, "a", ["bench", "ref"], None, None, False, False)
    b = build_parser().parse_args(["bench", "--policy", "x", "--no-single", "--teams", "ref", "--trainers", "aaron,flint",
                                   "--workers", "3", "--n", "2", "--block", "b", "--json"])
    assert (b.policy, b.n, b.block, b.teams, b.trainers, b.workers, b.no_single, b.json) == \
        ("x", 2, "b", ["ref"], ["aaron", "flint"], 3, True, True)


def test_bench_unknown_option_exits_2():
    with pytest.raises(SystemExit) as e:
        build_parser().parse_args(["bench", "--nope"])
    assert e.value.code == 2


def test_bench_requests_and_digest_line():
    reqs = bench_requests(block="a", n=1, teams=["bench"], trainers=["aaron"], policy="greedy-v1")
    assert len(reqs) == 1
    assert reqs[0]["seed"] == "prof-a-bench-0"
    assert reqs[0]["op"] == "gauntlet" and reqs[0]["stop_on_loss"] is False
    assert reqs[0]["trainers"] == ["aaron"] and reqs[0]["player_policy"] == "greedy-v1"
    assert len(reqs[0]["team"]) == 6
    full = bench_requests()
    assert [r["seed"] for r in full][:2] == ["prof-a-bench-0", "prof-a-bench-1"]
    assert [r["seed"] for r in full][-1] == "prof-a-ref-19" and len(full) == 40
    assert "trainers" not in full[0]
    assert log_line(VECTOR[0], "prof-a-bench-0") == VECTOR_LINE
    expected = hashlib.sha256(VECTOR_LINE.encode("utf-8")).hexdigest()
    assert digest_logs(VECTOR, ["prof-a-bench-0"]) == expected
    changed = [dict(VECTOR[0], battles=[VECTOR[0]["battles"][0], dict(VECTOR[0]["battles"][1], log_hash="sha256:bc")])]
    assert digest_logs(changed, ["prof-a-bench-0"]) != expected
