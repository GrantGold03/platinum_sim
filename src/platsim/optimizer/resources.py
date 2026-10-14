"""Team-wide resource assignment (T062; spec FR-004, FR-006, FR-008b; data-model TeamCandidate).

The optimizer works on level-agnostic team SPECS (`MemberSpec`: species, source variant, moves, held
item, ability). `realize(specs, levels, ledger)` turns a spec into a concrete `TeamCandidate` at a
start-level vector, or returns a `Refusal` naming why it cannot be built. A candidate that would break
a copy limit is therefore never generated:

- Members are processed in slot order. For each member every source option of its variant that exists
  at its level (`SourceOption.min_level`) is tried; a one-time source
  (gift / static / starter choice, `quantity`) already taken by an earlier member is skipped, and so is
  an option of a choose-one group (`exclusive_group`) that an earlier member holds with a different
  `group_choice` (004; validator SOURCE_EXHAUSTED).
- For each move, the legal sources at that level (`movesources.sources`) are tried in the documented
  preference order `movesources.move_source_key` (no limited copy before a limited copy; then
  level-up / pre-evolution level-up < unlimited TM/HM < tutor < move relearner < egg move). A
  source is taken only if every copy it consumes is still left (`ledger.tm_copies` /
  `ledger.item_copies` minus copies already assigned to earlier members).
- Evolution items consumed on the chosen path (`SourceOption.consumes`) and the held item are counted
  the same way. An NPC-trade mon that arrives holding its own copy of an item uses that copy (the
  validator's rule).
- Among the options that work, the one using the fewest limited copies is chosen, then the simplest
  source by `movesources.option_sort_key` (the species itself < a pre-evolution then evolve <
  Day-Care egg, which is therefore used only when an egg move or a breeding-only path needs it;
  ties: cheaper move sources, fewer evolutions, lowest minimum level, id). NPC trades are never
  ranked against non-trade options here: a variant holds either one NPC-trade option or none
  (candidates.variants), so trade vs non-trade stays an explicit optimizer choice (FR-008b).

Which member gets a contested copy is decided by slot order. That is a heuristic over candidates
(the screen tries other candidates too); legality is re-checked by the independent validator.

`member_floor(spec, ledger)` is the lowest start level at which the member alone can be built
(source minimum level and every move legal; legality is monotone in level, see movesources rules),
found by bisection and verified.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from functools import cache

from platsim.decomp.items import load_items
from platsim.decomp.moves import load_moves
from platsim.legality import movesources as MS
from platsim.legality.models import Build, MoveChoice, TeamCandidate, default_evs, default_ivs
from platsim.optimizer import candidates as C

UNLIMITED = MS.UNLIMITED


@dataclass(frozen=True)
class MemberSpec:
    species: str  # SPECIES_*
    variant: str  # Variant.key ("own" or an NPC-trade option id)
    moves: tuple[str, ...]  # MOVE_*
    item: str | None = None  # item key (data/generated items.json), e.g. "sitrus_berry"
    ability: str | None = None  # ABILITY_*; None until the ability screen (slot-1 placeholder)
    ability_reason: str | None = None

    def to_dict(self) -> dict:
        return {"species": self.species, "variant": self.variant, "moves": list(self.moves), "item": self.item,
                "ability": self.ability, "ability_reason": self.ability_reason}

    @classmethod
    def from_dict(cls, d: dict) -> MemberSpec:
        return cls(d["species"], d["variant"], tuple(d["moves"]), d.get("item"), d.get("ability"),
                   d.get("ability_reason"))

    def label(self) -> str:
        mv = load_moves()
        moves = "/".join(mv[m].name for m in self.moves)
        item = load_items()[f"ITEM_{self.item.upper()}"].name if self.item else "no item"
        return f"{C.display_name(self.species)} [{moves}] @ {item}" + (f" ({self.variant})" if self.variant != "own" else "")


TeamSpec = tuple[MemberSpec, ...]


def spec_to_json(team: TeamSpec) -> list[dict]:
    return [m.to_dict() for m in team]


def spec_from_json(d: list[dict]) -> TeamSpec:
    return tuple(MemberSpec.from_dict(x) for x in d)


@dataclass
class Refusal:
    slot: int
    reason: str


@dataclass
class Realized:
    team: TeamCandidate
    options: list  # SourceOption per member
    uses: dict[str, int] = field(default_factory=dict)  # resource -> copies used (limited only)
    who: dict[str, list[int]] = field(default_factory=dict)  # resource -> slots using it


def _resource_kind(res: str) -> str:
    return "tm" if re.fullmatch(r"(TM|HM)\d\d", res) else "item"


_COPIES: dict[tuple[int, str], int | str] = {}


def copies(res: str, led, team: tuple[str, ...] | None = None) -> int | str:
    """Pre-Champion copies (ledger.tm_copies / item_copies), memoised per ledger object. With `team`
    (the SPECIES_* of the whole team), a team-gated item (ledger.TEAM_GATED_ITEMS: Leftovers, 003
    FR-009) counts its wild-holder copies only if a holder is on the team; without it (a single
    member's level floor) it is not gated, and `realize` applies the gate for the real team."""
    from platsim.availability.ledger import TEAM_GATED_ITEMS, item_holders, team_item_copies

    item = res if res.startswith("ITEM_") else None
    if team is not None and item in TEAM_GATED_ITEMS:
        k = (id(led), res, bool(set(team) & item_holders(item)))
        if k not in _COPIES:
            _COPIES[k] = team_item_copies(led, item, team)
        return _COPIES[k]
    k = (id(led), res)
    if k not in _COPIES:
        _COPIES[k] = led.tm_copies(res) if _resource_kind(res) == "tm" else led.item_copies(res)
    return _COPIES[k]


def _affordable(uses: dict[str, int], used: Counter, led, team: tuple[str, ...] | None = None) -> bool:
    for r, n in uses.items():
        have = copies(r, led, team)
        if have == UNLIMITED:
            continue
        if used[r] + n > int(have):
            return False
    return True


def variant_of(spec: MemberSpec, led) -> C.Variant:
    for v in C.variants(spec.species, led):
        if v.key == spec.variant:
            return v
    raise ValueError(f"{spec.species}: unknown source variant {spec.variant!r}")


def default_ability(spec: MemberSpec, opt) -> tuple[str, str]:
    """Slot-1 placeholder (before the ability screen), or the NPC trade's fixed ability (FR-008c)."""
    sp = MS.by_constant()[spec.species]
    a1, a2 = sp.abilities[0], sp.abilities[1]
    if opt is not None and opt.fixed_mon:
        s = opt.fixed_mon["ability_slot"]
        return sp.abilities[s - 1] or a1, "fixed_by_trade"
    if a2 is None or a2 == a1:
        return a1, "single_ability"
    return a1, "tie_default"


_SOURCES: dict[tuple, list] = {}


def _sources(species: str, move: str, level: int, opt, led) -> list:
    """movesources.sources, memoised per (ledger, species, move, level, option): pure in those inputs."""
    k = (id(led), species, move, level, opt.id)
    if k not in _SOURCES:
        cs = MS.sources(species, move, level, led, opt)
        _SOURCES[k] = sorted(cs, key=lambda c: MS.move_source_key(c, led))
    return _SOURCES[k]


def _member(spec: MemberSpec, level: int, opt, led, used: Counter,
            team: tuple[str, ...] | None = None) -> tuple[list[MoveChoice], Counter, int] | None:
    """Move choices + limited copies this member consumes under `opt` + the picks' `movesources.move_cost`,
    or None."""
    local: Counter = Counter()
    choices: list[MoveChoice] = []
    picks: list[MoveChoice] = []
    mv = load_moves()
    for move in spec.moves:
        cs = _sources(spec.species, move, level, opt, led)
        pick = next((c for c in cs if _affordable(MS.uses_of(c), used + local, led, team)), None)
        if pick is None:
            return None
        for r, n in MS.uses_of(pick).items():
            local[r] += n
        picks.append(pick)
        choices.append(MoveChoice(mv[move].key, pick.source_kind, pick.detail, pick.availability_ref))
    for it, n in opt.consumes:
        local[it] += n
    if not _affordable({k: v for k, v in local.items()}, used, led, team):
        return None
    if spec.item:
        item_const = f"ITEM_{spec.item.upper()}"
        own_copy = bool(opt.fixed_mon and opt.fixed_mon.get("held_item") == item_const)
        if not own_copy:
            if copies(item_const, led, team) == 0 or not _affordable({item_const: 1}, used + local, led, team):
                return None
            local[item_const] += 1
    return choices, local, MS.move_cost(picks, led)


def _slot_cost(species: str, move: str) -> tuple:
    """How much a member loses when `move` gives way to a required HM: a modelled self-boost (a
    setup moveset the optimizer kept on purpose) only as a last resort, then the move's League
    coverage value (candidates.move_value; 0 for other status moves)."""
    mv = load_moves()[move]
    boost = 1 if C.boost_score(species, move) else 0
    return (boost, sum(C.move_value(species, move)) if C.is_attack(mv) else 0.0)


def place_required_hms(specs: TeamSpec, levels, led, required) -> tuple[TeamSpec | None, str | None]:
    """006 data-model H3 / research R2: put each required HM that no member carries yet on the
    member and slot that lose least (`_slot_cost`; a free slot first; ties: lower member index,
    then lower slot). Only members that can legally learn the HM at their level (some option of
    their variant) are carriers; slots already holding a required HM are never replaced.
    Deterministic. Returns (specs, None), or (None, HM name) when an HM has no carrier."""
    from dataclasses import replace

    out = list(specs)
    keys = MS.normalize_hms(required)
    req_moves = {MS.hm_by_key(k).move for k in keys}
    for key in keys:
        h = MS.hm_by_key(key)
        if any(h.move in s.moves for s in out):
            continue
        best = None
        for i, (s, lv) in enumerate(zip(out, levels)):
            if not any(MS.sources(s.species, h.move, int(lv), led, o) for o in variant_of(s, led).options(led)):
                continue
            if len(s.moves) < 4:
                cand = ((-1, 0.0), i, len(s.moves))
            else:
                slots = [(j, m) for j, m in enumerate(s.moves) if m not in req_moves]
                if not slots:
                    continue
                j, m = min(slots, key=lambda jm: (_slot_cost(s.species, jm[1]), jm[0]))
                cand = (_slot_cost(s.species, m), i, j)
            if best is None or cand < best:
                best = cand
        if best is None:
            return None, h.name
        _, i, j = best
        moves = list(out[i].moves)
        if j == len(moves):
            moves.append(h.move)
        else:
            moves[j] = h.move
        out[i] = replace(out[i], moves=tuple(moves))
    return tuple(out), None


def realize(specs: TeamSpec, levels, led, *, required_hms=()) -> Realized | Refusal:
    if required_hms:  # 006: every path to battle and report passes here, so no path can lose an HM
        placed, missing = place_required_hms(specs, levels, led, required_hms)
        if placed is None:
            return Refusal(0, f"no member can carry required HM {missing} at these levels")
        specs = placed
    used: Counter = Counter()
    who: dict[str, list[int]] = {}
    source_used: Counter = Counter()
    groups: dict[str, str | None] = {}  # 004: group -> the choice taken (same choice may repeat)
    builds: list[Build] = []
    options = []
    team = tuple(s.species for s in specs)
    for slot, (spec, level) in enumerate(zip(specs, levels)):
        variant = variant_of(spec, led)
        best = None
        for opt in variant.options(led):
            if level < opt.min_level:
                continue
            if opt.exclusive_group and groups.get(opt.exclusive_group, opt.group_choice) != opt.group_choice:
                continue
            if opt.quantity != UNLIMITED and source_used[opt.id] >= int(opt.quantity):
                continue
            r = _member(spec, level, opt, led, used, team)
            if r is None:
                continue
            limited = sum(n for res, n in r[1].items() if copies(res, led, team) != UNLIMITED)
            key = (limited, *MS.option_sort_key(opt, r[2]))
            if best is None or key < best[0]:
                best = (key, opt, r)
        if best is None:
            return Refusal(slot, f"slot {slot + 1} {C.display_name(spec.species)}: no source option of variant "
                                 f"{spec.variant!r} makes {list(spec.moves)} + item {spec.item} legal at Lv {level} "
                                 "with the copies left after earlier members")
        _, opt, (choices, local, _cost) = best
        for res, n in local.items():
            used[res] += n
            who.setdefault(res, []).append(slot)
        source_used[opt.id] += 1
        if opt.exclusive_group:
            groups[opt.exclusive_group] = opt.group_choice
        ivs, nature = default_ivs(), "Hardy"
        if opt.fixed_mon:
            if opt.fixed_mon.get("ivs"):
                ivs.update({k: x for k, x in opt.fixed_mon["ivs"].items() if x is not None})
            if opt.fixed_mon.get("nature"):
                nature = opt.fixed_mon["nature"].removeprefix("NATURE_").title()
        if spec.ability:
            ability, reason = spec.ability, spec.ability_reason or "tie_default"
        else:
            ability, reason = default_ability(spec, opt)
        builds.append(Build(species=MS.by_constant()[spec.species].key, source=opt.id, start_level=int(level),
                            moves=choices, ability=ability, ability_reason=reason, held_item=spec.item,
                            nature=nature, ivs=ivs, evs=default_evs()))
        options.append(opt)
    limited = {r: n for r, n in used.items() if copies(r, led, team) != UNLIMITED}
    team = TeamCandidate(builds, resource_use=dict(sorted(limited.items())))
    return Realized(team, options, dict(sorted(limited.items())), {r: who[r] for r in sorted(limited)})


def repair(specs: TeamSpec, levels, led, ranked: list[list[tuple[str, ...]]], *,
           required_hms=()) -> tuple[TeamSpec, list[str]] | Refusal:
    """Make `specs` buildable at `levels` by replacing refused members, in slot order: a refused member
    gets the first of its `ranked` movesets (best first) that can be built after the earlier members,
    keeping its held item if possible, else its first item candidate that fits (Sitrus first), else no
    item. Returns (specs, notes) or the Refusal when a member has no buildable alternative."""
    specs = list(specs)
    notes: list[str] = []
    team = tuple(sp.species for sp in specs)
    for _ in range(len(specs) + 1):
        r = realize(tuple(specs), levels, led, required_hms=required_hms)
        if not isinstance(r, Refusal):
            return tuple(specs), notes
        s = r.slot
        cur = specs[s]
        fixed = specs[:s]
        fixed_levels = list(levels[:s + 1])
        replacement = None
        for moves in [cur.moves] + [m for m in ranked[s] if m != cur.moves]:
            for item in dict.fromkeys([cur.item, *C.held_item_candidates(cur.species, moves, led, team), None]):
                cand = MemberSpec(cur.species, cur.variant, moves, item, cur.ability, cur.ability_reason)
                # partial team: copies only (006: required HMs are placed on whole teams)
                if not isinstance(realize(tuple(fixed + [cand]), fixed_levels, led), Refusal):
                    replacement = cand
                    break
            if replacement:
                break
        if replacement is None:
            return r
        notes.append(f"slot {s + 1}: {cur.label()} -> {replacement.label()} ({r.reason})")
        specs[s] = replacement
    r = realize(tuple(specs), levels, led, required_hms=required_hms)
    return (tuple(specs), notes) if not isinstance(r, Refusal) else r


@cache
def _floor_cached(spec: MemberSpec, led_id: int) -> int | None:
    led = _LEDGERS[led_id]
    lo_opts = variant_of(spec, led).options(led)
    if not lo_opts:
        return None

    def ok(level: int) -> bool:
        return not isinstance(realize((spec,), [level], led), Refusal)

    lo = min(o.min_level for o in lo_opts)
    if ok(lo):
        return lo
    if not ok(100):
        return None
    hi = 100  # ok(hi) True, ok(lo) False
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ok(mid):
            hi = mid
        else:
            lo = mid
    return hi


_LEDGERS: dict[int, object] = {}


def member_floor(spec: MemberSpec, led) -> int | None:
    """Lowest start level at which this member alone is legal (None: never)."""
    _LEDGERS[id(led)] = led
    return _floor_cached(spec, id(led))


def resource_lines(real: Realized, led) -> list:
    """Resources sheet rows (contracts/spreadsheet.md): limited TMs and items, who uses them."""
    from platsim.report.json_report import ResourceLine

    out = []
    names = [b.species for b in real.team.builds]
    team = tuple(o.stages[-1].species for o in real.options)
    for res, n in real.uses.items():
        out.append(ResourceLine(resource=res, kind=_resource_kind(res), used_by=[f"{s + 1}: {names[s]}" for s in real.who[res]],
                                copies_used=n, copies_available=copies(res, led, team)))
    return out


__all__ = ["MemberSpec", "Realized", "Refusal", "TeamSpec", "copies", "default_ability", "member_floor", "realize", "repair",
           "resource_lines", "spec_from_json", "spec_to_json", "variant_of"]
