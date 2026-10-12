"""Map story rank (003 T038/T039, research R9): gym badges needed to reach each map.

Used only to choose which *legal* source is named (data-model "Map story rank"); it never makes
a source legal or illegal, and the legality reachability (mapgraph.py, ledger phases) is untouched.

Decomp facts (all parsed, nothing hand-typed):
- **Badge per field move**: pokeplatinum/src/field_move_tasks.c, each `FieldMoves_Check<Move>`
  calls `PlayerHasRequiredBadge(..., BADGE_ID_X)` (`field_move_badges`). Cross-checked against
  res/field/scripts/scripts_field_moves.s, where `FindPartySlotWithMove VAR_RESULT, MOVE_X` is
  followed by `CheckBadgeAcquired BADGE_ID_Y` (Cut, Rock Smash, Strength, Rock Climb, Waterfall;
  the Surf and Defog scripts have no badge check). Any disagreement raises.
- **Gym order** (`gym_order`): the `GiveBadge BADGE_ID_X` sites (SCRCMD_GIVEBADGE) in map scripts
  give badge -> gym maps (the headers running that file) and the leader fought in the same file
  (`StartTrainerBattle TRAINER_LEADER_*`); badges are ordered by that leader's top party level in
  res/trainers/data/leader_*.json (strictly rising). generated/badges.txt is the badge *id* order,
  not the gym order, and is not used for ordering.
- **Obstacles** (`obstacles`): object events in res/field/events/*.json whose script id resolves to
  a scripts_field_moves.s entry starting with `FindPartySlotWithMove MOVE_X` (ids 10000 Cut tree,
  10001 Rock Smash rock, 10002 Strength boulder). Walls until MOVE_X's badge.
- **Tiles** (`tile_rules`): behaviour = attribute & TERRAIN_ATTRIBUTES_TILE_BEHAVIOR_MASK
  (include/constants/field/map.h), names from `enum TileBehavior`
  (include/constants/field/map_tile_behaviors.h). Surfable = TILE_BEHAVIOR_FLAG_SURFABLE in
  `sTileBehaviorFlags` (src/map_tile_behavior.c) minus `TileBehavior_IsBridge` (walked on, under
  which one can surf: src/overlay005/ov5_021DFB54.c PlayerAvatar_CanUseSurf); waterfall =
  `TileBehavior_IsWaterfall`; rock climb = `TileBehavior_IsRockClimbNorthSouth/EastWest`. Those
  three are passable only once Surf / Waterfall / Rock Climb is unlocked (waterfall and rock climb
  regardless of the collision bit); every other tile uses mapgraph's collision test.
- **Bicycle** (`BIKE_PREDICATES`, `bike_gates`): bike slopes / ramps / bike bridges
  (src/player_move.c sTileBehaviorCheckTable, PlayerAvatar_TileMove_BikeSlope: walking north onto
  a slope pushes the player back) and the coord events whose script runs `CheckPlayerOnBike` (the
  Cycling Road gates) are walls until a map whose scripts give ITEM_BICYCLE is reached
  (scripts_cycle_shop.s:18); the stage is then flooded again with the Bicycle.
- **Ledges** (`ledges`): one-way jumps (src/player_move.c PlayerAvatar_WillJump): moving in
  direction d onto a TileBehavior_IsJump<d> tile lands two tiles further.
- **Story blockers** (step 2, `story_blockers`): an object is a blocker when every script site
  that hides it (SetFlag of its hidden_flag, or RemoveObject of its id in its map's scripts:
  mapgraph._object_openers' rule) is reached forward from a `GiveBadge X` command (it stays a
  wall until X is held) or from a `CheckItem ITEM_Y` command (a wall until a map whose scripts give
  Y is reached: `SetVar VAR_0x8004, ITEM_Y` before Common_GiveItem*, or `AddItem ITEM_Y`). Example:
  FLAG_HIDE_HEARTHOME_CITY_ROUTE_209_BLOCKADE (scripts_hearthome_city_gym_leader_room.s:83, after
  GiveBadge BADGE_ID_RELIC at :71); the Route 210 Psyduck (RemoveObject LOCALID_PSYDUCK_* after
  CheckItem ITEM_SECRETPOTION, scripts_route_210_south.s:35-75; the potion is given in
  scripts_valor_lakefront.s:344).

Reachability: for badge stage k = 0..8 (k = badges held, in gym order), flood the tiles with the
ability-aware wall test (mapgraph._flood / _near / _header_tiles) from Twinleaf Town's warps.
Nodes are (space, tile), a space being a multi-header matrix (borders are tile adjacency) or one
header's own matrix; warps and script warps / boat rides / Distortion World links are taken from
mapgraph.build_graph() edges with strict usability (open; conditional once an opener's map is
reached; uncertain and post_game cut). A map's `badges_needed` is the first k at which any of its
tiles is reached; `hops` is its BFS distance, over the map links used at stage k, from the maps
already reached at stage k-1 (stage 0: from Twinleaf Town).

A link's arrival always enters its map, even with no passable tile next to the arrival point (the
Distortion World's floors are C-built platforms). Warp edges are used with mapgraph's strict
status, except `object_blocks_warp` (the tile model checks walls on the warp tile itself).

Known gaps (research R9 and found while building): Strength puzzles are "the boulder can be
removed"; story gates tied to neither a badge nor an item are not modelled - the var-driven ones
matter most: the Bicycle is available as soon as the Cycle Shop is reached (stage 1; in the game
its giver is hidden at new game and shown by scripts_team_galactic_eterna_building_4f.s:75,
a var-driven story chain), so Hearthome City is reached at stage 1, not 2; the Valor Lakefront
"Sunyshore blackout" pushback (coord event, VAR_VALOR_LAKEFRONT_BLOCK_SUNYSHORE_STATE) is open, so
Route 222 / Sunyshore are stage 3; fog is ignored; jump-twice ledges and the hidden-location
terrain swaps (Spring Path, Seabreak Path) are not applied; a script warp is usable from anywhere
in its map; a map's rank is that of its *earliest* region (Ravaged Path's entrance cave floor and
Route 218's east pier are stage 0 although their far side needs Rock Smash / Surf).

Runtime reads data/generated/story_rank.json (written by `platsim extract`) through `rank()`;
it never rebuilds.
"""

