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


# ---- Experience gain (T072, SC-006) ----------------------------------------------------------
# An independent Python reading of the decomp's exp award, written from the C (not from
# sim/exp.mjs). Line numbers are for pokeplatinum @ the pinned commit; `exp_formula()` re-reads
# every multiplier and divisor from the C and fails loudly if the code shape changes.
#
# BtlCmd_CalcExpGain (src/battle/battle_script.c:2187-2248), once per fainted enemy:
#   :2201-2214  over the player's party, only mons with species and HP != 0:
#               nGaining = mons whose bit is in sideGetExpMask; nShare = HOLD_EFFECT_EXP_SHARE holders
#   :2216-2217  `u16 exp = baseExpReward; exp = (exp * faintedLevel) / 7;`  (u16 truncation)
#   :2219-2231  with an Exp. Share holder: gainedExp = (exp/2)/nGaining, sharedExp = (exp/2)/nShare
#   :2232-2239  otherwise gainedExp = exp/nGaining, sharedExp = 0; each raised to a minimum of 1.
# BattleScript_GetExpTask (src/battle/battle_script.c:9685), SEQ_GET_EXP_START (:9725-9778), per
# party slot that is in the mask or holds an Exp. Share (:9704-9712):
#   :9740       only if HP != 0 and level != MAX_POKEMON_LEVEL
#   :9741-9747  totalExp = gainedExp if in the mask; += sharedExp if an Exp. Share holder
#   :9749-9751  HOLD_EFFECT_EXP_UP (Lucky Egg): totalExp * 150 / 100
#   :9753-9755  BATTLE_TYPE_TRAINER: totalExp * 150 / 100
#   :9757-9765  not OT (BattleSystem_PokemonIsOT, src/battle/battle_lib.c:6286): * 170 / 100 if the
#               mon's language != gGameLanguage, else * 150 / 100
#   totalExp is u32 (:9738), the factors are applied in that order with integer division.
# Pokemon_ShouldLevelUp (src/pokemon.c:3501-3526): exp is capped at the level-100 table value and
# the level rises one step at a time while exp >= table[level + 1] (re-run until it says no).

BATTLE_SCRIPT_C = DECOMP_ROOT / "src" / "battle" / "battle_script.c"


@dataclass(frozen=True)
class ExpFormula:
    level_divisor: int  # battle_script.c:2217
    lucky_egg: tuple[int, int]  # (mul, div), :9750
    trainer: tuple[int, int]  # :9754
    traded_foreign: tuple[int, int]  # :9759
    traded: tuple[int, int]  # :9761
    src: dict[str, str]


def _find(lines: list[str], pattern: str, start: int, what: str) -> tuple[int, re.Match]:
    rx = re.compile(pattern)
    for i in range(start, len(lines)):
        m = rx.search(lines[i])
        if m:
            return i, m
    raise ValueError(f"{rel(BATTLE_SCRIPT_C)}: {what} not found after line {start + 1}")


@cache
def exp_formula() -> ExpFormula:
    """Read the exp divisor and multipliers from battle_script.c (with their line numbers)."""
    lines = BATTLE_SCRIPT_C.read_text().splitlines()
    calc, _ = _find(lines, r"^static BOOL BtlCmd_CalcExpGain\(.*\)$", 0, "BtlCmd_CalcExpGain")
    div_i, m = _find(lines, r"exp = \(exp \* battleCtx->battleMons\[battleCtx->faintedMon\]\.level\) / (\d+);",
                     calc, "exp level divisor")
    level_divisor = int(m.group(1))
    task, _ = _find(lines, r"^static void BattleScript_GetExpTask\(.*\)$", 0, "BattleScript_GetExpTask")
    mul = r"totalExp = totalExp \* (\d+) / (\d+);"

    def factor_after(cond: str, what: str) -> tuple[int, tuple[int, int]]:
        ci, _ = _find(lines, cond, task, what)
        fi, fm = _find(lines, mul, ci + 1, what)
        if fi != ci + 1:
            raise ValueError(f"{rel(BATTLE_SCRIPT_C)}:{ci + 1}: {what}: factor is not on the next line")
        return fi, (int(fm.group(1)), int(fm.group(2)))

    egg_i, lucky_egg = factor_after(r"if \(itemEffect == HOLD_EFFECT_EXP_UP\) \{", "Lucky Egg factor")
    tr_i, trainer = factor_after(r"if \(battleType & BATTLE_TYPE_TRAINER\) \{", "trainer factor")
    fo_i, traded_foreign = factor_after(r"MON_DATA_LANGUAGE, NULL\) != gGameLanguage\) \{", "foreign trade factor")
    el_i, _ = _find(lines, r"\} else \{", fo_i + 1, "domestic trade branch")
    tdi, tm = _find(lines, mul, el_i + 1, "domestic trade factor")
    if tdi != el_i + 1:
        raise ValueError(f"{rel(BATTLE_SCRIPT_C)}:{el_i + 1}: domestic trade factor is not on the next line")
    traded = (int(tm.group(1)), int(tm.group(2)))
    r = rel(BATTLE_SCRIPT_C)
    return ExpFormula(level_divisor, lucky_egg, trainer, traded_foreign, traded, {
        "level_divisor": f"{r}:{div_i + 1}", "lucky_egg": f"{r}:{egg_i + 1}", "trainer": f"{r}:{tr_i + 1}",
        "traded_foreign": f"{r}:{fo_i + 1}", "traded": f"{r}:{tdi + 1}",
    })


