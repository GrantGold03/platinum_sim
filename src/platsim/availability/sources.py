"""Acquisition sources (T023): one `Entry` per way of obtaining a species, item, TM or tutor move.

Every entry carries the gates found on its path and the `file:line` it was read from. Entries never
carry a phase: `platsim.availability.ledger` derives `phase` from the gates, the map graph
(mapgraph.build_graph().reachable(strict=True)) and the National Dex verdict.

Gate kinds (data-model Gate.kind, extended):
- `script_flag` / `script_var` / `national_dex` / `event_only` / `badge` / `badge_count`:
  from platsim.availability.gates.node_gates on the script node that grants the thing;
- `uncertain`: no event / init script / C trigger of the map reaches the node, or a structural
  doubt; the ledger treats it as NOT pre-Champion (conservative);
- `slot_type`: an encounter-slot rule of src/overlay006/wild_encounters.c (R2 rule 3);
- `other_cartridge`: needs a second cartridge (dual-slot GBA encounters) - FR-005, never;
- `tid_parity`: depends on the parity of the player's Trainer ID (underground weights).

Item dependencies (`requires_items`, all-of; `requires_any`, any-of) are resolved by the ledger:
a rod slot needs the rod, Poke Radar slots need ITEM_POKE_RADAR, surfing needs ITEM_HM03, honey
trees need ITEM_HONEY, the Underground needs ITEM_EXPLORER_KIT, a fossil revival needs the fossil.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from platsim.availability import gates as G
from platsim.availability.mapgraph import (
    _trigger_starts,
    events_of,
    map_header_names,
    map_headers,
)
from platsim.decomp._util import line_of, ref
from platsim.decomp.constants import Ref, load_enum, rel
from platsim.decomp.scripts import (
    OP_CALL_COMMON,
    all_script_stems,
    load_script_file,
    parse_int,
    resolve_script_id,
    successors,
)
from platsim.pins import DECOMP_ROOT

PP = DECOMP_ROOT
ENC_DIR = PP / "res" / "field" / "encounters"
WILD_C = PP / "src" / "overlay006" / "wild_encounters.c"
DUAL_SLOT_C = PP / "src" / "overlay006" / "dual_slot_encounters.c"
MARSH_C = PP / "src" / "overlay006" / "great_marsh_daily_encounters.c"
HONEY_C = PP / "src" / "overlay005" / "honey_tree.c"
MAP_HEADER_C = PP / "src" / "map_header.c"
FOSSIL_C = PP / "src" / "scrcmd_fossil.c"
ROAMING_C = PP / "src" / "roaming_pokemon.c"
STARTER_C = PP / "src" / "choose_starter" / "choose_starter_app.c"
NPC_TRADE_C = PP / "src" / "overlay006" / "npc_trade.c"
NPC_TRADES_DIR = PP / "res" / "npc_trades"
MART_H = PP / "include" / "data" / "mart_items.h"
SHOP_C = PP / "src" / "scrcmd_shop.c"
GAME_CORNER_C = PP / "src" / "scrcmd_game_corner_prize.c"
HIDDEN_H = PP / "include" / "data" / "field" / "hidden_items.h"
SCRIPT_MANAGER_C = PP / "src" / "script_manager.c"
MINING_C = PP / "src" / "underground" / "mining.c"
MINING_H = PP / "include" / "underground" / "mining.h"
UNDERGROUND_C = PP / "src" / "underground.c"
BERRY_INIT_H = PP / "include" / "data" / "berry_init.h"
BERRY_PATCHES_C = PP / "src" / "berry_patches.c"
POKEMON_C = PP / "src" / "pokemon.c"
TRAINERS_DIR = PP / "res" / "trainers" / "data"

UNLIMITED = "unlimited"

# Script ID ranges (include/script_manager.h:89-119; read through scripts.script_ranges()).
VISIBLE_ITEMS_FILE = "scripts_visible_items"
HIDDEN_ITEMS_FILE = "scripts_hidden_items"


@dataclass
class Entry:
    kind: str  # data-model AvailabilityEntry.kind (+ berry_tree, trainer_seen, dex_seen)
    subject: str  # SPECIES_* / ITEM_* / MOVE_*
    map_header: str | None
    quantity: int | str
    gates: list[dict] = field(default_factory=list)
    src: list[str] = field(default_factory=list)
    level: tuple[int, int] | None = None  # (min, max); None = not fixed (e.g. trade: your mon's level)
    fixed_mon: dict | None = None
    requires_items: list[str] = field(default_factory=list)
    requires_any: list[str] = field(default_factory=list)
    exclusive_group: str | None = None  # entries in one group exclude each other (starter choice)
    detail: str = ""

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["level"] = list(self.level) if self.level else None
        return d


def gate(kind: str, ref_: str | Ref, detail: str, post_game: bool, requires: str = "") -> dict:
    return {"kind": kind, "ref": str(ref_), "detail": detail, "post_game": post_game, "requires": requires}


def _g(g: G.Gate) -> dict:
    return gate(g.kind, g.ref, g.detail, g.post_game, g.requires)


# ---------------------------------------------------------------------------------------------
# Script-node gates


def site_gates(header: str | None, stem: str, idx: int) -> list[dict]:
    """Gates on every path that reaches script node (stem, idx) from what starts the map's scripts.

    For a map scripts file the starts are mapgraph._trigger_starts(header) (events, init scripts,
    C triggers; frame/coord rows whose var condition cannot hold pre-game are dropped), split by
    object visibility (`object_visibility`): an entry started only by talking to an object that is
    hidden for the whole pre-game cannot run. Otherwise (a shared file) the file's live entries.
    - not reachable from any start -> one `uncertain` gate (conservative);
    - reachable only from starts of objects hidden before the Champion -> those objects' gates;
    - post-game even with National Dex branches open (`post_game_by_flag`) -> its gates, plus a
      `script_flag` gate saying so when every listed gate is a national_dex one;
    - post-game only because of National Dex branches -> its national_dex gates (the ledger
      decides with the National Dex verdict);
    - pre-game -> the gates passed on pre-game paths (badge checks etc.), none post-game.
    """
    sf = load_script_file(stem)
    if header is None or map_headers()[header].scripts != stem:
        return _node_gate_records(stem, idx, None)
    starts, _ = _trigger_starts(header)
    if not starts:
        return [gate(G.KIND_UNCERTAIN, sf.commands[idx].ref, "untriggered: no event, init script or C trigger of the map starts this file", False)]
    vis, nat, hidden = _split_starts(header, starts)
    for group, extra in ((vis, []), (vis + nat, "natdex"), (starts, "hidden")):
        if not group:
            continue
        ng = G.node_gates(stem, idx, starts=group, local_file=stem)
        if not ng.reachable:
            continue
        recs = _records(ng)
        if extra == "natdex":
            recs += [g for n in nat for g in hidden_gates_for(header, n)]
        elif extra == "hidden":
            recs += [g for n in starts if n not in vis and n not in nat for g in hidden_gates_for(header, n)]
        return recs
    return [gate(G.KIND_UNCERTAIN, sf.commands[idx].ref, "untriggered: no start of the map reaches this node", False)]


def _node_gate_records(stem: str, idx: int, starts) -> list[dict]:
    ng = G.node_gates(stem, idx, starts=starts, local_file=stem)
    if not ng.reachable:
        return [gate(G.KIND_UNCERTAIN, ng.ref, "untriggered: no start reaches this node", False)]
    return _records(ng)


def _records(ng: G.NodeGates) -> list[dict]:
    out = [_g(x) for x in ng.gates]
    if ng.post_game and ng.post_game_by_flag:
        if all(x["kind"] == G.KIND_NATIONAL_DEX for x in out):
            out.append(gate(G.KIND_GAME_COMPLETED, ng.ref, "post-game even with National Dex branches open (gates.node_gates post_game_by_flag)", True))
    elif ng.post_game:
        out = [x for x in out if x["kind"] == G.KIND_NATIONAL_DEX] or [
            gate(G.KIND_NATIONAL_DEX, ng.ref, "reachable only through National Dex branches (post_game_by_flag is False)", True)
        ]
    return out


@cache
def _new_game_set_flags() -> frozenset[str]:
    sf = load_script_file("scripts_init_new_game")
    return frozenset(p.operands[0].text for c in sf.commands for p in c.prims if p.op == "SCRCMD_SETFLAG")


@cache
def _clear_flag_sites() -> dict[str, tuple[tuple[str, int], ...]]:
    out: dict[str, list] = {}
    for stem in all_script_stems():
        for c in load_script_file(stem).commands:
            for p in c.prims:
                if p.op == "SCRCMD_CLEARFLAG":
                    out.setdefault(p.operands[0].text, []).append((stem, c.index))
    return {k: tuple(v) for k, v in out.items()}


_VIS_IN_PROGRESS: set[str] = set()


@cache
def object_visibility(flag: str) -> tuple[str, tuple[dict, ...]]:
    if flag in _VIS_IN_PROGRESS:
        # A cycle (the ClearFlag site is itself started by this object): conservative.
        return "hidden", (gate(G.KIND_UNCERTAIN, rel(PP / "res/field/scripts/scripts_init_new_game.s"), f"{flag}: visibility depends on itself", False),)
    _VIS_IN_PROGRESS.add(flag)
    try:
        return _object_visibility(flag)
    finally:
        _VIS_IN_PROGRESS.discard(flag)


@cache
def _reached() -> frozenset[str]:
    from platsim.availability.mapgraph import build_graph

    return frozenset(build_graph().reachable(strict=True))


def _object_visibility(flag: str) -> tuple[str, tuple[dict, ...]]:
    """'visible' | 'natdex' | 'hidden', with gates, for an object event's hidden_flag.

    An object is hidden at the start of a game when scripts_init_new_game sets its flag; it can
    appear before the Champion only through a ClearFlag of that flag at a pre-game node. (A flag
    not set at new game is treated as visible; a flag set on map load by an OnTransition script
    is not modelled - over-approximation toward pre-game, noted in the report.)"""
    if not flag or flag == "0" or flag not in _new_game_set_flags():
        return "visible", ()
    sites = _clear_flag_sites().get(flag, ())
    nat, post = [], []
    reached = _reached()
    for stem, i in sites:
        owners = _owners(stem)
        live = [h for h in owners if h in reached]
        if owners and not live:
            post.append([gate(G.KIND_REGION, load_script_file(stem).commands[i].ref, f"ClearFlag {flag} runs only in {owners[0]}, which is not reachable before the Champion (strict map graph)", True)])
            continue
        recs = site_gates(live[0], stem, i) if live else _node_gate_records(stem, i, None)
        kinds = {r["kind"] for r in recs if r["post_game"]} | {"uncertain" for r in recs if r["kind"] == G.KIND_UNCERTAIN}
        if not kinds:
            return "visible", ()
        (nat if kinds == {G.KIND_NATIONAL_DEX} else post).append(recs)
    head = gate("object_hidden", ref(PP / "res/field/scripts/scripts_init_new_game.s", f"SetFlag {flag}"), f"{flag} is set at new game; shown only by ClearFlag at {len(sites)} site(s)", False)
    if nat:
        return "natdex", tuple([head] + [r for recs in nat for r in recs])
    tail = [r for recs in post for r in recs] or [gate(G.KIND_GAME_COMPLETED, head["ref"], f"{flag}: no ClearFlag site at all", True)]
    if not any(r["post_game"] for r in tail):
        tail.append(gate(G.KIND_UNCERTAIN, head["ref"], f"{flag}: every ClearFlag site is untriggered", False))
    return "hidden", tuple([head] + tail)


def _start_objects(header: str) -> dict[tuple[str, int], list[str | None]]:
    """start node -> hidden flags of the objects that start it (None = a non-object trigger)."""
    h = map_headers()[header]
    sf = load_script_file(h.scripts)
    out: dict[tuple[str, int], list[str | None]] = {}
    objs: dict[int, list[str]] = {}
    for o in events_of(header)["object"]:
        sid = o.data.get("script")
        if isinstance(sid, int) and 1 <= sid < 2000:
            objs.setdefault(sid - 1, []).append(o.data.get("hidden_flag", "0"))
    for i, trigs in G.entry_triggers(h.scripts).items():
        if i >= len(sf.entries):
            continue
        n = (sf.stem, sf.command_for_entry(i))
        flags = list(objs.get(i, []))
        n_obj_trigs = len(flags)
        if len(trigs) > n_obj_trigs:
            flags.append(None)
        out[n] = flags
    return out


def _split_starts(header: str, starts):
    info = _start_objects(header)
    vis, nat = [], []
    for n in starts:
        flags = info.get(n, [None])
        states = {("visible" if f is None else object_visibility(f)[0]) for f in flags}
        if "visible" in states:
            vis.append(n)
        elif "natdex" in states:
            nat.append(n)
    return vis, nat, None


def hidden_gates_for(header: str, n) -> list[dict]:
    out = []
    for f in _start_objects(header).get(n, []):
        if f is not None:
            out.extend(object_visibility(f)[1])
    return out


def _owners(stem: str) -> list[str]:
    return [h for h in map_header_names() if h in map_headers() and map_headers()[h].scripts == stem]


# ---------------------------------------------------------------------------------------------
# Wild encounters


@cache
def _anchor(path: Path, needle: str) -> str:
    return ref(path, needle)


@cache
def great_marsh_headers() -> dict[str, int]:
    """MAP_HEADER_GREAT_MARSH_n -> area index (GreatMarsh_GetAreaNumFromMapId)."""
    text = MARSH_C.read_text()
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"case (MAP_HEADER_\w+):\s*areaNum = (\d+);", text)}


@cache
def honey_tree_headers() -> tuple[tuple[str, str], ...]:
    text = HONEY_C.read_text()
    m = re.search(r"sHoneyTreeMapHeaderIDs\[NUM_HONEY_TREES\] = \{(.*?)\};", text, re.S)
    base = text.count("\n", 0, m.start()) + 1
    out = []
    for i, line in enumerate(m.group(0).splitlines()):
        h = re.search(r"(MAP_HEADER_\w+)", line)
        if h:
            out.append((h.group(1), f"{rel(HONEY_C)}:{base + i}"))
    return tuple(out)


@cache
def feebas_headers() -> tuple[str, ...]:
    text = MAP_HEADER_C.read_text()
    m = re.search(r"BOOL MapHeader_HasFeebasTiles\(.*?\{(.*?)\n\}", text, re.S)
    return tuple(re.findall(r"(MAP_HEADER_\w+)", m.group(1)))


def _species_ok(s: str) -> bool:
    return s.startswith("SPECIES_") and s != "SPECIES_NONE"


def _add_slot(out, header, kind_detail, sp, lo, hi, src, gates=(), req=(), req_any=()):
    if not _species_ok(sp):
        return
    out.append(Entry("wild_slot", sp, header, UNLIMITED, list(gates), list(src), (lo, hi), None, list(req), list(req_any), None, kind_detail))


def _enc_line(path: Path, key: str) -> str:
    return ref(path, f'"{key}"')


def wild_entries() -> list[Entry]:
    out: list[Entry] = []
    swarm_gates = _enable_swarm_gates()
    marsh = great_marsh_headers()
    for h in map_header_names():
        mh = map_headers().get(h)
        if mh is None or mh.encounters == "ENCOUNTERS_NONE":
            continue
        path = ENC_DIR / f"{mh.encounters}.json"
        d = json.loads(path.read_text())
        header_ref = str(mh.ref)
        land = d.get("land_encounters", [])
        if d.get("land_rate", 0):
            for i, s in enumerate(land):
                if h in marsh and i in (6, 7):
                    continue  # always replaced while the Safari Game runs (wild_encounters.c:340)
                _add_slot(out, h, f"grass slot {i}", s["species"], s["level"], s["level"], [_enc_line(path, "land_encounters"), header_ref])
            for key, slots, cond in (("day", (2, 3), "DAY/TWILIGHT"), ("night", (2, 3), "NIGHT/LATE_NIGHT")):
                for sp, slot in zip(d.get(key, []), slots):
                    lv = land[slot]["level"]
                    _add_slot(out, h, f"{key} {cond} (slot {slot})", sp, lv, lv, [_enc_line(path, key), _anchor(WILD_C, "int timeOfDay = GetTimeOfDay();")])
            for sp, slot in zip(d.get("swarms", []), (0, 1)):
                lv = land[slot]["level"]
                _add_slot(out, h, f"swarm (slot {slot})", sp, lv, lv, [_enc_line(path, "swarms")],
                          [gate("slot_type", _anchor(WILD_C, "if (SpecialEncounter_IsSwarmEnabled(specialEncounter))"), "swarm slots need EnableSwarms", False)] + list(swarm_gates))
            for sp, slot in zip(d.get("radar", []), (4, 5, 10, 11)):
                lv = land[slot]["level"]
                _add_slot(out, h, f"poke radar (slot {slot})", sp, lv, lv, [_enc_line(path, "radar"), _anchor(WILD_C, "if (radarData->shakeType == 1) {")],
                          [gate("slot_type", _anchor(WILD_C, "if (radarData->shakeType == 1) {"), "Poke Radar patch encounter", False)], ["ITEM_POKE_RADAR"])
            for ver in ("ruby", "sapphire", "emerald", "firered", "leafgreen"):
                for sp, slot in zip(d.get(ver, []), (8, 9)):
                    lv = land[slot]["level"]
                    _add_slot(out, h, f"dual-slot {ver} (slot {slot})", sp, lv, lv, [_enc_line(path, ver)],
                              [gate("other_cartridge", _anchor(DUAL_SLOT_C, "if (!nationalDexObtained) {"), f"needs a GBA {ver} cartridge in slot 2 (FR-005) and the National Dex", False)])
            if "daily_encounters" in d:  # Trophy Garden
                for sp in d["daily_encounters"]:
                    lo, hi = land[6]["level"], land[7]["level"]
                    _add_slot(out, h, "trophy garden daily (slots 6/7)", sp, min(lo, hi), max(lo, hi), [_enc_line(path, "daily_encounters"), _anchor(WILD_C, "if (MapHeader_IsTrophyGarden(fieldSystem->location->mapHeaderID)) {")],
                              [gate(G.KIND_NATIONAL_DEX, f"{rel(WILD_C)}:{line_of(WILD_C, 'if (nationalDexObtained) {', 209)}", "Trophy Garden slots are replaced only with the National Dex", True)] + list(_backlot_gates()))
        if d.get("surf_rate", 0):
            for i, s in enumerate(d.get("surf_encounters", [])):
                _add_slot(out, h, f"surf slot {i}", s["species"], s["level_min"], s["level_max"], [_enc_line(path, "surf_encounters"), header_ref], req=["ITEM_HM03"])
        for rod, item in (("old_rod", "ITEM_OLD_ROD"), ("good_rod", "ITEM_GOOD_ROD"), ("super_rod", "ITEM_SUPER_ROD")):
            if d.get(f"{rod}_rate", 0):
                for i, s in enumerate(d.get(f"{rod}_encounters", [])):
                    _add_slot(out, h, f"{rod} slot {i}", s["species"], s["level_min"], s["level_max"], [_enc_line(path, f"{rod}_encounters"), header_ref], req=[item])
        if h in marsh:
            look = ENC_DIR / "encounters_great_marsh_lookout.json"
            ld = json.loads(look.read_text())
            lo, hi = sorted((land[6]["level"], land[7]["level"]))
            for sp in dict.fromkeys(ld["before_national_dex"]):
                _add_slot(out, h, f"great marsh daily, area {marsh[h]} (before National Dex)", sp, lo, hi, [_enc_line(look, "before_national_dex"), _anchor(MARSH_C, "encDataGroup = 10;")])
            for sp in dict.fromkeys(ld["after_national_dex"]):
                _add_slot(out, h, f"great marsh daily, area {marsh[h]} (after National Dex)", sp, lo, hi, [_enc_line(look, "after_national_dex"), _anchor(MARSH_C, "encDataGroup = 9;")],
                          [gate(G.KIND_NATIONAL_DEX, _anchor(MARSH_C, "if (nationalDexObtained) {"), "after_national_dex list needs the National Dex", True)])
        if h in feebas_headers():
            for rod in ("old_rod", "good_rod", "super_rod"):
                if d.get(f"{rod}_rate", 0):
                    s = d[f"{rod}_encounters"][0]
                    _add_slot(out, h, f"feebas tile ({rod})", "SPECIES_FEEBAS", s["level_min"], s["level_max"],
                              [_anchor(WILD_C, "if (MapHeader_HasFeebasTiles(fieldSystem->location->mapHeaderID)"), _anchor(MAP_HEADER_C, "BOOL MapHeader_HasFeebasTiles(")],
                              req=[f"ITEM_{rod.upper()}"])
    out.extend(_honey_entries())
    return out


def _honey_entries() -> list[Entry]:
    path = ENC_DIR / "encounters_honey_tree.json"
    d = json.loads(path.read_text())
    lv_ref = _anchor(WILD_C, "int species = HoneyTree_GetSpecies(fieldSystem);")
    out = []
    for header, href in honey_tree_headers():
        for group in ("common", "uncommon", "rare"):
            for sp in dict.fromkeys(d[group]):
                det = f"honey tree ({group})" + ("; only on the Trainer-ID-dependent Munchlax trees (honey_tree.c IsMunchlaxTree)" if group == "rare" else "")
                out.append(Entry("wild_slot", sp, header, UNLIMITED, [], [ref(path, f'"{group}"'), href, lv_ref], None, None, ["ITEM_HONEY"], [], None, det))
    return out


@cache
def _enable_swarm_gates() -> tuple[dict, ...]:
    """Gates of every EnableSwarms site (SCRCMD_ENABLESWARMS); swarms need one to have run."""
    sites = _prim_sites("SCRCMD_ENABLESWARMS")
    if not sites:
        return (gate(G.KIND_UNCERTAIN, rel(WILD_C), "no EnableSwarms site found", False),)
    out = []
    for stem, idx in sites:
        owners = _owners(stem)
        gs = site_gates(owners[0] if owners else None, stem, idx)
        out.extend(gs or [gate("script", load_script_file(stem).commands[idx].ref, "EnableSwarms site (pre-game)", False)])
    return tuple(out)


@cache
def _backlot_gates() -> tuple[dict, ...]:
    out = []
    for stem, idx in _prim_sites("SCRCMD_ADDTROPHYGARDENMON"):
        owners = _owners(stem)
        out.extend(site_gates(owners[0] if owners else None, stem, idx))
    return tuple(out)


@cache
def _prim_sites(op: str) -> tuple[tuple[str, int], ...]:
    out = []
    for stem in all_script_stems():
        for c in load_script_file(stem).commands:
            if any(p.op == op for p in c.prims):
                out.append((stem, c.index))
    return tuple(out)


# ---------------------------------------------------------------------------------------------
# Gifts, eggs, static encounters, roamers, fossils, NPC trades


@cache
def starter_species() -> tuple[tuple[str, str], ...]:
    out = []
    for i, line in enumerate(STARTER_C.read_text().splitlines(), start=1):
        m = re.match(r"#define STARTER_OPTION_\d+\s+(SPECIES_\w+)", line)
        if m:
            out.append((m.group(1), f"{rel(STARTER_C)}:{i}"))
    return tuple(out)


@cache
def roamer_species() -> dict[str, tuple[str, int, str]]:
    text = ROAMING_C.read_text().splitlines()
    out = {}
    for i, line in enumerate(text):
        m = re.match(r"\s*case (ROAMING_SLOT_\w+):", line)
        if m:
            sp = re.search(r"species = (SPECIES_\w+);", text[i + 1])
            lv = re.search(r"level = (\d+);", text[i + 2])
            if sp and lv:
                out[m.group(1)] = (sp.group(1), int(lv.group(1)), f"{rel(ROAMING_C)}:{i + 2}")
    return out


@cache
def fossil_species() -> tuple[tuple[str, str, str], ...]:
    out = []
    for i, line in enumerate(FOSSIL_C.read_text().splitlines(), start=1):
        m = re.search(r"\.item = (ITEM_\w+), \.species = (SPECIES_\w+)", line)
        if m:
            out.append((m.group(1), m.group(2), f"{rel(FOSSIL_C)}:{i}"))
    return tuple(out)


@cache
def _species_data():
    from platsim.decomp.species import by_constant

    return by_constant()


def npc_trade_fixed_mon(trade_const: str) -> tuple[dict, str, str]:
    """FixedMon of an NPC trade (res/npc_trades/<name>.json, built by NPCTrade_CreateMon)."""
    from platsim.decomp.stats import nature_name

    path = NPC_TRADES_DIR / f"{trade_const.removeprefix('NPC_TRADE_').lower()}.json"
    d = json.loads(path.read_text())
    sp = d["species"]
    pers = int(d["personality"])
    base = _species_data()[sp]
    slot = 2 if base.abilities[1] is not None and pers & 1 else 1
    fixed = {
        "species": sp,
        "level": None,  # = the level of the mon you hand over (npc_trade.c NPCTrade_CreateMon level arg)
        "ivs": {"hp": d["hpIV"], "atk": d["atkIV"], "def": d["defIV"], "spa": d["spAtkIV"], "spd": d["spDefIV"], "spe": d["speedIV"]},
        "personality": pers,
        "nature": nature_name(pers),
        "ability_slot": slot,
        "ability": base.abilities[slot - 1],
        "held_item": d["heldItem"],
        "is_traded": True,
        "requested_species": d["requestedSpecies"],
        "src": [ref(path), ref(NPC_TRADE_C, "Pokemon_InitWith(mon, npcTradeMon->species, level"), ref(POKEMON_C, "return (u8)(monPersonality % NATURE_COUNT);")],
    }
    return fixed, sp, ref(path)


def mon_entries() -> list[Entry]:
    out: list[Entry] = []
    ops = {
        "SCRCMD_GIVEPOKEMON": "gift",
        "SCRCMD_GIVEEGG": "egg",
        "SCRCMD_STARTWILDBATTLE": "static",
        "SCRCMD_STARTLEGENDARYBATTLE": "static",
        "SCRCMD_STARTFATEFULENCOUNTER": "static",
        "SCRCMD_STARTGIRATINAORIGINBATTLE": "static",
        "SCRCMD_ACTIVATEROAMINGPOKEMON": "roamer",
        "SCRCMD_INITNPCTRADE": "npc_trade",
    }
    for stem in all_script_stems():
        sf = load_script_file(stem)
        owners = _owners(stem)
        for c in sf.commands:
            for p in c.prims:
                kind = ops.get(p.op)
                if kind is None:
                    continue
                o = [x.text for x in p.operands]
                if not owners:
                    continue  # shared file: no map runs it (counted only through its callers)
                for h in owners:
                    gs = site_gates(h, stem, c.index)
                    base_src = [str(c.ref)]
                    if kind == "npc_trade":
                        fixed, sp, tref = npc_trade_fixed_mon(o[0])
                        out.append(Entry("npc_trade", sp, h, 1, gs, base_src + [tref], None, fixed, [], [], None, f"{o[0]} (give {fixed['requested_species']})"))
                    elif kind == "roamer":
                        sp, lv, rref = roamer_species()[o[0]]
                        out.append(Entry("roamer", sp, h, 1, gs, base_src + [rref], (lv, lv), None, [], [], None, o[0]))
                    elif kind == "egg":
                        out.append(Entry("egg", o[0], h, 1, gs, base_src, (1, 1), None, [], [], None, "GiveEgg (hatches at level 1)"))
                    elif o[0].startswith("SPECIES_"):
                        lv = parse_int(o[1])
                        out.append(Entry(kind, o[0], h, 1, gs, base_src, (lv, lv) if lv is not None else None, None, [], [], None, c.name))
                    elif o[0] == "VAR_0x8000" and _prev_cmd(sf, c.index, "GetPlayerStarterSpecies"):
                        lv = parse_int(o[1])
                        for sp, sref in starter_species():
                            out.append(Entry("gift", sp, h, 1, gs, base_src + [sref], (lv, lv), None, [], [], "starter", "starter choice (one of three)"))
                    elif _prev_cmd(sf, c.index, "GetSpeciesFromFossil", window=40):
                        lv = parse_int(o[1])
                        for item, sp, fref in fossil_species():
                            out.append(Entry("gift", sp, h, 1, gs, base_src + [fref], (lv, lv), None, [item], [], None, f"fossil revival of {item}"))
                    else:
                        out.append(Entry(kind, o[0], h, 1, gs + [gate(G.KIND_UNCERTAIN, c.ref, f"species operand {o[0]} not resolved", False)], base_src, None, None, [], [], None, c.name))
    return out


def _prev_cmd(sf, idx: int, name: str, window: int = 3) -> bool:
    return any(sf.commands[i].name == name for i in range(max(0, idx - window), idx))


# ---------------------------------------------------------------------------------------------
# Trainer battles (seen-species witnesses for the National Dex verdict)


@cache
def _trainer_party(const: str) -> tuple[tuple[str, ...], str]:
    path = TRAINERS_DIR / f"{const.removeprefix('TRAINER_').lower()}.json"
    d = json.loads(path.read_text())
    return tuple(m["species"] for m in d["party"]), ref(path)


def trainer_entries() -> list[Entry]:
    """Opponent species seen in battle (src/battle/battle_system.c BattleSystem_DexFlagSeen marks
    every opponent battler sent out, win or lose).

    - trainer object events (`"script": "TRAINER_*"`, converted by tools/jsoncnv/event.py), gated
      by their map (ledger) and by `object_visibility` of their hidden_flag;
    - StartTrainerBattle / StartTagBattle with literal TRAINER_* operands, gated by script node.
    """
    trainers = load_enum("trainers")
    out: list[Entry] = []
    for h in map_header_names():
        if h not in map_headers():
            continue
        for o in events_of(h)["object"]:
            sid = o.data.get("script")
            if isinstance(sid, str) and sid.startswith("TRAINER_") and sid in trainers.values:
                party, pref = _trainer_party(sid)
                flag = o.data.get("hidden_flag", "0")
                state, vg = object_visibility(flag)
                gs = [] if state == "visible" else list(vg)
                for sp in dict.fromkeys(party):
                    out.append(Entry("trainer_seen", sp, h, 0, gs, [str(o.ref), pref], None, None, [], [], None, f"{sid} hidden_flag={flag}"))
    for stem in all_script_stems():
        sf = load_script_file(stem)
        owners = _owners(stem)
        for c in sf.commands:
            for p in c.prims:
                if p.op not in ("SCRCMD_STARTTRAINERBATTLE", "SCRCMD_STARTTAGBATTLE"):
                    continue
                for x in p.operands[(1 if p.op == "SCRCMD_STARTTAGBATTLE" else 0):]:
                    t = x.text
                    if t.startswith("TRAINER_") and t in trainers.values and (TRAINERS_DIR / f"{t.removeprefix('TRAINER_').lower()}.json").exists():
                        party, pref = _trainer_party(t)
                        for h in owners:
                            gs = site_gates(h, stem, c.index)
                            for sp in dict.fromkeys(party):
                                out.append(Entry("trainer_seen", sp, h, 0, gs, [str(c.ref), pref], None, None, [], [], None, t))
    return out


def dex_seen_entries() -> list[Entry]:
    """Species marked seen by a script (SetSpeciesSeen / DrawPokemonPreview, src/scrcmd.c
    FieldSystem_WriteSpeciesSeen)."""
    out = []
    for op in ("SCRCMD_SETSPECIESSEEN", "SCRCMD_DRAWPOKEMONPREVIEW"):
        for stem, idx in _prim_sites(op):
            c = load_script_file(stem).commands[idx]
            sp = next((p.operands[0].text for p in c.prims if p.op == op), "")
            if not sp.startswith("SPECIES_"):
                continue
            for h in _owners(stem):
                out.append(Entry("dex_seen", sp, h, 0, site_gates(h, stem, idx), [str(c.ref), ref(PP / "src" / "scrcmd.c", "static void FieldSystem_WriteSpeciesSeen(FieldSystem *fieldSystem, u16 species)")], None, None, [], [], None, c.name))
    return out


# ---------------------------------------------------------------------------------------------
# Items


@cache
def _daily_flag_range() -> tuple[int, int]:
    e = load_enum("vars_flags")
    return e["DAILY_FLAGS_START"], e["DAILY_FLAGS_END"]


def _is_daily_flag(flag: str) -> bool:
    e = load_enum("vars_flags")
    lo, hi = _daily_flag_range()
    v = e.values.get(flag)
    return v is not None and lo <= v <= hi


def visible_item_entries() -> list[Entry]:
    """Item balls: object events with a 7000-range script (VisibleItems_*), only when some events
    JSON references the script (R2)."""
    sf = load_script_file(VISIBLE_ITEMS_FILE)
    out = []
    for h in map_header_names():
        if h not in map_headers():
            continue
        for o in events_of(h)["object"]:
            sid = o.data.get("script")
            if not isinstance(sid, int) or sid < 1:
                continue
            f, entry = resolve_script_id(sid, map_headers()[h].scripts)
            if f != VISIBLE_ITEMS_FILE or entry >= len(sf.entries):
                continue
            idx = sf.command_for_entry(entry)
            item = qty = None
            for c in sf.commands[idx : idx + 4]:
                if c.name == "SetVar" and c.args[0] == "VAR_0x8008":
                    item, iref = c.args[1], c.ref
                if c.name == "SetVar" and c.args[0] == "VAR_0x8009":
                    qty = parse_int(c.args[1])
            if item is None or qty is None:
                continue
            out.append(Entry("item_ball", item, h, qty, [], [str(o.ref), str(iref)], None, None, [], [], None, sf.entry_label(entry)))
    return out


@cache
def daily_hidden_flags() -> dict[str, str]:
    """Hidden-item flags cleared by FieldSystem_ClearDailyHiddenItemFlags (src/script_manager.c)."""
    out = {}
    for i, line in enumerate(SCRIPT_MANAGER_C.read_text().splitlines(), start=1):
        for m in re.finditer(r"(FLAG_OBTAINED_HIDDEN_\w+) - HIDDEN_ITEM_FLAGS_START", line):
            out[m.group(1)] = f"{rel(SCRIPT_MANAGER_C)}:{i}"
    return out


def hidden_item_entries() -> list[Entry]:
    flags = load_enum("vars_flags")
    start = flags["HIDDEN_ITEM_FLAGS_START"]
    table: dict[int, tuple[str, int, str, str]] = {}
    for i, line in enumerate(HIDDEN_H.read_text().splitlines(), start=1):
        m = re.search(r"HIDDEN_ITEM_ENTRY\((ITEM_\w+),\s*(\d+),\s*\d+,\s*(FLAG_\w+)\)", line)
        if m:
            table[flags[m.group(3)] - start] = (m.group(1), int(m.group(2)), m.group(3), f"{rel(HIDDEN_H)}:{i}")
    daily = daily_hidden_flags()
    lo = next(r.threshold for r in __import__("platsim.decomp.scripts", fromlist=["script_ranges"]).script_ranges() if r.file == HIDDEN_ITEMS_FILE)
    out = []
    for h in map_header_names():
        if h not in map_headers():
            continue
        for b in events_of(h)["bg"]:
            sid = b.data.get("script")
            if not isinstance(sid, int) or sid < lo or sid - lo not in table:
                continue
            item, qty, flag, href = table[sid - lo]
            q: int | str = qty
            det = flag
            src = [str(b.ref), href]
            if flag in daily:
                q, det = UNLIMITED, f"{flag} (re-hidden daily)"
                src.append(daily[flag])
            out.append(Entry("hidden_item", item, h, q, [], src, None, None, [], [], None, det))
    return out


@cache
def _give_common_nodes() -> frozenset[tuple[str, int]]:
    """First commands of CommonScript_AddItemQuantity* (the targets of Common_GiveItemQuantity*)."""
    sf = load_script_file("scripts_common")
    out = set()
    for i, (label, _) in enumerate(sf.entries):
        if label.startswith("CommonScript_AddItemQuantity"):
            out.add(("scripts_common", sf.command_for_entry(i)))
    return frozenset(out)


def _const_dataflow(sf) -> dict[int, dict[str, frozenset]]:
    """Possible literal values of VAR_0x8004 / VAR_0x8005 before each command (intra-file, calls
    followed, union at joins; '?' = written non-literally)."""
    tracked = ("VAR_0x8004", "VAR_0x8005")
    state: dict[int, dict[str, frozenset]] = {}
    work = [(sf.command_for_entry(i), {v: frozenset({"?"}) for v in tracked}) for i in range(len(sf.entries))]
    while work:
        idx, st = work.pop()
        if idx >= len(sf.commands):
            continue
        cur = state.get(idx)
        if cur is not None:
            merged = {v: cur[v] | st[v] for v in tracked}
            if merged == cur:
                continue
            st = merged
        state[idx] = st
        c = sf.commands[idx]
        nst = dict(st)
        for p in c.prims:
            ops = [o.text for o in p.operands]
            if p.op == "SCRCMD_SETVARFROMVALUE" and ops[0] in tracked:
                nst[ops[0]] = frozenset({ops[1]})
            elif p.op in ("SCRCMD_SETVARFROMVAR", "SCRCMD_ADDVAR", "SCRCMD_SUBVAR") and ops[0] in tracked:
                nst[ops[0]] = frozenset({"?"})
        for s in successors(sf, idx, sf.stem):
            if s.file == sf.stem:
                work.append((s.index, nst))
    return state


def npc_gift_entries() -> list[Entry]:
    """Common_GiveItemQuantity* (VAR_0x8004 item, VAR_0x8005 count) and AddItem with literals."""
    targets = _give_common_nodes()
    out = []
    skip = {VISIBLE_ITEMS_FILE, HIDDEN_ITEMS_FILE, "scripts_common"}
    for stem in all_script_stems():
        if stem in skip:
            continue
        owners = _owners(stem)
        if not owners:
            continue
        sf = load_script_file(stem)
        flow = None
        for c in sf.commands:
            for p in c.prims:
                items: list[tuple[str, int | None]] = []
                if p.op == OP_CALL_COMMON:
                    sid = parse_int(p.operands[0].text)
                    f, e = resolve_script_id(sid, stem)
                    if (f, load_script_file(f).command_for_entry(e)) not in targets:
                        continue
                    if flow is None:
                        flow = _const_dataflow(sf)
                    st = flow.get(c.index)
                    if st is None:
                        continue
                    qs = [parse_int(q) for q in st["VAR_0x8005"] if q != "?"]
                    q = min((x for x in qs if x is not None), default=None)
                    items = [(i, q) for i in sorted(st["VAR_0x8004"]) if i.startswith("ITEM_")]
                elif p.op == "SCRCMD_ADDITEM":
                    o = [x.text for x in p.operands]
                    if o[0].startswith("ITEM_"):
                        items = [(o[0], parse_int(o[1]))]
                if not items:
                    continue
                daily = _daily_guard(sf, c.index)
                for h in owners:
                    gs = site_gates(h, stem, c.index)
                    for item, q in items:
                        qty: int | str = UNLIMITED if daily else (q if q is not None else 1)
                        det = f"daily ({daily})" if daily else ("several possible items at this site; each counted once" if len(items) > 1 else "")
                        if q is None and not daily:
                            det = (det + "; " if det else "") + "quantity not literal, counted as 1"
                        out.append(Entry("npc_item_gift", item, h, qty, gs, [str(c.ref)], None, None, [], [], None, det))
    return out


def _daily_guard(sf, idx: int) -> str | None:
    """A FLAG_DAILY_* that some path to this gift sets (the gift repeats each day)."""
    from platsim.decomp.scripts import walk

    for i in range(len(sf.entries)):
        start = sf.command_for_entry(i)
        cmds = walk(sf, start)
        if not any(c.file == sf.stem and c.index == idx for c in cmds):
            continue
        for c in cmds:
            for p in c.prims:
                if p.op == "SCRCMD_SETFLAG" and _is_daily_flag(p.operands[0].text):
                    return f"{p.operands[0].text} set at {c.ref}"
    return None


@cache
def mart_lists() -> dict[str, list[tuple[str, str]]]:
    """mart_items.h: list name -> [(ITEM_*, file:line)]; plus PokeMartCommonItems with badges."""
    out: dict[str, list[tuple[str, str]]] = {}
    cur = None
    for i, line in enumerate(MART_H.read_text().splitlines(), start=1):
        m = re.match(r"const \w+ \*?(\w+)\[\] = \{", line)
        if m:
            cur = m.group(1)
            out[cur] = []
            continue
        if cur and line.startswith("};"):
            cur = None
            continue
        if cur:
            m = re.search(r"\{ (ITEM_\w+), (0x[0-9A-Fa-f]+|\d+) \}", line)
            if m:
                out[cur].append((m.group(1), f"{rel(MART_H)}:{i}", int(m.group(2), 0)))
                continue
            m = re.match(r"\s*(ITEM_\w+),", line)
            if m:
                out[cur].append((m.group(1), f"{rel(MART_H)}:{i}"))
            m = re.match(r"\s*\[(MART_SPECIALTIES_ID_\w+)\] = (\w+),?", line)
            if m:
                out.setdefault("__index__", []).append((m.group(1), m.group(2)))
    return out


@cache
def common_mart_badge_tiers() -> tuple[tuple[int, int], ...]:
    """ScrCmd_PokeMartCommon: badge count -> requiredBadges tier (src/scrcmd_shop.c)."""
    text = SHOP_C.read_text()
    m = re.search(r"switch \(badgeNum\) \{(.*?)\n    \}", text, re.S)
    out, pending = [], []
    for line in m.group(1).splitlines():
        c = re.match(r"\s*case (\d+):", line)
        if c:
            pending.append(int(c.group(1)))
        r = re.match(r"\s*requiredBadges = (\d+);", line)
        if r:
            out.extend((b, int(r.group(1))) for b in pending)
            pending = []
    return tuple(out)


def shop_entries() -> list[Entry]:
    lists = mart_lists()
    index = dict(lists.get("__index__", []))
    tiers = dict(common_mart_badge_tiers())
    max_tier = max(tiers.values())
    out = []
    for op in ("SCRCMD_POKEMARTCOMMON", "SCRCMD_POKEMARTSPECIALTIES"):
        for stem, idx in _prim_sites(op):
            c = load_script_file(stem).commands[idx]
            prim = next(p for p in c.prims if p.op == op)
            for h in _owners(stem):
                gs = site_gates(h, stem, idx)
                if op == "SCRCMD_POKEMARTCOMMON":
                    for item, iref, need in lists["PokeMartCommonItems"]:
                        badges = min((b for b, t in tiers.items() if t >= need), default=None)
                        g2 = list(gs)
                        if badges is None or need > max_tier:
                            g2.append(gate(G.KIND_UNCERTAIN, iref, f"tier {need} never offered", False))
                        elif badges:
                            g2.append(gate("badge_count", ref(SHOP_C, "switch (badgeNum) {"), f"sold from {badges} badges (tier {need})", False))
                        out.append(Entry("shop", item, h, UNLIMITED, g2, [str(c.ref), iref], None, None, [], [], None, "PokeMartCommon"))
                else:
                    mart = prim.operands[0].text
                    lst = index.get(mart)
                    if lst is None:
                        continue
                    for item, iref in lists[lst]:
                        out.append(Entry("shop", item, h, UNLIMITED, list(gs), [str(c.ref), iref], None, None, [], [], None, f"{mart} ({lst})"))
    return out


def game_corner_entries() -> list[Entry]:
    prizes = []
    for i, line in enumerate(GAME_CORNER_C.read_text().splitlines(), start=1):
        m = re.search(r"\{ (ITEM_\w+), (\d+) \}", line)
        if m:
            prizes.append((m.group(1), int(m.group(2)), f"{rel(GAME_CORNER_C)}:{i}"))
    out = []
    for stem, idx in _prim_sites("SCRCMD_GETGAMECORNERPRIZEDATA")[:1]:
        c = load_script_file(stem).commands[idx]
        for h in _owners(stem):
            gs = site_gates(h, stem, idx)
            for item, coins, pref in prizes:
                out.append(Entry("game_corner", item, h, UNLIMITED, gs, [str(c.ref), pref], None, None, [], [], None, f"{coins} coins"))
    return out


@cache
def mining_item_map() -> dict[str, tuple[str, str]]:
    """MINING_TREASURE_* -> (ITEM_*, ref) via underground.c's treasure->item table (indexed from
    MINING_TREASURE_START) and the enum order in include/underground/mining.h."""
    enum_text = MINING_H.read_text()
    m = re.search(r"MINING_TREASURE_OVAL_STONE = MINING_SPHERES_MAX,(.*?)\}", enum_text, re.S)
    names = ["MINING_TREASURE_OVAL_STONE"] + re.findall(r"(MINING_TREASURE_\w+)", m.group(1))
    table = {}
    for i, line in enumerate(UNDERGROUND_C.read_text().splitlines(), start=1):
        mm = re.match(r"\s*\[(\d+)\] = (ITEM_\w+),", line)
        if mm and int(mm.group(1)) not in table:
            table[int(mm.group(1))] = (mm.group(2), f"{rel(UNDERGROUND_C)}:{i}")
    return {n: table[k] for k, n in enumerate(names) if k in table and n != "MINING_TREASURE_MAX"}


def underground_entries() -> list[Entry]:
    """Mining (src/underground/mining.c sMiningObjects, weights chosen in Mining_GetWeightOfItem):
    columns by Trainer ID parity, and by National Dex. Unlimited (mining repeats)."""
    items = mining_item_map()
    wref = ref(MINING_C, "static int Mining_GetWeightOfItem(MiningObject *item)")
    seen = set()
    out = []
    for i, line in enumerate(MINING_C.read_text().splitlines(), start=1):
        m = re.search(r"\.itemID = (MINING_TREASURE_\w+), \.oddTIDWeight = (\d+), \.evenTIDWeight = (\d+), \.oddTIDNatDexWeight = (\d+), \.evenTIDNatDexWeight = (\d+)", line)
        if not m or m.group(1) not in items:
            continue
        item, iref = items[m.group(1)]
        for col, parity, natdex in ((2, "odd", False), (3, "even", False), (4, "odd", True), (5, "even", True)):
            if int(m.group(col)) == 0 or (item, parity, natdex) in seen:
                continue
            seen.add((item, parity, natdex))
            gs = [gate("tid_parity", wref, f"weight {m.group(col)} only for an {parity} Trainer ID", False)]
            if natdex:
                gs.append(gate(G.KIND_NATIONAL_DEX, wref, "National Dex weight column", True))
            out.append(Entry("underground", item, "MAP_HEADER_UNDERGROUND", UNLIMITED, gs, [f"{rel(MINING_C)}:{i}", iref], None, None, ["ITEM_EXPLORER_KIT"], [], f"tid_{parity}", f"mining ({parity} TID{', National Dex' if natdex else ''})"))
    return out


def berry_tree_entries() -> list[Entry]:
    """Initial berry patches (include/data/berry_init.h, loaded in src/game_start.c), placed by
    BERRY_SOIL objects (script 2800 range, data[0] = patch id). Unlimited: a fully grown patch
    yields at least 2 (src/berry_patches.c CalcBerryYield clamp), so replanting never runs out."""
    init = []
    for i, line in enumerate(BERRY_INIT_H.read_text().splitlines(), start=1):
        m = re.search(r"\.berryItemID = (ITEM_\w+), \.yield = (\d+)", line)
        if m:
            init.append((m.group(1), f"{rel(BERRY_INIT_H)}:{i}"))
    clamp = ref(BERRY_PATCHES_C, "if (berryPatch->yield < 2) {")
    lo = next(r.threshold for r in __import__("platsim.decomp.scripts", fromlist=["script_ranges"]).script_ranges() if "berry" in r.file.lower())
    out = []
    for h in map_header_names():
        if h not in map_headers():
            continue
        for o in events_of(h)["object"]:
            sid = o.data.get("script")
            if isinstance(sid, int) and lo <= sid < lo + 200 and o.data.get("data"):
                pid = o.data["data"][0]
                if pid < len(init):
                    item, iref = init[pid]
                    out.append(Entry("berry_tree", item, h, UNLIMITED, [], [str(o.ref), iref, clamp], None, None, [], [], None, f"patch {pid}"))
    return out


def tutor_entries() -> list[Entry]:
    """Move tutors (T015): the script node that opens each tutor (shard menu / OpenMoveTutorMenu)."""
    from platsim.decomp.tutors import load_tutors

    out = []
    for t in load_tutors():
        stem = Path(t.script).stem
        sf = load_script_file(stem)
        if t.bit_index is not None:
            line = int(t.src[1].rsplit(":", 1)[1])
            idx = next(c.index for c in sf.commands if c.ref.line == line)
        else:  # script tutors: the OpenMoveTutorMenu command
            idx = next(c.index for c in sf.commands if c.name == "OpenMoveTutorMenu")
        gs = site_gates(t.map_header, stem, idx)
        out.append(Entry("tutor", t.move, t.map_header, UNLIMITED, gs, list(t.src) + [str(sf.commands[idx].ref)], None, None, [], [], None, t.location))
    return out


def all_entries() -> list[Entry]:
    return (
        wild_entries()
        + mon_entries()
        + visible_item_entries()
        + hidden_item_entries()
        + npc_gift_entries()
        + shop_entries()
        + game_corner_entries()
        + underground_entries()
        + berry_tree_entries()
        + tutor_entries()
    )


__all__ = ["Entry", "UNLIMITED", "all_entries", "trainer_entries", "dex_seen_entries", "site_gates"]
