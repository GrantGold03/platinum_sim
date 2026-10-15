"""Held-item classification for candidate generation (007 T009; spec FR-009-FR-011, research R2).

An item is a held-item candidate when its hold effect DOES SOMETHING IN BATTLE, which is decided from
the decomp's battle code, not from a list of item names (Constitution I):

- `hold_effect_references()` finds every HOLD_EFFECT_* referenced in `src/battle/*.c` and
  `res/battle/scripts/**`, by name AND by number. The number matters: the type-resist berry
  subscript (subscript_type_resist_berry.s) loads the hold effect with `GetItemHoldEffect` and
  compares it to the literals 19-35, so a name-only search marks all 17 resist berries as unused.
  The numeric value of an effect is its line index in `generated/item_hold_effects.txt`.
  (`src/battle/trainer_ai/` is not searched: the AI reading an item is not the item doing anything.)
- `NO_OUTCOME` (rule table, decomp constants only) holds effects that battle code reads but that
  cannot change a trainer battle's outcome. Each entry names the function every reference must lie
  in; a test checks that.
- Experience / EV items are DERIVED: effects referenced in the functions that award experience or
  effort values (`BtlCmd_CalcExpGain`, `BattleScript_GetExpTask`, `BattleScript_CalcEffortValues`).
  They raise the final level the objective minimises, so they are never candidates. (This replaces
  the stale hand list `EXP_HOLD_EFFECTS`, which named an effect that no longer exists.)
- Species gates (Light Ball, Thick Club, ...) are parsed from the battle code's
  `... == HOLD_EFFECT_X ... SPECIES_Y` conditions.

Copies always come from the ledger through `team_item_copies` (Leftovers is team-gated, 003 FR-009).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

from platsim.decomp.items import load_items
from platsim.pins import DECOMP_ROOT

BATTLE_SRC = DECOMP_ROOT / "src" / "battle"
BATTLE_SCRIPTS = DECOMP_ROOT / "res" / "battle" / "scripts"
HOLD_EFFECTS_TXT = DECOMP_ROOT / "generated" / "item_hold_effects.txt"

# Read by battle code, but no effect on a trainer battle's outcome: effect -> (function, reason).
NO_OUTCOME: dict[str, tuple[str, str]] = {
    # battle_lib.c:4127 SWITCH_IN_CHECK_STATE_AMULET_COIN sets prizeMoneyMul = 2
    "HOLD_EFFECT_MONEY_UP": ("BattleSystem_TriggerEffectOnSwitch", "prize money only (battle_lib.c:4127)"),
    # Battler_IsTrappedMsg is only reached from Run (battle_controller_player.c:618, after the trainer-battle
    # branch at :605 refuses Run) and Teleport (BtlCmd_TryTeleport; Teleport fails in trainer battles);
    # Battler_CanEscape only from Run / BtlCmd_TryEscape; subscript_escape.s is the Run script.
    "HOLD_EFFECT_FLEE": ("Battler_IsTrappedMsg|Battler_CanEscape|subscript_escape.s",
                         "only helps run away; Run is refused in trainer battles (battle_controller_player.c:605)"),
    # battle_system.c:746, inside BattleSystem_UseBagItem
    "HOLD_EFFECT_FRIENDSHIP_UP": ("BattleSystem_UseBagItem", "friendship only (battle_system.c:746)"),
}
EXP_FUNCTIONS = ("BtlCmd_CalcExpGain", "BattleScript_GetExpTask", "BattleScript_CalcEffortValues")

_FUNC_DEF = re.compile(r"^(?:static\s+)?(?:inline\s+)?[A-Za-z_][\w\s\*]*?\b(\w+)\s*\([^;]*\)\s*$")


@cache
def hold_effect_numbers() -> dict[str, int]:
    return {e: i for i, e in enumerate(HOLD_EFFECTS_TXT.read_text().split())}


@dataclass(frozen=True)
class Ref:
    path: str
    line: int
    function: str | None


@cache
def hold_effect_references() -> dict[str, tuple[Ref, ...]]:
    """HOLD_EFFECT_* -> where battle code references it (by name, or by number in a script)."""
    names = hold_effect_numbers()
    by_num = {i: e for e, i in names.items()}
    out: dict[str, list[Ref]] = {}
    for path in sorted(BATTLE_SRC.glob("*.c")):
        func = None
        lines = path.read_text().splitlines()
        for n, line in enumerate(lines, 1):
            if line.startswith("}"):  # end of a function: later file-scope tables belong to none
                func = None
            m = _FUNC_DEF.match(line)
            if m and n < len(lines) and lines[n].startswith("{"):
                func = m.group(1)
            for e in re.findall(r"\bHOLD_EFFECT_\w+", line):
                if e in names:
                    out.setdefault(e, []).append(Ref(str(path.relative_to(DECOMP_ROOT)), n, func))
    for path in sorted(BATTLE_SCRIPTS.rglob("*.s")):
        text = path.read_text()
        held_vars = set(re.findall(r"GetItemHoldEffect\s+\w+,\s*(\w+)", text))
        for n, line in enumerate(text.splitlines(), 1):
            for e in re.findall(r"\bHOLD_EFFECT_\w+", line):
                if e in names:
                    out.setdefault(e, []).append(Ref(str(path.relative_to(DECOMP_ROOT)), n, None))
            m = re.match(r"\s*CompareVarToValue\s+OPCODE_EQU,\s*(\w+),\s*(\d+)\b", line)
            if m and m.group(1) in held_vars and int(m.group(2)) in by_num:
                out.setdefault(by_num[int(m.group(2))], []).append(Ref(str(path.relative_to(DECOMP_ROOT)), n, None))
    return {e: tuple(v) for e, v in out.items()}


@cache
def exp_ev_effects() -> frozenset[str]:
    return frozenset(e for e, refs in hold_effect_references().items()
                     if any(r.function in EXP_FUNCTIONS for r in refs))


@cache
def species_gates() -> dict[str, frozenset[str]]:
    """HOLD_EFFECT_* -> species it works for, from `... == HOLD_EFFECT_X ... SPECIES_Y` conditions."""
    out: dict[str, set[str]] = {}
    for path in sorted(BATTLE_SRC.glob("*.c")):
        text = path.read_text()
        for m in re.finditer(r"==\s*(HOLD_EFFECT_\w+)", text):
            chunk = re.split(r"[{;]|\n\s*\+", text[m.end():], maxsplit=1)[0]
            sp = re.findall(r"\bSPECIES_\w+", chunk)
            if sp:
                out.setdefault(m.group(1), set()).update(sp)
    return {e: frozenset(v) for e, v in out.items()}


@dataclass(frozen=True)
class ItemClass:
    item: str  # ITEM_*
    hold_effect: str
    in_battle: bool
    excluded_reason: str | None  # None = a candidate (subject to copies and gates)
    species: frozenset[str] | None  # species gate, if any


@cache
def item_class(item_const: str) -> ItemClass:
    it = next(i for i in load_items().values() if i.const == item_const)
    e = it.hold_effect
    refs = hold_effect_references()
    gate = species_gates().get(e)
    if e == "HOLD_EFFECT_NONE" or e not in refs:
        return ItemClass(item_const, e, False, "not_in_battle: its hold effect is not referenced in battle code", gate)
    if e in exp_ev_effects():
        return ItemClass(item_const, e, True, "exp_ev: raises experience or effort values (raises final levels)", gate)
    if e in NO_OUTCOME:
        return ItemClass(item_const, e, True, f"no_outcome: {NO_OUTCOME[e][1]}", gate)
    return ItemClass(item_const, e, True, None, gate)


def offerable_items(member_species: str, team, led) -> list[str]:
    """Item keys this member may be offered before move pairing (spec FR-009, without the
    player-modelled filter, which candidates applies with the policy in use)."""
    from platsim.availability.ledger import team_item_copies

    out = []
    for it in sorted(load_items().values(), key=lambda i: i.key):
        c = item_class(it.const)
        if c.excluded_reason is not None:
            continue
        if c.species is not None and member_species not in c.species:
            continue
        if team_item_copies(led, it.const, tuple(team)) == 0:
            continue
        out.append(it.key)
    return out


__all__ = ["EXP_FUNCTIONS", "ItemClass", "NO_OUTCOME", "exp_ev_effects", "hold_effect_numbers",
           "hold_effect_references", "item_class", "offerable_items", "species_gates"]
