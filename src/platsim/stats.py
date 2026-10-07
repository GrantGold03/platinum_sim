"""Statistics for evaluation reports and comparisons (T054, research R8, Constitution IV).

Standard library only (no scipy). All intervals are two-sided 95% unless `z` is given.

- `wilson_ci(k, n)`: Wilson score interval for a binomial proportion (no continuity
  correction; Newcombe 1998 "method 3"). Used for clear rate, per-battle and Champion rates.
- `wilson_half_width(k, n)`: (hi - lo) / 2, the quantity compared with the budget preset target
  (±2 points `standard`, ±1.5 `thorough`).
- `runs_needed(p, half_width)`: smallest n whose Wilson half-width at an observed rate p is
  <= half_width. (R8 quotes "about 1,800" for p=0.75, ±0.02; this returns 1799.)
- `mcnemar_exact(a, b)`: paired comparison of two candidates on the SAME seeds (FR-019). Only
  discordant pairs carry information: n10 = A won / B lost, n01 = A lost / B won. Under H0
  n10 ~ Binomial(n10 + n01, 1/2); the two-sided exact p-value is
  min(1, 2 * P(X <= min(n10, n01))), computed with exact integer arithmetic.
  `verdict` is "A" / "B" only when p < alpha, else "indistinguishable" (Constitution IV).
- `mean_ci(values)`: mean with a normal-approximation CI, mean +/- z * s / sqrt(n), s the sample
  standard deviation (n-1). Used for the expected final average level. The normal
  approximation is adequate at the run counts used (>= 100 per evaluation; the t quantile at
  99 df is 1.984 vs z 1.960, i.e. the interval is ~1% too narrow at n=100 and less above).
  Callers should not use it for n < 30.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

# Standard-normal 0.975 quantile, Phi^-1(0.975) to 15 significant digits.
Z95 = 1.959963984540054


def wilson_ci(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"need 0 <= k <= n, got k={k}, n={n}")
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    hw = (z / denom) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return (max(0.0, centre - hw), min(1.0, centre + hw))


def wilson_half_width(k: int, n: int, z: float = Z95) -> float:
    lo, hi = wilson_ci(k, n, z)
    return (hi - lo) / 2


def _wilson_hw_at(p: float, n: int, z: float) -> float:
    z2 = z * z
    return (z / (1 + z2 / n)) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))


def runs_needed(p: float, half_width: float, z: float = Z95) -> int:
    """Smallest n with Wilson half-width <= half_width when the observed rate is p.

    The half-width is decreasing in n, so a doubling search then bisection is exact.
    """
    if not 0 <= p <= 1:
        raise ValueError(f"p must be in [0, 1], got {p}")
    if not 0 < half_width < 0.5:
        raise ValueError(f"half_width must be in (0, 0.5), got {half_width}")
    hi = 1
    while _wilson_hw_at(p, hi, z) > half_width:
        hi *= 2
    lo = hi // 2  # hw(lo) > target (or lo == 0)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _wilson_hw_at(p, mid, z) > half_width:
            lo = mid
        else:
            hi = mid
    return hi


def binom_cdf_half(k: int, n: int) -> Fraction:
    """P(X <= k) for X ~ Binomial(n, 1/2), exact."""
    if k < 0:
        return Fraction(0)
    if k >= n:
        return Fraction(1)
    return Fraction(sum(math.comb(n, i) for i in range(k + 1)), 2**n)


@dataclass(frozen=True)
class PairedComparison:
    n: int  # shared seeds
    a_rate: float
    b_rate: float
    a_only: int  # n10: A won, B lost
    b_only: int  # n01: A lost, B won
    p_value: float
    alpha: float
    verdict: str  # "A" | "B" | "indistinguishable"

    @property
    def diff(self) -> float:
        return self.a_rate - self.b_rate


def mcnemar_exact_p(a_only: int, b_only: int) -> float:
    m = a_only + b_only
    if m == 0:
        return 1.0
    return float(min(Fraction(1), 2 * binom_cdf_half(min(a_only, b_only), m)))


def mcnemar_exact(
    a: Sequence[bool], b: Sequence[bool], alpha: float = 0.05
) -> PairedComparison:
    """Compare candidates A and B whose outcomes a[i], b[i] come from the same seed i."""
    if len(a) != len(b):
        raise ValueError(f"paired outcomes must have equal length, got {len(a)} and {len(b)}")
    if not a:
        raise ValueError("no paired outcomes")
    a_only = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    b_only = sum(1 for x, y in zip(a, b, strict=True) if y and not x)
    p = mcnemar_exact_p(a_only, b_only)
    if p < alpha and a_only != b_only:
        verdict = "A" if a_only > b_only else "B"
    else:
        verdict = "indistinguishable"
    n = len(a)
    return PairedComparison(
        n=n,
        a_rate=sum(map(bool, a)) / n,
        b_rate=sum(map(bool, b)) / n,
        a_only=a_only,
        b_only=b_only,
        p_value=p,
        alpha=alpha,
        verdict=verdict,
    )


@dataclass(frozen=True)
class MeanCI:
    n: int
    mean: float
    sd: float
    lo: float
    hi: float

    @property
    def half_width(self) -> float:
        return (self.hi - self.lo) / 2


def mean_ci(values: Sequence[float], z: float = Z95) -> MeanCI:
    n = len(values)
    if n < 2:
        raise ValueError(f"need at least 2 values for a CI, got {n}")
    m = math.fsum(values) / n
    sd = math.sqrt(math.fsum((v - m) ** 2 for v in values) / (n - 1))
    hw = z * sd / math.sqrt(n)
    return MeanCI(n=n, mean=m, sd=sd, lo=m - hw, hi=m + hw)


def avg_final_level_ci(final_levels: Sequence[Sequence[int]], z: float = Z95) -> MeanCI:
    """Mean and CI of the team's average final level across runs (GauntletRun.final_levels)."""
    return mean_ci([math.fsum(row) / len(row) for row in final_levels], z)