from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from platsim.availability.mapgraph import (
    EVERYWHERE,
    START,
    WARP_OPERANDS,
    Edge,
    MapGraph,
    _flood,
    _header_tiles,
    _int_operand,
    _near,
    _STATIONARY,
    build_graph,
    cell_attributes,
    events_of,
    headers_for_script_file,
    load_matrix,
    map_header_names,
    map_headers,
)
from platsim.decomp.constants import Ref, load_enum, rel
from platsim.decomp.scripts import all_script_stems, load_script_file, resolve_script_id
from platsim.pins import DECOMP_COMMIT, DECOMP_ROOT

FIELD_MOVE_TASKS_C = DECOMP_ROOT / "src" / "field_move_tasks.c"
FIELD_MOVES_S = DECOMP_ROOT / "res" / "field" / "scripts" / "scripts_field_moves.s"
MAP_TILE_BEHAVIOR_C = DECOMP_ROOT / "src" / "map_tile_behavior.c"
MAP_TILE_BEHAVIORS_H = DECOMP_ROOT / "include" / "constants" / "field" / "map_tile_behaviors.h"
MAP_H = DECOMP_ROOT / "include" / "constants" / "field" / "map.h"
TRAINERS_DIR = DECOMP_ROOT / "res" / "trainers" / "data"
FIELD_MOVES_STEM = "scripts_field_moves"

# Field moves that change where the player can walk, and how (research R9).
SURF, WATERFALL, ROCK_CLIMB = "MOVE_SURF", "MOVE_WATERFALL", "MOVE_ROCK_CLIMB"

BICYCLE = "ITEM_BICYCLE"
STAGES = 9  # 0..8 badges

# Tiles only a cyclist passes: src/player_move.c sTileBehaviorCheckTable (bike slope: walking
# north onto one pushes the player back south, PlayerAvatar_TileMove_BikeSlope; ramps) and the
# bike bridges (PlayerAvatar_WillBeOnBikeBridge).
BIKE_PREDICATES = (
    "TileBehavior_IsBikeSlope",
    "TileBehavior_IsBikeRampEastward",
    "TileBehavior_IsBikeRampWestward",
    "TileBehavior_IsBikeBridgeNorthSouth",
    "TileBehavior_IsBikeBridgeEastWest",
)


# ---------------------------------------------------------------------------------------------
# Field move -> badge


