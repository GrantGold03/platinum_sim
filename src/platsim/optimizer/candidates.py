"""Per-member candidate generation (T061; spec FR-003-FR-008c, research.md R8 "Prune").

Everything here is a HEURISTIC OVER CANDIDATES, never over legality: it decides which legal builds
the optimizer *tries*. Legality itself always comes from `legality/movesources.py` (move sources,
source options) and the availability ledger (copies), and every team the optimizer outputs is
re-checked by the independent validator (Constitution III).

Species
-------
`resolve_species(names, ledger)` maps display names / keys / SPECIES_* to SPECIES_* constants and
raises `InvalidRequest` (user-facing; CLI exit 2) for unknown names (with the closest matches),
alternate forms, or species with no pre-Champion source, naming the reason: trade evolution (FR-005),
post-game only (FR-003 / FR-003a, with the ledger's own phase reasons), or no source at all. (001's
Munchlax project rule, FR-006a, was lifted by 003 FR-008.)

Source variants (FR-008b)
-------------------------
A member's pre-Champion source options (`movesources.source_options`) are grouped into battle-relevant
VARIANTS: one "own" variant (every non-NPC-trade option: wild, gift, egg, static, breeding; these give
identical battle stats at a given level, FR-008) and one variant per NPC-trade option (fixed IVs /
nature / ability and boosted exp, FR-008a). Each variant is a separate candidate dimension, so a
species with an NPC trade has both evaluated. Within a variant, the concrete option is picked per
level by `resources.realize` (lowest minimum level that makes every move legal).

Move candidates (research R8 "Prune" + a coverage heuristic)
-------------------------------------------------------------
1. Legal pool: every move any stage of any option of the variant could know (level-up, TM/HM, tutor,
   egg, Draco Meteor), kept only if `movesources.sources` gives a legal source at the reference level
   `ref_level` under some option of the variant.
2. Damaging moves only enter the coverage search. Excluded as attacks (heuristic): power 0 (status) and
   power 1 (variable power / fixed damage: the screening policy greedy-v1 scores them 0, greedy.mjs),
   and conditional attacks listed in EXCLUDED_ATTACK_EFFECTS (one-hit KO, Explosion/Self-Destruct,
   Future Sight, Fake Out, Snore, Dream Eater, Last Resort, Focus Punch, False Swipe, Struggle).
3. R8 dominance pruning: move B is dropped when another legal move A has the same type, category,
   accuracy and priority, strictly higher power, B's effect is the plain BATTLE_EFFECT_HIT, and A's
   effect is plain HIT or a chance-based secondary effect (effect_chance > 0, i.e. no drawback).
4. Per-move value vs the League: v(m, o) = power x hit chance x STAB weight 1.5 (if the move's type
   is one of the member's types) x the member's base Atk or SpA (by category) x a drawback/bonus weight
   (recharge/charge-turn 0.5, recoil 0.85, user stat drop 0.75-0.95, lock-in/crash 0.8, multi-hit x3,
   hit-twice x2) x the decomp type-chart multiplier against opponent mon o's types
   (sTypeMatchupMultipliers, battle_lib.c). Opponent weights: Elite Four mons 1, Cynthia's mons 2
   (FR-017: the Champion dominates failures). These weights are policy/search tuning, not game facts.
5. A moveset's coverage score = sum over opponent mons of weight x max over its moves of v(m, o). The
   top `POOL` moves by individual score are combined 4 at a time; the best `K_MOVESETS` sets that differ
   pairwise in at least 2 moves become the member's moveset candidates. The best `RANKED` combos are
   kept in order: when a team cannot be built because an earlier member took the last copy of a TM or
   item, `resources.repair` falls back to that member's next-best combo that can be built.
6. Setup variant: if the member can legally learn a self-boosting status move that the expectimax2-v2
   player models (its SELF_BOOSTS table, parsed from sim/policy/expectimax2.mjs so the two cannot
   drift), one extra moveset = the best 3-move coverage subset + the best such boost move (score:
   stages of the member's better attacking stat x1, Speed x0.5, defenses x0.25). greedy-v1 never uses
   status moves, so setup variants are NOT screened by greedy: they are tested with expectimax2-v2 in
   the optimizer's setup check (run.py), and kept only if significantly better.
   Fewer than 4 attacks available: the set is filled with the best boost move, then shortened.

Held-item candidates (FR-006, FR-006a)
--------------------------------------
Per moveset: (a) the best HP-restoring berry with HOLD_EFFECT_HP_PCT_RESTORE (Sitrus Berry in the
decomp data) if the ledger has a pre-Champion copy; (b) the type-boosting item (sTypeBoostingItems,
battle_lib.c) for the type of the moveset's highest-scoring move, preferring an item with unlimited
copies. Experience items (Lucky Egg, Exp. Share, Macho Brace) are never candidates: they raise the
final level the objective minimises. Copy limits are enforced team-wide by `resources.py`.
"""

from __future__ import annotations

import difflib
import itertools
import json
import re
from dataclasses import dataclass, field
from functools import cache
from typing import NamedTuple

from platsim.decomp.item_use import is_excluded_single_use
from platsim.decomp.items import load_items, tm_moves
from platsim.decomp.moves import load_moves
from platsim.decomp.stats import calc_stats
from platsim.decomp.weights import gyro_ball_power, return_power, species_weight_hg, weight_tier_power
from platsim.legality import movesources as MS
from platsim.optimizer.api import InvalidRequest
from platsim.pins import DECOMP_ROOT, REPO_ROOT