@dataclass(frozen=True)
class PartyMonExp:
    """One player party slot as BtlCmd_CalcExpGain / BattleScript_GetExpTask see it."""

    alive: bool  # MON_DATA_HP != 0 (battle_script.c:2204, :9740)
    in_mask: bool  # sideGetExpMask bit for this slot (:2205, :9741)
    exp_share: bool = False  # HOLD_EFFECT_EXP_SHARE (:2209, :9745)
    lucky_egg: bool = False  # HOLD_EFFECT_EXP_UP (:9749)
    traded: bool = False  # BattleSystem_PokemonIsOT == FALSE (:9757; FR-008a)
    foreign_language: bool = False  # MON_DATA_LANGUAGE != gGameLanguage (:9758)
    level: int = 1  # level == MAX_POKEMON_LEVEL gets nothing (:9740)


@dataclass(frozen=True)
class ExpAward:
    exp: int  # u16 base yield, battle_script.c:2216-2217
    gained: int  # battleCtx->gainedExp
    shared: int  # battleCtx->sharedExp
    n_gaining: int
    n_share: int
    totals: tuple[int, ...]  # exp added to each party slot (0 = nothing)


def _mul(x: int, f: tuple[int, int]) -> int:
    return (x * f[0]) // f[1]


def exp_gain(base_exp_reward: int, fainted_level: int, party: list[PartyMonExp] | tuple[PartyMonExp, ...],
             *, trainer_battle: bool = True) -> ExpAward:
    """Exp each player party slot receives when one enemy faints (see the block comment above)."""
    f = exp_formula()
    n_gaining = sum(1 for m in party if m.alive and m.in_mask)  # :2201-2207
    n_share = sum(1 for m in party if m.alive and m.exp_share)  # :2209-2212
    exp = ((base_exp_reward * fainted_level) // f.level_divisor) & 0xFFFF  # u16 exp (:2216-2217)
    # nGaining == 0 is a division by zero in the C. It happens only when no live mon is in the
    # mask, and gainedExp is then read by nobody (:9740-9743), so 0 is used here.
    if n_share:
        gained = max(1, (exp // 2) // n_gaining) if n_gaining else 0  # :2220-2224
        shared = max(1, (exp // 2) // n_share)  # :2226-2230
    else:
        gained = max(1, exp // n_gaining) if n_gaining else 0  # :2232-2236
        shared = 0  # :2238
    totals = []
    for m in party:
        if not (m.in_mask or m.exp_share) or not m.alive or m.level == max_level():  # :9709, :9740
            totals.append(0)
            continue
        total = gained if m.in_mask else 0  # :9741-9743
        if m.exp_share:
            total += shared  # :9745-9747
        if m.lucky_egg:
            total = _mul(total, f.lucky_egg)  # :9749-9751
        if trainer_battle:
            total = _mul(total, f.trainer)  # :9753-9755
        if m.traded:
            total = _mul(total, f.traded_foreign if m.foreign_language else f.traded)  # :9757-9765
        totals.append(total)
    return ExpAward(exp, gained, shared, n_gaining, n_share, tuple(totals))


def apply_exp(rate: str, level: int, exp: int, amount: int) -> tuple[int, int]:
    """(new_level, new_exp) after adding `amount`: Pokemon_ShouldLevelUp (src/pokemon.c:3501-3526)
    run until it returns FALSE (SEQ_GET_EXP_CHECK_LEVEL_UP, battle_script.c:9824)."""
    top = max_level()
    exp = min(exp + amount, exp_at(rate, top))  # pokemon.c:3507-3512
    while level + 1 <= top and exp >= exp_at(rate, level + 1):  # pokemon.c:3514-3522
        level += 1
    return level, exp