def _camel_to_const(name: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", "_", name).upper()


def _c_field_move_badges() -> dict[str, tuple[str, str]]:
    """MOVE_* -> (BADGE_ID_*, file:line) from the FieldMoves_Check<Move> bodies."""
    text = FIELD_MOVE_TASKS_C.read_text()
    moves = load_enum("moves")
    out: dict[str, tuple[str, str]] = {}
    for m in re.finditer(r"static enum FieldMoveError FieldMoves_Check(\w+)\(const FieldMoveContext \*\w+\)\s*\{(.*?)\n\}", text, re.S):
        b = re.search(r"PlayerHasRequiredBadge\([^,]+,\s*(BADGE_ID_\w+)\)", m.group(2))
        if not b:
            continue
        move = "MOVE_" + _camel_to_const(m.group(1))
        if move not in moves.values:
            raise ValueError(f"{rel(FIELD_MOVE_TASKS_C)}: FieldMoves_Check{m.group(1)} -> {move} is not a move")
        line = text.count("\n", 0, m.start() + m.group(0).index("PlayerHasRequiredBadge")) + 1
        out[move] = (b.group(1), f"{rel(FIELD_MOVE_TASKS_C)}:{line}")
    return out


def _script_field_move_badges() -> dict[str, tuple[str, str]]:
    """MOVE_* -> (BADGE_ID_*, ref) where scripts_field_moves.s checks the badge right after
    finding the move in the party (within the next two commands)."""
    sf = load_script_file(FIELD_MOVES_STEM)
    out: dict[str, tuple[str, str]] = {}
    cmds = sf.commands
    for i, c in enumerate(cmds):
        if c.name != "FindPartySlotWithMove":
            continue
        for d in cmds[i + 1 : i + 4]:
            if d.name == "CheckBadgeAcquired":
                move, badge = c.args[1], d.args[0]
                prev = out.get(move)
                if prev and prev[0] != badge:
                    raise ValueError(f"{FIELD_MOVES_STEM}: {move} checks {prev[0]} at {prev[1]} and {badge} at {d.ref}")
                out[move] = (badge, str(d.ref))
                break
    return out


def _cross_check(c_table: dict[str, str], script_table: dict[str, tuple[str, str]]) -> None:
    for move, (badge, ref) in script_table.items():
        if c_table.get(move) != badge:
            raise ValueError(f"field move badge disagreement for {move}: {rel(FIELD_MOVE_TASKS_C)} says "
                             f"{c_table.get(move)}, {ref} says {badge}")


@cache
def field_move_badges() -> dict[str, str]:
    """MOVE_* -> BADGE_ID_* (src/field_move_tasks.c), cross-checked with scripts_field_moves.s."""
    c = _c_field_move_badges()
    table = {m: b for m, (b, _) in c.items()}
    script = _script_field_move_badges()
    if not script:
        raise ValueError(f"no FindPartySlotWithMove/CheckBadgeAcquired pair in {rel(FIELD_MOVES_S)}")
    _cross_check(table, script)
    return table


@cache
def field_move_refs() -> dict[str, str]:
    return {m: ref for m, (_, ref) in _c_field_move_badges().items()}


# ---------------------------------------------------------------------------------------------
# Gym order


@dataclass(frozen=True)
class Gym:
    badge: str  # BADGE_ID_*
    leader: str  # TRAINER_LEADER_*
    top_level: int  # highest level in the leader's party
    maps: tuple[str, ...]  # headers whose scripts run the GiveBadge
    give_refs: tuple[str, ...]
    leader_ref: str


def _prim_sites(op: str) -> list[tuple[str, int, list[str]]]:
    out = []
    for stem in all_script_stems():
        sf = load_script_file(stem)
        for c in sf.commands:
            for p in c.prims:
                if p.op == op:
                    out.append((stem, c.index, [o.text for o in p.operands]))
    return out


def _running_headers(stem: str) -> tuple[str, ...]:
    return tuple(h for h in headers_for_script_file().get(stem, ()) if map_headers()[h].scripts == stem)


@cache
def give_badge_sites() -> tuple[tuple[str, str, int], ...]:
    """(BADGE_ID_*, script stem, command index) of every GiveBadge (SCRCMD_GIVEBADGE)."""
    return tuple((ops[0], stem, idx) for stem, idx, ops in _prim_sites("SCRCMD_GIVEBADGE"))


@cache
def gym_order() -> tuple[Gym, ...]:
    """The eight gyms in story order: badges ordered by their leader's top party level."""
    badges = [b for b in load_enum("badges").values if b.startswith("BADGE_ID_")]
    by_badge: dict[str, dict] = {}
    for badge, stem, idx in give_badge_sites():
        maps = _running_headers(stem)
        if not maps:
            continue  # a script file no map runs
        sf = load_script_file(stem)
        leaders = {o.text for c in sf.commands for p in c.prims if p.op == "SCRCMD_STARTTRAINERBATTLE"
                   for o in p.operands[:1] if o.text.startswith("TRAINER_LEADER_")}
        if len(leaders) != 1:
            raise ValueError(f"{sf.commands[idx].ref}: GiveBadge {badge} file fights leaders {sorted(leaders)}")
        d = by_badge.setdefault(badge, {"leaders": set(), "maps": [], "refs": []})
        d["leaders"] |= leaders
        d["maps"].extend(maps)
        d["refs"].append(str(sf.commands[idx].ref))
    if sorted(by_badge) != sorted(badges):
        raise ValueError(f"GiveBadge sites cover {sorted(by_badge)}, generated/badges.txt has {sorted(badges)}")
    gyms = []
    for badge, d in by_badge.items():
        if len(d["leaders"]) != 1:
            raise ValueError(f"{badge}: several leaders {sorted(d['leaders'])}")
        leader = next(iter(d["leaders"]))
        path = TRAINERS_DIR / f"{leader.removeprefix('TRAINER_').lower()}.json"
        party = json.loads(path.read_text())["party"]
        gyms.append(Gym(badge, leader, max(m["level"] for m in party), tuple(dict.fromkeys(d["maps"])),
                        tuple(d["refs"]), rel(path)))
    gyms.sort(key=lambda g: g.top_level)
    if len({g.top_level for g in gyms}) != len(gyms):
        raise ValueError(f"leader top levels tie, gym order undefined: {[(g.badge, g.top_level) for g in gyms]}")
    return tuple(gyms)


@cache
def badge_stage() -> dict[str, int]:
    """BADGE_ID_* -> number of badges held once it is won (1..8)."""
    return {g.badge: i + 1 for i, g in enumerate(gym_order())}


def move_stage(move: str) -> int:
    return badge_stage()[field_move_badges()[move]]


# ---------------------------------------------------------------------------------------------
# Tiles


def _eval_int(expr: str, names: dict[str, int]) -> int:
    toks = re.sub(r"\b([A-Z_][A-Z0-9_]*)\b", lambda m: str(names[m.group(1)]), expr)
    if not re.fullmatch(r"[\d\s()|<>&+x]*", toks):
        raise ValueError(f"cannot evaluate {expr!r}")
    return int(eval(toks, {"__builtins__": {}}))  # noqa: S307 - digits and | << only


@cache
def tile_behaviors() -> dict[str, int]:
    """TILE_BEHAVIOR_* -> value from `enum TileBehavior` (map_tile_behaviors.h)."""
    text = MAP_TILE_BEHAVIORS_H.read_text()
    body = re.search(r"enum TileBehavior\s*\{(.*?)\};", text, re.S)
    if not body:
        raise ValueError(f"enum TileBehavior not in {rel(MAP_TILE_BEHAVIORS_H)}")
    out, v = {}, -1
    for line in body.group(1).splitlines():
        line = re.sub(r"//.*", "", line).strip().rstrip(",")
        if not line:
            continue
        m = re.fullmatch(r"(\w+)\s*(?:=\s*(\w+))?", line)
        if not m:
            raise ValueError(f"unparsed enum TileBehavior line {line!r}")
        v = int(m.group(2), 0) if m.group(2) else v + 1
        out[m.group(1)] = v
    return out


def _predicate(fn: str) -> frozenset[int]:
    text = MAP_TILE_BEHAVIOR_C.read_text()
    m = re.search(rf"BOOL {fn}\(u8 behavior\)\s*\{{(.*?)\n\}}", text, re.S)
    if not m:
        raise ValueError(f"{fn} not in {rel(MAP_TILE_BEHAVIOR_C)}")
    names = re.findall(r"behavior == (TILE_BEHAVIOR_\w+)", m.group(1))
    if not names:
        raise ValueError(f"{fn}: no behaviour compared")
    return frozenset(tile_behaviors()[n] for n in names)


@dataclass(frozen=True)
class TileRules:
    mask: int
    surf: frozenset[int]
    waterfall: frozenset[int]
    rock_climb: frozenset[int]
    bike: frozenset[int]


@cache
def tile_rules() -> TileRules:
    text = MAP_TILE_BEHAVIOR_C.read_text()
    flags = {k: int(v, 0) for k, v in re.findall(r"#define\s+(TILE_BEHAVIOR_FLAG_\w+)\s+(\d+|0x[0-9a-fA-F]+)\b", MAP_TILE_BEHAVIORS_H.read_text())}
    for k, v in re.findall(r"#define\s+(TILE_BEHAVIOR_FLAG_\w+)\s+(\(.*\))", MAP_TILE_BEHAVIORS_H.read_text()):
        flags[k] = _eval_int(v, flags)
    table = re.search(r"sTileBehaviorFlags\[\]\s*=\s*\{(.*?)\};", text, re.S)
    if not table:
        raise ValueError(f"sTileBehaviorFlags not in {rel(MAP_TILE_BEHAVIOR_C)}")
    beh = tile_behaviors()
    surfable = {beh[b] for b, f in re.findall(r"\[(TILE_BEHAVIOR_\w+)\]\s*=\s*(\w+)", table.group(1))
                if flags[f] & flags["TILE_BEHAVIOR_FLAG_SURFABLE"]}
    if beh["TILE_BEHAVIOR_WATER_SEA"] not in surfable:  # positive control on the parse
        raise ValueError("sTileBehaviorFlags parse: TILE_BEHAVIOR_WATER_SEA not surfable")
    mask = int(re.search(r"#define\s+TERRAIN_ATTRIBUTES_TILE_BEHAVIOR_MASK\s+(\w+)", MAP_H.read_text()).group(1), 0)
    return TileRules(
        mask,
        frozenset(surfable) - _predicate("TileBehavior_IsBridge"),
        _predicate("TileBehavior_IsWaterfall"),
        _predicate("TileBehavior_IsRockClimbNorthSouth") | _predicate("TileBehavior_IsRockClimbEastWest"),
        frozenset().union(*(_predicate(f) for f in BIKE_PREDICATES)),
    )


# ---------------------------------------------------------------------------------------------
# Spaces: a multi-header matrix (tiles of all its headers) or one header's own matrix.

Space = tuple[str, str]  # ("matrix", stem) | ("header", MAP_HEADER_*)


def space_of(header: str) -> Space:
    mx = load_matrix(map_headers()[header].matrix)
    return ("matrix", mx.stem) if mx.headers is not None else ("header", header)


@cache
def _space_headers(space: Space) -> tuple[str, ...]:
    if space[0] == "header":
        return (space[1],)
    return tuple(h for h in map_header_names() if h in map_headers() and map_headers()[h].matrix == space[1])


def header_at(space: Space, pos: tuple[int, int]) -> str:
    if space[0] == "header":
        return space[1]
    return load_matrix(space[1]).headers[pos[1] // 32][pos[0] // 32]


@cache
def _space_tiles(space: Space) -> tuple[dict, dict]:
    """(pos -> walkable by collision bit (mapgraph._header_tiles), pos -> behaviour)."""
    walk: dict[tuple[int, int], bool] = {}
    for h in _space_headers(space):
        walk.update(_header_tiles(h))
    mask = tile_rules().mask
    beh: dict[tuple[int, int], int] = {}
    for h in _space_headers(space):
        mx = load_matrix(map_headers()[h].matrix)
        for r in range(mx.height):
            for c in range(mx.width):
                if mx.headers is not None and mx.headers[r][c] != h:
                    continue
                attrs = cell_attributes(mx, r, c)
                if attrs is None:
                    continue
                for tz in range(32):
                    for tx in range(32):
                        beh[(c * 32 + tx, r * 32 + tz)] = attrs[tz * 32 + tx] & mask
    return walk, beh


@cache
def passable(space: Space, abilities: frozenset[str]) -> dict[tuple[int, int], bool]:
    """pos -> passable with these field moves unlocked (cached per ability set)."""
    walk, beh = _space_tiles(space)
    rules = tile_rules()
    out = {}
    for pos, ok in walk.items():
        b = beh[pos]
        if b in rules.bike:
            out[pos] = ok and BICYCLE in abilities
        elif b in rules.rock_climb:
            out[pos] = ROCK_CLIMB in abilities
        elif b in rules.waterfall:
            out[pos] = WATERFALL in abilities and SURF in abilities
        elif not ok:
            out[pos] = False
        elif b in rules.surf:
            out[pos] = SURF in abilities
        else:
            out[pos] = True
    return out


# One-way ledges: src/player_move.c PlayerAvatar_WillJump - moving in direction d onto a
# TileBehavior_IsJump<d> tile jumps the player over it, landing two tiles away. Direction deltas
# as MapObject_GetDxFromDir / GetDzFromDir (north = -z). The Distortion World's *Twice variants
# are not modelled.
_JUMP_DIRS = {"North": (0, -1), "South": (0, 1), "West": (-1, 0), "East": (1, 0)}


@cache
def ledges(space: Space) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    """(ledge tile, jump direction) of every ledge in the space."""
    by_beh: dict[int, tuple[int, int]] = {}
    for name, d in _JUMP_DIRS.items():
        for b in _predicate(f"TileBehavior_IsJump{name}"):
            by_beh[b] = d
    _, beh = _space_tiles(space)
    return tuple((p, by_beh[b]) for p, b in beh.items() if b in by_beh)


# ---------------------------------------------------------------------------------------------
# Objects: field-move obstacles and story blockers


@dataclass(frozen=True)
class Blocker:
    header: str
    x: int
    z: int
    id: str
    why: str  # "MOVE_*" (obstacle) | "BADGE_ID_*" | "ITEM_*" (story blocker)
    ref: Ref

    @property
    def move(self) -> str:
        return self.why


@cache
def _field_move_entry_moves() -> dict[int, str]:
    """scripts_field_moves.s entry index -> the MOVE_* its first FindPartySlotWithMove names."""
    sf = load_script_file(FIELD_MOVES_STEM)
    out = {}
    for i in range(len(sf.entries)):
        for c in sf.commands[sf.command_for_entry(i):]:
            if c.name == "FindPartySlotWithMove":
                out[i] = c.args[1]
                break
            if c.name == "End":
                break
    return out


@cache
def obstacles() -> tuple[Blocker, ...]:
    """Cut trees, Rock Smash rocks, Strength boulders: objects whose script is a field-move
    obstacle entry of scripts_field_moves.s (ids 10000-10002) with a badge-checked move."""
    entry_moves = _field_move_entry_moves()
    badges = field_move_badges()
    out = []
    for h in map_header_names():
        if h not in map_headers():
            continue
        for o in events_of(h)["object"]:
            sid = o.data.get("script")
            if not isinstance(sid, int) or sid <= 0:
                continue
            f, entry = resolve_script_id(sid, map_headers()[h].scripts)
            move = entry_moves.get(entry) if f == FIELD_MOVES_STEM else None
            if move is None or move not in badges:
                continue
            if f == FIELD_MOVES_STEM and load_script_file(f).entry_label(entry).endswith("FromMenu"):
                continue
            out.append(Blocker(h, o.x, o.z, o.data.get("id", ""), move, o.ref))
    return tuple(out)


def _hide_sites_from(node: tuple[str, int]) -> tuple[set[str], set[tuple[str, str]]]:
    """Flags set and (script stem, object id) removed on paths forward from `node`."""
    from platsim.availability.gates import _reach_cached

    flags, removed = set(), set()
    for stem, idx in _reach_cached(node, node[0]):
        for p in load_script_file(stem).commands[idx].prims:
            if p.op == "SCRCMD_SETFLAG":
                flags.add(p.operands[0].text)
            elif p.op == "SCRCMD_REMOVEOBJECT":
                removed.add((stem, p.operands[0].text))
    return flags, removed


@cache
def _item_ball_entries() -> tuple:
    from platsim.availability.sources import hidden_item_entries, visible_item_entries

    return tuple(visible_item_entries()) + tuple(hidden_item_entries())


@cache
def item_source_maps(item: str) -> tuple[str, ...]:
    """Headers where `item` is obtained: scripts that give it (`SetVar VAR_0x8004, ITEM_Y`, the
    Common_GiveItem* argument as in sources.npc_gift_entries, or `AddItem ITEM_Y, n`), and its
    visible / hidden item balls (sources.visible_item_entries / hidden_item_entries)."""
    out = [e.map_header for e in _item_ball_entries() if e.subject == item and e.map_header]
    for stem in all_script_stems():
        sf = load_script_file(stem)
        for c in sf.commands:
            for p in c.prims:
                ops = [o.text for o in p.operands]
                if (p.op == "SCRCMD_SETVARFROMVALUE" and ops[:2] == ["VAR_0x8004", item]) or (
                    p.op == "SCRCMD_ADDITEM" and ops[:1] == [item]
                ):
                    out.extend(_running_headers(stem))
    return tuple(dict.fromkeys(out))


@cache
def story_blockers() -> tuple[Blocker, ...]:
    """Step 2 (T039): stationary objects every hiding site of which follows a GiveBadge (wall until
    that badge) or a CheckItem (wall until the item's source map is reached)."""
    from platsim.availability.gates import flag_set_sites

    openers: list[tuple[str, tuple[str, int], set[str], set[tuple[str, str]]]] = []
    for badge, stem, idx in give_badge_sites():
        if _running_headers(stem):
            openers.append((badge, (stem, idx), *_hide_sites_from((stem, idx))))
    for stem, idx, ops in _prim_sites("SCRCMD_CHECKITEM"):
        if ops[0].startswith("ITEM_") and _running_headers(stem):
            openers.append((ops[0], (stem, idx), *_hide_sites_from((stem, idx))))
    # Script nodes that hide each flag / object, and which gate (if any) precedes them.
    from platsim.availability.gates import _reach_cached

    gated_nodes: dict[tuple[str, int], set[str]] = {}
    for why, node, _, _ in openers:
        for n in _reach_cached(node, node[0]):
            gated_nodes.setdefault(n, set()).add(why)
    out = []
    for h in map_header_names():
        if h not in map_headers():
            continue
        stem = map_headers()[h].scripts
        for o in events_of(h)["object"]:
            if not _STATIONARY.match(o.data.get("movement_type", "")):
                continue
            flag = o.data.get("hidden_flag", "0")
            sites = list(flag_set_sites().get(flag, ())) if flag and flag != "0" else []
            sf = load_script_file(stem)
            sites += [(stem, c.index) for c in sf.commands for p in c.prims
                      if p.op == "SCRCMD_REMOVEOBJECT" and p.operands[0].text == o.data.get("id")]
            if not sites:
                continue
            whys = [gated_nodes.get(s) for s in dict.fromkeys(sites)]
            if any(not w for w in whys):
                continue  # some hiding site is not behind a badge / item gate: not modelled
            # Earliest gate that opens it: the union over sites, resolved per stage later.
            for why in sorted(set().union(*whys)):
                out.append(Blocker(h, o.x, o.z, o.data.get("id", ""), why, o.ref))
    return tuple(out)


# ---------------------------------------------------------------------------------------------
# Transitions between spaces


@dataclass(frozen=True)
class Link:
    src: str
    dst: str
    arrive: tuple[int, int] | None  # None: anywhere passable in dst (no coordinates)
    edge: Edge


@cache
def _graph_links() -> tuple[dict[tuple[str, Ref], Edge], dict[str, tuple[Link, ...]]]:
    """Warp edges by (src, warp event ref); map-level links (script warps, ships, C elevators)."""
    g = build_graph()
    warps = {(e.src, e.ref): e for e in g.edges if e.kind == "warp"}
    coords: dict[Ref, list[tuple[str, int | None, int | None]]] = {}
    for stem in all_script_stems():
        for c in load_script_file(stem).commands:
            for p in c.prims:
                if p.op in WARP_OPERANDS:
                    mi, xi, zi = WARP_OPERANDS[p.op]
                    coords.setdefault(c.ref, []).append((p.operands[mi].text, _int_operand(p, xi), _int_operand(p, zi)))
    by_src: dict[str, list[Link]] = {}
    for e in g.edges:
        if e.kind in ("script_warp", "ship"):
            for dst, x, z in coords.get(e.ref, ()):
                if dst == e.dst:
                    by_src.setdefault(e.src, []).append(Link(e.src, e.dst, (x, z) if x is not None and z is not None else None, e))
        elif e.kind == "c_elevator":
            by_src.setdefault(e.src, []).append(Link(e.src, e.dst, None, e))
    return warps, {k: tuple(v) for k, v in by_src.items()}


@cache
def _warp_links(header: str) -> tuple[tuple[tuple[int, int], Link], ...]:
    """(warp tile, Link) for each warp event of `header` that mapgraph made an edge of."""
    warps, _ = _graph_links()
    out = []
    for w in events_of(header)["warp"]:
        e = warps.get((header, w.ref))
        if e is None:
            continue
        dw = events_of(e.dst)["warp"]
        i = w.data.get("dest_warp_id")
        if isinstance(i, int) and 0 <= i < len(dw):
            out.append(((w.x, w.z), Link(header, e.dst, (dw[i].x, dw[i].z), e)))
        else:
            out.append(((w.x, w.z), Link(header, e.dst, None, e)))
    return tuple(out)


def _usable(e: Edge, reached_maps: set[str]) -> bool | None:
    """True / False, or None if it is conditional and not opened yet (re-checked later).

    Strict mapgraph usability, except a warp that is `uncertain` only because an object stands
    on its tile (`object_blocks_warp`): here walls come from the tile model (obstacles, story
    blockers, checked on the warp tile itself), and the one such edge is the Wayward Cave hidden
    entrance, whose object stands on the Cycling Road bridge above it (LOCALID_CYCLIST_MEGAN,
    y=8, events_route_206.json:38)."""
    if e.status == "open":
        return True
    if e.status == "uncertain" and e.kind == "warp" and e.gates and all(
        g.detail.startswith("object_blocks_warp") for g in e.gates
    ):
        return True
    if e.status in ("post_game", "uncertain"):
        return False
    return True if MapGraph._opened(e, reached_maps) else None


# ---------------------------------------------------------------------------------------------
# Badge-staged reachability


@dataclass
class StageResult:
    maps: set[str]
    links: set[tuple[str, str]]  # map-level links used (for hops)
    via: dict[str, str]  # map -> how it was first entered (diagnostics)


def _arrival(dst: str, at: tuple[int, int] | None, abilities: frozenset[str]) -> tuple[Space, list[tuple[int, int]]]:
    sp = space_of(dst)
    tiles = passable(sp, abilities)
    if at is None:
        return sp, [p for p, ok in tiles.items() if ok and header_at(sp, p) == dst]
    return sp, _near(tiles, *at)


@cache
def bike_gates() -> tuple[tuple[str, tuple[tuple[int, int], ...], Ref], ...]:
    """(header, tiles, ref) of coord events whose script checks `CheckPlayerOnBike` and turns a
    walker back (the Cycling Road gates, scripts_route_206_cycling_road_*_gate.s
    `*_CoordEvent_OnlyBicycles`). Walls until the Bicycle is obtained."""
    from platsim.decomp.scripts import walk

    out = []
    for h in map_header_names():
        if h not in map_headers():
            continue
        for ce in events_of(h)["coord"]:
            sid = ce.data.get("script")
            if not isinstance(sid, int) or sid <= 0:
                continue
            f, entry = resolve_script_id(sid, map_headers()[h].scripts)
            sf = load_script_file(f)
            if entry >= len(sf.entries):
                continue
            if any(c.name == "CheckPlayerOnBike" for c in walk(sf, sf.command_for_entry(entry))):
                tiles = tuple((ce.x + dx, ce.z + dz) for dx in range(ce.data.get("width", 1)) for dz in range(ce.data.get("length", 1)))
                out.append((h, tiles, ce.ref))
    return tuple(out)


def _stage(k: int, with_story: bool) -> StageResult:
    """Stage k; the Bicycle (bike tiles and bike gates) is unlocked once a map whose scripts give
    it is reached, and the stage is then flooded again with it."""
    items: frozenset[str] = frozenset()
    while True:
        res = _flood_stage(k, with_story, items)
        if BICYCLE in items or not set(item_source_maps(BICYCLE)) & res.maps:
            return res
        items |= {BICYCLE}


def _flood_stage(k: int, with_story: bool, items: frozenset[str]) -> StageResult:
    abilities = frozenset(m for m in field_move_badges() if move_stage(m) <= k) | items
    walls: dict[Space, set[tuple[int, int]]] = {}
    if BICYCLE not in items:
        for h, tiles, _ in bike_gates():
            walls.setdefault(space_of(h), set()).update(tiles)
    for o in obstacles():
        if move_stage(o.why) > k:
            walls.setdefault(space_of(o.header), set()).add((o.x, o.z))
    item_walls: dict[str, list[tuple[Space, tuple[int, int]]]] = {}
    if with_story:
        opened_at: dict[tuple[str, tuple[int, int]], list[str]] = {}
        for b in story_blockers():
            opened_at.setdefault((b.header, (b.x, b.z)), []).append(b.why)
        for (h, pos), whys in opened_at.items():
            if any(w.startswith("BADGE_ID_") and badge_stage()[w] <= k for w in whys):
                continue
            walls.setdefault(space_of(h), set()).add(pos)
            for w in whys:
                if w.startswith("ITEM_"):
                    item_walls.setdefault(w, []).append((space_of(h), pos))

    reached: dict[Space, set[tuple[int, int]]] = {}
    maps: set[str] = set()
    links: set[tuple[str, str]] = set()
    via: dict[str, str] = {}
    pending: list[Link] = []
    map_links = _graph_links()[1]
    done_map_links: set[str] = set()
    # Start on Twinleaf Town's warp tiles (the player's and rival's doors).
    queue: deque[tuple[Space, list[tuple[int, int]], str, str | None]] = deque()
    for (x, z), _ in _warp_links(START):
        sp = space_of(START)
        queue.append((sp, _near(passable(sp, abilities), x, z), "start", START))
    opened_items: set[str] = set()

    def take(link: Link) -> None:
        links.add((link.src, link.dst))
        # Arriving puts the player in dst even when no passable tile is next to the arrival
        # point (e.g. the Distortion World, whose floors are C-built platforms).
        queue.append((*_arrival(link.dst, link.arrive, abilities), f"{link.edge.kind} {link.src} -> {link.dst} @{link.edge.ref}", link.dst))

    while True:
        while queue:
            sp, starts, how, dst = queue.popleft()
            tiles = passable(sp, abilities)
            seen = reached.setdefault(sp, set())
            w = walls.get(sp, set())
            starts = [s for s in starts if tiles.get(s) and s not in seen and s not in w]
            new = _flood(tiles, starts, w | seen if len(seen) < 4096 else _Union(w, seen)) if starts else set()
            seen |= new
            new_maps = ({header_at(sp, p) for p in new} | ({dst} if dst else set())) - maps
            if not new and not new_maps:
                continue
            maps |= new_maps
            for h in new_maps:
                via[h] = how
            for (lx, lz), (dx, dz) in ledges(sp):
                if (lx - dx, lz - dz) in new and (lx, lz) not in w:
                    land = (lx + dx, lz + dz)
                    if tiles.get(land) and land not in seen:
                        queue.append((sp, [land], f"ledge {header_at(sp, (lx, lz))} {(lx, lz)}", None))
            for h in _space_headers(sp):
                for (x, z), link in _warp_links(h):
                    if (x, z) in w:
                        continue  # a closed obstacle / blocker stands on the warp tile
                    if any(q in new for q in _near(tiles, x, z)) or (x, z) in new:
                        u = _usable(link.edge, maps)
                        if u:
                            take(link)
                        elif u is None:
                            pending.append(link)
            for h in new_maps:
                if h in done_map_links:
                    continue
                done_map_links.add(h)
                for link in map_links.get(h, ()):
                    u = _usable(link.edge, maps)
                    if u:
                        take(link)
                    elif u is None:
                        pending.append(link)
        changed = False
        still = []
        for link in pending:
            if MapGraph._opened(link.edge, maps):
                take(link)
                changed = True
            else:
                still.append(link)
        pending = still
        for item, ws in item_walls.items():
            if item in opened_items or not set(item_source_maps(item)) & maps:
                continue
            opened_items.add(item)
            for sp, pos in ws:
                walls.get(sp, set()).discard(pos)
                seen = reached.get(sp, set())
                x, z = pos
                if any(q in seen for q in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1))):
                    queue.append((sp, [pos], f"{item} opens {pos}", None))
                    changed = True
        if not changed:
            break
    # Borders crossed inside multi-header matrices.
    for sp, seen in reached.items():
        if sp[0] != "matrix":
            continue
        for x, z in seen:
            a = header_at(sp, (x, z))
            for q in ((x + 1, z), (x, z + 1)):
                if q in seen:
                    b = header_at(sp, q)
                    if b != a and EVERYWHERE not in (a, b):
                        links.add((a, b))
                        links.add((b, a))
    return StageResult(maps, links, via)


