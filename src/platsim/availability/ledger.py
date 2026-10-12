"""Availability ledger (T024): phases derived from gates and reachability, plus the queries the
legality validator uses.

Phase of an entry (never set by hand):
- `unobtainable`: a gate of kind `event_only` (Mystery Gift / distribution event, see
  gates.event_only_items) or `other_cartridge` (dual-slot GBA) - one cartridge alone never has it;
  or a project rule: an encounter of an EXCLUDED_SPECIES species, and the items that species holds
  in the wild (spec FR-006a, user decision 2026-10-07: Munchlax);
- `post_game`: its map is not reachable before the Champion (mapgraph strict reachability), or a
  post-game gate (script_flag / script_var / region), or an `uncertain` gate (conservative), or
  a `national_dex` gate while the National Dex verdict is negative, or a required item with no
  pre-Champion source;
- `pre_champion`: otherwise.

National Dex verdict (`national_dex_verdict`): the only grant is SetNationalDexEnabled in
scripts_sandgem_town_pokemon_research_lab.s, behind CheckLocalDexCompleted = every Sinnoh-dex
species *seen* (src/pokedex.c Pokedex_LocalDexCompleted, LOCAL_DEX_GOAL = REGIONAL_DEX_COUNT with
no exclusions). The verdict is positive only if (a) the grant node is pre-game when National Dex
branches are left open and (b) every species of res/pokemon/sinnoh_pokedex.json (entries 1..210;
entry 0 maps to regional number 0, tools/dataproc/src/dexproc.c) has a pre-Champion witness that
does not itself need the National Dex: a pre-Champion catch/gift/egg/trade/static entry, a
non-trade evolution of one, a trainer battle on a reachable map (seen even when lost), or a
scripted SetSpeciesSeen / DrawPokemonPreview.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from platsim.availability import gates as G
from platsim.availability import sources as S
from platsim.decomp._util import ref
from platsim.decomp.constants import rel
from platsim.legality.models import LegalityOptions
from platsim.pins import DECOMP_COMMIT, DECOMP_ROOT

PP = DECOMP_ROOT
UNLIMITED = S.UNLIMITED
PRE = "pre_champion"
POST = "post_game"
NEVER = "unobtainable"
SINNOH_DEX = PP / "res" / "pokemon" / "sinnoh_pokedex.json"
LAB = "scripts_sandgem_town_pokemon_research_lab"
POKEDEX_C = PP / "src" / "pokedex.c"
MAP_HEADER_C = PP / "src" / "map_header.c"
ITEMS_DIR = PP / "res" / "items" / "data"
ITEM_C = PP / "src" / "item.c"
PARTY_CALLBACKS_C = PP / "src" / "applications" / "party_menu" / "callbacks.c"
ITEM_USE_C = PP / "src" / "item_use_functions.c"

NEVER_KINDS = frozenset({G.KIND_EVENT_ONLY, "other_cartridge"})
# Maps entered by an item rather than a warp (the Explorer Kit opens the Underground).
ITEM_ENTERED_MAPS = {"MAP_HEADER_UNDERGROUND": "ITEM_EXPLORER_KIT"}


def _reached() -> tuple[frozenset[str], frozenset[str]]:
    """(maps reachable before the Champion, maps reachable with post-game edges too); both strict."""
    from platsim.availability.mapgraph import build_graph

    g = build_graph()
    return frozenset(g.reachable(strict=True)), frozenset(g.reachable(strict=True, post_game=True))


# 003 research R3: a map the decomp itself names UNUSED_ (generated/map_headers.txt) that the map graph
# cannot reach even with post-game edges can never be entered. Real post-game areas the graph cannot
# model (Turnback Cave's random warps, the Battle Tower rooms) are not UNUSED_ and stay plain POST.
UNUSED_MAP_PREFIX = "MAP_HEADER_UNUSED_"


@dataclass
class Classified:
    entry: S.Entry
    phase: str
    reasons: list[str] = field(default_factory=list)
    uncertain: bool = False
    needs_national_dex: bool = False
    # 003 research R3: on a map that cannot be entered even after the Champion. Phase stays POST;
    # no legality option ever admits such an entry.
    unreachable: bool = False

    def to_json(self) -> dict[str, Any]:
        d = self.entry.to_json()
        d["phase"] = self.phase
        d["phase_reasons"] = self.reasons
        d["uncertain"] = self.uncertain
        d["needs_national_dex"] = self.needs_national_dex
        d["unreachable"] = self.unreachable
        return d


def _base_phase(e: S.Entry, reached: frozenset[str], ever: frozenset[str] | None = None) -> Classified:
    reasons: list[str] = []
    kinds = {g["kind"] for g in e.gates}
    if kinds & NEVER_KINDS:
        for g in e.gates:
            if g["kind"] in NEVER_KINDS:
                reasons.append(f"{g['kind']} @{g['ref']}: {g['detail']}")
        return Classified(e, NEVER, reasons)
    phase = PRE
    uncertain = False
    natdex = False
    unreachable = False
    if e.map_header and e.map_header not in ITEM_ENTERED_MAPS and e.map_header not in reached:
        phase = POST
        reasons.append(f"region: {e.map_header} is not reachable before the Champion (mapgraph strict)")
        if ever is not None and e.map_header.startswith(UNUSED_MAP_PREFIX) and e.map_header not in ever:
            unreachable = True
            reasons.append(f"unreachable: {e.map_header} is an unused map that cannot be entered even after the "
                           "Champion (mapgraph strict, post-game edges)")
    for g in e.gates:
        if g["kind"] == G.KIND_UNCERTAIN:
            phase, uncertain = POST, True
            reasons.append(f"uncertain @{g['ref']}: {g['detail']} (treated as not pre-Champion)")
        elif g["post_game"] and g["kind"] == G.KIND_NATIONAL_DEX:
            natdex = True
        elif g["post_game"]:
            phase = POST
            reasons.append(f"{g['kind']} @{g['ref']}: {g['detail']}")
    return Classified(e, phase, reasons, uncertain, natdex, unreachable)


@dataclass(eq=False)
class Ledger:
    entries: list[Classified]
    national_dex: dict
    reached: frozenset[str]
    derived: dict = field(default_factory=dict)
    # Legality options (legality/models.LegalityOptions) this view applies. The entries and phases
    # never depend on them; what `pre()` admits does (003), so option-dependent caches key on them.
    options: LegalityOptions = field(default_factory=LegalityOptions)

    def with_options(self, options: LegalityOptions | None) -> Ledger:
        """A view of this ledger with other legality options: same entries and shared `derived`
        caches (option-dependent caches key on the options). One view object per options value, so
        callers that memoise per ledger object (optimizer) separate option sets automatically."""
        if options is None or options == self.options:
            return self
        views = self.derived.setdefault("_option_views", {})
        views.setdefault(self.options, self)
        if options not in views:
            views[options] = Ledger(self.entries, self.national_dex, self.reached, self.derived, options)
        return views[options]

    # -- queries -------------------------------------------------------------------------

    def pre(self, subject: str | None = None, kind: str | None = None) -> list[Classified]:
        """Entries usable under this view's options: pre-Champion entries, plus what the 003 rules
        admit (`admits`). With default options this is exactly the pre-Champion entries."""
        return [
            c for c in self.entries
            if (subject is None or c.entry.subject == subject) and (kind is None or c.entry.kind == kind) and self.admits(c)
        ]

    def admits(self, c: Classified) -> bool:
        """003 research R2: one phase filter for every reader.
        - pokemon sources (ACQUIRE_KINDS): PRE; POST with allow_post_game_pokemon; other-cartridge
          NEVER entries with allow_unobtainable_pokemon;
        - everything else (items, TMs, tutors, wild held items): PRE; POST with allow_post_game_items;
        - entries on maps that can never be entered (`unreachable`) are never admitted."""
        if c.phase == PRE:
            return True
        if c.unreachable:
            return False
        o = self.options
        if c.entry.kind in ACQUIRE_KINDS:
            if c.phase == POST:
                return o.allow_post_game_pokemon
            return c.phase == NEVER and o.allow_unobtainable_pokemon and any(r.startswith("other_cartridge") for r in c.reasons)
        return c.phase == POST and o.allow_post_game_items

    def species_sources(self, species: str) -> list[dict]:
        """Pre-Champion ways to own `species`: direct entries, then evolutions of an obtainable
        pre-evolution (EVO_TRADE / EVO_TRADE_WITH_HELD_ITEM excluded, FR-005). Breeding is not
        derived (an under-approximation)."""
        cache = self.derived.setdefault("species_sources", {})
        key = (self.options, species)  # `derived` is shared by every options view (003 research R2)
        if key not in cache:
            cache[key] = list(_species_sources(self, species))
        return cache[key]

    def tm_copies(self, tm: str) -> int | str:
        """'TM26' / 'ITEM_TM26' -> copies obtainable pre-Champion, or 'unlimited'. HMs are never
        consumed (party_menu/callbacks.c: Bag_TryRemoveItem only when !Item_IsHMMove)."""
        item = tm if tm.startswith("ITEM_") else f"ITEM_{tm}"
        n = self.item_copies(item)
        if item.startswith("ITEM_HM") and n not in (0, UNLIMITED):
            return UNLIMITED
        return n

    def item_copies(self, item: str) -> int | str:
        """Copies of `item` obtainable pre-Champion (0 if none). Berries with a pre-Champion source
        are unlimited when a berry patch is reachable (replanting; berry_patches.c yield >= 2)."""
        return _item_copies(self, item)

    def tutor_available(self, location: str) -> bool:
        return any(c.entry.detail == location for c in self.pre(kind="tutor"))

    def to_json(self) -> dict[str, Any]:
        return {
            "decomp_commit": DECOMP_COMMIT,
            "national_dex": self.national_dex,
            "pp_restore_between_battles": self.derived["pp_restore"],
            "counts": self.derived["counts"],
            "phase_rules": __doc__.split("Phase of an entry (never set by hand):")[1].split("National Dex verdict")[0].strip(),
            "entries": [c.to_json() for c in self.entries],
        }


# ---------------------------------------------------------------------------------------------
# Build


# Project rule (spec FR-003a, user decision 2026-10-07): sources that need the National Dex are excluded.
ALLOW_NATIONAL_DEX = False

# Project rule slot for pokemon excluded entirely (their encounters and wild held items become
# unobtainable). Empty since 003 (FR-008, user decision 2026-10-11): Munchlax, excluded by 001 FR-006a
# on 2026-10-07, is allowed again, and its wild held Leftovers count (the validator then allows
# Leftovers only on a team with Munchlax or Snorlax, 003 FR-009).
EXCLUDED_SPECIES: frozenset[str] = frozenset()
EXCLUDED_SPECIES_REASON = "project_rule: {sp} is excluded entirely"
ACQUIRE_KINDS = ("wild_slot", "gift", "egg", "static", "roamer", "npc_trade")


@cache
def build_ledger() -> Ledger:
    reached, ever = _reached()
    entries = _merge_wild(S.all_entries())
    entries += S.wild_held_item_entries(entries)  # spec FR-006a; phases follow the encounter's gates
    base = [_base_phase(e, reached) for e in entries]
    # Pass 1: without the National Dex (verdict inputs must not depend on it).
    _resolve_items(base, natdex_ok=False)
    verdict = national_dex_verdict(base, reached)
    final = [_apply_project_rules(_base_phase(e, reached, ever)) for e in entries]
    # User decision 2026-10-07 (spec FR-003a): National Dex sources are NOT allowed, even though the
    # decomp verdict says the National Dex is obtainable pre-Champion. The verdict is still recorded.
    _resolve_items(final, natdex_ok=verdict["pre_champion"] and ALLOW_NATIONAL_DEX)
    led = Ledger(final, verdict, reached)
    led.derived["pp_restore"] = pp_restore_between_battles(led)
    led.derived["counts"] = _counts(led)
    return led


def _apply_project_rules(c: Classified) -> Classified:
    """EXCLUDED_SPECIES: its encounters and its wild held items become unobtainable."""
    e = c.entry
    sp = e.subject if e.kind in ACQUIRE_KINDS else e.via_species if e.kind == "wild_held_item" else None
    if sp in EXCLUDED_SPECIES:
        c.phase = NEVER
        c.reasons.append(EXCLUDED_SPECIES_REASON.format(sp=sp))
    return c


def _merge_wild(entries: list[S.Entry]) -> list[S.Entry]:
    """Merge wild slots that differ only by slot index (same map, species, slot type, gates)."""
    out: list[S.Entry] = []
    index: dict[tuple, S.Entry] = {}
    for e in entries:
        if e.kind != "wild_slot":
            out.append(e)
            continue
        typ = re.sub(r"\s*\(slot \d+\)|\s+slot \d+$", "", e.detail).strip()
        key = (e.map_header, e.subject, typ, json.dumps(e.gates, sort_keys=True), tuple(e.requires_items), tuple(e.requires_any))
        cur = index.get(key)
        if cur is None:
            ne = S.Entry(e.kind, e.subject, e.map_header, e.quantity, list(e.gates), list(e.src), e.level, None, list(e.requires_items), list(e.requires_any), e.exclusive_group, typ,
                         rate_percent=e.rate_percent)
            index[key] = ne
            out.append(ne)
        else:
            lo = min(cur.level[0], e.level[0]) if cur.level and e.level else None
            hi = max(cur.level[1], e.level[1]) if cur.level and e.level else None
            cur.level = (lo, hi) if lo is not None else cur.level
            if cur.rate_percent is not None and e.rate_percent is not None:  # 003 R8: slots of one method add up
                cur.rate_percent += e.rate_percent
            for s in e.src:
                if s not in cur.src:
                    cur.src.append(s)
    return out


def _resolve_items(cs: list[Classified], natdex_ok: bool) -> None:
    """Fixpoint over item dependencies (rods, radar, HM03, honey, fossils, Explorer Kit)."""
    for c in cs:
        if c.needs_national_dex and c.phase == PRE and not natdex_ok:
            c.phase = POST
            c.reasons.append("national_dex: needs the National Dex (excluded: spec FR-003a, or decomp verdict negative)")
    pending = [c for c in cs if c.phase == PRE and (c.entry.requires_items or c.entry.requires_any or c.entry.map_header in ITEM_ENTERED_MAPS)]
    for c in pending:
        c.phase = "?"
    while True:
        have = {c.entry.subject for c in cs if c.phase == PRE}
        changed = False
        for c in pending:
            if c.phase != "?":
                continue
            req = list(c.entry.requires_items)
            if c.entry.map_header in ITEM_ENTERED_MAPS:
                req.append(ITEM_ENTERED_MAPS[c.entry.map_header])
            if all(r in have for r in req) and (not c.entry.requires_any or any(r in have for r in c.entry.requires_any)):
                c.phase = PRE
                changed = True
        if not changed:
            break
    for c in pending:
        if c.phase == "?":
            c.phase = POST
            missing = [r for r in c.entry.requires_items + c.entry.requires_any if r not in {x.entry.subject for x in cs if x.phase == PRE}]
            c.reasons.append(f"requires item(s) with no pre-Champion source: {', '.join(missing)}")
    # Propagate the National Dex dependency through required items (e.g. Poke Radar slots need
    # ITEM_POKE_RADAR, given only right after the National Dex).
    while True:
        free = {c.entry.subject for c in cs if c.phase == PRE and not c.needs_national_dex}
        changed = False
        for c in pending:
            if c.phase != PRE or c.needs_national_dex:
                continue
            req = list(c.entry.requires_items) + ([ITEM_ENTERED_MAPS[c.entry.map_header]] if c.entry.map_header in ITEM_ENTERED_MAPS else [])
            if any(r not in free for r in req) or (c.entry.requires_any and not any(r in free for r in c.entry.requires_any)):
                c.needs_national_dex = True
                c.reasons.append("national_dex: a required item is obtainable only with the National Dex")
                changed = True
        if not changed:
            break


def _regional_dex() -> list[tuple[str, str]]:
    text = SINNOH_DEX.read_text()
    data = json.loads(text)
    lines = text.splitlines()
    out = []
    for i, sp in enumerate(data):
        if i == 0:
            continue  # regional number 0: not in the dex (tools/dataproc/src/dexproc.c national[species] = i)
        ln = next(n for n, l in enumerate(lines, start=1) if f'"{sp}"' in l)
        out.append((sp, f"{rel(SINNOH_DEX)}:{ln}"))
    return out


def national_dex_verdict(base: list[Classified], reached: frozenset[str]) -> dict:
    from platsim.decomp.scripts import load_script_file

    sf = load_script_file(LAB)
    grant = next(c for c in sf.commands if any(p.op == "SCRCMD_GETSETNATIONALDEXENABLED" and p.operands[0].text == "1" for p in c.prims))
    lab_header = S._owners(LAB)[0]
    grant_gates = S.site_gates(lab_header, LAB, grant.index)
    grant_ok = lab_header in reached and not any(g["post_game"] and g["kind"] != G.KIND_NATIONAL_DEX or g["kind"] == G.KIND_UNCERTAIN for g in grant_gates)
    check = next(c for c in sf.commands if c.name == "CheckLocalDexCompleted")
    witnesses: dict[str, list[str]] = {}

    def add(sp_: str, why: str) -> None:
        witnesses.setdefault(sp_, []).append(why)

    pre = [c for c in base if c.phase == PRE and c.entry.kind in ("wild_slot", "gift", "egg", "static", "roamer", "npc_trade")]
    for c in pre:
        add(c.entry.subject, f"{c.entry.kind} {c.entry.map_header} {c.entry.src[0]}")
    seen_entries = [_base_phase(e, reached) for e in S.trainer_entries() + S.dex_seen_entries()]
    for c in seen_entries:
        if c.phase == PRE and not c.needs_national_dex:
            add(c.entry.subject, f"{c.entry.kind} {c.entry.map_header} {c.entry.src[0]} ({c.entry.detail})")
    # evolutions of owned species (non-trade): evolving registers the species
    from platsim.decomp.species import by_constant

    sp = by_constant()
    owned = {c.entry.subject for c in pre}
    frontier = list(owned)
    while frontier:
        s = frontier.pop()
        for ev in sp[s].evolutions if s in sp else ():
            if ev.method.startswith("EVO_TRADE"):
                continue
            add(ev.target, f"evolution of {s} ({ev.method})")
            if ev.target not in owned:
                owned.add(ev.target)
                frontier.append(ev.target)
    dex = _regional_dex()
    missing = [s for s, _ in dex if s not in witnesses]
    league = ("TRAINER_ELITE_FOUR", "TRAINER_CHAMPION")
    league_only = [s for s, _ in dex if s in witnesses and all(any(t in w for t in league) for w in witnesses[s])]
    return {
        "pre_champion": bool(grant_ok and not missing),
        "grant": {"ref": str(grant.ref), "gates": grant_gates, "pre_game_without_national_dex_branches": grant_ok},
        "condition": {
            "ref": str(check.ref),
            "rule": "Pokedex_LocalDexCompleted: seen Sinnoh-dex species >= LOCAL_DEX_GOAL",
            "src": [ref(POKEDEX_C, "BOOL Pokedex_LocalDexCompleted("), ref(PP / "include" / "pokedex.h", "#define LOCAL_DEX_GOAL")],
            "dex_size": len(dex),
        },
        "missing": missing,
        "witnesses_league_only": league_only,
        "witnesses": {s: witnesses[s][:3] for s, _ in dex if s in witnesses},
        "witness_count": {s: len(witnesses[s]) for s, _ in dex if s in witnesses},
    }


# ---------------------------------------------------------------------------------------------
# Queries


@cache
def _location_evolution_maps() -> dict[str, list[str]]:
    """EVO_LEVEL_MAGNETIC_FIELD / MOSS_ROCK / ICE_ROCK -> maps (src/map_header.c mapEvolutionMethods)."""
    text = MAP_HEADER_C.read_text()
    m = re.search(r"mapEvolutionMethods\[\] = \{(.*?)\};", text, re.S)
    toks = re.findall(r"(MAP_HEADER_\w+|EVO_\w+)", m.group(1))
    out: dict[str, list[str]] = {}
    for h, ev in zip(toks[::2], toks[1::2]):
        out.setdefault(ev, []).append(h)
    return out


def _species_sources(led: Ledger, species: str):
    from platsim.decomp.species import by_constant

    sp = by_constant()
    for c in led.pre(subject=species):
        if c.entry.kind in ("wild_slot", "gift", "egg", "static", "roamer", "npc_trade"):
            yield {"kind": c.entry.kind, "species": species, "map_header": c.entry.map_header, "detail": c.entry.detail,
                   "level": list(c.entry.level) if c.entry.level else None, "fixed_mon": c.entry.fixed_mon,
                   "exclusive_group": c.entry.exclusive_group, "needs_national_dex": c.needs_national_dex, "src": c.entry.src}
    # evolution from an obtainable pre-evolution
    for pre_key, pre_sp in sp.items():
        for ev in pre_sp.evolutions:
            if ev.target != species or pre_sp.form is not None:
                continue
            if ev.method in ("EVO_TRADE", "EVO_TRADE_WITH_HELD_ITEM"):
                continue
            need = []
            if isinstance(ev.param, str) and ev.param.startswith("ITEM_"):
                need.append(ev.param)
            ok = all(led.item_copies(i) != 0 for i in need)
            if isinstance(ev.param, str) and ev.param.startswith("SPECIES_"):
                ok = ok and bool(led.species_sources(ev.param))
            loc = _location_evolution_maps().get(ev.method)
            if loc is not None:
                ok = ok and any(h in led.reached for h in loc)
            if not ok:
                continue
            pre_sources = led.species_sources(pre_key)
            if pre_sources:
                yield {"kind": "evolution", "species": species, "from": pre_key, "method": ev.method, "param": ev.param,
                       "requires_items": need, "needs_national_dex": all(p.get("needs_national_dex") for p in pre_sources),
                       "via": pre_sources, "src": pre_sp_src(pre_sp)}


def pre_sp_src(s) -> list[str]:
    return list(getattr(s, "src", [])[:1])


def once_flag_groups(led: Ledger, item: str) -> dict[str, list[Classified]]:
    """Pre-Champion finite entries of `item` grouped by their one-time flag (Entry.once_flag)."""
    out: dict[str, list[Classified]] = {}
    for c in led.pre(subject=item):
        if c.entry.once_flag and c.entry.quantity != UNLIMITED and c.entry.kind not in ("trainer_seen", "dex_seen"):
            out.setdefault(c.entry.once_flag, []).append(c)
    return out


# 003 FR-009 (user decision 2026-10-11): Leftovers comes from wild Munchlax / Snorlax (they hold it in
# both held-item slots), and a team may use those copies only if one of them is on the team. Other
# sources (the post-game Victory Road item ball) count for any team.
TEAM_GATED_ITEMS = ("ITEM_LEFTOVERS",)


@cache
def item_holders(item: str) -> frozenset[str]:
    """Species whose wild data (res/pokemon/*/data.json held_items) holds `item` in either slot."""
    from platsim.decomp.species import by_constant

    out = set()
    for const, sp in by_constant().items():
        raw = json.loads((PP / "res" / "pokemon" / sp.key / "data.json").read_text()) if sp.form is None else {}
        if item in (raw.get("held_items") or {}).values():
            out.add(const)
    return frozenset(out)


def team_item_copies(led: Ledger, item: str, team_species) -> int | str:
    """Copies of `item` this team may use. For a TEAM_GATED_ITEMS item, the copies held by wild
    `item_holders(item)` count only when one of those species is on the team."""
    if item not in TEAM_GATED_ITEMS or set(team_species) & item_holders(item):
        return led.item_copies(item)
    holders = item_holders(item)
    return _item_copies(led, item, skip=lambda c: c.entry.kind == "wild_held_item" and c.entry.via_species in holders)


def _item_copies(led: Ledger, item: str, skip=None) -> int | str:
    """Sum of pre-Champion quantities, except that entries sharing a one-time flag (Entry.once_flag:
    an item ball shown in two map headers, a hidden item on a map seam, one NPC gift reachable from
    two rooms or two branches) are one acquisition: a flag group adds the max quantity of one
    member, not the sum."""
    total = 0
    groups: dict[str, int] = {}
    for c in led.pre(subject=item):
        if c.entry.kind in ("trainer_seen", "dex_seen") or (skip is not None and skip(c)):
            continue
        if c.entry.quantity == UNLIMITED:
            return UNLIMITED
        q = int(c.entry.quantity)
        if c.entry.once_flag:
            groups[c.entry.once_flag] = max(groups.get(c.entry.once_flag, 0), q)
        else:
            total += q
    total += sum(groups.values())
    if total and _is_berry(item) and led.pre(kind="berry_tree"):
        return UNLIMITED
    return total


def _shared_flag_groups(led: Ledger) -> list[dict]:
    """Every one-time flag shared by more than one pre-Champion entry of one item (counts summary)."""
    items = sorted({c.entry.subject for c in led.entries if c.phase == PRE and c.entry.once_flag})
    out = []
    for item in items:
        for flag, cs in once_flag_groups(led, item).items():
            if len(cs) > 1:
                out.append({"item": item, "flag": flag, "entries": [f"{c.entry.kind} {c.entry.map_header} {c.entry.src[0]}" for c in cs],
                            "flag_src": sorted({r for c in cs for r in c.entry.once_flag_src}),
                            "quantity_summed": sum(int(c.entry.quantity) for c in cs),
                            "quantity_counted": max(int(c.entry.quantity) for c in cs)})
    return out


@cache
def _item_json(item: str) -> dict:
    path = ITEMS_DIR / f"{item.removeprefix('ITEM_').lower()}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _is_berry(item: str) -> bool:
    return _item_json(item).get("fieldPocket") == "POCKET_BERRIES"


def pp_restore_between_battles(led: Ledger) -> dict:
    """True when some PP-restoring item (item data `itemUseParams.ppRestored`, or a berry whose hold
    effect restores PP) has unlimited pre-Champion copies, so PP can be refilled before each
    League battle."""
    items = {}
    for path in sorted(ITEMS_DIR.glob("*.json")):
        d = json.loads(path.read_text())
        params = d.get("itemUseParams") or {}
        if "ppRestored" in params or "ppRestoredAll" in params or any("pp" in k.lower() and "restore" in k.lower() for k in params):
            items["ITEM_" + path.stem.upper()] = ref(path, '"itemUseParams"')
    copies = {i: led.item_copies(i) for i in items}
    sources = {i: [f"{c.entry.kind} {c.entry.map_header} {c.entry.quantity} {c.entry.src[0]}" for c in led.pre(subject=i)] for i in items}
    value = any(v == UNLIMITED for v in copies.values())
    return {"value": value, "items": copies, "item_data": items, "sources": sources,
            "rule": "true iff a PP-restoring item has unlimited pre-Champion copies (shop, Game Corner, daily hidden item, daily gift, or berry replanting)"}


def _counts(led: Ledger) -> dict:
    from platsim.decomp.items import load_items
    from platsim.decomp.species import by_constant

    all_species = [k for k, s in by_constant().items() if s.form is None]
    avail_species = [s for s in all_species if led.species_sources(s)]
    tms = sorted({k for k in (c.entry.subject for c in led.entries) if re.fullmatch(r"ITEM_(TM|HM)\d\d", k)} | {f"ITEM_TM{i:02d}" for i in range(1, 93)})
    tm_counts = {t: led.tm_copies(t) for t in tms}
    held = sorted({k for k, it in load_items().items() if it.hold_effect != "HOLD_EFFECT_NONE"})
    held_counts = {h: led.item_copies(h) for h in held}
    phases: dict[str, int] = {}
    for c in led.entries:
        phases[c.phase] = phases.get(c.phase, 0) + 1
    return {
        "entries_by_phase": phases,
        "species_pre_champion": len(avail_species),
        "species_total": len(all_species),
        "tms_unlimited": sorted(t for t, v in tm_counts.items() if v == UNLIMITED),
        "tms_finite": {t: v for t, v in tm_counts.items() if v not in (0, UNLIMITED)},
        "tms_unavailable": sorted(t for t, v in tm_counts.items() if v == 0),
        "held_items_unlimited": sorted(h for h, v in held_counts.items() if v == UNLIMITED),
        "held_items_finite": {h: v for h, v in held_counts.items() if v not in (0, UNLIMITED)},
        "held_items_unavailable_count": sum(1 for v in held_counts.values() if v == 0),
        "shared_once_flag_groups": _shared_flag_groups(led),
        "maps_reachable": len(led.reached),
    }


def availability_json() -> dict:
    return build_ledger().to_json()


__all__ = ["Ledger", "build_ledger", "availability_json", "national_dex_verdict", "PRE", "POST", "NEVER"]