PP = DECOMP_ROOT
BATTLE_LIB_C = PP / "src" / "battle" / "battle_lib.c"
BATTLE_H = PP / "include" / "constants" / "battle.h"
EXPECTIMAX2 = REPO_ROOT / "sim" / "policy" / "expectimax2.mjs"
TRAINERS_JSON = REPO_ROOT / "data" / "generated" / "trainers.json"
GAUNTLET_KEYS = ("elite_four_aaron", "elite_four_bertha", "elite_four_flint", "elite_four_lucian", "champion_cynthia")
CHAMPION_WEIGHT = 2.0  # FR-017 emphasis (search tuning)
POOL = 10  # damaging moves combined per member
K_MOVESETS = 3
RANKED = 210  # combos kept for resource-conflict repair (resources.repair); C(POOL, 4) = all of them
STAB_WEIGHT = 1.5  # heuristic weight (search tuning)
PLAIN = "BATTLE_EFFECT_HIT"
# Attacks that only work under a condition the search cannot arrange (heuristic): first turn only,
# target asleep / user asleep, all other moves used, user not hit first, user faints, delayed hit.
EXCLUDED_ATTACK_EFFECTS = frozenset({
    "BATTLE_EFFECT_ONE_HIT_KO", "BATTLE_EFFECT_HALVE_DEFENSE", "BATTLE_EFFECT_HIT_IN_3_TURNS",
    "BATTLE_EFFECT_ALWAYS_FLINCH_FIRST_TURN_ONLY", "BATTLE_EFFECT_DAMAGE_WHILE_ASLEEP",
    "BATTLE_EFFECT_FAIL_IF_NOT_USED_ALL_OTHER_MOVES", "BATTLE_EFFECT_HIT_LAST_WHIFF_IF_HIT",
    "BATTLE_EFFECT_RECOVER_DAMAGE_SLEEP", "BATTLE_EFFECT_STRUGGLE", "BATTLE_EFFECT_LEAVE_WITH_1_HP",
})
EFFECT_WEIGHT = {
    "BATTLE_EFFECT_RECHARGE_AFTER": 0.5,
    "BATTLE_EFFECT_SKIP_CHARGE_TURN_IN_SUN": 0.5,
    "BATTLE_EFFECT_FLY": 0.5, "BATTLE_EFFECT_DIG": 0.5, "BATTLE_EFFECT_DIVE": 0.5, "BATTLE_EFFECT_BOUNCE": 0.5,
    "BATTLE_EFFECT_SHADOW_FORCE": 0.5, "BATTLE_EFFECT_CHARGE_TURN_DEF_UP": 0.5,
    "BATTLE_EFFECT_CHARGE_TURN_HIGH_CRIT": 0.5, "BATTLE_EFFECT_CHARGE_TURN_HIGH_CRIT_FLINCH": 0.5,
    "BATTLE_EFFECT_RECOIL_HALF": 0.85, "BATTLE_EFFECT_RECOIL_THIRD": 0.85, "BATTLE_EFFECT_RECOIL_QUARTER": 0.85,
    "BATTLE_EFFECT_RECOIL_BURN_HIT": 0.85, "BATTLE_EFFECT_RECOIL_PARALYZE_HIT": 0.85,
    "BATTLE_EFFECT_USER_SP_ATK_DOWN_2": 0.75, "BATTLE_EFFECT_DEF_SPD_DOWN_HIT": 0.95,
    "BATTLE_EFFECT_LOWER_OWN_ATK_AND_DEF": 0.9, "BATTLE_EFFECT_CONTINUE_AND_CONFUSE_SELF": 0.8,
    "BATTLE_EFFECT_CRASH_ON_MISS": 0.8, "BATTLE_EFFECT_DOUBLE_POWER_EACH_TURN_LOCK_INTO": 0.5,
    "BATTLE_EFFECT_MULTI_HIT": 3.0, "BATTLE_EFFECT_HIT_TWICE": 2.0, "BATTLE_EFFECT_POISON_MULTI_HIT": 2.0,
}
EXP_HOLD_EFFECTS = frozenset({"HOLD_EFFECT_EXP_UP", "HOLD_EFFECT_EXP_SHARE", "HOLD_EFFECT_LVLUP_SPEED_DOWN"})
HP_BERRY_EFFECT = "HOLD_EFFECT_HP_PCT_RESTORE"
# 014: plain damage boosters, applied by the battle player's damage model (sim/damage.mjs:381-382, :639)
POWER_UP_SE = "HOLD_EFFECT_POWER_UP_SE"  # Expert Belt: super-effective hits
POWER_UP_BY_CLASS = {"CLASS_PHYSICAL": "HOLD_EFFECT_POWER_UP_PHYS", "CLASS_SPECIAL": "HOLD_EFFECT_POWER_UP_SPEC"}

# 024: variable-power moves (data power 1) the optimizer offers, scored at the power the game computes (research R4):
# Return at max friendship (the simulator's assumption, as legality's), Grass Knot / Low Kick from the opponent's weight
# tier (the decomp boundary rule, decomp/weights.py), Gyro Ball from the member's speed at the candidate level (IV 15,
# EV 85, Hardy: the team defaults) against the opponent's speed at its level (its iv, EV 0, its nature).
FRIENDSHIP = 255
OFFERED_VARIABLE = frozenset({"MOVE_RETURN", "MOVE_GRASS_KNOT", "MOVE_LOW_KICK", "MOVE_GYRO_BALL"})
# Not offered, with the reason (documented in the README; asserted absent by tests/unit/test_variable_power.py).
NOT_OFFERED_VARIABLE = {
    "MOVE_HIDDEN_POWER": "IVs are a uniform 15 by assumption (user, 2026-10-19); its type and power would be fixed by that",
    "MOVE_FRUSTRATION": "power 1 at friendship 255",
    "MOVE_MAGNITUDE": "no player computes its power", "MOVE_WRING_OUT": "no player computes its power",
    "MOVE_CRUSH_GRIP": "no player computes its power", "MOVE_PUNISHMENT": "no player computes its power",
    "MOVE_FLAIL": "no player computes its power", "MOVE_REVERSAL": "no player computes its power",
    "MOVE_FLING": "no player computes its power", "MOVE_TRUMP_CARD": "no player computes its power",
    "MOVE_NATURAL_GIFT": "no player computes its power", "MOVE_PRESENT": "no player computes its power",
    "MOVE_SPIT_UP": "no player computes its power",
    "(fixed damage, OHKO, counters)": "not attacks for candidate scoring (data power 1, excluded by is_attack as today)",
}
# 025 (H4): the critical-hit stage table of the game (battle_lib.c sCriticalStageRates, :7097-7103: a critical hit at
# 1 in 16, 8, 4, 3, 2 by stage; BattleSystem_CalcCriticalMulti :7105-7135 doubles damage), read from the decomp by name like
# the type chart; the stage counts the move's high-critical-ratio effect and, under item-conditioned valuation, the held
# item (HOLD_EFFECT_CRITRATE_UP: Razor Claw, Scope Lens). Abilities are not counted here (plan, Complexity: none).
def _crit_stage_rates() -> tuple[int, ...]:
    text = BATTLE_LIB_C.read_text()
    body = text[text.index("sCriticalStageRates[] = {"):]
    body = body[:body.index("};")]
    rates = tuple(int(x) for x in re.findall(r"(\d+)\s*,", body))
    if len(rates) < 5:
        raise ValueError(f"sCriticalStageRates: expected 5 stages, parsed {rates}")
    return rates


CRIT_STAGE_RATES: tuple[int, ...] = _crit_stage_rates()
MAX_CRIT_STAGE = 4
ACCURACY_UP_EFFECT = "HOLD_EFFECT_ACCURACY_UP"
CRITRATE_UP_EFFECT = "HOLD_EFFECT_CRITRATE_UP"
ACCURACY_UP_PARAM_DEFAULT = 10  # Wide Lens's decomp param; used only if no ACCURACY_UP item is in the data


def is_high_crit(effect: str) -> bool:
    return "HIGH_CRITICAL" in effect


def crit_stage(move, item_effect: str | None) -> int:
    stage = (1 if is_high_crit(move.effect) else 0) + (1 if item_effect == CRITRATE_UP_EFFECT else 0)
    return min(stage, MAX_CRIT_STAGE)


def crit_term(stage: int) -> float:
    """Expected-damage multiplier of critical hits at `stage`: 1 + P(crit), a crit doubling damage."""
    return 1.0 + 1.0 / CRIT_STAGE_RATES[min(stage, MAX_CRIT_STAGE)]


