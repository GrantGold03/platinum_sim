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


# ---------------------------------------------------------------------------------------------
# Move-item pairing (007 T037; spec FR-006, FR-009 relevance, research R2.5)


@cache
def effect_script_items() -> dict[str, frozenset[str]]:
    """BATTLE_EFFECT_* -> hold effects its own effect script checks (CheckItemHoldEffect): the weather
    rocks (effect_script_0136/0137/0115/0164) and Power Herb (the charge-turn scripts). Judgment's
    Plate check (effect_script_0268) is a type change, not a pairing, and is left out."""
    from platsim.optimizer import move_classes as MC

    out = {}
    for effect in MC.effect_index():
        text = MC.effect_script(effect).read_text()
        hes = set(re.findall(r"\bHOLD_EFFECT_\w+", text))
        hes = {h for h in hes if not h.startswith("HOLD_EFFECT_ARCEUS_")}
        if hes:
            out[effect] = frozenset(hes)
    return out


# Pairings the effect scripts can't show (rule table over decomp constants; research R2.5):
#   EXTEND_SCREENS is read only in BtlCmd_TryReflect / BtlCmd_TryLightScreen (battle_script.c:4229, 4272);
#   LEECH_BOOST in the Leech Seed, drain, Dream Eater, Ingrain and Aqua Ring heal subscripts;
#   SLP_RESTORE / STATUS_RESTORE cure the sleep Rest puts on its user (subscript_rest.s:32; battle_lib.c:4608, 4662).
PAIRED_EFFECTS = {
    "HOLD_EFFECT_EXTEND_SCREENS": {"BATTLE_EFFECT_SET_REFLECT", "BATTLE_EFFECT_SET_LIGHT_SCREEN"},
    "HOLD_EFFECT_LEECH_BOOST": {"BATTLE_EFFECT_STATUS_LEECH_SEED", "BATTLE_EFFECT_RECOVER_HALF_DAMAGE_DEALT",
                                "BATTLE_EFFECT_GROUND_TRAP_USER_CONTINUOUS_HEAL", "BATTLE_EFFECT_RESTORE_HP_EVERY_TURN"},
    "HOLD_EFFECT_SLP_RESTORE": {"BATTLE_EFFECT_REST"},
}
CHOICE = {"HOLD_EFFECT_CHOICE_ATK", "HOLD_EFFECT_CHOICE_SPATK", "HOLD_EFFECT_CHOICE_SPEED"}
# Items that only hurt their holder; worth holding only to give away with Trick / Switcheroo.
DRAWBACK = {"HOLD_EFFECT_SPEED_DOWN_GROUNDED", "HOLD_EFFECT_PRIORITY_DOWN", "HOLD_EFFECT_DMG_USER_CONTACT_XFR",
            "HOLD_EFFECT_PSN_USER", "HOLD_EFFECT_BRN_USER"}
TRICK = "BATTLE_EFFECT_SWITCH_HELD_ITEMS"
ITEM_TIE_RULE = "more copies; higher effect_param; classic STRENGTHEN_* before ARCEUS_*; item key"  # FR-011


@cache
def league_move_types() -> frozenset[str]:
    """Types of every move the League (Elite Four + Cynthia) parties carry (trainers.json)."""
    import json

    from platsim.decomp.moves import load_moves
    from platsim.optimizer.candidates import GAUNTLET_KEYS, TRAINERS_JSON

    mv = load_moves()
    data = {t["key"]: t for t in json.loads(TRAINERS_JSON.read_text())["trainers"]}
    return frozenset(mv[m].type for k in GAUNTLET_KEYS for mon in data[k]["party"] for m in (mon.get("moves") or [])
                     if m in mv and mv[m].category != "CLASS_STATUS")


def _resist_type(hold_effect: str) -> str | None:
    if hold_effect == "HOLD_EFFECT_WEAKEN_NORMAL":
        return "TYPE_NORMAL"
    m = re.fullmatch(r"HOLD_EFFECT_WEAKEN_SE_(\w+)", hold_effect)
    return f"TYPE_{m.group(1)}".replace("TYPE_FIGHT", "TYPE_FIGHTING") if m else None


def relevant(item_key: str, member_species: str, moveset, ) -> bool:
    """Is this item worth offering with this moveset (spec FR-006, FR-009)?"""
    from platsim.decomp.moves import load_moves
    from platsim.legality import movesources as MS
    from platsim.optimizer import candidates as C

    it = _by_key()[item_key]
    he = it.hold_effect
    mv = load_moves()
    effects = {mv[m].effect for m in moveset}
    types = MS.by_constant()[member_species].types
    if he in DRAWBACK:
        return TRICK in effects
    if he in CHOICE:
        return all(mv[m].category != "CLASS_STATUS" for m in moveset)
    if he == "HOLD_EFFECT_HP_RESTORE_PSN_TYPE":
        return "TYPE_POISON" in types
    if he in PAIRED_EFFECTS:
        return bool(effects & PAIRED_EFFECTS[he])
    paired_by_script = {e for e, hs in effect_script_items().items() if he in hs}
    if paired_by_script:
        return bool(effects & paired_by_script)
    rt = _resist_type(he)
    if rt:
        weak = rt == "TYPE_NORMAL" or C.type_mult(rt, types) > 1
        return weak and rt in league_move_types()
    tb = [t for t, hes in C.type_boost_items().items() if he in hes]
    if tb:
        return any(mv[m].type in tb and mv[m].category != "CLASS_STATUS" for m in moveset)
    return True


@cache
def _by_key():
    return {i.key: i for i in load_items().values()}


def _tie_key(item_key: str, copies) -> tuple:
    from platsim.legality import movesources as MS

    it = _by_key()[item_key]
    unlimited = copies == MS.UNLIMITED
    return (not unlimited, -(0 if unlimited else int(copies)), -it.effect_param,
            it.hold_effect.startswith("HOLD_EFFECT_ARCEUS_"), item_key)


def items_for(member_species: str, moveset, team, led, policy: str | None = None) -> list[str]:
    """Item keys offered with this moveset (spec FR-009): offerable, relevant, modelled by `policy`
    (when given), and one item per hold-effect family by ITEM_TIE_RULE (FR-011: a Plate and a classic
    type booster share a family: the boosted type)."""
    from platsim.availability.ledger import team_item_copies
    from platsim.optimizer import candidates as C
    from platsim.optimizer import move_classes as MC

    fam = {}
    for key in offerable_items(member_species, team, led):
        it = _by_key()[key]
        if policy and not MC.item_modelled(policy, it.hold_effect):
            continue
        if not relevant(key, member_species, moveset):
            continue
        tb = [t for t, hes in C.type_boost_items().items() if it.hold_effect in hes]
        family = ("type", tb[0]) if tb else ("effect", it.hold_effect)
        copies = team_item_copies(led, it.const, tuple(team))
        if family not in fam or _tie_key(key, copies) < fam[family][0]:
            fam[family] = (_tie_key(key, copies), key)
    return sorted(k for _, k in fam.values())


__all__ = ["EXP_FUNCTIONS", "ItemClass", "NO_OUTCOME", "exp_ev_effects", "hold_effect_numbers",
           "hold_effect_references", "item_class", "items_for", "offerable_items", "relevant", "species_gates", "ITEM_TIE_RULE"]
