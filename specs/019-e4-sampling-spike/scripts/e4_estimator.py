"""Feature 019, US1: composite Elite Four estimator checked against stored evaluations.

Composite estimate = (Elite Four pass rate) x (Cynthia conditional win rate), where the pass rate is Cynthia's full-run
battle count over the run count. Interval (research R1): product of per-factor Wilson bounds at 97.5% each, so the
joint coverage is at least 95% (Bonferroni). A delta-method interval is reported for information only. Verdicts
(research R2): the threshold verdict (above / borderline / below, from the interval against the threshold) is the
pass criterion; the full verdict adds the preset's half-width target and the final-level gap rule, exactly as
`platsim.evaluate` applies them.

usage: uv run python specs/019-e4-sampling-spike/scripts/e4_estimator.py [--dirs ...] [--threshold 0.75] [--out FILE] [--control]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CHAMPION, EVIDENCE, REPO, SPEC_DIRS, StoredEvaluation, dedup, load_stored  # noqa: E402

from platsim.budget import get_preset  # noqa: E402
from platsim.stats import Z95, wilson_ci  # noqa: E402

Z975 = 2.241402727604947  # two-sided 97.5% (each factor), so the product interval covers >= 95% jointly
MAX_LEVEL_GAP = 10


def wilson_bounds(k: int, n: int, level: float = 0.975) -> tuple[float, float]:
    """Wilson interval at a per-factor confidence level (0.95 -> z 1.96, 0.975 -> z 2.2414)."""
    z = {0.95: Z95, 0.975: Z975}[level]
    return wilson_ci(k, n, z)


def product_interval(e4: tuple[float, float], cyn: tuple[float, float]) -> tuple[float, float]:
    """Bonferroni product: lower = L_e4 * L_cyn, upper = U_e4 * U_cyn (research R1)."""
    return (e4[0] * cyn[0], e4[1] * cyn[1])


def delta_interval(p1: float, n1: int, p2: float, n2: int, z: float = Z95) -> tuple[float, float]:
    """Log-scale delta method for a product of two independent proportions (informational)."""
    if p1 <= 0 or p2 <= 0 or n1 <= 0 or n2 <= 0:
        return (0.0, 0.0)
    var = (1 - p1) / (n1 * p1) + (1 - p2) / (n2 * p2)
    est = p1 * p2
    s = math.sqrt(var)
    return (est * math.exp(-z * s), min(1.0, est * math.exp(z * s)))


def threshold_verdict(interval: tuple[float, float], threshold: float) -> str:
    lo, hi = interval
    if lo < threshold <= hi:
        return "borderline"
    return "above" if lo >= threshold else "below"


def verdict(estimate: float, interval: tuple[float, float], preset_name: str, threshold: float,
            gap: float | None) -> tuple[str, str]:
    """(threshold_verdict, full_verdict) with the project's rule: borderline when lower < threshold <= upper;
    qualified when not borderline, the preset qualifies, estimate >= threshold, half-width <= target, gap <= 10."""
    preset = get_preset(preset_name)
    tv = threshold_verdict(interval, threshold)
    hw = (interval[1] - interval[0]) / 2
    target = preset.ci_half_width
    qualified = (tv != "borderline" and preset.qualifying and estimate >= threshold and target is not None
                 and hw <= target and gap is not None and gap <= MAX_LEVEL_GAP)
    full = "qualified" if qualified else ("borderline" if tv == "borderline" else "not_qualified")
    return tv, full


def runs_needed_for_half_width(hw_now: float, n_now: int, target: float | None) -> int | None:
    """Run count at which the composite half-width would meet the target, by the 1/sqrt(n) scaling of a Wilson
    half-width (an approximation stated in the log; exact for the single-proportion case at these rates)."""
    if target is None or hw_now <= target:
        return n_now if target is not None else None
    return math.ceil(n_now * (hw_now / target) ** 2)


def runs_to_clear_threshold(estimate: float, lower: float, n_now: int, threshold: float) -> int | None:
    """Run count at which the composite lower bound would reach the threshold, by the same 1/sqrt(n) scaling of
    the lower margin (estimate - lower); None when the estimate itself is not above the threshold."""
    if estimate <= threshold:
        return None
    margin_now, margin_needed = estimate - lower, estimate - threshold
    if margin_now <= margin_needed:
        return n_now
    return math.ceil(n_now * (margin_now / margin_needed) ** 2)


def disagreement_kind(stored_threshold: str, stored_full: str, comp_threshold: str, comp_full: str) -> str:
    if stored_full == comp_full and stored_threshold == comp_threshold:
        return "agree"
    if stored_threshold != comp_threshold:
        return "threshold"
    return "half-width only"


@dataclass
class CompositeEstimate:
    dir: str
    kind: str  # topup | fullrun
    n_runs: int
    e4_pass: float
    e4_bounds: tuple[float, float]
    cyn_rate: float
    cyn_battles: int
    cyn_bounds: tuple[float, float]
    estimate: float
    interval_bonferroni: tuple[float, float]
    interval_delta: tuple[float, float]
    half_width: float
    stored_clear_rate: float
    stored_half_width: float
    half_width_ratio: float
    contains_stored: bool
    stored_threshold_verdict: str
    stored_full_verdict: str
    threshold_verdict: str
    full_verdict: str
    agreement: bool  # pass criterion: threshold verdicts agree (FR-004)
    disagreement_kind: str
    runs_needed: int | None
    not_estimable: str | None = None
    duplicate_of: str | None = None


def stored_verdicts(s: StoredEvaluation, threshold: float) -> tuple[str, str]:
    tv = threshold_verdict(s.clear_ci95, threshold)
    full = "qualified" if s.qualified else ("borderline" if s.borderline else "not_qualified")
    return tv, full


def composite(s: StoredEvaluation, kind: str, threshold: float | None = None) -> CompositeEstimate:
    thr = s.threshold if threshold is None else threshold
    n = s.n_runs
    cb_full = s.cynthia_battles
    if kind == "topup":
        cb = s.champion_battles
        rate = s.champion_rate
        not_est = None
        if s.champion_status == "no_reach" or not cb or rate is None:
            not_est = f"not estimable: champion_status={s.champion_status!r}, champion_battles={cb}"
    elif kind == "fullrun":
        cb = cb_full
        rate = s.cynthia_full_rate
        not_est = None if cb else "not estimable: no full run reached Cynthia"
    else:
        raise ValueError(kind)
    stv, sfull = stored_verdicts(s, thr)
    s_hw = (s.clear_ci95[1] - s.clear_ci95[0]) / 2
    if not_est:
        return CompositeEstimate(s.dir, kind, n, cb_full / n if n else 0.0, (0, 0), 0.0, 0, (0, 0), 0.0, (0, 0), (0, 0),
                                 0.0, s.clear_rate, s_hw, 0.0, False, stv, sfull, "n/a", "n/a", False, "n/a", None,
                                 not_estimable=not_est, duplicate_of=s.duplicate_of)
    cyn_wins = round(rate * cb)
    e4_b = wilson_bounds(cb_full, n, 0.975)
    cyn_b = wilson_bounds(cyn_wins, cb, 0.975)
    e4_pass = cb_full / n
    est = e4_pass * (cyn_wins / cb)
    iv = product_interval(e4_b, cyn_b)
    dv = delta_interval(e4_pass, n, cyn_wins / cb, cb)
    hw = (iv[1] - iv[0]) / 2
    tv, full = verdict(est, iv, s.budget_preset, thr, s.final_level_gap_max)
    kind_d = disagreement_kind(stv, sfull, tv, full)
    preset = get_preset(s.budget_preset)
    if kind_d == "half-width only":
        rn = runs_needed_for_half_width(hw, n, preset.ci_half_width)
    elif kind_d == "threshold" and tv == "borderline" and est > thr:
        rn = runs_to_clear_threshold(est, iv[0], n, thr)
    else:
        rn = None
    return CompositeEstimate(
        dir=s.dir, kind=kind, n_runs=n, e4_pass=e4_pass, e4_bounds=e4_b, cyn_rate=cyn_wins / cb, cyn_battles=cb,
        cyn_bounds=cyn_b, estimate=est, interval_bonferroni=iv, interval_delta=dv, half_width=hw,
        stored_clear_rate=s.clear_rate, stored_half_width=s_hw, half_width_ratio=(hw / s_hw if s_hw else float("inf")),
        contains_stored=iv[0] <= s.clear_rate <= iv[1], stored_threshold_verdict=stv, stored_full_verdict=sfull,
        threshold_verdict=tv, full_verdict=full, agreement=(tv == stv), disagreement_kind=kind_d, runs_needed=rn,
        duplicate_of=s.duplicate_of)


def control_case() -> StoredEvaluation:
    """Positive control: Elite Four pass 0.70 (Cynthia reached 1,400 of 2,000) with Cynthia at 0.95; a Cynthia-only
    rule would qualify, the composite must say below."""
    return StoredEvaluation(dir="<control>", n_runs=2000, clear_rate=0.665, clear_ci95=wilson_ci(1330, 2000),
                            per_battle={"aaron": {"battles": 2000, "rate": 1.0}, "bertha": {"battles": 2000, "rate": 1.0},
                                        "flint": {"battles": 2000, "rate": 1.0}, "lucian": {"battles": 2000, "rate": 0.70},
                                        CHAMPION: {"battles": 1400, "rate": 0.95}},
                            champion_rate=0.95, champion_battles=2001, champion_ci95=wilson_ci(1901, 2001),
                            budget_preset="standard", threshold=0.75, qualified=False, borderline=False,
                            final_level_gap_max=2.0, champion_status="met")


def table(rows: list[CompositeEstimate]) -> str:
    out = ["dir | kind | n | stored clear [ci] | composite [bonferroni] | [delta] | hw ratio | contains | stored tv/full | composite tv/full | kind | runs_needed | note"]
    for c in rows:
        if c.not_estimable:
            out.append(f"{c.dir} | {c.kind} | {c.n_runs} | {c.stored_clear_rate:.4f} | - | - | - | - | {c.stored_threshold_verdict}/{c.stored_full_verdict} | - | - | - | {c.not_estimable}")
            continue
        note = f"dup of {c.duplicate_of}" if c.duplicate_of else ""
        out.append(f"{c.dir} | {c.kind} | {c.n_runs} | {c.stored_clear_rate:.4f} [{c.stored_clear_rate - c.stored_half_width:.4f}, {c.stored_clear_rate + c.stored_half_width:.4f}] | "
                   f"{c.estimate:.4f} [{c.interval_bonferroni[0]:.4f}, {c.interval_bonferroni[1]:.4f}] | [{c.interval_delta[0]:.4f}, {c.interval_delta[1]:.4f}] | "
                   f"{c.half_width_ratio:.2f} | {c.contains_stored} | {c.stored_threshold_verdict}/{c.stored_full_verdict} | {c.threshold_verdict}/{c.full_verdict} | "
                   f"{c.disagreement_kind} | {c.runs_needed if c.runs_needed is not None else '-'} | {note}")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="*", default=SPEC_DIRS)
    ap.add_argument("--threshold", type=float, default=None, help="default: each result's own threshold")
    ap.add_argument("--out", default=str(EVIDENCE / "estimator.json"))
    ap.add_argument("--control", action="store_true", help="print the positive control only")
    a = ap.parse_args(argv)
    if a.control:
        c = composite(control_case(), "topup")
        print(table([c]))
        ok = c.threshold_verdict == "below"
        print(f"control: composite threshold verdict {c.threshold_verdict!r} (Cynthia-only would be 'above'): {'ok' if ok else 'FAILED'}")
        return 0 if ok else 1
    stored = dedup([load_stored(d) for d in a.dirs])
    rows: list[CompositeEstimate] = []
    for s in stored:
        rows.append(composite(s, "fullrun", a.threshold))
        rows.append(composite(s, "topup", a.threshold))
    print(table(rows))
    # pass criterion: topup rows (distinct only), contains_stored and threshold agreement
    judged = [c for c in rows if c.kind == "topup" and not c.duplicate_of and not c.not_estimable]
    ident = [c for c in rows if c.kind == "fullrun" and not c.not_estimable]
    ident_ok = all(abs(c.estimate - c.stored_clear_rate) < 1e-9 for c in ident)
    passed = all(c.contains_stored and c.agreement for c in judged) and ident_ok
    fails = [c for c in judged if not (c.contains_stored and c.agreement)]
    hw_only = [c for c in judged if c.disagreement_kind == "half-width only"]
    summary = {"judged": len(judged), "pass": passed, "fullrun_identity_ok": ident_ok,
               "failures": [c.dir for c in fails], "half_width_only": [(c.dir, c.runs_needed) for c in hw_only],
               "threshold_runs_to_clear": [(c.dir, c.runs_needed) for c in fails if c.disagreement_kind == "threshold"],
               "max_half_width_ratio": max((c.half_width_ratio for c in judged), default=None)}
    print(json.dumps(summary))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"summary": summary, "rows": [asdict(c) for c in rows]}, indent=1))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