# 025: move effects that are a pure cost to the user (the dominance rule's cost class; each with its reason). A move with a
# cost effect loses on the effect axis to a plain move or to one with a secondary; two different secondaries are incomparable.
# Self stat drops are costs by the owner's decision (spec clarification 3): the drop lasts only until the user switches, which
# the battle player's model prices (sim/test/switch_reset.test.mjs pins the reset).
EFFECT_COSTS: dict[str, str] = {
    "BATTLE_EFFECT_DIG": "charge turn (two-turn move)", "BATTLE_EFFECT_FLY": "charge turn", "BATTLE_EFFECT_DIVE": "charge turn",
    "BATTLE_EFFECT_BOUNCE": "charge turn", "BATTLE_EFFECT_SKIP_CHARGE_TURN_IN_SUN": "charge turn (Solar Beam)",
    "BATTLE_EFFECT_CHARGE_TURN_DEF_UP": "charge turn (Skull Bash)", "BATTLE_EFFECT_CHARGE_TURN_HIGH_CRIT": "charge turn (Sky Attack)",
    "BATTLE_EFFECT_CHARGE_TURN_HIGH_CRIT_FLINCH": "charge turn", "BATTLE_EFFECT_SHADOW_FORCE": "charge turn",
    "BATTLE_EFFECT_RECHARGE_AFTER": "recharge turn (Hyper Beam, Giga Impact)",
    "BATTLE_EFFECT_RECOIL_HALF": "recoil", "BATTLE_EFFECT_RECOIL_THIRD": "recoil", "BATTLE_EFFECT_RECOIL_QUARTER": "recoil",
    "BATTLE_EFFECT_RECOIL_BURN_HIT": "recoil (Flare Blitz)", "BATTLE_EFFECT_RECOIL_PARALYZE_HIT": "recoil (Volt Tackle)",
    "BATTLE_EFFECT_USER_SP_ATK_DOWN_2": "self stat drop (Overheat, Draco Meteor, Leaf Storm, Psycho Boost)",
    "BATTLE_EFFECT_LOWER_OWN_ATK_AND_DEF": "self stat drop (Superpower)",
    "BATTLE_EFFECT_DEF_SPD_DOWN_HIT": "self stat drop (Close Combat)",
    "BATTLE_EFFECT_SPEED_DOWN_HIT": "self stat drop (Hammer Arm)",
    "BATTLE_EFFECT_CONTINUE_AND_CONFUSE_SELF": "locks in and confuses the user (Outrage, Thrash, Petal Dance)",
    "BATTLE_EFFECT_CRASH_ON_MISS": "crash damage on a miss (Jump Kick)",
    "BATTLE_EFFECT_DOUBLE_POWER_EACH_TURN_LOCK_INTO": "locks in (Rollout, Ice Ball)",
    "BATTLE_EFFECT_HIT_IN_3_TURNS": "delayed hit (Future Sight)",
    "BATTLE_EFFECT_ALWAYS_FLINCH_FIRST_TURN_ONLY": "first turn only (Fake Out)",
    "BATTLE_EFFECT_RECOVER_DAMAGE_SLEEP": "only while the target sleeps (Dream Eater)",
    "BATTLE_EFFECT_HIT_LAST_WHIFF_IF_HIT": "fails when hit first (Focus Punch)",
    "BATTLE_EFFECT_LEAVE_WITH_1_HP": "the user faints (Explosion, Self-Destruct)",
}


def effect_class(effect: str) -> str:
    if effect == PLAIN:
        return "plain"
    return "cost" if effect in EFFECT_COSTS else "secondary"


MEMBER_IVS = {k: 15 for k in ("hp", "atk", "def", "spa", "spd", "spe")}
MEMBER_EVS = {k: 85 for k in ("hp", "atk", "def", "spa", "spd", "spe")}
MEMBER_NATURE = "NATURE_HARDY"


# ---------------------------------------------------------------------------------------------
# Decomp tables


@cache
def type_chart() -> dict[tuple[str, str], float]:
    """(attacking type, defending type) -> multiplier, from sTypeMatchupMultipliers (battle_lib.c);
    values TYPE_MULTI_* from include/constants/battle.h divided by 10 (comment above the table)."""
    defs = dict(re.findall(r"#define (TYPE_MULTI_\w+)\s+(\d+)", BATTLE_H.read_text()))
    text = BATTLE_LIB_C.read_text()
    body = text[text.index("sTypeMatchupMultipliers[][3] = {"):]
    body = body[:body.index("};")]
    out = {}
    for a, d, m in re.findall(r"\{\s*(TYPE_\w+),\s*(TYPE_\w+),\s*(TYPE_MULTI_\w+)\s*\}", body):
        out[(a, d)] = int(defs[m]) / 10
    if not out:
        raise RuntimeError("type chart not found in battle_lib.c")
    return out


def type_mult(atk: str, defender_types) -> float:
    chart = type_chart()
    m = 1.0
    for t in dict.fromkeys(defender_types):
        m *= chart.get((atk, t), 1.0)
    return m


@cache
def type_boost_items() -> dict[str, list[str]]:
    """TYPE_* -> [hold effect] from sTypeBoostingItems (battle_lib.c)."""
    text = BATTLE_LIB_C.read_text()
    body = text[text.index("sTypeBoostingItems[] = {"):]
    body = body[:body.index("};")]
    out: dict[str, list[str]] = {}
    for eff, t in re.findall(r"\{\s*(HOLD_EFFECT_\w+),\s*(TYPE_\w+)\s*\}", body):
        out.setdefault(t, []).append(eff)
    return out


@cache
def expectimax_self_boosts() -> dict[str, dict[str, int]]:
    """Effect name (without BATTLE_EFFECT_) -> stat stages, parsed from expectimax2.mjs SELF_BOOSTS."""
    text = EXPECTIMAX2.read_text()
    body = text[text.index("const SELF_BOOSTS = {"):]
    body = body[:body.index("};")]
    out = {}
    for name, stats in re.findall(r"(\w+): \{([^}]*)\}", body):
        out[name] = {k: int(v) for k, v in re.findall(r"(\w+): (-?\d+)", stats)}
    if not out:
        raise RuntimeError("SELF_BOOSTS not found in sim/policy/expectimax2.mjs")
    return out


class LeagueOpponent(NamedTuple):
    species: str
    types: tuple[str, ...]
    weight: float
    level: int  # 024
    iv: int  # 024: trainers.json's single IV for every stat
    nature: str  # 024: NATURE_*


@cache
def league_opponents() -> tuple[LeagueOpponent, ...]:
    """(species, types, weight, level, iv, nature) for every mon of the five gauntlet trainers (trainers.json); the first
    three positions as before feature 024."""
    data = json.loads(TRAINERS_JSON.read_text())["trainers"]
    by_key = {t["key"]: t for t in data}
    out = []
    for k in GAUNTLET_KEYS:
        w = CHAMPION_WEIGHT if k.startswith("champion") else 1.0
        for mon in by_key[k]["party"]:
            out.append(LeagueOpponent(mon["species"], tuple(MS.by_constant()[mon["species"]].types), w,
                                      int(mon["level"]), int(mon["iv"]), mon["nature"]))
    return tuple(out)


@cache
def _opponent_speed(opp: LeagueOpponent) -> int:
    base = MS.by_constant()[opp.species].base_stats
    ivs = {k: opp.iv for k in base}
    evs = {k: 0 for k in base}
    return calc_stats(base, ivs, evs, opp.level, opp.nature, opp.species)["spe"]


@cache
def _member_speed(const_member: str, level: int) -> int:
    base = MS.by_constant()[const_member].base_stats
    return calc_stats(base, MEMBER_IVS, MEMBER_EVS, level, MEMBER_NATURE, const_member)["spe"]


def variable_power(move_const: str, const_member: str, member_level: int, opp: LeagueOpponent) -> int | None:
    """024: the game's power of an offered variable-power move against `opp`; None for every other move."""
    if move_const not in OFFERED_VARIABLE:
        return None
    if move_const == "MOVE_RETURN":
        return return_power(FRIENDSHIP)
    if move_const in ("MOVE_GRASS_KNOT", "MOVE_LOW_KICK"):
        return weight_tier_power(species_weight_hg(opp.species))
    return gyro_ball_power(_member_speed(const_member, member_level), _opponent_speed(opp))


