"""platsim command line (contracts/cli.md). Each subcommand registers itself in `_SUBCOMMANDS`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from platsim.pins import PinError


def _add_extract(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("extract", help="extract game data from the decomp into data/generated/")
    p.add_argument("--check", action="store_true",
                   help="regenerate in memory and exit 1 if data/generated differs")
    p.add_argument("--out", type=Path, default=None,
                   help="output directory (default: data/generated)")

    def run(args: argparse.Namespace) -> int:
        from platsim import extract

        return extract.main(check_only=args.check, out_dir=args.out or extract.DEFAULT_OUT)

    p.set_defaults(func=run)


def _add_divergences(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("divergences",
                       help="regenerate the Showdown-vs-decomp divergence ledger data/divergences.json")
    p.add_argument("--check", action="store_true",
                   help="regenerate in memory and exit 1 if the ledger file differs")
    p.add_argument("--out", type=Path, default=None, help="ledger path (default: data/divergences.json)")
    p.add_argument("--dump", type=Path, default=None,
                   help="use this sim/dump_dex.mjs output instead of running node")
    p.add_argument("--ledger", type=Path, default=None,
                   help="only validate an existing ledger file (exit 1 if an entry lacks a resolution)")

    def run(args: argparse.Namespace) -> int:
        from platsim.divergence import compare

        return compare.main(args.out or compare.LEDGER_PATH, dump_path=args.dump,
                            ledger_in=args.ledger, check_only=args.check)

    p.set_defaults(func=run)


def _add_validate(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("validate", help="legality check of a team (FR-003..FR-008c); exit 2 if illegal")
    p.add_argument("team", type=Path, help="team file: JSON (TeamCandidate / {'team': [...]}) or Showdown export text")
    p.add_argument("--json", action="store_true", help="print the violations as JSON")

    def run(args: argparse.Namespace) -> int:
        import json

        from platsim.legality.validator import format_violations, validate

        if not args.team.is_file():
            print(f"platsim validate: no such file: {args.team}", file=sys.stderr)
            return 1
        try:
            violations = validate(str(args.team))
        except (ValueError, KeyError) as e:
            print(f"platsim validate: cannot read {args.team}: {e}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps({"team": str(args.team), "legal": not violations,
                              "violations": [v.to_dict() for v in violations]}, indent=2))
        elif violations:
            print(format_violations(violations))
            print(f"{args.team}: ILLEGAL - {len(violations)} violation(s)")
        else:
            print(f"{args.team}: legal (no violations)")
        return 2 if violations else 0

    p.set_defaults(func=run)


def _add_evaluate(sub: argparse._SubParsersAction) -> None:
    from platsim.budget import DEFAULT_PRESET, PRESETS

    p = sub.add_parser("evaluate", help="battle-test a fixed team (User Story 2); exit 2 if the team is illegal")
    p.add_argument("team", type=Path, help="team file: JSON (TeamCandidate / {'team': [...]}) or Showdown export text")
    p.add_argument("--runs", type=int, default=2000,
                   help="minimum full gauntlets (default 2000); more are added until the budget CI target is met")
    p.add_argument("--seed", default="0", help="master seed (any string; default '0')")
    p.add_argument("--workers", type=int, default=None, help="worker processes (default: CPU count)")
    p.add_argument("--player-policy", default="expectimax2-v1", help="player policy (default expectimax2-v1)")
    p.add_argument("--budget", choices=sorted(PRESETS), default=DEFAULT_PRESET,
                   help="budget preset (research R8): CI target for the gauntlet and Cynthia (default standard)")
    p.add_argument("--min-clear", type=float, default=0.75, help="qualification threshold (default 0.75, FR-015)")
    p.add_argument("--max-runs", type=int, default=20000, help="cap on full gauntlets when extending to the CI target")
    p.add_argument("--out", type=Path, default=None, help="output directory (default runs/evaluate-<time>-<hash>/)")

    def run(args: argparse.Namespace) -> int:
        from platsim.evaluate import InvalidTeamInput, UsageError, evaluate, summary_text
        from platsim.legality.validator import format_violations

        if not args.team.is_file():
            print(f"platsim evaluate: no such file: {args.team}", file=sys.stderr)
            return 2
        try:
            report, paths = evaluate(args.team, runs=args.runs, seed=args.seed, workers=args.workers,
                                     player_policy=args.player_policy, budget=args.budget, threshold=args.min_clear,
                                     max_runs=args.max_runs, out_dir=args.out)
        except InvalidTeamInput as e:
            if e.violations:
                print(format_violations(e.violations), file=sys.stderr)
            print(f"platsim evaluate: {e}", file=sys.stderr)
            return 2
        except UsageError as e:
            print(f"platsim evaluate: {e}", file=sys.stderr)
            return 2
        print(summary_text(report))
        for kind, path in paths.items():
            print(f"{kind}: {path}")
        return 0

    p.set_defaults(func=run)


def _add_optimize(sub: argparse._SubParsersAction) -> None:
    from platsim.budget import DEFAULT_PRESET, PRESETS

    p = sub.add_parser("optimize", help="optimize six species for the lowest average level after Cynthia (User Story 1)")
    p.add_argument("species", nargs="+", help="six species (display names or keys, e.g. Garchomp / garchomp)")
    p.add_argument("--min-clear", type=float, default=0.75, help="required full-gauntlet clear rate (default 0.75, FR-015)")
    p.add_argument("--seed", default="default", help="master seed (any string; default 'default')")
    p.add_argument("--workers", type=int, default=None, help="worker processes (default: CPU count; never changes results)")
    p.add_argument("--budget", choices=sorted(PRESETS), default=DEFAULT_PRESET,
                   help="simulation budget preset (research R8; 'quick' is for testing and never qualifies)")
    p.add_argument("--out", type=Path, default=None,
                   help="output directory (default runs/optimize-<hash of the request>/; re-running resumes from its state.json)")

    def run(args: argparse.Namespace) -> int:
        from platsim.optimizer.api import InvalidRequest, OptimizeRequest, run_optimization

        if len(args.species) != 6:
            print(f"platsim optimize: exactly 6 species are required, got {len(args.species)}", file=sys.stderr)
            return 2
        req = OptimizeRequest(species=tuple(args.species), min_clear=args.min_clear, seed=args.seed,
                              budget=args.budget, workers=args.workers, out_dir=args.out)
        try:
            res = run_optimization(req)
        except InvalidRequest as e:
            for name, why in e.reasons.items():
                print(f"  {name}: {why}", file=sys.stderr)
            print(f"platsim optimize: {e}", file=sys.stderr)
            return 2
        from platsim.report.json_report import EvaluationReport

        rep = EvaluationReport.from_json((res.out_dir / "result.json").read_text(encoding="utf-8"))
        if rep.no_qualifying is not None:
            nq = rep.no_qualifying
            print(f"{nq.message}: best clear rate {nq.best_clear_rate:.4f} [{nq.best_clear_ci95[0]:.4f}, "
                  f"{nq.best_clear_ci95[1]:.4f}] over {nq.best_n_runs} runs at start levels {nq.best_levels}")
        else:
            from platsim.evaluate import summary_text

            print("start levels " + " / ".join(f"{b.species} {b.start_level}" for b in rep.team.builds))
            print(summary_text(rep))
        for name in ("result.json", "result.xlsx", "result.csv", "team.txt", "state.json"):
            print(f"{name}: {res.out_dir / name}")
        return 0

    p.set_defaults(func=run)


# Later tasks append (e.g. validate T031, divergences T053, optimize, serve).
_SUBCOMMANDS: list[Callable[[argparse._SubParsersAction], None]] = [_add_extract, _add_divergences, _add_validate,
                                                                 _add_evaluate, _add_optimize]


def _add_serve(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("serve", help="local web page and HTTP API (contracts/http-api.md); binds to 127.0.0.1 only")
    p.add_argument("--port", type=int, default=8000, help="port on 127.0.0.1 (default 8000)")
    p.add_argument("--runs-dir", type=Path, default=None, help="job directory (default: runs/)")

    def run(args: argparse.Namespace) -> int:
        from platsim.web.app import DEFAULT_RUNS_DIR, serve

        return serve(port=args.port, runs_dir=args.runs_dir or DEFAULT_RUNS_DIR)

    p.set_defaults(func=run)


_SUBCOMMANDS.append(_add_serve)


def _add_explain(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("explain", help="trace a legality fact or opponent detail to the decomp (User Story 3)")
    p.add_argument("subject", help="tmNN, hmNN, species:<key>, item:<key>, move:<key>, trainer:<key>, divergence:<id>")
    p.add_argument("--json", action="store_true", help="print the explanation as JSON")
    p.add_argument("--level", type=int, default=100, help="move:<key> only: level the learners are checked at (default 100)")

    def run(args: argparse.Namespace) -> int:
        from platsim import explain

        return explain.main(args.subject, as_json=args.json, level=args.level)

    p.set_defaults(func=run)


_SUBCOMMANDS.append(_add_explain)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="platsim")
    sub = parser.add_subparsers(dest="command", required=True)
    for add in _SUBCOMMANDS:
        add(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except PinError as e:
        print(f"platsim: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
