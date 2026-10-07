"""Experience tables (T016): pokeplatinum/res/pokemon/.shared/exp_tables.csv.

The CSV has a `level` column (0..MAX_POKEMON_LEVEL) and one column per growth rate. Column order
after `level` is the order of generated/exp_rates.txt (EXP_RATE_COUNT excluded); this module checks
that the CSV header names match the enum names.

level_from_exp mirrors SpeciesData_GetLevelAt (src/pokemon.c:2378): scan i = 1..MAX_POKEMON_LEVEL
and stop at the first table[i] > exp; return i - 1 (so exp >= table[100] gives 100).
"""

import csv
import re
from dataclasses import dataclass
from functools import cache

from platsim.decomp._util import line_of
from platsim.decomp.constants import load_enum, rel
from platsim.pins import DECOMP_ROOT

EXP_CSV = DECOMP_ROOT / "res" / "pokemon" / ".shared" / "exp_tables.csv"
POKEMON_C = DECOMP_ROOT / "src" / "pokemon.c"
POKEMON_H = DECOMP_ROOT / "include" / "constants" / "pokemon.h"


@cache
def max_level() -> int:
    m = re.search(r"#define\s+MAX_POKEMON_LEVEL\s+(\d+)", POKEMON_H.read_text())
    if not m:
        raise ValueError(f"MAX_POKEMON_LEVEL not found in {rel(POKEMON_H)}")
    return int(m.group(1))


@dataclass(frozen=True)
class ExpTables:
    tables: dict[str, tuple[int, ...]]  # EXP_RATE_* -> exp at level 0..MAX_POKEMON_LEVEL
    src: tuple[str, ...]


@cache
def load_exp_tables() -> ExpTables:
    rates = [n for n in load_enum("exp_rates").values if n != "EXP_RATE_COUNT"]
    with EXP_CSV.open(newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    if header[0] != "level" or len(header) - 1 != len(rates):
        raise ValueError(f"{rel(EXP_CSV)}: unexpected header {header}")
    for col, rate in zip(header[1:], rates):
        # e.g. "medium_fast" <-> EXP_RATE_MEDIUM_FAST, "unused_6" <-> EXP_RATE_6_UNUSED
        want = rate.removeprefix("EXP_RATE_").lower()
        if sorted(col.split("_")) != sorted(want.split("_")):
            raise ValueError(f"{rel(EXP_CSV)}: column {col!r} does not match {rate}")
    levels = [int(r[0]) for r in body]
    if levels != list(range(max_level() + 1)):
        raise ValueError(f"{rel(EXP_CSV)}: levels are not 0..{max_level()}")
    tables = {rate: tuple(int(r[i + 1]) for r in body) for i, rate in enumerate(rates)}
    src = (
        f"{rel(EXP_CSV)}:1",
        f"{rel(POKEMON_C)}:{line_of(POKEMON_C, 'u32 SpeciesData_GetLevelAt(')}",
    )
    return ExpTables(tables, src)


def exp_at(rate: str, level: int) -> int:
    """Exp needed to be at `level` (Pokemon_GetExpRateBaseExpAt: expTable[level])."""
    return load_exp_tables().tables[rate][level]


def level_from_exp(rate: str, exp: int) -> int:
    table = load_exp_tables().tables[rate]
    i = 1
    while i < max_level() + 1:
        if table[i] > exp:
            break
        i += 1
    return i - 1