# ---------------------------------------------------------------------------------------------
# Species resolution


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


@cache
def _name_index() -> dict[str, str]:
    from platsim.legality.validator import _species_index

    return dict(_species_index())


def display_name(const: str) -> str:
    return MS.species_name(const) if const in MS.by_constant() else const


def unavailable_reason(const: str, led) -> str | None:
    """None if `const` has a pre-Champion source option; otherwise a user-facing reason."""
    from platsim.availability.ledger import NEVER, POST

    if const not in MS.by_constant():
        return "alternate forms are not modelled by the availability ledger (rejected conservatively)"
    if MS.source_options(const, led):
        return None
    name = display_name(const)
    trade_ok = MS.options_of(led).allow_trade_evolutions
    trade = [(p, ev) for p, ev in MS._preds().get(const, []) if ev.method in MS.TRADE_METHODS]
    if trade:
        p, ev = trade[0]
        held = f" holding {ev.param}" if isinstance(ev.param, str) else ""
        if not trade_ok:
            return f"{name} is only reachable by trade evolution from {display_name(p)} ({ev.method}{held}), " \
                   "which needs a second cartridge (FR-005; allow it with --allow-trade-evolutions)"
        miss = ([f"{display_name(p)} has no pre-Champion source"] if not MS.source_options(p, led) else []) + \
               ([f"{ev.param} has no pre-Champion copy"] if held and led.item_copies(ev.param) == 0 else [])
        return f"{name} is only reachable by trade evolution from {display_name(p)} ({ev.method}{held}); trade " \
               f"evolutions are allowed, but {'; '.join(miss) or 'no pre-Champion path reaches it'}"
    # walk the pre-evolution chain for post-game / unobtainable entries
    chain, todo = [], [const]
    while todo:
        c = todo.pop()
        if c in chain:
            continue
        chain.append(c)
        todo += [p for p, ev in MS._preds().get(c, []) if trade_ok or ev.method not in MS.TRADE_METHODS]
    post, never = [], []
    for c in led.entries:
        if c.entry.subject in chain or getattr(c.entry, "via_species", None) in chain:
            if c.phase == POST:
                post.append(f"{c.entry.kind} {c.entry.map_header}: {'; '.join(c.reasons[:2])}")
            elif c.phase == NEVER:
                never.append(f"{c.entry.kind} {c.entry.map_header}: {'; '.join(c.reasons[:2])}")
    if post:
        return f"{name} is only obtainable post-game (FR-003/FR-003a): " + " | ".join(post[:3])
    if never:
        return f"{name} is unobtainable on one cartridge: " + " | ".join(never[:3])
    return f"{name} has no pre-Champion source (no wild, gift, egg, static, NPC trade, breeding or " \
           "non-trade evolution source; National Dex sources excluded)"


def resolve_species(names, led) -> list[str]:
    """Six names/keys/constants -> SPECIES_* constants, or InvalidRequest naming every problem."""
    names = list(names)
    reasons: dict[str, str] = {}
    out: list[str] = []
    if len(names) != 6:
        raise InvalidRequest(f"exactly 6 species are required, got {len(names)}", {})
    idx = _name_index()
    for n in names:
        const = idx.get(_norm(str(n)))
        if const is None:
            cands = difflib.get_close_matches(_norm(str(n)), list(idx), n=5, cutoff=0.6)
            shown = list(dict.fromkeys(display_name(idx[c]) for c in cands))
            reasons[str(n)] = "unknown species" + (f"; closest matches: {', '.join(shown)}" if shown else "")
            continue
        why = unavailable_reason(const, led)
        if why:
            reasons[str(n)] = why
            continue
        out.append(const)
    if reasons:
        msg = "; ".join(f"{k}: {v}" for k, v in reasons.items())
        raise InvalidRequest(f"invalid species: {msg}", reasons)
    # 004 FR-004: one choice per choose-one group (one starter line, one fossil Trainer ID).
    clash = MS.team_group_conflicts(out, led)
    if clash:
        reasons = {str(n): clash[c] for n, c in zip(names, out) if c in clash}
        raise InvalidRequest(f"invalid species: {'; '.join(dict.fromkeys(reasons.values()))}", reasons)
    return out


# ---------------------------------------------------------------------------------------------
# Variants and move pools


@dataclass(frozen=True)
class Variant:
    """A battle-relevant group of source options of one species (see module doc)."""

    species: str  # SPECIES_*
    key: str  # "own" or the NPC-trade option id
    option_ids: tuple[str, ...]
    traded: bool

    def options(self, led) -> list:
        ids = set(self.option_ids)
        return [o for o in MS.source_options(self.species, led) if o.id in ids]


def variants(const: str, led) -> list[Variant]:
    opts = MS.source_options(const, led)
    own = tuple(o.id for o in opts if o.kind != "npc_trade")
    out = []
    if own:
        out.append(Variant(const, "own", own, False))
    for o in opts:
        if o.kind == "npc_trade":
            out.append(Variant(const, o.id, (o.id,), bool(o.fixed_mon and o.fixed_mon.get("is_traded"))))
    return out


def _moves_by_key() -> dict[str, object]:
    return load_moves()


def candidate_move_consts(variant: Variant, led) -> list[str]:
    """Every move some stage of some option could know (before the legality filter)."""
    sp = MS.by_constant()
    tms = tm_moves()
    out: list[str] = []
    for o in variant.options(led):
        for st in o.stages:
            s = sp[st.species]
            out += [mv for _, mv in s.learnset_level]
            out += [tms[m] for m in s.learnset_tm if m in tms]
            out += list(s.learnset_tutor)
        if o.kind == "breed":
            out += list(sp[o.stages[0].species].egg_moves)
    return list(dict.fromkeys(m for m in out if m in load_moves()))


def legal_moves(variant: Variant, level: int, led) -> list[str]:
    opts = variant.options(led)
    out = []
    for mv in candidate_move_consts(variant, led):
        if any(level >= o.min_level and MS.sources(variant.species, mv, level, led, o) for o in opts):
            out.append(mv)
    return out


def is_attack(mv) -> bool:
    return mv.power > 1 and mv.category != "CLASS_STATUS" and mv.effect not in EXCLUDED_ATTACK_EFFECTS


def _acc(m) -> int:
    return 101 if m.accuracy == 0 else m.accuracy  # 0 means "never misses" in the data


def _effect_order(a, b) -> tuple[bool, bool] | None:
    """(at least as good, strictly better) of a's effect against b's, or None when incomparable."""
    if a.effect == b.effect:
        return a.effect_chance >= b.effect_chance, a.effect_chance > b.effect_chance
    ca, cb = effect_class(a.effect), effect_class(b.effect)
    if cb == "cost" and ca != "cost":
        return True, True
    if cb == "plain" and ca == "secondary":
        return True, True
    return None


