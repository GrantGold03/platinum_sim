"""T054: statistics against published and hand-computed values."""

import math

import pytest

from platsim.stats import (
    Z95,
    avg_final_level_ci,
    binom_cdf_half,
    mcnemar_exact,
    mcnemar_exact_p,
    mean_ci,
    runs_needed,
    wilson_ci,
    wilson_half_width,
)


# Newcombe RG (1998), "Two-sided confidence intervals for the single proportion: comparison of
# seven methods", Stat Med 17:857-872, Table I, method 3 (Wilson score, no continuity correction).
# The 0/20 row is also checked by hand below.
@pytest.mark.parametrize(
    ("k", "n", "lo", "hi"),
    [(81, 263, 0.2553, 0.3662), (15, 148, 0.0624, 0.1605), (0, 20, 0.0, 0.1611), (1, 29, 0.0061, 0.1718)],
)
def test_wilson_newcombe_table(k, n, lo, hi):
    got = wilson_ci(k, n)
    assert round(got[0], 4) == lo and round(got[1], 4) == hi


def test_wilson_zero_successes_by_hand():
    # k=0: centre = (z²/2n)/(1+z²/n), hw = (z/(1+z²/n))·(z/2n) = (z²/2n)/(1+z²/n), so
    # upper = (z²/n)/(1+z²/n). z²=3.841459, z²/20=0.192073, 0.192073/1.192073 = 0.161125.
    assert wilson_ci(0, 20)[1] == pytest.approx(0.161125, abs=1e-6)
    assert wilson_ci(0, 20)[0] == 0.0


def test_wilson_symmetry_and_edges():
    lo, hi = wilson_ci(30, 100)
    lo2, hi2 = wilson_ci(70, 100)
    assert lo == pytest.approx(1 - hi2) and hi == pytest.approx(1 - lo2)
    assert wilson_ci(0, 0) == (0.0, 1.0)
    with pytest.raises(ValueError):
        wilson_ci(5, 4)
    assert wilson_half_width(81, 263) == pytest.approx((0.36622 - 0.25529) / 2, abs=1e-4)


def test_runs_needed():
    # Normal approximation (R8 "about 1,800"): z²·p(1-p)/h² = 3.841459·0.1875/0.0004 = 1800.7.
    # Wilson at p=0.75: hw(n) = z/(1+z²/n)·sqrt(p(1-p)/n + z²/4n²).
    #   n=1799: sqrt(0.1875/1799 + 3.841459/12945604) = sqrt(1.042246e-4 + 2.967e-7)
    #           = 0.0102236; × 1.959964/1.0021353 = 1.955788  -> 0.0199950 <= 0.02
    #   n=1798: same steps give 0.0200006 > 0.02. So the answer is 1799.
    def hw(p, n):
        return Z95 / (1 + Z95**2 / n) * math.sqrt(p * (1 - p) / n + Z95**2 / (4 * n * n))

    assert hw(0.75, 1799) <= 0.02 < hw(0.75, 1798)
    assert runs_needed(0.75, 0.02) == 1799
    # Classic sample-size value at p=0.5, ±2 points: 1.96²·0.25/0.0004 = 2401 (normal approx);
    # Wilson needs slightly fewer.
    n = runs_needed(0.5, 0.02)
    assert 2390 <= n <= 2401 and hw(0.5, n) <= 0.02 < hw(0.5, n - 1)
    assert runs_needed(0.75, 0.015) > runs_needed(0.75, 0.02)


def test_binomial_half_exact():
    # Bin(10, 1/2): P(X<=1) = (C(10,0)+C(10,1))/2^10 = 11/1024.
    assert binom_cdf_half(1, 10) * 1024 == 11
    assert binom_cdf_half(10, 10) == 1


def test_mcnemar_exact_by_hand():
    # 1 vs 9 discordant: p = 2·11/1024 = 0.021484375.
    assert mcnemar_exact_p(1, 9) == 0.021484375
    # 0 vs 6: p = 2·(1/64) = 0.03125.   0 vs 5: p = 2/32 = 0.0625 (not significant at 0.05).
    assert mcnemar_exact_p(0, 6) == 0.03125
    assert mcnemar_exact_p(0, 5) == 0.0625
    assert mcnemar_exact_p(5, 5) == 1.0  # 2·P(X<=5 | n=10) = 2·638/1024 > 1 -> capped
    assert mcnemar_exact_p(0, 0) == 1.0


def test_paired_comparison_verdicts():
    # 100 shared seeds: 80 concordant, A-only 9, B-only 1 -> p = 0.0215 -> "A".
    a = [True] * 9 + [False] * 1 + [True] * 50 + [False] * 40
    b = [False] * 9 + [True] * 1 + [True] * 50 + [False] * 40
    r = mcnemar_exact(a, b)
    assert (r.a_only, r.b_only, r.n) == (9, 1, 100)
    assert r.p_value == 0.021484375 and r.verdict == "A"
    assert r.a_rate == 0.59 and r.b_rate == 0.51
    assert mcnemar_exact(b, a).verdict == "B"
    # 0 vs 5 discordant -> p=0.0625 -> indistinguishable, even though B's rate is higher.
    a2 = [False] * 5 + [True] * 95
    b2 = [True] * 100
    assert mcnemar_exact(a2, b2).verdict == "indistinguishable"
    with pytest.raises(ValueError):
        mcnemar_exact([True], [True, False])


def test_mean_ci_by_hand():
    # values 1..5: mean 3; s² = (4+1+0+1+4)/4 = 2.5, s = 1.581139; se = s/√5 = 0.707107;
    # hw = 1.959964·0.707107 = 1.385904.
    r = mean_ci([1, 2, 3, 4, 5])
    assert r.mean == 3 and r.sd == pytest.approx(1.581139, abs=1e-6)
    assert r.lo == pytest.approx(3 - 1.385904, abs=1e-6)
    assert r.hi == pytest.approx(3 + 1.385904, abs=1e-6)
    with pytest.raises(ValueError):
        mean_ci([1.0])


def test_avg_final_level_ci():
    # Run averages: (50·6)/6 = 50, (52·6)/6 = 52 -> mean 51; s = √2 = 1.414214; se = 1;
    # hw = 1.959964.
    r = avg_final_level_ci([[50] * 6, [52] * 6])
    assert r.mean == 51 and r.half_width == pytest.approx(1.959964, abs=1e-6)
