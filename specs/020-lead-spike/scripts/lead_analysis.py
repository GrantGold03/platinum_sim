"""Feature 020: lead spike analysis (research R1-R6). Pure functions plus a CLI over the recordings.

usage: uv run python specs/020-lead-spike/scripts/lead_analysis.py [--evidence-dir runs/020-evidence] [--teams b2main,b2branch,b2v2] [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from platsim.stats import PairedComparison, mcnemar_exact, wilson_ci

REPO = Path(__file__).resolve().parents[3]
TRAINERS = ("aaron", "bertha", "flint", "lucian", "cynthia")
SPREADS_N100 = (12, 8, 15)


def rotate(team: list, i: int) -> list:
    """Member i first, the others in their existing relative order (R1). i == 0 is the identity."""
    return [team[i]] + [m for j, m in enumerate(team) if j != i]


def load_recording(path: str | Path) -> dict:
    lines = Path(path).read_text().splitlines()
    header = json.loads(lines[0])
    runs = [json.loads(line) for line in lines[1:]]
    for i, r in enumerate(runs):
        if r["run"] != i:
            raise ValueError(f"{path}: run index {r['run']} at line {i + 2}")
    if header.get("runs") is not None and len(runs) != header["runs"]:
        raise ValueError(f"{path}: {len(runs)} runs, header says {header['runs']}")
    return {"header": header, "runs": runs, "path": str(path)}


def seeds(rec: dict) -> list[str]:
    return [r["seed"] for r in rec["runs"]]


def cleared(rec: dict) -> list[bool]:
    return [bool(r["cleared"]) for r in rec["runs"]]


def check_paired(a: dict, b: dict) -> None:
    if seeds(a) != seeds(b):
        raise ValueError(f"recordings are not paired: seed lists differ ({a.get('path')} vs {b.get('path')})")


def lead_row(rec: dict, start_levels: list[int], order: list[int]) -> dict:
    """Per-lead summary. `order[k]` is the original member index sitting at rotated position k."""
    runs = rec["runs"]
    n = len(runs)
    wins = sum(cleared(rec))
    per = {t: [0, 0] for t in TRAINERS}
    for r in runs:
        for b in r["battles"]:
            d = per.get(b["trainer"])
            if d is not None:
                d[0] += 1
                d[1] += bool(b["won"])
    per_trainer = {t: {"battles": v[0], "rate": (v[1] / v[0]) if v[0] else None} for t, v in per.items()}
    # expected final levels per member, back in original order, over cleared runs
    finals = [[None] * len(start_levels) for _ in range(0)]
    sums = [0.0] * len(start_levels)
    k = 0
    for r in runs:
        if r["cleared"]:
            k += 1
            for pos, lvl in enumerate(r["final_levels"]):
                sums[order[pos]] += lvl
    expected = [s / k for s in sums] if k else [None] * len(start_levels)
    lead_idx = order[0]
    lead_gain = (expected[lead_idx] - start_levels[lead_idx]) if k else None
    return {"lead_index": lead_idx, "lead_species": rec["header"].get("lead_species"), "n": n, "cleared": wins,
            "clear_rate": wins / n, "ci95": wilson_ci(wins, n), "per_trainer": per_trainer,
            "cynthia_rate": per_trainer["cynthia"]["rate"], "expected_final_levels": expected, "lead_gain": lead_gain,
            "start_levels": list(start_levels)}


def choose_best(recs: dict[int, dict], n: int) -> tuple[int, bool]:
    """Best lead by clear count over runs 0..n-1; ties to the lowest index (R2). Returns (index, tied)."""
    counts = {i: sum(cleared(r)[:n]) for i, r in recs.items()}
    best = max(counts.values())
    winners = sorted(i for i, c in counts.items() if c == best)
    return winners[0], len(winners) > 1


def _cmp(a: list[bool], b: list[bool]) -> PairedComparison:
    return mcnemar_exact(a, b, alpha=0.05)


def held_out(chosen: dict, first: dict, lo: int = 1000, hi: int = 2000) -> PairedComparison:
    check_paired(chosen, first)
    return _cmp(cleared(chosen)[lo:hi], cleared(first)[lo:hi])


def naive(chosen: dict, first: dict) -> PairedComparison:
    check_paired(chosen, first)
    return _cmp(cleared(chosen), cleared(first))


def control(first: dict) -> PairedComparison:
    return _cmp(cleared(first), cleared(first))


def screening(recs: dict[int, dict], sizes=(200, 400, 1000)) -> dict:
    choices = {s: choose_best(recs, s)[0] for s in sizes}
    ref = choices[sizes[-1]]
    return {"choices": choices, "agree": {s: choices[s] == ref for s in sizes[:-1]}}


def level_gains(rows: dict[int, dict], chosen: int) -> dict:
    """Chosen lead's own gain minus the mean of the other leads' own gains (R6)."""
    own = {i: r["lead_gain"] for i, r in rows.items() if r["lead_gain"] is not None}
    others = [g for i, g in own.items() if i != chosen]
    return {"chosen_gain": own.get(chosen), "others_mean_gain": statistics.mean(others) if others else None,
            "difference": (own[chosen] - statistics.mean(others)) if chosen in own and others else None}


def split_sample(recs: dict[int, dict], rows: dict[int, dict]) -> dict:
    chosen, tied = choose_best(recs, 1000)
    first = recs[0]
    if chosen == 0:
        ho = held_out(first, first)
        nv = naive(first, first)
    else:
        ho = held_out(recs[chosen], first)
        nv = naive(recs[chosen], first)
    ctl = control(first)
    def d(c: PairedComparison) -> dict:
        return {"n": c.n, "a_rate": c.a_rate, "b_rate": c.b_rate, "only_chosen": c.a_only, "only_first": c.b_only,
                "p": c.p_value, "verdict": c.verdict}
    return {"chosen_lead": chosen, "chosen_species": rows[chosen]["lead_species"], "tied": tied,
            "first_listed_already_best": chosen == 0,
            "held_out": d(ho), "naive_selection_biased": d(nv), "control_discordant": ctl.a_only + ctl.b_only,
            "supported_gain": (chosen != 0 and ho.verdict == "A"),
            "level_gains": level_gains(rows, chosen)}


def analyse_team(team: str, evidence_dir: Path) -> dict:
    files = sorted(evidence_dir.glob(f"{team}-lead*.jsonl"))
    recs: dict[int, dict] = {}
    for f in files:
        rec = load_recording(f)
        recs[int(rec["header"]["lead_index"])] = rec
    if 0 not in recs:
        raise SystemExit(f"{team}: lead 0 (first-listed) recording missing under {evidence_dir}")
    base = recs[0]["header"]
    start_levels = [lvl for _, lvl in base["builds"]]
    rows: dict[int, dict] = {}
    for i, rec in sorted(recs.items()):
        check_paired(rec, recs[0])
        rows[i] = lead_row(rec, start_levels, rec["header"]["order_indices"])
    best = max(rows, key=lambda i: rows[i]["clear_rate"])
    worst = min(rows, key=lambda i: rows[i]["clear_rate"])
    out = {"team": team, "builds": base["builds"], "leads_present": sorted(rows), "rows": rows,
           "best": best, "worst": worst, "spread_points": 100 * (rows[best]["clear_rate"] - rows[worst]["clear_rate"]),
           "spreads_n100": SPREADS_N100}
    if len(rows) == 6:
        out["split_sample"] = split_sample(recs, rows)
        out["screening"] = screening(recs)
    else:
        out["note"] = f"only {len(rows)} of 6 leads present: split-sample and screening skipped; team not judged"
    return out


def print_team(t: dict) -> None:
    print(f"== team {t['team']}  builds {t['builds']}")
    print("lead species       cleared  clear [ci95]            " + "  ".join(f"{x[:6]:>6}" for x in TRAINERS) + "   expected final levels (member order)   lead gain")
    for i, r in sorted(t["rows"].items()):
        pt = "  ".join(f"{(r['per_trainer'][x]['rate'] if r['per_trainer'][x]['rate'] is not None else 0):6.3f}" for x in TRAINERS)
        efl = "[" + ", ".join(f"{x:.2f}" if x is not None else "-" for x in r["expected_final_levels"]) + "]"
        print(f"{i:>4} {str(r['lead_species']):<12} {r['cleared']:>4}/{r['n']}  {r['clear_rate']:.4f} [{r['ci95'][0]:.4f}, {r['ci95'][1]:.4f}]  {pt}   {efl}   {r['lead_gain']:.2f}" if r["lead_gain"] is not None else f"{i:>4} {str(r['lead_species']):<12} {r['cleared']:>4}/{r['n']}  {r['clear_rate']:.4f}  {pt}   {efl}   -")
    print(f"spread: best lead {t['best']} ({t['rows'][t['best']]['lead_species']}) {t['rows'][t['best']]['clear_rate']:.4f}, worst lead {t['worst']} ({t['rows'][t['worst']]['lead_species']}) {t['rows'][t['worst']]['clear_rate']:.4f}: {t['spread_points']:.1f} points (vs {t['spreads_n100']} at n 100)")
    if "note" in t:
        print(t["note"]); return
    s = t["split_sample"]
    ho, nv = s["held_out"], s["naive_selection_biased"]
    print(f"split-sample: chosen on pairs 0..999 = lead {s['chosen_lead']} ({s['chosen_species']}){' [tie, lowest index]' if s['tied'] else ''}"
          + ("; first-listed already best (0 discordant; no gain)" if s["first_listed_already_best"] else ""))
    print(f"  held-out pairs 1000..1999: chosen {ho['a_rate']:.4f} vs first-listed {ho['b_rate']:.4f}; only-chosen {ho['only_chosen']} only-first {ho['only_first']}; p {ho['p']:.3g}; verdict {ho['verdict']}; supported gain: {s['supported_gain']}")
    print(f"  naive all 2,000 pairs [selection-biased]: chosen {nv['a_rate']:.4f} vs first {nv['b_rate']:.4f}; only-chosen {nv['only_chosen']} only-first {nv['only_first']}; p {nv['p']:.3g}; verdict {nv['verdict']}")
    print(f"  control (first-listed vs itself): discordant {s['control_discordant']}")
    lg = s["level_gains"]
    print(f"  level gains: chosen lead {lg['chosen_gain']:.2f} vs others' mean {lg['others_mean_gain']:.2f} (difference {lg['difference']:+.2f})")
    sc = t["screening"]
    print(f"screening: chosen at 200 = {sc['choices'][200]}, at 400 = {sc['choices'][400]}, at 1000 = {sc['choices'][1000]}; agree 200 {sc['agree'][200]}, 400 {sc['agree'][400]}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-dir", default=str(REPO / "runs" / "020-evidence"))
    ap.add_argument("--teams", default="b2main,b2branch,b2v2")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    ed = Path(a.evidence_dir)
    teams = [analyse_team(t, ed) for t in a.teams.split(",")]
    for t in teams:
        print_team(t); print()
    judged = [t for t in teams if "split_sample" in t]
    supported = {t["team"]: t["split_sample"]["supported_gain"] for t in judged}
    go = any(supported.values())
    summary = {"supported_gain": supported, "not_judged": [t["team"] for t in teams if "split_sample" not in t],
               "confirmation_stage_check": "go" if go else "no-go (reporting follow-on only)"}
    print(json.dumps(summary))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"summary": summary, "teams": teams}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