def dominance_axes(a, b) -> list[str] | None:
    """025 (widening the R8 rule, dominance assessment): the axes on which `a` is strictly better than `b`, when `a` is at
    least as good on every axis (same type and category; power, accuracy, priority, PP, effect) and strictly better on one;
    None otherwise."""
    if a.type != b.type or a.category != b.category:
        return None
    if not (a.power >= b.power and _acc(a) >= _acc(b) and a.priority >= b.priority and a.pp >= b.pp):
        return None
    eff = _effect_order(a, b)
    if eff is None or not eff[0]:
        return None
    axes = [name for name, gt in (("power", a.power > b.power), ("accuracy", _acc(a) > _acc(b)),
                                  ("priority", a.priority > b.priority), ("PP", a.pp > b.pp), ("effect", eff[1])) if gt]
    return axes or None


def dominates(a, b) -> bool:
    """Strict dominance: same type and category, at least as good on power, accuracy, priority, PP and effect, strictly
    better on one (R8 widened by feature 025 with PP and the effect cost class)."""
    return dominance_axes(a, b) is not None


def prune(move_consts: list[str]) -> tuple[list[str], dict[str, str]]:
    """Damaging moves after dominance pruning; and {dropped move: reason naming the winner and the axes}."""
    mv = load_moves()
    attacks = [m for m in move_consts if is_attack(mv[m])]
    dropped = {}
    kept = []
    for b in attacks:
        dom = next(((a, dominance_axes(mv[a], mv[b])) for a in attacks if a != b and dominates(mv[a], mv[b])), None)
        if dom:
            dropped[b] = (f"dominated by {dom[0]} (same type/category; at least as good on power, accuracy, priority, PP, "
                          f"effect; better: {', '.join(dom[1])})")
        else:
            kept.append(b)
    return kept, dropped


@cache
def _accuracy_up_param() -> int:
    for it in load_items().values():
        if it.hold_effect == ACCURACY_UP_EFFECT:
            return int(it.effect_param)
    return ACCURACY_UP_PARAM_DEFAULT


def move_value(const_member: str, move_const: str, member_level: int = 100, item_effect: str | None = None) -> list[float]:
    """v(m, o) for every League opponent mon (module doc, step 4), in league_opponents() order. 024: the power is
    the data power for fixed-power moves and the game's computed power per opponent for the offered variable-power
    moves (`variable_power`), which is why the member's level is needed (Gyro Ball). 025: every value carries the
    critical-hit term of the move's crit stage; under `item_effect` the valuation is item-conditioned: HOLD_EFFECT_ACCURACY_UP
    raises the accuracy factor (capped at 1), HOLD_EFFECT_CRITRATE_UP raises the crit stage."""
    m = load_moves()[move_const]
    sp = MS.by_constant()[const_member]
    acc = 1.0 if m.accuracy == 0 else m.accuracy / 100
    if item_effect == ACCURACY_UP_EFFECT and m.accuracy != 0:
        acc = min(1.0, acc * (100 + _accuracy_up_param()) / 100)
    crit = crit_term(crit_stage(m, item_effect))
    stab = STAB_WEIGHT if m.type in sp.types else 1.0
    stat = sp.base_stats["atk"] if m.category == "CLASS_PHYSICAL" else sp.base_stats["spa"]
    effw = EFFECT_WEIGHT.get(m.effect, 1.0)
    out = []
    for opp in league_opponents():
        power = variable_power(move_const, const_member, member_level, opp)
        # the same multiplication order as before 024, so fixed-power values are bit-identical (tie order in ranked lists)
        base = (m.power if power is None else power) * acc * stab * stat * effw
        out.append(opp.weight * base * type_mult(m.type, opp.types) * crit)
    return out


def coverage(vals: list[list[float]]) -> float:
    return sum(max(col) for col in zip(*vals)) if vals else 0.0


# ---- 026: candidate sets by marginal coverage (spec FR-001 to FR-006; research R1 to R3) ---------------------------
NO_LIVE_REASON = "no better option: its two strongest moves cover every League opponent"


_COV_CACHE: dict[tuple, float] = {}


def _cov(moves, vals: dict[str, list[float]]) -> float:
    """coverage() of a set of moves, memoised per value table (the dead-move repair asks for the same subsets many times)."""
    k = (id(vals), frozenset(moves))
    c = _COV_CACHE.get(k)
    if c is None:
        if len(_COV_CACHE) > 200000:
            _COV_CACHE.clear()
        c = _COV_CACHE[k] = coverage([vals[m] for m in moves])
    return c


def marginal(move: str, moveset, vals: dict[str, list[float]]) -> float:
    """A move's marginal contribution to a set: the set's coverage minus the coverage of the set without it."""
    ms = list(moveset)
    return _cov(ms, vals) - _cov([m for m in ms if m != move], vals)


def dead_moves(moveset, vals: dict[str, list[float]]) -> list[str]:
    """The moves of a set that are never the best choice against any opponent given the set's other moves. A tie between
    two moves (equal values everywhere, Aerial Ace and Pluck) counts for the one first by name, so only the other is dead."""
    ms = list(moveset)
    out = []
    for m in ms:
        best_somewhere = False
        for i, v in enumerate(vals[m]):
            if v <= 0:
                continue
            if all(vals[o][i] < v or (vals[o][i] == v and o > m) for o in ms if o != m):
                best_somewhere = True
                break
        if not best_somewhere:
            out.append(m)
    return out


def live_moves(cands: list[str], vals: dict[str, list[float]], scores: dict[str, float]) -> list[str]:
    """Moves that are the best choice against at least one opponent given the member's two strongest moves by score."""
    top2 = sorted(cands, key=lambda m: (-scores[m], m))[:2]
    return [m for m in cands if m not in top2 and marginal(m, top2 + [m], vals) > 0]


def takeover(move: str, moveset, vals: dict[str, list[float]]) -> set[int]:
    """Opponent indexes where `move` would be the best move of `moveset` + move (strictly better than every member)."""
    ms = [m for m in moveset if m != move]
    out = set()
    for i, v in enumerate(vals[move]):
        best = max((vals[m][i] for m in ms), default=0.0)
        if v > best:
            out.add(i)
    return out


# The cost class of 025 (EFFECT_COSTS) split into two tiers for pool entry (FR-006; a refinement found on Staraptor, where the
# single-tier rule locked Close Combat out while keeping Fly in): a TURN cost (charge turn, recharge, lock-in, delayed hit,
# first-turn-only, sleep-only, fails-when-hit, the user faints) is a move a competent player does not click when a cost-free
# move already hits the opponent, so it enters only for opponents no cost-free move hits at all (an immunity); a DAMAGE cost
# (recoil, a self stat drop, crash damage) is an accepted price, so it is compared with cost-free candidates only: it enters when
# it answers an opponent no cost-free candidate answers. Dominance (prune) keeps the single class.
TURN_COST_EFFECTS = frozenset({
    "BATTLE_EFFECT_DIG", "BATTLE_EFFECT_FLY", "BATTLE_EFFECT_DIVE", "BATTLE_EFFECT_BOUNCE", "BATTLE_EFFECT_SKIP_CHARGE_TURN_IN_SUN",
    "BATTLE_EFFECT_CHARGE_TURN_DEF_UP", "BATTLE_EFFECT_CHARGE_TURN_HIGH_CRIT", "BATTLE_EFFECT_CHARGE_TURN_HIGH_CRIT_FLINCH",
    "BATTLE_EFFECT_SHADOW_FORCE", "BATTLE_EFFECT_RECHARGE_AFTER", "BATTLE_EFFECT_CONTINUE_AND_CONFUSE_SELF",
    "BATTLE_EFFECT_DOUBLE_POWER_EACH_TURN_LOCK_INTO", "BATTLE_EFFECT_HIT_IN_3_TURNS", "BATTLE_EFFECT_ALWAYS_FLINCH_FIRST_TURN_ONLY",
    "BATTLE_EFFECT_RECOVER_DAMAGE_SLEEP", "BATTLE_EFFECT_HIT_LAST_WHIFF_IF_HIT", "BATTLE_EFFECT_LEAVE_WITH_1_HP"})


