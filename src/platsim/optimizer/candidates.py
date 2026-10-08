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
the Munchlax project rule (FR-006a), post-game only (FR-003 / FR-003a, with the ledger's own phase
reasons), or no source at all.

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

from platsim.decomp.items import load_items, tm_moves
from platsim.decomp.moves import load_moves
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


@cache
def league_opponents() -> tuple[tuple[str, tuple[str, ...], float], ...]:
    """(species, types, weight) for every mon of the five gauntlet trainers (trainers.json)."""
    data = json.loads(TRAINERS_JSON.read_text())["trainers"]
    by_key = {t["key"]: t for t in data}
    out = []
    for k in GAUNTLET_KEYS:
        w = CHAMPION_WEIGHT if k.startswith("champion") else 1.0
        for mon in by_key[k]["party"]:
            out.append((mon["species"], tuple(MS.by_constant()[mon["species"]].types), w))
    return tuple(out)


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
    from platsim.availability.ledger import EXCLUDED_SPECIES, NEVER, POST

    if const not in MS.by_constant():
        return "alternate forms are not modelled by the availability ledger (rejected conservatively)"
    if MS.source_options(const, led):
        return None
    name = display_name(const)
    if const in EXCLUDED_SPECIES:
        return f"{name} is excluded entirely by project rule (spec FR-006a, user decision 2026-10-07)"
    trade = [(p, ev) for p, ev in MS._preds().get(const, []) if ev.method in MS.TRADE_METHODS]
    if trade:
        p, ev = trade[0]
        held = f" holding {ev.param}" if isinstance(ev.param, str) else ""
        return f"{name} is only reachable by trade evolution from {display_name(p)} ({ev.method}{held}), " \
               "which needs a second cartridge (FR-005)"
    # walk the pre-evolution chain for post-game / excluded entries
    chain, todo = [], [const]
    while todo:
        c = todo.pop()
        if c in chain:
            continue
        chain.append(c)
        todo += [p for p, ev in MS._preds().get(c, []) if ev.method not in MS.TRADE_METHODS]
    post, never = [], []
    for c in led.entries:
        if c.entry.subject in chain or getattr(c.entry, "via_species", None) in chain:
            if c.phase == POST:
                post.append(f"{c.entry.kind} {c.entry.map_header}: {'; '.join(c.reasons[:2])}")
            elif c.phase == NEVER:
                never.append(f"{c.entry.kind} {c.entry.map_header}: {'; '.join(c.reasons[:2])}")
    if any(c in EXCLUDED_SPECIES for c in chain):
        return f"{name} is only obtainable through an excluded species (project rule, spec FR-006a)"
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


def dominates(a, b) -> bool:
    """R8 strict dominance (module doc, step 3)."""
    return (a.type == b.type and a.category == b.category and a.accuracy == b.accuracy
            and a.priority == b.priority and a.power > b.power and b.effect == PLAIN
            and (a.effect == PLAIN or a.effect_chance > 0))


def prune(move_consts: list[str]) -> tuple[list[str], dict[str, str]]:
    """Damaging moves after R8 pruning; and {dropped move: reason}."""
    mv = load_moves()
    attacks = [m for m in move_consts if is_attack(mv[m])]
    dropped = {}
    kept = []
    for b in attacks:
        dom = next((a for a in attacks if a != b and dominates(mv[a], mv[b])), None)
        if dom:
            dropped[b] = f"dominated by {dom} (same type/category/accuracy/priority, higher power, R8)"
        else:
            kept.append(b)
    return kept, dropped


def move_value(const_member: str, move_const: str) -> list[float]:
    """v(m, o) for every League opponent mon (module doc, step 4), in league_opponents() order."""
    m = load_moves()[move_const]
    sp = MS.by_constant()[const_member]
    acc = 1.0 if m.accuracy == 0 else m.accuracy / 100
    stab = STAB_WEIGHT if m.type in sp.types else 1.0
    stat = sp.base_stats["atk"] if m.category == "CLASS_PHYSICAL" else sp.base_stats["spa"]
    base = m.power * acc * stab * stat * EFFECT_WEIGHT.get(m.effect, 1.0)
    return [w * base * type_mult(m.type, types) for _, types, w in league_opponents()]


