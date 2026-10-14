"""Legality validator (T029, Constitution III). Independent of the optimizer: this module and
everything it imports never import `platsim.optimizer` (tests/unit/test_validator.py checks it).

`validate(team, ledger=None, final_levels=None, options=None) -> list[Violation]`

`options` (models.LegalityOptions; default: the ledger's own, i.e. both OFF for `build_ledger()`)
selects the optional rules: egg moves and trade evolutions (user decisions 2026-10-08).

`team` is a TeamCandidate, a dict (TeamCandidate JSON `{"builds": [...]}` or the fixture shape
`{"team": [...]}`), or Showdown export text (see `load_team`). Keys may be data/generated keys
(`garchomp`, `close_combat`) or decomp constants (`SPECIES_GARCHOMP`, `MOVE_CLOSE_COMBAT`).

Violation codes (each carries `src` refs: decomp lines behind the rule, plus the spec FR):
- TEAM_SIZE: not exactly 6 members (spec FR-001).
- SCHEMA: a member record cannot be read.
- SPECIES_UNKNOWN; SPECIES_FORM_UNSUPPORTED (alternate forms are not modelled by the availability
  ledger, so they are conservatively rejected); SPECIES_TRADE_EVOLUTION (only reachable through a
  trade evolution, FR-005, while allow_trade_evolutions is off; with it on, when the trade
  evolution's pre-evolution or held item has no pre-Champion source); SPECIES_UNAVAILABLE (no
  pre-Champion source, FR-003/FR-003a).
- SOURCE_INVALID: `source` is not one of the species' pre-Champion source options (FR-008b);
  SOURCE_EXHAUSTED: a one-time source (gift, static, trade, starter choice) used by more members
  than it can give.
- LEVEL_OUT_OF_RANGE (1..100); LEVEL_BELOW_MINIMUM: below the lowest level the species can have
  on that source (FR-007, data-model Build.start_level).
- MOVE_COUNT (1..4); MOVE_DUPLICATE; MOVE_UNKNOWN; MOVE_NOT_LEARNABLE (no legal source at
  start_level, FR-007); MOVE_SOURCE_MISMATCH (learnable, but not by the declared source_kind);
  EGG_MOVE_NOT_ALLOWED (an egg move - the move would be legal as an egg move, or is declared
  `egg` - while allow_egg_moves is off).
- ABILITY_INVALID (not one of the species' abilities); ABILITY_FIXED_BY_TRADE (the NPC trade's
  personality fixes another ability, FR-008c); ABILITY_REASON (ability_reason contradicts the data:
  `single_ability` on a two-ability species, or `fixed_by_trade` without an NPC-trade source).
- IV_INVALID / EV_INVALID / NATURE_INVALID (FR-008: IV 15, EV 85, neutral nature, or the FixedMon
  values of an NPC trade).
- ITEM_UNKNOWN; ITEM_NOT_HOLDABLE (preventToss items cannot be given); ITEM_UNAVAILABLE (no
  pre-Champion copy, FR-006); ITEM_COPIES (held items + items used up by evolutions, relearner
  Heart Scales and tutor shards exceed the pre-Champion copies, FR-006).
- TM_COPIES: members using one TM exceed its pre-Champion copies (FR-004; HMs unlimited).
- LEVEL_GAP: final levels (when present) differ by more than 10 (FR-016 / data-model).
- REQUIRED_HM_MISSING (006 FR-004): `required_hms` names an HM that no member's moves contain (one
  violation per HM; the requirement is an explicit input, empty by default).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any

from platsim.decomp._util import ref
from platsim.decomp.items import load_items
from platsim.decomp.moves import load_moves
from platsim.decomp.stats import nature_affinities
from platsim.legality import movesources as MS
from platsim.legality.models import (
    DEFAULT_EV,
    LegalityOptions,
    DEFAULT_IV,
    STAT_KEYS,
    Build,
    MoveChoice,
    ShowdownSet,
    TeamCandidate,
    Violation,
    import_team,
)
from platsim.pins import DECOMP_ROOT, REPO_ROOT

PP = DECOMP_ROOT
SPEC = REPO_ROOT / "specs" / "001-champion-team-optimizer" / "spec.md"
DATA_MODEL = REPO_ROOT / "specs" / "001-champion-team-optimizer" / "data-model.md"
SPEC_004 = REPO_ROOT / "specs" / "004-breeding-source-limits" / "spec.md"
SPEC_006 = REPO_ROOT / "specs" / "006-required-hms" / "spec.md"
TEAM_SIZE = 6
MAX_LEVEL_GAP = 10


def _repo_ref(path: Path, needle: str) -> str:
    for i, line in enumerate(path.read_text().splitlines(), start=1):
        if needle in line:
            return f"{path.relative_to(REPO_ROOT)}:{i}"
    return str(path.relative_to(REPO_ROOT))


@cache
def _src() -> dict[str, list[str]]:
    pokemon_c = PP / "src" / "pokemon.c"
    bag_c = PP / "src" / "applications" / "bag" / "main.c"
    fr = lambda n: _repo_ref(SPEC, f"**{n}**")  # noqa: E731
    return {
        "team": [fr("FR-001")],
        "species": [fr("FR-003"), fr("FR-003a"), fr("FR-005")],
        "trade_evo": [ref(pokemon_c, "case EVO_CLASS_BY_TRADE:"), fr("FR-005")],
        "egg_option": MS.refs()["egg"][:2],
        "source": [fr("FR-008b"), _repo_ref(DATA_MODEL, "| source | AvailabilityEntry ref")],
        "level": [fr("FR-007"), _repo_ref(DATA_MODEL, "| start_level | int 1–100")],
        "moves": [fr("FR-007")],
        "ability": [ref(pokemon_c, "void Pokemon_CalcAbility("), fr("FR-008c")],
        "stats": [fr("FR-008")],
        "nature": [ref(pokemon_c, "static const s8 sNatureStatAffinities[][5] = {"), fr("FR-008")],
        "item": [fr("FR-006")],
        "holdable": [ref(bag_c, "if (Item_Get(itemData, ITEM_PARAM_PREVENT_TOSS) == FALSE) {"), fr("FR-006")],
        "tm": [ref(PP / "src" / "applications" / "party_menu" / "callbacks.c", "Item_IsHMMove"), fr("FR-004")],
        "gap": [fr("FR-016"), _repo_ref(DATA_MODEL, "final level gap ≤ 10")],
        # 004: one choice per choose-one group (starter choice FR-002, fossil Trainer ID FR-011)
        "group": [_repo_ref(SPEC_004, "**FR-002**"), _repo_ref(SPEC_004, "**FR-011**")],
    }


# ---------------------------------------------------------------------------------------------
# Name resolution (keys, constants or display names)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


@cache
def _species_index() -> dict[str, str]:
    from platsim.decomp.species import load_species

    out = {}
    for key, s in load_species().items():
        const = f"SPECIES_{key.upper()}"
        out[_norm(key)] = const
        out[_norm(const)] = const
        if s.form is None:
            out.setdefault(_norm(s.name), const)
    return out


@cache
def _move_index() -> dict[str, str]:
    out = {}
    for const, m in load_moves().items():
        out[_norm(const.removeprefix("MOVE_"))] = const
        out[_norm(const)] = const
        out.setdefault(_norm(m.name), const)
    return out


@cache
def _item_index() -> dict[str, str]:
    out = {}
    for const, it in load_items().items():
        out[_norm(const.removeprefix("ITEM_"))] = const
        out[_norm(const)] = const
        out.setdefault(_norm(it.name), const)
    return out


@cache
def _ability_index() -> dict[str, str]:
    from platsim.decomp.constants import load_enum

    enum = load_enum("abilities")
    names = json.loads((PP / "res" / "text" / "ability_names.json").read_text())["messages"]
    out = {}
    for const, i in enum.values.items():
        out[_norm(const.removeprefix("ABILITY_"))] = const
        out[_norm(const)] = const
        if i < len(names):
            out.setdefault(_norm(names[i]["en_US"]), const)
    return out


def _resolve(index: dict[str, str], value: str | None) -> str | None:
    if value is None:
        return None
    return index.get(_norm(str(value)))


def _nature_const(value: str) -> str | None:
    v = _norm(str(value)).removeprefix("nature")
    for n in nature_affinities():
        if _norm(n.removeprefix("NATURE_")) == v:
            return n
    return None


# ---------------------------------------------------------------------------------------------
# Input


def _ledger(ledger, options: LegalityOptions | None):
    from platsim.availability.ledger import build_ledger

    return (ledger or build_ledger()).with_options(options)


def load_team(path_or_text: str | Path, ledger=None, options: LegalityOptions | None = None
              ) -> tuple[TeamCandidate | None, list[int] | None, list[Violation]]:
    """Read a team file: JSON (TeamCandidate or {"team": [...]}) or Showdown export text.
    Returns (team, final_levels, violations found while reading)."""
    p = Path(path_or_text)
    text = p.read_text() if p.exists() else str(path_or_text)
    if text.lstrip().startswith("{"):
        d = json.loads(text)
        return _team_from_dict(d)
    sets = import_team(text, key_of=_showdown_key)
    return from_showdown(sets, ledger, options), None, []


def _showdown_key(kind: str, name: str) -> str:
    idx = {"species": _species_index, "move": _move_index, "item": _item_index, "ability": _ability_index}.get(kind)
    if idx is None:
        return _nature_const(name) or name
    return _resolve(idx(), name) or name


def _team_from_dict(d: dict[str, Any]) -> tuple[TeamCandidate | None, list[int] | None, list[Violation]]:
    raw = d.get("builds", d.get("team"))
    if not isinstance(raw, list):
        return None, None, [Violation("SCHEMA", "team JSON needs a 'builds' (or 'team') list", _src()["team"])]
    builds, bad = [], []
    finals = d.get("final_levels")
    per = [b.get("final_level") for b in raw if isinstance(b, dict)]
    if finals is None and per and all(isinstance(x, int) for x in per):
        finals = per
    for i, b in enumerate(raw, start=1):
        try:
            builds.append(Build.from_dict(b))
        except (KeyError, TypeError, ValueError) as e:
            bad.append(Violation("SCHEMA", f"member {i}: cannot read build: {e!r}", _src()["team"]))
    return TeamCandidate(builds, dict(d.get("resource_use", {}))), finals, bad


def from_showdown(sets: list[ShowdownSet], ledger=None, options: LegalityOptions | None = None) -> TeamCandidate:
    """Showdown text carries no provenance (source, move sources, ability_reason). For each member
    try every source option; per move take the best legal source by `movesources.move_source_key`,
    and keep the simplest option (`movesources.option_sort_key`: the species itself < a
    pre-evolution then evolve < NPC trade < Day-Care egg) under which the member has no violation
    of its own. If none works, the first option is kept so the validator reports why. Team-wide copy limits are
    checked afterwards on the chosen sources (a different TM choice could in principle avoid a
    TM_COPIES violation reported here)."""
    led = _ledger(ledger, options)
    builds = []
    for slot, s in enumerate(sets, start=1):
        species = _resolve(_species_index(), s.species) or s.species
        opts = MS.source_options(species, led) if species in MS.by_constant() else []
        cands = []
        for o in opts:
            mcs = []
            for mv in s.moves:
                cs = MS.sources(species, _resolve(_move_index(), mv) or mv, s.level, led, o)
                cs.sort(key=lambda c: MS.move_source_key(c, led))
                mcs.append(cs[0] if cs else MoveChoice(mv, "level_up", "unresolved (no legal source found)"))
            reason = "fixed_by_trade" if o.fixed_mon else "tie_default"
            cands.append((MS.option_sort_key(o, MS.move_cost(mcs, led)),
                          Build(species=species, source=o.id, start_level=s.level, moves=mcs, ability=s.ability,
                                ability_reason=reason, held_item=s.item, nature=s.nature or "",
                                ivs=dict(s.ivs), evs=dict(s.evs))))
        valid = [(k, b) for k, b in cands if not _validate_build(slot, b, led)["violations"]]
        pick = min(valid, key=lambda kb: kb[0])[1] if valid else None
        cands = [b for _, b in cands]
        if pick is None:
            pick = cands[0] if cands else Build(
                species=species, source="none", start_level=s.level,
                moves=[MoveChoice(mv, "level_up", "unresolved") for mv in s.moves], ability=s.ability,
                ability_reason="tie_default", held_item=s.item, nature=s.nature or "", ivs=dict(s.ivs), evs=dict(s.evs))
        builds.append(pick)
    return TeamCandidate(builds)


def showdown_name(kind: str, key: str) -> str:
    """Display name for Showdown export (models.export_team name_of): decomp names."""
    if kind == "species":
        c = _resolve(_species_index(), key)
        return MS.species_name(c) if c in MS.by_constant() else key
    if kind == "move":
        c = _resolve(_move_index(), key)
        return load_moves()[c].name if c else key
    if kind == "item":
        c = _resolve(_item_index(), key)
        return load_items()[c].name if c else key
    if kind == "ability":
        c = _resolve(_ability_index(), key)
        from platsim.decomp.constants import load_enum

        names = json.loads((PP / "res" / "text" / "ability_names.json").read_text())["messages"]
        return names[load_enum("abilities").values[c]]["en_US"] if c else key
    if kind == "nature":
        c = _nature_const(key)
        return c.removeprefix("NATURE_").title() if c else key
    return key


# ---------------------------------------------------------------------------------------------
# Validation


def validate(team: TeamCandidate | dict | str, ledger=None, final_levels: list[int] | None = None,
             options: LegalityOptions | None = None, *, required_hms=()) -> list[Violation]:
    led = _ledger(ledger, options)
    out: list[Violation] = []
    if isinstance(team, str):
        team, finals, read = load_team(team, led)
        out += read
        final_levels = final_levels if final_levels is not None else finals
    elif isinstance(team, dict):
        team, finals, read = _team_from_dict(team)
        out += read
        final_levels = final_levels if final_levels is not None else finals
    if team is None:
        return out
    n = len(team.builds) + sum(1 for v in out if v.code == "SCHEMA")
    if n != TEAM_SIZE:
        out.append(Violation("TEAM_SIZE", f"team has {n} members; exactly {TEAM_SIZE} are required", _src()["team"]))
    tm_use: Counter[str] = Counter()
    tm_who: dict[str, list[str]] = {}
    item_use: Counter[str] = Counter()
    item_who: dict[str, list[str]] = {}
    item_bonus: Counter[str] = Counter()
    source_use: Counter[str] = Counter()
    groups: dict[str, list[tuple[str, str | None]]] = {}  # group -> [("member N Name", choice)]
    opt_by_id: dict[str, MS.SourceOption] = {}
    for slot, b in enumerate(team.builds, start=1):
        r = _validate_build(slot, b, led)
        out += r["violations"]
        who = f"member {slot} ({b.species})"
        for k, v in r["tm"].items():
            tm_use[k] += v
            tm_who.setdefault(k, []).append(who)
        for k, v in r["items"].items():
            item_use[k] += v
            item_who.setdefault(k, []).append(who)
        for k, v in r["bonus"].items():
            item_bonus[k] += v
        o = r["option"]
        if o is not None:
            source_use[o.id] += 1
            opt_by_id[o.id] = o
            if o.exclusive_group:
                groups.setdefault(o.exclusive_group, []).append((f"member {slot} {MS.species_name(o.member)}", o.group_choice))
    for tm, used in sorted(tm_use.items()):
        have = led.tm_copies(tm)
        if have != MS.UNLIMITED and used > have:
            out.append(Violation("TM_COPIES", f"{tm} is used by {used} members ({', '.join(tm_who[tm])}) but only {have} "
                                 f"cop{'y is' if have == 1 else 'ies are'} obtainable before the Champion",
                                 _src()["tm"] + [s for c in led.pre(subject=f'ITEM_{tm}') for s in c.entry.src[:1]]))
    for item, used in sorted(item_use.items()):
        have = led.item_copies(item)
        if have == MS.UNLIMITED:
            continue
        have += item_bonus[item]
        if used > have:
            out.append(Violation("ITEM_COPIES", f"{item} is needed {used} times ({', '.join(item_who[item])}) but only {have} "
                                 f"cop{'y is' if have == 1 else 'ies are'} obtainable before the Champion",
                                 _src()["item"] + [s for c in led.pre(subject=item) for s in c.entry.src[:1]]))
    # 003 FR-009: Leftovers held by wild Munchlax / Snorlax count only with one of them on the team.
    from platsim.availability.ledger import TEAM_GATED_ITEMS, item_holders, team_item_copies

    team_consts = [c for c in (_resolve(_species_index(), b.species) for b in team.builds) if c]
    for item in TEAM_GATED_ITEMS:
        used = item_use.get(item, 0)
        if not used:
            continue
        have = team_item_copies(led, item, team_consts)
        if have != MS.UNLIMITED and used > have + item_bonus[item]:
            holders = " or ".join(sorted(MS.species_name(s) for s in item_holders(item)))
            extra = (f"; only {have} other cop{'y is' if have == 1 else 'ies are'} obtainable" if have else "")
            out.append(Violation("LEFTOVERS_NEEDS_MUNCHLAX",
                                 f"{load_items()[item].name} is held by {used} members ({', '.join(item_who[item])}): it comes "
                                 f"from wild {holders}, so one of them must be on the team{extra}",
                                 _src()["item"] + [s for c in led.pre(subject=item) for s in c.entry.src[:1]]))
    for oid, used in sorted(source_use.items()):
        q = opt_by_id[oid].quantity  # 004: grouped options too (the starter gift is still one Pokemon)
        if q != MS.UNLIMITED and used > int(q):
            out.append(Violation("SOURCE_EXHAUSTED", f"source {oid} gives {q} Pokemon but {used} members use it",
                                 _src()["source"] + list(opt_by_id[oid].src[:2])))
    # 004 FR-002/FR-011: members of one group (gift or bred from it) must share one choice.
    for g, members in groups.items():
        if len({ch for _, ch in members}) > 1:
            text = MS.group_conflict_text(g, members)
            refs = [s for oid in source_use for s in opt_by_id[oid].src[:1] if opt_by_id[oid].exclusive_group == g]
            out.append(Violation("SOURCE_EXHAUSTED", text, _src()["source"] + _src()["group"] + sorted(set(refs))))
    if final_levels:
        gap = max(final_levels) - min(final_levels)
        if gap > MAX_LEVEL_GAP:
            out.append(Violation("LEVEL_GAP", f"final levels {final_levels} differ by {gap} (> {MAX_LEVEL_GAP})", _src()["gap"]))
    if required_hms:  # 006 FR-002/FR-004: each required HM is in some member's final moveset
        carried = {_resolve(_move_index(), m.move) for b in team.builds for m in b.moves}
        for key in MS.normalize_hms(required_hms):
            h = MS.hm_by_key(key)
            if h.move not in carried:
                out.append(Violation("REQUIRED_HM_MISSING", f"required HM {h.name} is not in any member's moveset",
                                     list(h.src) + [_repo_ref(SPEC_006, "**FR-002**")]))
    return out


def _validate_build(slot: int, b: Build, led) -> dict[str, Any]:
    v: list[Violation] = []
    res: dict[str, Any] = {"violations": v, "tm": Counter(), "items": Counter(), "bonus": Counter(), "option": None}
    tag = f"member {slot} ({b.species})"
    species = _resolve(_species_index(), b.species)
    if species is None:
        v.append(Violation("SPECIES_UNKNOWN", f"{tag}: unknown species", _src()["species"]))
        return res
    if species not in MS.by_constant():
        v.append(Violation("SPECIES_FORM_UNSUPPORTED", f"{tag}: alternate forms are not modelled by the availability "
                           "ledger; rejected conservatively", _src()["species"]))
        return res
    opts = MS.source_options(species, led)
    name = MS.species_name(species)
    if not opts:
        trade = [(p, ev) for p, ev in MS._preds().get(species, []) if ev.method in MS.TRADE_METHODS]
        if trade:
            p, ev = trade[0]
            held = ev.param if isinstance(ev.param, str) else None
            how = f"{MS.species_name(p)} ({ev.method}{', holding ' + held if held else ''})"
            if MS.options_of(led).allow_trade_evolutions:
                miss = []
                if not MS.source_options(p, led):
                    miss.append(f"{MS.species_name(p)} has no pre-Champion source")
                if held and led.item_copies(held) == 0:
                    miss.append(f"{held} has no pre-Champion copy (ledger)")
                msg = (f"{tag}: {name} is only reachable by trade evolution from {how}; trade evolutions are allowed, "
                       f"but {'; '.join(miss) or 'no pre-Champion path reaches it'}")
            else:
                msg = (f"{tag}: {name} is only reachable by trade evolution from {how}, which needs a second "
                       "cartridge (FR-005; enable allow_trade_evolutions / --allow-trade-evolutions to allow it)")
            v.append(Violation("SPECIES_TRADE_EVOLUTION", msg, _src()["trade_evo"] + MS.by_constant()[p].src[6:7]))
        else:
            v.append(Violation("SPECIES_UNAVAILABLE", f"{tag}: {name} has no pre-Champion source (no wild, gift, egg, "
                               "static, NPC trade, breeding or non-trade evolution source; National Dex sources excluded)",
                               _src()["species"]))
        return res
    opt = next((o for o in opts if o.id == b.source), None)
    if opt is None:
        v.append(Violation("SOURCE_INVALID", f"{tag}: source {b.source!r} is not a pre-Champion source of {name}; "
                           f"valid: {[o.id for o in opts[:6]]}{' ...' if len(opts) > 6 else ''}", _src()["source"]))
    res["option"] = opt
    check_opts = [opt] if opt else opts
    level = b.start_level
    if not 1 <= level <= 100:
        v.append(Violation("LEVEL_OUT_OF_RANGE", f"{tag}: start_level {level} is outside 1..100", _src()["level"]))
        return res
    floor = min(o.min_level for o in check_opts)
    move_level = max(level, floor)  # moves are checked at the floor so one level error does not cascade
    if level < floor:
        v.append(Violation("LEVEL_BELOW_MINIMUM", f"{tag}: start_level {level} is below Lv {floor}, the lowest level {name} "
                           f"can have via {opt.id if opt else 'any source'}", _src()["level"] + list(check_opts[0].src[:2])))
    # moves
    if not 1 <= len(b.moves) <= 4:
        v.append(Violation("MOVE_COUNT", f"{tag}: {len(b.moves)} moves (1..4 allowed)", _src()["moves"]))
    seen = set()
    for m in b.moves:
        mv = _resolve(_move_index(), m.move)
        if mv is None:
            v.append(Violation("MOVE_UNKNOWN", f"{tag}: unknown move {m.move!r}", _src()["moves"]))
            continue
        if mv in seen:
            v.append(Violation("MOVE_DUPLICATE", f"{tag}: {mv} listed twice", _src()["moves"]))
            continue
        seen.add(mv)
        legal = list({(c.source_kind, c.detail): c for o in check_opts for c in MS.sources(species, mv, move_level, led, o)}.values())
        if not MS.options_of(led).allow_egg_moves and (not legal or m.source_kind == "egg"):
            eggs = _egg_alternatives(species, mv, move_level, led, check_opts)
            if eggs or (m.source_kind == "egg" and legal):
                other = f"; legal without egg moves: {', '.join(sorted({c.source_kind for c in legal}))}" if legal else ""
                v.append(Violation("EGG_MOVE_NOT_ALLOWED",
                                   f"{tag}: {mv} is an egg move here"
                                   + (f" ({eggs[0].detail})" if eggs else " (declared source_kind 'egg')")
                                   + " and egg moves are not allowed; pass --allow-egg-moves (allow_egg_moves) to "
                                     f"allow them{other}",
                                   _src()["egg_option"] + _src()["moves"]))
                continue
        if not legal:
            why = []
            for o in check_opts:
                why += MS.explain(species, mv, move_level, led, o)
            v.append(Violation("MOVE_NOT_LEARNABLE", f"{tag}: {mv} has no legal source at Lv {move_level}: "
                               + "; ".join(dict.fromkeys(why)),
                               _src()["moves"] + MS.by_constant()[species].src[5:6]))
            continue
        match = [c for c in legal if c.source_kind == m.source_kind]
        if not match:
            kinds = sorted({c.source_kind for c in legal})
            v.append(Violation("MOVE_SOURCE_MISMATCH", f"{tag}: {mv} is not learnable by {m.source_kind!r} here; legal: "
                               + "; ".join(f"{c.source_kind}: {c.detail}" for c in legal[:4]) + f" (kinds {kinds})",
                               _src()["moves"] + [s for c in legal[:2] for s in (c.availability_ref or "").split("; ") if s]))
            continue
        # prefer the declared detail when it names one of the legal choices
        chosen = next((c for c in match if c.detail == m.detail), None) or min(match, key=lambda c: MS.move_source_key(c, led))
        for k, n in MS.uses_of(chosen).items():
            if re.fullmatch(r"(TM|HM)\d\d", k):
                res["tm"][k] += n
            else:
                res["items"][k] += n
    # evolution items used up on the chosen path
    if opt:
        for it, n in opt.consumes:
            res["items"][it] += n
    # ability
    ability = _resolve(_ability_index(), b.ability)
    sp = MS.by_constant()[species]
    valid_abilities = [a for a in sp.abilities if a]
    fixed = opt.fixed_mon if opt else None
    if ability not in valid_abilities:
        v.append(Violation("ABILITY_INVALID", f"{tag}: ability {b.ability!r} is not one of {name}'s abilities {valid_abilities}",
                           _src()["ability"] + sp.src[3:4]))
    elif fixed:
        slot_ = fixed["ability_slot"]
        want = sp.abilities[slot_ - 1] or sp.abilities[0]
        if ability != want:
            v.append(Violation("ABILITY_FIXED_BY_TRADE", f"{tag}: the NPC trade's personality {fixed['personality']} fixes "
                               f"ability slot {slot_} = {want}, not {ability}", _src()["ability"] + list(fixed["src"])))
    if b.ability_reason == "single_ability" and len(set(valid_abilities)) > 1:
        v.append(Violation("ABILITY_REASON", f"{tag}: ability_reason 'single_ability' but {name} has two abilities "
                           f"{valid_abilities}", _src()["ability"] + sp.src[3:4]))
    if b.ability_reason == "fixed_by_trade" and not fixed:
        v.append(Violation("ABILITY_REASON", f"{tag}: ability_reason 'fixed_by_trade' but the source is not an NPC trade",
                           _src()["ability"]))
    # IVs / EVs / nature
    want_ivs = {k: DEFAULT_IV for k in STAT_KEYS}
    if fixed and fixed.get("ivs"):
        want_ivs.update({k: x for k, x in fixed["ivs"].items() if x is not None})
    if b.ivs != want_ivs:
        v.append(Violation("IV_INVALID", f"{tag}: IVs {b.ivs} must be {want_ivs}"
                           + (" (fixed by the NPC trade)" if fixed else " (FR-008)"),
                           _src()["stats"] + (list(fixed["src"][:1]) if fixed else [])))
    if any(b.evs[k] != DEFAULT_EV for k in STAT_KEYS):
        v.append(Violation("EV_INVALID", f"{tag}: EVs {b.evs} must be {DEFAULT_EV} in every stat (FR-008)", _src()["stats"]))
    nat = _nature_const(b.nature)
    if fixed and fixed.get("nature"):
        if nat != fixed["nature"]:
            v.append(Violation("NATURE_INVALID", f"{tag}: nature {b.nature!r}; the NPC trade's personality fixes {fixed['nature']}",
                               _src()["nature"] + list(fixed["src"])))
    elif nat is None or any(nature_affinities()[nat].values()):
        v.append(Violation("NATURE_INVALID", f"{tag}: nature {b.nature!r} is not a neutral nature (FR-008)", _src()["nature"]))
    # held item
    if b.held_item:
        item = _resolve(_item_index(), b.held_item)
        if item is None or item == "ITEM_NONE":
            v.append(Violation("ITEM_UNKNOWN", f"{tag}: unknown item {b.held_item!r}", _src()["item"]))
        else:
            from platsim.availability.ledger import _item_json

            if _item_json(item).get("preventToss"):
                v.append(Violation("ITEM_NOT_HOLDABLE", f"{tag}: {item} cannot be given to a Pokemon (preventToss)",
                                   _src()["holdable"] + load_items()[item].src[1:2]))
            elif fixed and fixed.get("held_item") == item:
                res["bonus"][item] += 1  # the traded Pokemon arrives holding its own copy
                res["items"][item] += 1
            elif led.item_copies(item) == 0:
                v.append(Violation("ITEM_UNAVAILABLE", f"{tag}: {item} has no pre-Champion source (ledger)",
                                   _src()["item"] + load_items()[item].src[1:2]))
            else:
                res["items"][item] += 1
    return res


def _egg_alternatives(species: str, mv: str, level: int, led, check_opts) -> list[MoveChoice]:
    """Egg-move sources the move would have with allow_egg_moves on (same options otherwise)."""
    import dataclasses

    on = led.with_options(dataclasses.replace(MS.options_of(led), allow_egg_moves=True))
    ids = {o.id for o in check_opts}
    opts = [o for o in MS.source_options(species, on) if o.id in ids]
    return [c for o in opts for c in MS.sources(species, mv, level, on, o) if c.source_kind == "egg"]


def format_violations(vs: list[Violation]) -> str:
    return "\n".join(f"{x.code}: {x.message}\n    src: {', '.join(x.src)}" for x in vs)


__all__ = ["validate", "load_team", "from_showdown", "showdown_name", "format_violations"]
