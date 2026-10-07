"""Small helpers shared by the decomp readers: source-line lookup for `src` refs."""

from functools import cache
from pathlib import Path

from platsim.decomp.constants import Ref, rel


@cache
def _lines(path: Path) -> tuple[str, ...]:
    return tuple(path.read_text().splitlines())


def line_of(path: Path, needle: str, start: int = 1) -> int:
    """1-based line of the first line at or after `start` containing `needle`."""
    for i, line in enumerate(_lines(path)[start - 1 :], start=start):
        if needle in line:
            return i
    raise ValueError(f"{rel(path)}: {needle!r} not found")


def ref(path: Path, needle: str | None = None, start: int = 1) -> str:
    """`path:line` string; line 1 when no needle is given."""
    return str(Ref(rel(path), line_of(path, needle, start) if needle else 1))


def lines(path: Path) -> tuple[str, ...]:
    return _lines(path)
