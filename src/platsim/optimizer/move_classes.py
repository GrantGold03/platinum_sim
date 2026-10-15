"""Move classification for candidate generation (007 T007; spec FR-001 to FR-004, research R1).

Every move effect gets exactly one category, DERIVED from the decomp wherever the decomp says it:

- The effect script of a move is `res/battle/scripts/effects/effect_script_NNNN.s`, where NNNN is
  the effect's line index in `generated/move_battle_effects.txt` (battle_script.c:2084 jumps to
  `BE_SEQ[CURRENT_MOVE_DATA.effect]`).
- Most status scripts are one `UpdateVar ... MOVE_SIDE_EFFECT_{TO_ATTACKER|TO_DEFENDER|ON_HIT}|
  MOVE_SUBSCRIPT_PTR_X`, which names the subscript that does the work
  (include/data/move_side_effect_subscripts.h). The direction and the pointer name decide the
  category: a TO_DEFENDER `*_DOWN_*` pointer lowers the foe's stats, a TO_ATTACKER `*_UP_*` pointer
  raises the user's, and so on (DERIVED below).
- A damaging script that writes `BTLVAR_DAMAGE` without `CalcDamage` deals fixed damage (exactly six
  effects). A damaging move whose data power is 1 and whose script calls `CalcDamage` computes its
  power at run time (variable power).

`RULES` holds the meanings the scripts can't express: about 20 decomp constants, never move names
(Constitution I). Each entry carries its reason. A test checks every constant exists in the decomp
and that every effect of every move classifies, so the table cannot rot silently (the stale
`HOLD_EFFECT_LVLUP_SPEED_DOWN` in the old `EXP_HOLD_EFFECTS` is what an unguarded table does).

Which categories are OFFERED is a separate question: in scope (`OFFERED`) and modelled by the
battle player in use (`modelled()`, parsed from sim/policy/expectimax2.mjs MODELLED; spec FR-001).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

from platsim.decomp.moves import load_moves
from platsim.pins import DECOMP_ROOT, REPO_ROOT

EFFECTS_TXT = DECOMP_ROOT / "generated" / "move_battle_effects.txt"
EFFECT_SCRIPTS = DECOMP_ROOT / "res" / "battle" / "scripts" / "effects"
SUBSCRIPT_PTRS_H = DECOMP_ROOT / "include" / "data" / "move_side_effect_subscripts.h"
EXPECTIMAX2 = REPO_ROOT / "sim" / "policy" / "expectimax2.mjs"

# Categories (data-model.md MoveClass). In scope = offered when the player models the effect.
RECOVERY, INFLICT_STATUS, LEECH_SEED, SELF_BOOST = "recovery", "inflict_status", "leech_seed", "self_boost"
PROTECTION, SCREEN, WEATHER, OTHER = "protection", "screen", "weather", "other"
ATTACK, VARIABLE_ATTACK = "attack", "variable_attack"
FOE_DROP, FIXED_DAMAGE, NO_EFFECT_SINGLES = "foe_drop", "fixed_damage", "no_effect_singles"
SACRIFICE, REACTIVE, CONDITIONAL_ATTACK = "sacrifice", "reactive", "conditional_attack"
STATUS_CATEGORIES = (RECOVERY, INFLICT_STATUS, LEECH_SEED, SELF_BOOST, PROTECTION, SCREEN, WEATHER, OTHER)
OFFERED = frozenset(STATUS_CATEGORIES + (ATTACK, VARIABLE_ATTACK))

STAGE_RESET = ("stat stages reset when the foe faints or switches out "
               "(battle_lib.c:97-100, BattleSystem_CleanupFaintedMon battle_lib.c:2156-2162), "
               "so a drop is lost with every League KO; spec FR-002")

# Attacks that only work under a condition the search cannot arrange (unchanged from the old
# candidates.EXCLUDED_ATTACK_EFFECTS): first turn only, target asleep / user asleep, all other
# moves used, user not hit first, user faints, delayed hit.
EXCLUDED_ATTACK_EFFECTS = frozenset({
    "BATTLE_EFFECT_ONE_HIT_KO", "BATTLE_EFFECT_HALVE_DEFENSE", "BATTLE_EFFECT_HIT_IN_3_TURNS",
    "BATTLE_EFFECT_ALWAYS_FLINCH_FIRST_TURN_ONLY", "BATTLE_EFFECT_DAMAGE_WHILE_ASLEEP",
    "BATTLE_EFFECT_FAIL_IF_NOT_USED_ALL_OTHER_MOVES", "BATTLE_EFFECT_HIT_LAST_WHIFF_IF_HIT",
    "BATTLE_EFFECT_RECOVER_DAMAGE_SLEEP", "BATTLE_EFFECT_STRUGGLE", "BATTLE_EFFECT_LEAVE_WITH_1_HP",
})

# The non-derivable meanings (research R1, spec FR-003). Keys are BATTLE_EFFECT_* constants.
RULES: dict[str, tuple[str, str]] = {
    # self-raises whose subscript pointer doesn't say *_UP_*
    "BATTLE_EFFECT_CRIT_UP_2": (SELF_BOOST, "Focus Energy: raises the user's critical-hit stage"),
    "BATTLE_EFFECT_EVA_UP_2_MINIMIZE": (SELF_BOOST, "Minimize: +2 evasion"),
    "BATTLE_EFFECT_STOCKPILE": (SELF_BOOST, "Stockpile: +1 Def and SpD per use"),
    "BATTLE_EFFECT_MAX_ATK_LOSE_HALF_MAX_HP": (SELF_BOOST, "Belly Drum: Attack to +6 for half max HP"),
    "BATTLE_EFFECT_RANDOM_STAT_UP_2": (SELF_BOOST, "Acupressure: +2 to a random stat"),
    "BATTLE_EFFECT_CURSE": (SELF_BOOST, "Curse (non-Ghost user): +1 Atk/Def, -1 Speed; the Ghost branch is not modelled"),
    "BATTLE_EFFECT_SP_DEF_UP_DOUBLE_ELECTRIC_POWER": (SELF_BOOST, "Charge: +1 SpD"),
    # no effect in a single trainer battle
    "BATTLE_EFFECT_MAKE_GLOBAL_TARGET": (NO_EFFECT_SINGLES, "Follow Me: redirects only in double battles"),
    # the user faints
    "BATTLE_EFFECT_FAINT_AND_ATK_SP_ATK_DOWN_2": (SACRIFICE, "Memento: the user faints"),
    "BATTLE_EFFECT_FAINT_AND_FULL_HEAL_NEXT_MON": (SACRIFICE, "Healing Wish: the user faints"),
    "BATTLE_EFFECT_FAINT_FULL_RESTORE_NEXT_MON": (SACRIFICE, "Lunar Dance: the user faints"),
    # reactive / needs another move first
    "BATTLE_EFFECT_COUNTER": (REACTIVE, "Counter: only returns physical damage taken this turn"),
    "BATTLE_EFFECT_MIRROR_COAT": (REACTIVE, "Mirror Coat: only returns special damage taken this turn"),
    "BATTLE_EFFECT_METAL_BURST": (REACTIVE, "Metal Burst: only returns damage taken this turn"),
    "BATTLE_EFFECT_BIDE": (REACTIVE, "Bide: returns damage taken over two turns"),
    "BATTLE_EFFECT_SPIT_UP": (REACTIVE, "Spit Up: fails without Stockpile"),
    "BATTLE_EFFECT_SWALLOW": (REACTIVE, "Swallow: fails without Stockpile"),
    "BATTLE_EFFECT_RANDOM_POWER_MAYBE_HEAL": (REACTIVE, "Present: random power, may heal the foe"),
    # attacks whose power the optimizer can't predict before battle (spec FR-003, research R3)
    "BATTLE_EFFECT_INCREASE_POWER_WITH_LESS_HP": (CONDITIONAL_ATTACK, "Flail / Reversal: power 20 at full HP, depends on the user's HP in battle"),
    "BATTLE_EFFECT_HIGHER_POWER_WHEN_LOW_PP": (CONDITIONAL_ATTACK, "Trump Card: power depends on PP left"),
    "BATTLE_EFFECT_NATURAL_GIFT": (CONDITIONAL_ATTACK, "Natural Gift: consumes the held berry"),
    "BATTLE_EFFECT_FLING": (CONDITIONAL_ATTACK, "Fling: consumes the held item"),
    "BATTLE_EFFECT_POWER_BASED_ON_LOW_FRIENDSHIP": (CONDITIONAL_ATTACK, "Frustration: power 0 at friendship 255 (spec FR-012)"),
    # damaging without CalcDamage, but a real attack
    "BATTLE_EFFECT_BEAT_UP": (ATTACK, "Beat Up: one hit per able party member (unchanged from before 007)"),
}

_PAIR = re.compile(r"MOVE_SIDE_EFFECT_((?:\w+\|)*)MOVE_SUBSCRIPT_PTR_(\w+)")
_STATUS_PTRS = {"SLEEP", "POISON", "BADLY_POISON", "PARALYZE", "BURN", "YAWN"}
_RECOVERY_PTRS = {"RECOVER_HALF_MAX_HP", "REST", "ROOST", "PRESENT_HEAL"}
_SCREEN_PTRS = {"REFLECT", "LIGHT_SCREEN", "SAFEGUARD_START"}


@dataclass(frozen=True)
class MoveClass:
    effect: str
    category: str
    reason: str  # why it is (or isn't) offered
    derived_from: str  # script path:line, or "RULES"

    @property
    def in_scope(self) -> bool:
        return self.category in OFFERED


@cache
def effect_index() -> dict[str, int]:
    return {e: i for i, e in enumerate(EFFECTS_TXT.read_text().split())}


def effect_script(effect: str):
    return EFFECT_SCRIPTS / f"effect_script_{effect_index()[effect]:04d}.s"


@cache
def subscript_ptrs() -> frozenset[str]:
    return frozenset(re.findall(r"MOVE_SUBSCRIPT_PTR_(\w+)", SUBSCRIPT_PTRS_H.read_text()))


def _rel(path) -> str:
    return str(path.relative_to(DECOMP_ROOT.parent)) if path.is_relative_to(DECOMP_ROOT.parent) else str(path)


@cache
def classify(effect: str, status: bool) -> MoveClass:
    """The category of `effect` for a status move (`status=True`) or a damaging move."""
    if effect in RULES:
        cat, why = RULES[effect]
        return MoveClass(effect, cat, why, "RULES")
    path = effect_script(effect)
    text = path.read_text()
    src = _rel(path)
    if not status:
        if effect in EXCLUDED_ATTACK_EFFECTS:
            return MoveClass(effect, CONDITIONAL_ATTACK, "conditional attack the search cannot arrange", "EXCLUDED_ATTACK_EFFECTS")
        calc = "CalcDamage" in text
        if not calc and "BTLVAR_DAMAGE" in text:
            return MoveClass(effect, FIXED_DAMAGE, "fixed damage: the script sets BTLVAR_DAMAGE without CalcDamage (spec FR-003)", src)
        if not calc:
            raise ValueError(f"{effect}: damaging script without CalcDamage and not in RULES ({src})")
        return MoveClass(effect, ATTACK, "attack", src)  # variable power is decided per move (power <= 1)
    pairs = [(d.replace("MOVE_SIDE_EFFECT_", "").strip("|").split("|"), p) for d, p in _PAIR.findall(text)]
    ptrs = {p for _, p in pairs}
    if "BATTLE_TYPE_TRAINER" in text and "MOVE_STATUS_FAILED" in text:
        return MoveClass(effect, NO_EFFECT_SINGLES, "fails in trainer battles (script checks BATTLE_TYPE_TRAINER)", src)
    if "MOVE_STATUS_SPLASH" in text and not pairs:
        return MoveClass(effect, NO_EFFECT_SINGLES, "does nothing (Splash)", src)
    if pairs and all("TO_DEFENDER" in d and re.search(r"_DOWN_\d_STAGES?$", p) for d, p in pairs):
        return MoveClass(effect, FOE_DROP, STAGE_RESET, src)
    if any("TO_ATTACKER" in d and "_UP_" in p for d, p in pairs):
        return MoveClass(effect, SELF_BOOST, "raises the user's stats", src)
    if any("TO_DEFENDER" in d and p in _STATUS_PTRS for d, p in pairs):
        return MoveClass(effect, INFLICT_STATUS, "inflicts a major status (or Yawn)", src)
    if "LEECH_SEED_START" in ptrs:
        return MoveClass(effect, LEECH_SEED, "Leech Seed", src)
    if ptrs & _RECOVERY_PTRS or "TryWish" in text or "MOVE_EFFECT_INGRAIN" in text or "MOVE_EFFECT_AQUA_RING" in text:
        return MoveClass(effect, RECOVERY, "restores the user's HP", src)
    if ptrs & {"PROTECT", "TRY_SUBSTITUTE"}:
        return MoveClass(effect, PROTECTION, "protection", src)
    if ptrs & _SCREEN_PTRS:
        return MoveClass(effect, SCREEN, "screen / Safeguard", src)
    if "WEATHER_START" in ptrs:
        return MoveClass(effect, WEATHER, "sets the weather", src)
    return MoveClass(effect, OTHER, "other status move", src)


def move_class(move_const: str) -> MoveClass:
    m = load_moves()[move_const]
    status = m.category == "CLASS_STATUS"
    if status and m.range == "RANGE_ALLY":  # Helping Hand: targets an ally, none in a single battle
        return MoveClass(m.effect, NO_EFFECT_SINGLES, "targets an ally (RANGE_ALLY); no ally in a single battle",
                         f"res/moves/{m.key}/data.json range")
    c = classify(m.effect, status)
    if not status and c.category == ATTACK and m.power <= 1:
        return MoveClass(m.effect, VARIABLE_ATTACK, "power computed in battle (spec FR-012, research R3)", c.derived_from)
    return c


# ---------------------------------------------------------------------------------------------
# What the battle player models (sim/policy/expectimax2.mjs MODELLED; spec FR-001, FR-009, FR-013)


@cache
def modelled_table() -> dict[str, tuple[frozenset[str], frozenset[str]]]:
    """policy name -> (modelled BATTLE_EFFECT names without prefix, modelled HOLD_EFFECT names
    without prefix), parsed from the literal `export const MODELLED = {...};` table."""
    text = EXPECTIMAX2.read_text()
    if "export const MODELLED = {" not in text:
        return {}
    body = text[text.index("export const MODELLED = {"):]
    body = body[:body.index("\n};")]
    out: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
    for name, inner in re.findall(r"'([\w-]+)':\s*\{(.*?)\n  \}", body, re.S):
        base = re.search(r"extends:\s*'([\w-]+)'", inner)
        effects = re.search(r"effects:\s*\[(.*?)\]", inner, re.S)
        items = re.search(r"items:\s*\[(.*?)\]", inner, re.S)
        be, bi = out[base.group(1)] if base else (frozenset(), frozenset())  # a version extends an earlier one
        out[name] = (be | frozenset(re.findall(r"'(\w+)'", effects.group(1) if effects else "")),
                     bi | frozenset(re.findall(r"'(\w+)'", items.group(1) if items else "")))
    return out


def modelled(policy: str) -> tuple[frozenset[str], frozenset[str]]:
    t = modelled_table()
    if policy not in t:
        raise KeyError(f"no MODELLED entry for player policy {policy!r} in {EXPECTIMAX2}")
    return t[policy]


def effect_modelled(policy: str, effect: str) -> bool:
    return effect.removeprefix("BATTLE_EFFECT_") in modelled(policy)[0]


def item_modelled(policy: str, hold_effect: str) -> bool:
    return hold_effect.removeprefix("HOLD_EFFECT_") in modelled(policy)[1]


def offered(move_const: str, policy: str) -> tuple[bool, str]:
    """Whether a legal move is offered as a candidate, and the reason if not (spec FR-001-FR-003)."""
    c = move_class(move_const)
    if not c.in_scope:
        return False, f"{c.category}: {c.reason}"
    if c.category in STATUS_CATEGORIES and not effect_modelled(policy, c.effect):
        return False, f"not offered: not modelled by {policy}"
    return True, ""


__all__ = ["ATTACK", "EXCLUDED_ATTACK_EFFECTS", "MoveClass", "OFFERED", "RULES", "STATUS_CATEGORIES",
           "VARIABLE_ATTACK", "classify", "effect_modelled", "effect_script", "item_modelled", "modelled",
           "modelled_table", "move_class", "offered"]