def cost_tier(move: str) -> str | None:
    """'turn' | 'damage' | None for a move constant (the EFFECT_COSTS class split for pool entry)."""
    eff = load_moves()[move].effect
    if effect_class(eff) != "cost":
        return None
    return "turn" if eff in TURN_COST_EFFECTS else "damage"


def prefer_cost_free(candidates, moveset, vals, scores, cost_tier=None) -> str | None:
    """The move to add to `moveset` (R3): the candidate with the highest marginal contribution, ties by score then name,
    except for cost moves: a turn-cost move is allowed only for an opponent no cost-free move hits (neither a cost-free
    candidate's takeover nor a cost-free move already in the set with a positive value), a damage-cost move only for an
    opponent no cost-free candidate takes over; an allowed cost move is taken when its contribution is at least the best
    cost-free candidate's. None when no allowed candidate adds coverage."""
    tier = cost_tier or globals()["cost_tier"]
    ms = list(moveset)
    pos = [(m, marginal(m, ms + [m], vals)) for m in candidates if m not in ms]
    pos = [(m, g) for m, g in pos if g > 0]
    if not pos:
        return None
    key = lambda mg: (-mg[1], -scores[mg[0]], mg[0])  # noqa: E731
    free = sorted((x for x in pos if not tier(x[0])), key=key)
    cost = sorted((x for x in pos if tier(x[0])), key=key)
    if not cost:
        return free[0][0]
    covered_cand: set[int] = set()
    for m, _ in free:
        covered_cand |= takeover(m, ms, vals)
    n_opp = len(next(iter(vals.values())))
    covered_set = {i for i in range(n_opp) if any(vals[m][i] > 0 and not tier(m) for m in ms)}
    allowed = [(m, g) for m, g in cost
               if takeover(m, ms, vals) - covered_cand - (covered_set if tier(m) == "turn" else set())]
    if not free:
        return allowed[0][0] if allowed else None
    if allowed and allowed[0][1] >= free[0][1]:
        return allowed[0][0]
    return free[0][0]


def pool_by_marginal(cands: list[str], vals, scores, size: int = POOL, cost_tier=None) -> list[str]:
    """The pool built greedily by marginal contribution (FR-002): the first move by score; each next the one adding the most
    coverage to the pool so far (cost preference), ties by score then name; when nothing adds coverage, the rest by score."""
    if not cands:
        return []
    tier = cost_tier or globals()["cost_tier"]
    pool = [sorted(cands, key=lambda m: (-scores[m], m))[0]]
    while len(pool) < size and len(pool) < len(cands):
        rest = [m for m in cands if m not in pool]
        m = prefer_cost_free(rest, pool, vals, scores, cost_tier=tier)
        if m is None:  # nothing allowed adds coverage: fill by score, cost-free moves before cost moves
            m = sorted(rest, key=lambda x: (tier(x) is not None, -scores[x], x))[0]
        pool.append(m)
    return pool


def _rank_key(combo, vals, scores):
    """Coverage, then the standalone sum, then name (today's key; a marginal-sum tie-break was tried and dropped: a filler that
    backs nothing up maximises the other moves' marginals, so it rewarded the weakest filler)."""
    return (-_cov(combo, vals), -sum(scores[m] for m in combo), combo)


def rank_sets(pool: list[str], vals, scores, size: int = 4) -> list[tuple[str, ...]]:
    """Every `size`-move combination of the pool, best first by coverage, the standalone sum, name (FR-003)."""
    size = min(size, len(pool))
    return sorted(itertools.combinations(sorted(pool), size), key=lambda c: _rank_key(c, vals, scores))


def _repaired(combo, cands, vals, scores, cost_tier=None) -> tuple[str, ...]:
    """Replace each dead move by the legal move with the highest marginal contribution given the other moves (cost
    preference); repeats until the set is all-live or no replacement adds coverage (each replacement raises coverage)."""
    ms = list(combo)
    changed = True
    while changed:
        changed = False
        dead = set(dead_moves(ms, vals))
        for i, m in enumerate(ms):
            if m in dead:
                others = [x for j, x in enumerate(ms) if j != i]
                r = prefer_cost_free([c for c in cands if c not in ms], others, vals, scores, cost_tier=cost_tier)
                if r is not None:
                    ms[i] = r
                    changed = True
                    break
    return tuple(sorted(ms))


FILLER_REASON = ("no live replacement left: the set's other moves already cover every League opponent; nothing else it "
                 "learns is the best choice against any of them")


def filler_reason(cands, vals, scores) -> str:
    """The reason a set keeps a dead move: nothing live beyond the two strongest moves (NO_LIVE_REASON), or the set's live
    moves cover everyone and no legal move adds coverage (FILLER_REASON)."""
    return NO_LIVE_REASON if not live_moves(cands, vals, scores) else FILLER_REASON


def display_move(m: str) -> str:
    return load_moves()[m].name if m in load_moves() else m


