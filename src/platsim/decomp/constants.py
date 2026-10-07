"""Readers for pokeplatinum/generated/*.txt constant lists (T011).

Each .txt is turned into a C header by metang (pokeplatinum/generated/meson.build). Enum files use
C-enum semantics: every name is the previous value + 1, and `NAME = X` sets NAME to X, where X is
an integer literal or an earlier name. Counting then continues from that value. Mask files
(meson.build `'type': 'mask'`) are bitmasks with different semantics; `load_enum` refuses them.
`load_names` returns their names in file order.
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from platsim.pins import DECOMP_ROOT

GENERATED = DECOMP_ROOT / "generated"
_MASK_RE = re.compile(r"'(\w+)':\s*\{\s*'type':\s*'mask'")
_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*(\S+))?\s*$")


@dataclass(frozen=True)
class Ref:
    """A source reference into the decomp: repo-relative path and 1-based line."""

    path: str
    line: int

    def __str__(self) -> str:
        return f"{self.path}:{self.line}"


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(DECOMP_ROOT.resolve()))


@cache
def mask_names() -> frozenset[str]:
    text = (GENERATED / "meson.build").read_text()
    return frozenset(_MASK_RE.findall(text))


@dataclass(frozen=True)
class Enum:
    name: str
    values: dict[str, int]
    refs: dict[str, Ref]

    def __getitem__(self, key: str) -> int:
        return self.values[key]

    def name_of(self, value: int, prefix: str = "") -> str:
        """First name with this value (and the given prefix), in file order."""
        for k, v in self.values.items():
            if v == value and k.startswith(prefix):
                return k
        raise KeyError(f"{self.name}: no name with value {value} and prefix {prefix!r}")


def _parse_int(token: str) -> int | None:
    try:
        return int(token, 0)
    except ValueError:
        return None


@cache
def load_enum(name: str) -> Enum:
    if name in mask_names():
        raise ValueError(f"{name} is a mask in generated/meson.build; use load_names()")
    path = GENERATED / f"{name}.txt"
    values: dict[str, int] = {}
    refs: dict[str, Ref] = {}
    nxt = 0
    for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.split("//")[0].strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            raise ValueError(f"{rel(path)}:{lineno}: cannot parse {raw!r}")
        key, rhs = m.groups()
        if rhs is None:
            value = nxt
        else:
            literal = _parse_int(rhs)
            if literal is not None:
                value = literal
            elif rhs in values:
                value = values[rhs]
            else:
                raise ValueError(f"{rel(path)}:{lineno}: {key} refers to unknown name {rhs!r}")
        if key in values:
            raise ValueError(f"{rel(path)}:{lineno}: duplicate name {key}")
        values[key] = value
        refs[key] = Ref(rel(path), lineno)
        nxt = value + 1
    return Enum(name, values, refs)


@cache
def load_names(name: str) -> tuple[tuple[str, Ref], ...]:
    """Names in file order with refs; for masks, whose numeric values are not derived here."""
    path = GENERATED / f"{name}.txt"
    out = []
    for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.split("//")[0].strip()
        if line:
            out.append((line.split()[0], Ref(rel(path), lineno)))
    return tuple(out)
