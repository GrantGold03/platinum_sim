"""platsim command line. Subcommands are added by later tasks (see tasks.md)."""

import sys


def main(argv: list[str] | None = None) -> int:
    print("platsim: no subcommands implemented yet", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