def choose_sets(ranked, k: int, cands, vals, scores, cost_tier=None):
    """(sets, one_apart, reason) (R2, revised at implementation): every ranked combo has its dead moves replaced where a live
    legal move exists (a replacement raises coverage); the repaired sets are re-ranked by coverage; the next offered set is the
    best one at least two moves apart from those offered, unless an all-live set one move apart has strictly higher coverage
    (FR-004a). A set keeps a dead move only when no live replacement exists (filler, listed with `reason`); a set is never
    dropped for a lower-coverage all-live one."""
    repaired: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for combo in ranked:
        c = _repaired(combo, cands, vals, scores, cost_tier=cost_tier)
        if c not in seen:
            seen.add(c)
            repaired.append(c)
    repaired.sort(key=lambda c: _rank_key(c, vals, scores))
    repaired = [c for c in repaired if len(c) == len(ranked[0])] if ranked else repaired
    accepted: list[tuple[str, ...]] = []
    one_apart: list[tuple[str, ...]] = []

    def dist(c):
        return min((len(set(c) ^ set(p)) // 2 for p in accepted), default=99)

    cov = lambda c: _cov(c, vals)  # noqa: E731
    while len(accepted) < k:
        best2 = next((c for c in repaired if c not in accepted and dist(c) >= 2), None)
        best1 = next((c for c in repaired if c not in accepted and dist(c) == 1 and not dead_moves(c, vals)), None)
        if best2 is None and best1 is None:
            break
        # FR-004a (option B): the one-apart all-live set replaces a two-apart set only when that set carries a dead move
        # and the all-live set is at least as good as its live part
        if best1 is not None and (best2 is None or (dead_moves(best2, vals) and cov(best1) >= cov(best2))):
            accepted.append(best1)
            one_apart.append(best1)
        else:
            accepted.append(best2)
    reason = filler_reason(cands, vals, scores) if any(dead_moves(c, vals) for c in accepted) else None
    return accepted, one_apart, reason


def boost_score(const_member: str, move_const: str) -> float | None:
    eff = load_moves()[move_const].effect.removeprefix("BATTLE_EFFECT_")
    boosts = expectimax_self_boosts().get(eff)
    if not boosts:
        return None
    sp = MS.by_constant()[const_member]
    main = "atk" if sp.base_stats["atk"] >= sp.base_stats["spa"] else "spa"
    return (boosts.get(main, 0) + 0.5 * boosts.get("spe", 0)
            + 0.25 * (boosts.get("def", 0) + boosts.get("spd", 0)))


@dataclass
class MemberCandidates:
    species: str
    variant: Variant
    ref_level: int
    movesets: list[tuple[str, ...]]  # attack movesets (screened by greedy), best first
    setup_moveset: tuple[str, ...] | None  # tested by expectimax2 (run.py setup check)
    items: dict[tuple[str, ...], list[str | None]]  # moveset -> held-item candidates (item keys)
    ranked: list[tuple[str, ...]] = field(default_factory=list)  # all combos, best first (repair order)
    pool: list[str] = field(default_factory=list)
    pruned: dict[str, str] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    variable_offered: list[str] = field(default_factory=list)  # 024: the member's legal offered variable-power moves
    extras: int = 0  # how many of `movesets` are appended sets (024 variable-power and 025 item-conditioned): the last `extras`
    items_extra: dict[tuple[str, ...], list[str]] = field(default_factory=dict)  # 025: appended items per base/024 set
    item_extras: dict[tuple[str, ...], str] = field(default_factory=dict)  # 025: item-conditioned extra set -> its item
    extra_kind: dict[tuple[str, ...], str] = field(default_factory=dict)  # appended set -> variable_power | accuracy_item | crit_item
    extras_by_kind: dict[str, int] = field(default_factory=dict)
    dead_moves: dict[tuple[str, ...], list[str]] = field(default_factory=dict)  # 026: per offered base set (expected empty)
    no_live_reason: str | None = None  # 026: set when a set with dead moves was accepted (FR-005)
    one_apart: list[tuple[str, ...]] = field(default_factory=list)  # 026: sets accepted one move apart (FR-004a)
    unavailable: frozenset = frozenset()  # 026: moves the team allocation took away (story 3)

    def summary(self) -> dict:
        return {"species": self.species, "variant": self.variant.key, "ref_level": self.ref_level,
                "variable_offered": list(self.variable_offered), "extras": self.extras,
                "dead_moves": {"|".join(k): v for k, v in self.dead_moves.items()},
                "no_live_reason": self.no_live_reason, "one_apart": [list(x) for x in self.one_apart],
                "unavailable": sorted(self.unavailable),
                "extras_by_kind": dict(self.extras_by_kind),
                "items_extra": {"|".join(k): v for k, v in self.items_extra.items()},
                "item_extras": {"|".join(k): v for k, v in self.item_extras.items()},
                "movesets": [list(m) for m in self.movesets],
                "setup_moveset": list(self.setup_moveset) if self.setup_moveset else None,
                "items": {"|".join(k): v for k, v in self.items.items()},
                "ranked_count": len(self.ranked),
                "pool": self.pool, "pruned": self.pruned,
                "scores": {k: round(v, 1) for k, v in self.scores.items()}}


_ITEM_COPIES: dict[tuple[int, str], int | str] = {}


def _item_copies(led, const: str) -> int | str:
    k = (id(led), const)
    if k not in _ITEM_COPIES:
        _ITEM_COPIES[k] = led.item_copies(const)
    return _ITEM_COPIES[k]


def _item_for_effect(effect: str, led) -> str | None:
    """025: the offerable item with `effect` (a pre-Champion copy, not single-use): unlimited copies first, then by key."""
    found = []
    for it in load_items().values():
        if it.hold_effect == effect and _item_copies(led, it.const) != 0 and not is_excluded_single_use(it.key):
            found.append((_item_copies(led, it.const) != MS.UNLIMITED, it.key))
    return sorted(found)[0][1] if found else None


def extra_item_candidates(const_member: str, moveset: tuple[str, ...], led) -> list[str]:
    """025 (H4): items appended after today's candidates for a moveset: the ACCURACY_UP item when any attack can miss
    (0 < accuracy < 100), then the CRITRATE_UP item when the set has an attack; each only with a pre-Champion copy."""
    mv = load_moves()
    attacks = [m for m in moveset if is_attack(mv[m]) or m in OFFERED_VARIABLE]
    out: list[str] = []
    if any(0 < mv[m].accuracy < 100 for m in attacks):
        it = _item_for_effect(ACCURACY_UP_EFFECT, led)
        if it:
            out.append(it)
    if attacks:
        it = _item_for_effect(CRITRATE_UP_EFFECT, led)
        if it:
            out.append(it)
    return out


def held_item_candidates(const_member: str, moveset: tuple[str, ...], led,
                         team: tuple[str, ...] | None = None, level: int = 100) -> list[str | None]:
    """Held items worth trying: the best HP berry, a boost for the strongest attack, and (003 FR-009)
    Leftovers when this team may hold it: a wild holder (Munchlax / Snorlax) is on the team, or a
    non-holder copy exists (post-game items rule). `team` is the six SPECIES_* of the job.
    Then (014), for a moveset with an attack, the damage boosters with a copy: Expert Belt, and the
    physical / special booster matching the strongest attack's category; existing items keep their places.
    An item used up when it triggers is never offered unless it is a berry (013; the decomp reader
    platsim.decomp.item_use decides), whichever branch above proposed it."""
    from platsim.availability.ledger import TEAM_GATED_ITEMS, team_item_copies

    items = load_items()
    out: list[str | None] = []
    berries = sorted((it for it in items.values() if it.hold_effect == HP_BERRY_EFFECT
                      and _item_copies(led, it.const) != 0), key=lambda it: (-it.effect_param, it.key))
    if berries:
        out.append(berries[0].key)
    attacks = [m for m in moveset if is_attack(load_moves()[m]) or m in OFFERED_VARIABLE]  # 024
    if attacks:
        best = max(attacks, key=lambda m: (sum(move_value(const_member, m, level)), m))
        t = load_moves()[best].type
        effs = set(type_boost_items().get(t, []))
        boosts = [it for it in items.values() if it.hold_effect in effs and _item_copies(led, it.const) != 0
                  and it.hold_effect not in EXP_HOLD_EFFECTS]
        boosts.sort(key=lambda it: (_item_copies(led, it.const) != MS.UNLIMITED, -it.effect_param, it.key))
        if boosts:
            out.append(boosts[0].key)
    if team is not None:
        for const in TEAM_GATED_ITEMS:
            if team_item_copies(led, const, team) != 0:
                out.append(items[const].key)
    if attacks:
        for eff in (POWER_UP_SE, POWER_UP_BY_CLASS.get(load_moves()[best].category)):
            for it in sorted((it for it in items.values() if it.hold_effect == eff
                              and _item_copies(led, it.const) != 0), key=lambda it: it.key):
                if it.key not in out:
                    out.append(it.key)
    out = [it for it in out if not is_excluded_single_use(it)]
    return out or [None]


def member_candidates(const: str, variant: Variant, ref_level: int, led, k: int = K_MOVESETS,
                      team: tuple[str, ...] | None = None, unavailable: frozenset = frozenset()) -> MemberCandidates:
    level = max(ref_level, min(o.min_level for o in variant.options(led)))
    legal = [m for m in legal_moves(variant, level, led) if m not in unavailable]
    attacks, dropped = prune(legal)
    # 026: one value table over the attacks and the offered variable-power moves; the pool by marginal contribution
    variable = [m for m in legal if m in OFFERED_VARIABLE]
    cands = attacks + variable
    scores = {m: sum(move_value(const, m, level)) for m in cands}
    vals = {m: move_value(const, m, level) for m in cands}
    pool = pool_by_marginal(cands, vals, scores)
    size = min(4, len(pool))
    ranked_sets = rank_sets(pool, vals, scores, size)
    combos = [(*_rank_key(c, vals, scores)[:2], c) for c in ranked_sets]
    one_apart: list[tuple[str, ...]] = []
    no_live_reason = None
    if size == 4:
        chosen, one_apart, no_live_reason = choose_sets(ranked_sets, k, cands, vals, scores)
    else:
        chosen = []
        for combo in ranked_sets:
            if combo not in chosen:
                chosen.append(combo)
            if len(chosen) >= k:
                break
    boosts = sorted(((boost_score(const, m), m) for m in legal if boost_score(const, m)), key=lambda x: (-x[0], x[1]))
    setup = None
    if boosts and pool:
        best3 = min(((-coverage([vals[m] for m in c]), c) for c in itertools.combinations(sorted(pool), min(3, len(pool)))))[1]
        if len(best3) == 3:
            best3 = _repaired(best3, cands, vals, scores)
        setup = tuple(best3) + (boosts[0][1],)
    if not chosen:
        if boosts:
            chosen = [(boosts[0][1],)]
        else:  # nothing scoreable: any legal moves (still legal; validator re-checks)
            chosen = [tuple(sorted(legal)[:4])] if legal else []
    if not chosen:
        raise InvalidRequest(f"{display_name(const)}: no legal move at Lv {level}", {const: "no legal move"})
    # 024: extra sets carrying a variable-power move, appended AFTER today's sets (FR-006, FR-006a): combos over the pool
    # plus the member's offered variable moves, at least one variable move each, ranked by the 026 key, diverse among
    # themselves only and not already offered (026: a variable move may already be in a base set).
    extras: list[tuple[str, ...]] = []
    extra_combos: list[tuple[str, ...]] = []
    if variable and size == 4:
        wide = sorted(set(pool) | set(variable))
        ranked_extra = [c for c in itertools.combinations(wide, 4) if any(m in OFFERED_VARIABLE for m in c)]
        ranked_extra.sort(key=lambda c: _rank_key(c, vals, scores))
        extra_combos = [c for c in ranked_extra if c not in set(chosen)]
        for combo in extra_combos:
            if all(len(set(combo) ^ set(c)) // 2 >= 2 for c in extras):
                extras.append(combo)
            if len(extras) >= k:
                break
    # 025 (H4, FR-001a): item-conditioned extra sets. For each conditioning item the member can hold, re-value every attack
    # under the item, cut a pool and rank the four-move sets as today, and append up to k sets not already offered, diverse
    # among themselves; each is paired with the item. Lens-conditioned sets come before claw-conditioned ones.
    item_sets: list[tuple[tuple[str, ...], str, str]] = []
    extra_kind: dict[tuple[str, ...], str] = {c: "variable_power" for c in extras}
    if size == 4:
        mv = load_moves()
        conditioning = []
        if any(0 < mv[m].accuracy < 100 for m in cands):
            it = _item_for_effect(ACCURACY_UP_EFFECT, led)
            if it:
                conditioning.append(("accuracy_item", ACCURACY_UP_EFFECT, it))
        if cands:
            it = _item_for_effect(CRITRATE_UP_EFFECT, led)
            if it:
                conditioning.append(("crit_item", CRITRATE_UP_EFFECT, it))
        existing = set(chosen) | set(extras)
        for kind, effect, item in conditioning:
            vals_i = {m: move_value(const, m, level, item_effect=effect) for m in cands}
            sc_i = {m: sum(v) for m, v in vals_i.items()}
            pool_i = pool_by_marginal(cands, vals_i, sc_i)  # 026: the same pool and ranking rule under the item valuation
            ranked_i = rank_sets(pool_i, vals_i, sc_i, 4)
            picked: list[tuple[str, ...]] = []
            for c in ranked_i:
                if c in existing or any(len(set(c) ^ set(p)) // 2 < 2 for p in picked):
                    continue
                picked.append(c)
                if len(picked) >= k:
                    break
            for c in picked:
                item_sets.append((c, item, kind))
                existing.add(c)
                extra_kind[c] = kind
                for m in c:
                    scores.setdefault(m, sc_i[m])
    # order each moveset by score (stable display; worker order does not matter for legality)
    chosen = [tuple(sorted(c, key=lambda m: (-scores.get(m, 0), m))) for c in chosen]
    extras = [tuple(sorted(c, key=lambda m: (-scores.get(m, 0), m))) for c in extras]
    item_sets = [(tuple(sorted(c, key=lambda m: (-scores.get(m, 0), m))), item, kind) for c, item, kind in item_sets]
    extra_kind = {tuple(sorted(c, key=lambda m: (-scores.get(m, 0), m))): kind for c, kind in extra_kind.items()}
    if setup:
        setup = tuple(sorted(setup, key=lambda m: (-scores.get(m, 0), m)))
    ranked = [tuple(sorted(c, key=lambda m: (-scores.get(m, 0), m))) for *_, c in combos[:RANKED]]
    dead = {tuple(sorted(c, key=lambda m: (-scores.get(m, 0), m))): dead_moves(c, vals) for c in chosen}
    ranked += [tuple(sorted(c, key=lambda m: (-scores.get(m, 0), m))) for c in extra_combos]  # 024: prefix unchanged
    movesets = chosen + extras + [c for c, _, _ in item_sets]
    items = {ms: held_item_candidates(const, ms, led, team, level) for ms in chosen + extras + ([setup] if setup else [])}
    item_extras: dict[tuple[str, ...], str] = {}
    for c, item, _ in item_sets:
        usual = held_item_candidates(const, c, led, team, level)
        items[c] = [item] + [x for x in usual if x != item]
        item_extras[c] = item
    items_extra = {ms: extra_item_candidates(const, ms, led) for ms in chosen + extras}
    by_kind: dict[str, int] = {}
    for kind in extra_kind.values():
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return MemberCandidates(const, variant, level, movesets, setup, items, ranked, pool, dropped,
                            {m: scores[m] for m in pool + variable + [m for c, _, _ in item_sets for m in c] if m in scores},
                            variable_offered=variable, extras=len(extras) + len(item_sets),
                            items_extra=items_extra, item_extras=item_extras, extra_kind=extra_kind, extras_by_kind=by_kind,
                            dead_moves=dead, no_live_reason=no_live_reason,
                            one_apart=[tuple(sorted(c, key=lambda m: (-scores.get(m, 0), m))) for c in one_apart],
                            unavailable=frozenset(unavailable))


__all__ = ["MemberCandidates", "Variant", "candidate_move_consts", "choose_sets", "coverage", "dead_moves", "display_name", "dominates",
           "cost_tier", "filler_reason", "live_moves", "marginal", "pool_by_marginal", "prefer_cost_free", "rank_sets", "takeover",
           "held_item_candidates", "league_opponents", "legal_moves", "member_candidates", "prune",
           "resolve_species", "type_chart", "type_mult", "unavailable_reason", "variants"]