def coverage(vals: list[list[float]]) -> float:
    return sum(max(col) for col in zip(*vals)) if vals else 0.0


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

    def summary(self) -> dict:
        return {"species": self.species, "variant": self.variant.key, "ref_level": self.ref_level,
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


def held_item_candidates(const_member: str, moveset: tuple[str, ...], led) -> list[str | None]:
    items = load_items()
    out: list[str | None] = []
    berries = sorted((it for it in items.values() if it.hold_effect == HP_BERRY_EFFECT
                      and _item_copies(led, it.const) != 0), key=lambda it: (-it.effect_param, it.key))
    if berries:
        out.append(berries[0].key)
    attacks = [m for m in moveset if is_attack(load_moves()[m])]
    if attacks:
        best = max(attacks, key=lambda m: (sum(move_value(const_member, m)), m))
        t = load_moves()[best].type
        effs = set(type_boost_items().get(t, []))
        boosts = [it for it in items.values() if it.hold_effect in effs and _item_copies(led, it.const) != 0
                  and it.hold_effect not in EXP_HOLD_EFFECTS]
        boosts.sort(key=lambda it: (_item_copies(led, it.const) != MS.UNLIMITED, -it.effect_param, it.key))
        if boosts:
            out.append(boosts[0].key)
    return out or [None]


def member_candidates(const: str, variant: Variant, ref_level: int, led, k: int = K_MOVESETS) -> MemberCandidates:
    level = max(ref_level, min(o.min_level for o in variant.options(led)))
    legal = legal_moves(variant, level, led)
    attacks, dropped = prune(legal)
    scores = {m: sum(move_value(const, m)) for m in attacks}
    pool = sorted(attacks, key=lambda m: (-scores[m], m))[:POOL]
    vals = {m: move_value(const, m) for m in pool}
    size = min(4, len(pool))
    combos = []
    for combo in itertools.combinations(sorted(pool), size):
        combos.append((-coverage([vals[m] for m in combo]), -sum(scores[m] for m in combo), combo))
    combos.sort()
    chosen: list[tuple[str, ...]] = []
    for _, _, combo in combos:
        if all(len(set(combo) ^ set(c)) // 2 >= 2 or size < 4 for c in chosen):
            if combo not in chosen:
                chosen.append(combo)
        if len(chosen) >= k:
            break
    boosts = sorted(((boost_score(const, m), m) for m in legal if boost_score(const, m)), key=lambda x: (-x[0], x[1]))
    setup = None
    if boosts and pool:
        best3 = min(((-coverage([vals[m] for m in c]), c) for c in itertools.combinations(sorted(pool), min(3, len(pool)))))[1]
        setup = tuple(best3) + (boosts[0][1],)
    if not chosen:
        if boosts:
            chosen = [(boosts[0][1],)]
        else:  # nothing scoreable: any legal moves (still legal; validator re-checks)
            chosen = [tuple(sorted(legal)[:4])] if legal else []
    if not chosen:
        raise InvalidRequest(f"{display_name(const)}: no legal move at Lv {level}", {const: "no legal move"})
    # order each moveset by score (stable display; worker order does not matter for legality)
    chosen = [tuple(sorted(c, key=lambda m: (-scores.get(m, 0), m))) for c in chosen]
    if setup:
        setup = tuple(sorted(setup, key=lambda m: (-scores.get(m, 0), m)))
    ranked = [tuple(sorted(c, key=lambda m: (-scores.get(m, 0), m))) for _, _, c in combos[:RANKED]]
    items = {ms: held_item_candidates(const, ms, led) for ms in chosen + ([setup] if setup else [])}
    return MemberCandidates(const, variant, level, chosen, setup, items, ranked, pool, dropped,
                            {m: scores[m] for m in pool})


__all__ = ["MemberCandidates", "Variant", "candidate_move_consts", "coverage", "display_name", "dominates",
           "held_item_candidates", "league_opponents", "legal_moves", "member_candidates", "prune",
           "resolve_species", "type_chart", "type_mult", "unavailable_reason", "variants"]