class _Union:
    """`in` over two sets without copying the big one (for mapgraph._flood's `walls`)."""

    def __init__(self, a: set, b: set) -> None:
        self.a, self.b = a, b

    def __contains__(self, item) -> bool:
        return item in self.a or item in self.b


def _bfs(sources: set[str], links: set[tuple[str, str]]) -> dict[str, int]:
    adj: dict[str, list[str]] = {}
    for a, b in links:
        adj.setdefault(a, []).append(b)
    dist = {s: 0 for s in sources}
    q = deque(sorted(sources))
    while q:
        cur = q.popleft()
        for n in sorted(adj.get(cur, ())):
            if n not in dist:
                dist[n] = dist[cur] + 1
                q.append(n)
    return dist


@cache
def build_story_rank(story_blockers: bool = True) -> dict[str, dict]:
    """MAP_HEADER_* -> {"badges_needed": 0..8 | None, "hops": int | None} for every header.

    `story_blockers=False` is step 1 alone (field moves and tiles only)."""
    out: dict[str, dict] = {h: {"badges_needed": None, "hops": None} for h in map_header_names()}
    prev: set[str] = {START}
    for k in range(STAGES):
        res = _stage(k, story_blockers)
        dist = _bfs(prev, res.links)
        for h in sorted(res.maps):
            if h in out and out[h]["badges_needed"] is None:
                out[h] = {"badges_needed": k, "hops": dist.get(h)}
        prev = prev | res.maps
    return out


