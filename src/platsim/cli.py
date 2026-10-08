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


# Later tasks append (e.g. validate T031, divergences T053, optimize, serve).
_SUBCOMMANDS: list[Callable[[argparse._SubParsersAction], None]] = [_add_extract, _add_divergences, _add_validate,
                                                                 _add_evaluate]


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
