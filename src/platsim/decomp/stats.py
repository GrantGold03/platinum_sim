"""Stat formula: port of Pokemon_CalcStats (src/pokemon.c:564) and Pokemon_GetNatureStatValue
(src/pokemon.c:2593).

    hp    = (2*base + iv + ev/4) * level / 100 + level + 10        (Shedinja: 1)
    other = nature((2*base + iv + ev/4) * level / 100 + 5)
    nature(x) = u16(x*110)/100 for +, u16(x*90)/100 for -, else x  (C integer division)

The nature table is parsed from `sNatureStatAffinities` in src/pokemon.c, not typed here.
Stat keys: hp, atk, def, spa, spd, spe (STAT_* names from generated/pokemon_stats.txt).
"""

import re
from functools import cache

from platsim.decomp._util import line_of, lines
from platsim.decomp.constants import load_enum, rel
from platsim.pins import DECOMP_ROOT

POKEMON_C = DECOMP_ROOT / "src" / "pokemon.c"

STAT_KEYS = {
    "STAT_ATTACK": "atk",
    "STAT_DEFENSE": "def",
    "STAT_SPEED": "spe",
    "STAT_SPECIAL_ATTACK": "spa",
    "STAT_SPECIAL_DEFENSE": "spd",
}
KEYS = ("hp", "atk", "def", "spa", "spd", "spe")
SHEDINJA = "SPECIES_SHEDINJA"


@cache
def nature_affinities() -> dict[str, dict[str, int]]:
    """NATURE_* -> {stat key: +1/0/-1}, parsed from sNatureStatAffinities."""
    start = line_of(POKEMON_C, "static const s8 sNatureStatAffinities[][5] = {")
    src = lines(POKEMON_C)
    out: dict[str, dict[str, int]] = {}
    current = None
    for lineno in range(start + 1, len(src) + 1):
        text = src[lineno - 1].strip()
        if text == "};":
            break
        if m := re.fullmatch(r"\[(NATURE_\w+)\] = \{", text):
            current = out.setdefault(m.group(1), {})
        elif m := re.fullmatch(r"\[(STAT_\w+) - 1\] = (-?\d+),", text):
            current[STAT_KEYS[m.group(1)]] = int(m.group(2))
    natures = [n for n in load_enum("natures").values if n != "NATURE_COUNT"]
    if list(out) != natures or any(len(v) != 5 for v in out.values()):
        raise ValueError(f"{rel(POKEMON_C)}:{start}: nature table does not match generated/natures.txt")
    return out


def nature_name(personality: int) -> str:
    """Pokemon_GetNatureOf (src/pokemon.c:2410): personality % NATURE_COUNT."""
    natures = load_enum("natures")
    return natures.name_of(personality % natures["NATURE_COUNT"], "NATURE_")


def _nature_stat(nature: str, value: int, key: str) -> int:
    aff = nature_affinities()[nature][key]
    if aff == 1:
        return ((value * 110) & 0xFFFF) // 100  # `u16 result = v*110; result /= 100;`
    if aff == -1:
        return ((value * 90) & 0xFFFF) // 100
    return value


def calc_stats(
    base: dict[str, int],
    ivs: dict[str, int],
    evs: dict[str, int],
    level: int,
    nature: str,
    species: str | None = None,
) -> dict[str, int]:
    """Stats as Pokemon_CalcStats computes them. Values are non-negative, so `//` == C `/`."""
    out: dict[str, int] = {}
    if species == SHEDINJA:
        out["hp"] = 1
    else:
        out["hp"] = (2 * base["hp"] + ivs["hp"] + evs["hp"] // 4) * level // 100 + level + 10
    for k in ("atk", "def", "spa", "spd", "spe"):
        raw = (2 * base[k] + ivs[k] + evs[k] // 4) * level // 100 + 5
        out[k] = _nature_stat(nature, raw, k)
    return out