def story_rank_json() -> dict:
    """The data/generated/story_rank.json payload (`platsim extract`)."""
    return {
        "decomp_commit": DECOMP_COMMIT,
        "gym_order": [
            {"badge": g.badge, "leader": g.leader, "top_level": g.top_level, "maps": list(g.maps),
             "src": list(g.give_refs) + [g.leader_ref]}
            for g in gym_order()
        ],
        "field_moves": {m: {"badge": b, "src": field_move_refs()[m]} for m, b in sorted(field_move_badges().items())},
        "ranks": build_story_rank(),
        "rule": "research R9: badge-staged tile reachability (src/platsim/availability/story_rank.py)",
    }


# ---------------------------------------------------------------------------------------------
# Runtime lookup


def _default_path() -> Path:
    from platsim.extract import DEFAULT_OUT

    return DEFAULT_OUT / "story_rank.json"


@cache
def _load(path: Path) -> dict[str, dict]:
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `uv run platsim extract`")
    return json.loads(path.read_text())["ranks"]


def rank(map_header: str, path: Path | None = None) -> tuple[int | None, int | None]:
    """(badges_needed, hops) of a map from data/generated/story_rank.json; (None, None) if the
    map is unknown or not reachable before the Champion. Never rebuilds."""
    r = _load(path or _default_path()).get(map_header)
    if r is None:
        return None, None
    return r["badges_needed"], r["hops"]
