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


# Later tasks append (e.g. validate T031, divergences T053, optimize, serve).
_SUBCOMMANDS: list[Callable[[argparse._SubParsersAction], None]] = [_add_extract]


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
