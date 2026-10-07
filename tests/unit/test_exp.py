"""T016 exp table tests. Values copied from pokeplatinum/res/pokemon/.shared/exp_tables.csv."""

import pytest

from platsim.decomp.exp import exp_at, level_from_exp, load_exp_tables

# res/pokemon/.shared/exp_tables.csv:102 (level 100 row):
# 100,1000000,600000,1640000,1059860,800000,1250000,1000000,1000000
LEVEL_100 = {
    "EXP_RATE_MEDIUM_FAST": 1000000,
    "EXP_RATE_ERRATIC": 600000,
    "EXP_RATE_FLUCTUATING": 1640000,
    "EXP_RATE_MEDIUM_SLOW": 1059860,
    "EXP_RATE_FAST": 800000,
    "EXP_RATE_SLOW": 1250000,
    "EXP_RATE_6_UNUSED": 1000000,
    "EXP_RATE_7_UNUSED": 1000000,
}


def test_level_100_matches_csv():
    for rate, exp in LEVEL_100.items():
        assert exp_at(rate, 100) == exp
        assert level_from_exp(rate, exp) == 100
        assert level_from_exp(rate, exp + 12345) == 100  # loop ends at 101 -> 100


def test_level_2_row():
    # res/pokemon/.shared/exp_tables.csv:4  2,8,15,4,9,6,10,8,8
    assert exp_at("EXP_RATE_MEDIUM_FAST", 2) == 8
    assert exp_at("EXP_RATE_SLOW", 2) == 10


@pytest.mark.parametrize("rate", list(LEVEL_100))
def test_boundaries(rate):
    # SpeciesData_GetLevelAt (src/pokemon.c:2378-2391): first i with table[i] > exp, return i-1.
    for n in range(2, 101):
        t = exp_at(rate, n)
        assert level_from_exp(rate, t - 1) == n - 1
        assert level_from_exp(rate, t) == n


def test_zero_exp_is_level_1():
    # csv rows 0 and 1 are both 0, so exp 0 -> level 1 (loop starts at i = 1).
    assert level_from_exp("EXP_RATE_SLOW", 0) == 1


def test_src():
    assert load_exp_tables().src[1] == "src/pokemon.c:2378"
