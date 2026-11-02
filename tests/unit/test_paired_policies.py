"""018 T017: pure parts of specs/018-expectimax2-v4/scripts/paired_policies.py (no pool, no battle)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from platsim.stats import mcnemar_exact

SCRIPT = Path(__file__).resolve().parents[2] / "specs/018-expectimax2-v4/scripts/paired_policies.py"
spec = importlib.util.spec_from_file_location("paired_policies", SCRIPT)
PP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PP)


def test_safe_name_is_filesystem_safe_and_distinct_per_candidate():
    names = ["expectimax2-v2", "expectimax2-v4", "expectimax2-v4?kRoot=4&kPly2=1&beam=1&floor=0.02",
             "expectimax2-v4?kRoot=8&kPly2=1&beam=2&floor=0"]
    safe = [PP.safe_name(n) for n in names]
    assert len(set(safe)) == len(names)
    for s in safe:
        assert "/" not in s and "?" not in s and "&" not in s and "=" not in s and " " not in s


def test_cache_entry_is_reused_only_for_the_same_code_and_size():
    entry = {"sim_code_hash": "sha256:abc", "n": 3, "cleared": [True, False, True]}
    assert PP.cache_valid(entry, "sha256:abc", 3)
    assert not PP.cache_valid(entry, "sha256:def", 3)
    assert not PP.cache_valid(entry, "sha256:abc", 4)
    assert not PP.cache_valid({"sim_code_hash": "sha256:abc", "n": 3, "cleared": [True]}, "sha256:abc", 3)
    assert not PP.cache_valid({}, "sha256:abc", 3)


def test_summary_row_matches_the_mcnemar_oracle():
    a_cl = [True, True, False, True, False, True, True, False]
    b_cl = [True, False, False, True, True, True, False, False]
    base = {"master": "018-pairs|bench", "sim_code_hash": "sha256:abc", "gauntlets_per_s": 5.0}
    a = {**base, "policy": "expectimax2-v4", "cleared": a_cl}
    b = {**base, "policy": "expectimax2-v2", "cleared": b_cl, "gauntlets_per_s": 4.0}
    row = PP.summary_row("bench", a, b)
    cmp = mcnemar_exact(a_cl, b_cl)
    assert (row["a_only"], row["b_only"], row["p_value"], row["verdict"]) == (cmp.a_only, cmp.b_only, cmp.p_value, cmp.verdict)
    assert row["a_only"] == 2 and row["b_only"] == 1  # by hand: A-only at indices 1, 6; B-only at 4
    assert row["a_cleared"] == 5 and row["b_cleared"] == 4 and row["n"] == 8
    assert row["a_gauntlets_per_s"] == 5.0 and row["b_gauntlets_per_s"] == 4.0
    assert "bench" in PP.row_text(row) and "verdict" in PP.row_text(row)
