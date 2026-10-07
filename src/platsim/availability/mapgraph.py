"""Map graph and pre-Champion reachability (T021, research R2 rule 2).

Nodes are the `MAP_HEADER_*` names in pokeplatinum/generated/map_headers.txt (below
MAP_HEADER_COUNT). Each header's scripts / init scripts / events / encounters / matrix come from
include/data/map_headers.h.

Edges (each keeps the `file:line` that defines it and, for script edges, the triggering node):
- `warp`: `warp_events` in res/field/events/<eventsArchiveID>.json. `MAP_HEADER_DYNAMIC`
  destinations ("go back where you came from") add no new map and are skipped.
- `script_warp` / `ship`: script commands whose primitive is SCRCMD_WARP (`Warp`) or
  SCRCMD_PLAYBOATCUTSCENE (`TakeShipFrom*` / `TakeShipTo*`), found with platsim.decomp.scripts.
  The source map is every header whose scriptsArchiveID is that file.
- `matrix`: 4-neighbour adjacency of two different headers in a multi-header matrix
  (res/field/matrices/*.json `headers`; map_matrix_000 is the overworld). MAP_HEADER_EVERYWHERE
  cells never connect.
- `hidden_location`: adjacency whose terrain is swapped by src/map_matrix.c
  MapMatrix_RevealSpringPath / MapMatrix_RevealSeabreakPath, applied in
  src/field_map_change.c (FieldMapChange_InitTerrainCollisionManager) from the hidden-location
  vars that `EnableHiddenLocation` sets. Such an edge opens only once some EnableHiddenLocation
  for that location has run.

Status of an edge:
- `open`: usable before the Champion.
- `post_game`: its trigger script node is post-game (gates.py), or every way of removing a
  blocking object is post-game, or every EnableHiddenLocation for it is post-game.
- `uncertain`: we cannot tell from scripts alone. Kinds of uncertainty recorded:
  * `object_blocks_warp`: a non-moving object stands on the warp tile and nothing we can find
    removes it (no SetFlag/RemoveObject site);
  * `coord_barrier`: a coord event whose script has a post-game gate cuts the warp off from the
    rest of its map (tile flood fill with the coord tiles as walls; see `_coord_barriers`);
  * `terrain`: two headers touch in the matrix but no walkable tile pair crosses their border
    (collision bit, include/constants/field/map.h:21-23) - for the edge itself this is a hard
    "no", so these edges are *dropped*, and listed;
  * `untriggered`: a script warp whose node no event / init script of the map reaches.
Reachability is computed to a fixpoint (an object's hidden flag may be set by a script in a map
that only becomes reachable later). `reachable(strict=True)` treats uncertain edges as cut;
`strict=False` treats them as open. The difference is the uncertainty report.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path

from platsim.availability.gates import (
    KIND_REGION,
    KIND_UNCERTAIN,
    Gate,
    NodeGates,
    flag_set_sites,
    node_gates,
)
from platsim.decomp.constants import Ref, load_enum, rel
from platsim.decomp.scripts import (
    ScriptFile,
    all_script_stems,
    load_script_file,
    parse_int,
    resolve_script_id,
)
from platsim.pins import DECOMP_ROOT

MAP_HEADERS_H = DECOMP_ROOT / "include" / "data" / "map_headers.h"
EVENTS_DIR = DECOMP_ROOT / "res" / "field" / "events"
MATRIX_DIR = DECOMP_ROOT / "res" / "field" / "matrices"
LAND_DIR = DECOMP_ROOT / "res" / "field" / "maps" / "data"
MAP_H = DECOMP_ROOT / "include" / "constants" / "field" / "map.h"
MAP_MATRIX_C = DECOMP_ROOT / "src" / "map_matrix.c"
FIELD_MAP_CHANGE_C = DECOMP_ROOT / "src" / "field_map_change.c"

START = "MAP_HEADER_TWINLEAF_TOWN"
EVERYWHERE = "MAP_HEADER_EVERYWHERE"
DYNAMIC = "MAP_HEADER_DYNAMIC"



# ---------------------------------------------------------------------------------------------
# Map headers


@dataclass(frozen=True)
class MapHeader:
    name: str
    id: int
    ref: Ref
    scripts: str
    init_scripts: str
    events: str
    encounters: str
    matrix: str


@cache
def map_header_names() -> tuple[str, ...]:
    enum = load_enum("map_headers")
    count = enum["MAP_HEADER_COUNT"]
    return tuple(k for k, v in enum.values.items() if v < count)


@cache
def map_headers() -> dict[str, MapHeader]:
    enum = load_enum("map_headers")
    lines = MAP_HEADERS_H.read_text().splitlines()
    out: dict[str, MapHeader] = {}
    cur: str | None = None
    fields: dict[str, str] = {}
    start = 0
    for lineno, line in enumerate(lines, start=1):
        m = re.match(r"\s*\[(MAP_HEADER_\w+)\]\s*=\s*\{", line)
        if m:
            cur, fields, start = m.group(1), {}, lineno
            continue
        if cur is None:
            continue
        m = re.match(r"\s*\.(\w+)\s*=\s*([^,]+),", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
            continue
        if re.match(r"\s*\},", line):
            out[cur] = MapHeader(
                cur,
                enum[cur],
                Ref(rel(MAP_HEADERS_H), start),
                fields["scriptsArchiveID"],
                fields["initScriptsArchiveID"],
                fields["eventsArchiveID"],
                fields["wildEncountersArchiveID"],
                fields["mapMatrixID"],
            )
            cur = None
    return out


@cache
def headers_for_script_file() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for h in map_headers().values():
        out.setdefault(h.scripts, []).append(h.name)
        out.setdefault(h.init_scripts, []).append(h.name)
    return {k: tuple(v) for k, v in out.items()}


# ---------------------------------------------------------------------------------------------
# Events


@dataclass(frozen=True)
class Event:
    kind: str  # warp | object | coord | bg
    index: int
    data: dict
    ref: Ref

    @property
    def x(self) -> int:
        return self.data["x"]

    @property
    def z(self) -> int:
        return self.data["z"]


def _element_lines(text: str, key: str) -> list[int]:
    """1-based line of each element's opening brace in the top-level array `key`."""
    i = text.find(f'"{key}"')
    if i < 0:
        return []
    i = text.index("[", i)
    depth, out = 0, []
    line = text.count("\n", 0, i) + 1
    for ch in text[i:]:
        if ch == "\n":
            line += 1
        elif ch in "[{":
            depth += 1
            if depth == 2 and ch == "{":
                out.append(line)
        elif ch in "]}":
            depth -= 1
            if depth == 0:
                break
    return out


@cache
def load_events(events_stem: str) -> dict[str, tuple[Event, ...]]:
    path = EVENTS_DIR / f"{events_stem}.json"
    if not path.exists():
        return {"warp": (), "object": (), "coord": (), "bg": ()}
    text = path.read_text()
    data = json.loads(text)
    out = {}
    for kind, key in (("warp", "warp_events"), ("object", "object_events"), ("coord", "coord_events"), ("bg", "bg_events")):
        items = data.get(key, [])
        lines = _element_lines(text, key)
        if len(lines) != len(items):
            raise ValueError(f"{rel(path)}: {key} line scan found {len(lines)} of {len(items)}")
        out[kind] = tuple(Event(kind, i, d, Ref(rel(path), ln)) for i, (d, ln) in enumerate(zip(items, lines)))
    return out


def events_of(header: str) -> dict[str, tuple[Event, ...]]:
    return load_events(map_headers()[header].events)


# ---------------------------------------------------------------------------------------------
# Terrain (land data collision bits)


@cache
def _map_h_define(name: str) -> int:
    m = re.search(rf"#define\s+{name}\s+(\S+)", MAP_H.read_text())
    if not m:
        raise ValueError(f"{name} not in {rel(MAP_H)}")
    return int(m.group(1), 0)


@cache
def land_attributes(land_name: str) -> tuple[int, ...] | None:
    """Terrain attributes (32x32 u16, row-major by z) of land data MAP_nnn; None for MAP_NONE.

    MAP_nnn -> map_data_nnn.bin by its value in generated/maps.txt (res/field/maps/data/
    map_data.order lists the files in that order).
    """
    maps = load_enum("maps")
    idx = maps[land_name]
    if idx == maps["MAP_NONE"]:
        return None
    return land_attributes_by_id(idx)


@cache
def land_attributes_by_id(idx: int) -> tuple[int, ...]:
    """Layout: a TERRAIN_ATTRIBUTES_OFFSET-byte header, then TERRAIN_ATTRIBUTES_SIZE bytes
    (include/constants/field/map.h; read order in src/overlay005/land_data.c:480-492)."""
    raw = (LAND_DIR / f"map_data_{idx:03d}.bin").read_bytes()
    off = _map_h_define("TERRAIN_ATTRIBUTES_OFFSET")
    n = _map_h_define("TERRAIN_ATTRIBUTES_SIZE") // 2
    return struct.unpack_from(f"<{n}H", raw, off)


def tile_blocked(attr: int) -> bool:
    shift = _map_h_define("TERRAIN_ATTRIBUTES_COLLISION_SHIFT")
    mask = _map_h_define("TERRAIN_ATTRIBUTES_COLLISION_MASK") >> shift
    return bool((attr >> shift) & mask)


@dataclass(frozen=True)
class Matrix:
    stem: str
    width: int
    height: int
    headers: tuple[tuple[str, ...], ...] | None
    lands: tuple[tuple[str, ...], ...]
    row_lines: tuple[int, ...]

    def ref(self, row: int | None = None) -> Ref:
        path = rel(MATRIX_DIR / f"{self.stem}.json")
        return Ref(path, self.row_lines[row] if row is not None and self.row_lines else 1)


@cache
def load_matrix(stem: str) -> Matrix:
    path = MATRIX_DIR / f"{stem}.json"
    text = path.read_text()
    d = json.loads(text)
    lands = tuple(tuple(r) for r in d["maps"])
    headers = tuple(tuple(r) for r in d["headers"]) if d.get("headers") else None
    rows: list[int] = []
    if headers:
        start = text.find('"headers"')
        line0 = text.count("\n", 0, start) + 1
        for off, ln in enumerate(text[start:].splitlines()):
            if ln.strip().startswith("["):
                if ln.strip().startswith("[["):
                    rows.append(line0 + off)
                elif '"MAP_HEADER' in ln:
                    rows.append(line0 + off)
            if len(rows) == len(headers):
                break
    return Matrix(stem, len(lands[0]), len(lands), headers, lands, tuple(rows))


@cache
def _header_tiles(header: str) -> dict[tuple[int, int], bool]:
    """(x, z) -> walkable for one header's part of its matrix (tile coords as in events).

    Uses the pre-Champion default terrain (see `cell_attributes`)."""
    h = map_headers()[header]
    mx = load_matrix(h.matrix)
    out = {}
    for r in range(mx.height):
        for c in range(mx.width):
            if mx.headers is not None and mx.headers[r][c] != header:
                continue
            attrs = cell_attributes(mx, r, c)
            if attrs is None:
                continue
            for tz in range(32):
                for tx in range(32):
                    out[(c * 32 + tx, r * 32 + tz)] = not tile_blocked(attrs[tz * 32 + tx])
    return out


@dataclass(frozen=True)
class Reveal:
    """A MapMatrix_Reveal* land-data swap and when FieldMapChange applies it."""

    function: str
    location: str  # HIDDEN_LOCATION_*
    applied_when_enabled: bool
    cells: tuple[tuple[tuple[int, int], int], ...]  # ((row, col), land data id)
    ref: Ref


@cache
def reveals() -> tuple[Reveal, ...]:
    """Parse src/map_matrix.c MapMatrix_Reveal* and their guards in src/field_map_change.c."""
    text = MAP_MATRIX_C.read_text()
    swaps: dict[str, list] = {}
    refs: dict[str, Ref] = {}
    for m in re.finditer(r"void (MapMatrix_Reveal\w+)\(MapMatrix \*mapMatrix\)\s*\{(.*?)\n\}", text, re.S):
        cells = []
        for expr, val in re.findall(r"mapMatrixLandDataIDs\[([^\]]+)\]\s*=\s*(\d+)", m.group(2)):
            a = re.fullmatch(r"\s*(\d+)\s*\+\s*mapMatrixWidth\s*\*\s*(\d+)\s*", expr)
            b = re.fullmatch(r"\s*mapMatrixWidth\s*\*\s*(\d+)\s*\+\s*(\d+)\s*", expr)
            if a:
                cells.append(((int(a.group(2)), int(a.group(1))), int(val)))
            elif b:
                cells.append(((int(b.group(1)), int(b.group(2))), int(val)))
            else:
                raise ValueError(f"unparsed land index {expr!r} in {m.group(1)}")
        swaps[m.group(1)] = cells
        refs[m.group(1)] = Ref(rel(MAP_MATRIX_C), text.count("\n", 0, m.start()) + 1)
    out = []
    fmc = FIELD_MAP_CHANGE_C.read_text()
    for m in re.finditer(
        r"if \((!?)SystemVars_CheckHiddenLocation\([^,]+,\s*(HIDDEN_LOCATION_\w+)\)\)\s*\{\s*(MapMatrix_Reveal\w+)\(",
        fmc,
    ):
        fn = m.group(3)
        out.append(Reveal(fn, m.group(2), m.group(1) != "!", tuple(swaps[fn]), refs[fn]))
    if len(out) != len(swaps):
        raise ValueError("every MapMatrix_Reveal* must have one guard in field_map_change.c")
    return tuple(out)


def cell_attributes(mx: Matrix, r: int, c: int) -> tuple[int, ...] | None:
    """Terrain of matrix cell (r, c) before any EnableHiddenLocation has run.

    The reveal functions return early unless matrixID is 0 (src/map_matrix.c), so only
    map_matrix_000 is affected; swaps guarded by `!CheckHiddenLocation` are applied.
    """
    if mx.stem == "map_matrix_000":
        for rv in reveals():
            if rv.applied_when_enabled:
                continue
            for cell, land in rv.cells:
                if cell == (r, c):
                    return land_attributes_by_id(land)
    return land_attributes(mx.lands[r][c])


def _flood(tiles: dict, starts: list[tuple[int, int]], walls: set) -> set:
    seen = set()
    work = [s for s in starts if s in tiles and s not in walls]
    while work:
        p = work.pop()
        if p in seen:
            continue
        seen.add(p)
        x, z = p
        for q in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if q in tiles and tiles[q] and q not in walls and q not in seen:
                work.append(q)
    return seen


def _near(tiles: dict, x: int, z: int) -> list[tuple[int, int]]:
    """A warp/door tile and its walkable neighbours (door tiles themselves may be collision)."""
    out = [(x, z)] if tiles.get((x, z)) else []
    for q in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
        if tiles.get(q):
            out.append(q)
    return out


# ---------------------------------------------------------------------------------------------
# Overworld components (multi-header matrices)


@dataclass(frozen=True)
class Terrain:
    """Walkable-tile components of a multi-header matrix (pre-Champion default terrain)."""

    matrix: str
    comp: dict  # (x, z) -> component id, walkable tiles only
    header_of_comp: dict  # component id -> frozenset of headers it touches
    links: dict  # (header_a, header_b, comp) -> Ref of a matrix row where they touch

    def header_at(self, x: int, z: int) -> str | None:
        mx = load_matrix(self.matrix)
        r, c = z // 32, x // 32
        if 0 <= r < mx.height and 0 <= c < mx.width:
            return mx.headers[r][c]
        return None


@cache
def terrain(matrix_stem: str) -> Terrain | None:
    mx = load_matrix(matrix_stem)
    if mx.headers is None:
        return None
    walk: set[tuple[int, int]] = set()
    for r in range(mx.height):
        for c in range(mx.width):
            if mx.headers[r][c] == EVERYWHERE:
                continue
            attrs = cell_attributes(mx, r, c)
            if attrs is None:
                continue
            for tz in range(32):
                for tx in range(32):
                    if not tile_blocked(attrs[tz * 32 + tx]):
                        walk.add((c * 32 + tx, r * 32 + tz))
    comp: dict[tuple[int, int], int] = {}
    n = 0
    for t in walk:
        if t in comp:
            continue
        stack = [t]
        comp[t] = n
        while stack:
            x, z = stack.pop()
            for q in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                if q in walk and q not in comp:
                    comp[q] = n
                    stack.append(q)
        n += 1
    hdr: dict[int, set[str]] = {}
    links: dict[tuple[str, str, int], Ref] = {}
    for (x, z), k in comp.items():
        a = mx.headers[z // 32][x // 32]
        hdr.setdefault(k, set()).add(a)
        for q in ((x + 1, z), (x, z + 1)):
            if q in comp:
                b = mx.headers[q[1] // 32][q[0] // 32]
                if b != a:
                    for key in ((a, b, k), (b, a, k)):
                        links.setdefault(key, mx.ref(z // 32))
    return Terrain(matrix_stem, comp, {k: frozenset(v) for k, v in hdr.items()}, links)


@cache
def anchored_components(matrix_stem: str) -> frozenset[int]:
    """Components holding a tile on/next to an arrival point: any warp event of a header in this
    matrix, or the (x, z) of a script Warp / boat cutscene into one of its headers."""
    t = terrain(matrix_stem)
    if t is None:
        return frozenset()
    points: list[tuple[int, int]] = []
    for h in map_headers().values():
        if h.matrix == matrix_stem:
            points.extend((w.x, w.z) for w in events_of(h.name)["warp"])
    for stem in all_script_stems():
        for c in load_script_file(stem).commands:
            for p in c.prims:
                if p.op in WARP_OPERANDS:
                    mi, xi, zi = WARP_OPERANDS[p.op]
                    dst = p.operands[mi].text
                    h = map_headers().get(dst)
                    x, z = _int_operand(p, xi), _int_operand(p, zi)
                    if h is not None and h.matrix == matrix_stem and x is not None and z is not None:
                        points.append((x, z))
    out = set()
    for x, z in points:
        for q in ((x, z), (x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if q in t.comp:
                out.add(t.comp[q])
    return frozenset(out)


def border_evidence(matrix_stem: str, a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
    """(walkable tile pairs across the a|b cell border, how many of them lie in anchored components)."""
    t = terrain(matrix_stem)
    anchored = anchored_components(matrix_stem)
    (r1, c1), (r2, c2) = sorted((a, b))
    pairs = []
    if r1 == r2:  # c2 = c1 + 1
        x = c1 * 32 + 31
        pairs = [((x, r1 * 32 + i), (x + 1, r1 * 32 + i)) for i in range(32)]
    else:  # r2 = r1 + 1
        z = r1 * 32 + 31
        pairs = [((c1 * 32 + i, z), (c1 * 32 + i, z + 1)) for i in range(32)]
    walk = [(p, q) for p, q in pairs if p in t.comp and q in t.comp]
    return len(walk), sum(1 for p, _ in walk if t.comp[p] in anchored)


# ---------------------------------------------------------------------------------------------
# Edges


@dataclass(frozen=True)
class Opener:
    """A script node whose execution opens a conditional edge, and where it runs."""

    node: tuple[str, int]
    ref: Ref
    gates: NodeGates
    maps: tuple[str, ...] | None  # headers running this file; None = shared/common file


@dataclass(frozen=True)
class Edge:
    src: str  # MAP_HEADER_*
    dst: str  # MAP_HEADER_*
    kind: str  # warp | script_warp | ship | matrix | hidden_location | c_elevator
    ref: Ref
    status: str  # open | post_game | uncertain | conditional
    gates: tuple[Gate, ...] = ()
    trigger: Ref | None = None
    note: str = ""
    openers: tuple[Opener, ...] = ()

    @property
    def src_header(self) -> str:  # kept for callers written against place-level edges
        return self.src

    @property
    def dst_header(self) -> str:
        return self.dst


def _gates_for_node(stem: str, idx: int) -> NodeGates:
    return node_gates(stem, idx, local_file=stem)


def _triggered_entries(header: str) -> set[int]:
    """ScriptEntry indices of the header's scripts file that its events / init scripts use."""
    h = map_headers()[header]
    ids: set[int] = set()
    ev = events_of(header)
    for kind in ("object", "coord", "bg"):
        for e in ev[kind]:
            sid = e.data.get("script")
            if isinstance(sid, int):
                ids.add(sid)
    init = load_script_file(h.init_scripts) if (Path(DECOMP_ROOT / "res/field/scripts" / f"{h.init_scripts}.s")).exists() else None
    if init is not None:
        for name, args, _ in init.init_entries:
            if name != "InitScriptEntry_OnFrameTable" and args:
                v = parse_int(args[-1])
                if v is not None:
                    ids.add(v)
        for c in init.commands:
            if c.name == "InitScriptGoToIfEqual":
                v = parse_int(c.args[2])
                if v is not None:
                    ids.add(v)
    out = set()
    for sid in ids:
        if sid <= 0:
            continue
        f, entry = resolve_script_id(sid, h.scripts)
        if f == h.scripts:
            out.add(entry)
    return out


@cache
def c_script_triggers() -> dict[str, tuple[tuple[int, Ref], ...]]:
    """MAP_HEADER_* -> map-local script IDs started from C code in a file that names that header.

    Some maps (the Distortion World uses events_empty) start their scripts from C:
    `ScriptManager_Set/Start(..., ID, ...)` or a `.scriptID = ID` table field. IDs are literals or
    `#define`s in the same file. A C file's local IDs (1..1999) are attributed to every map header
    that file names. This is an over-approximation used only to decide whether a script node has a
    trigger at all.
    """
    src_root = DECOMP_ROOT / "src"
    out: dict[str, list[tuple[int, Ref]]] = {}
    call = re.compile(r"ScriptManager_(?:Set|Start)\([^,]+,\s*(\w+)|\.scriptID\s*=\s*(\w+)")
    for path in sorted(src_root.rglob("*.c")):
        text = path.read_text(errors="replace")
        if "MAP_HEADER_" not in text or ("ScriptManager_" not in text and ".scriptID" not in text):
            continue
        defines = dict(re.findall(r"#define\s+(\w+)\s+(\S+)", text))
        ids: list[tuple[int, Ref]] = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in call.finditer(line):
                tok = m.group(1) or m.group(2)
                v = parse_int(defines.get(tok, tok))
                if v is not None and 1 <= v < 2000:
                    ids.append((v, Ref(rel(path), lineno)))
        if not ids:
            continue
        for h in set(re.findall(r"\b(MAP_HEADER_[A-Z0-9_]+)\b", text)):
            out.setdefault(h, []).extend(ids)
    return {k: tuple(v) for k, v in out.items()}


def _trigger_starts(src: str) -> tuple[list[tuple[str, int]], dict[tuple[str, int], str]]:
    """Command nodes where the map's scripts start, with a note on what starts each one."""
    h = map_headers()[src]
    sf = load_script_file(h.scripts)
    starts, why = [], {}
    for i in sorted(_triggered_entries(src)):
        if i < len(sf.entries):
            n = (sf.stem, sf.command_for_entry(i))
            starts.append(n)
            why.setdefault(n, "event/init data")
    for sid, ref in c_script_triggers().get(src, ()):
        f, i = resolve_script_id(sid, h.scripts)
        if f == sf.stem and i < len(sf.entries):
            n = (sf.stem, sf.command_for_entry(i))
            if n not in why:
                starts.append(n)
                why[n] = f"C trigger {ref}"
    return starts, why



SHARED_SCRIPT_WARPS: list[tuple[Ref, str]] = []


def _int_operand(prim, i: int) -> int | None:
    if i >= len(prim.operands):
        return None
    return parse_int(prim.operands[i].text)


# primitive -> (map operand, x operand, z operand)
WARP_OPERANDS = {"SCRCMD_WARP": (0, 2, 3), "SCRCMD_PLAYBOATCUTSCENE": (2, 3, 4)}


def _script_edges() -> list[Edge]:
    edges = []
    SHARED_SCRIPT_WARPS.clear()
    owners = headers_for_script_file()
    for stem in all_script_stems():
        sf = load_script_file(stem)
        for c in sf.commands:
            for p in c.prims:
                if p.op not in WARP_OPERANDS:
                    continue
                mi, xi, zi = WARP_OPERANDS[p.op]
                dst = p.operands[mi].text
                if not dst.startswith("MAP_HEADER_") or dst == DYNAMIC:
                    continue
                kind = "ship" if p.op == "SCRCMD_PLAYBOATCUTSCENE" else "script_warp"
                srcs = [h for h in owners.get(stem, ()) if map_headers()[h].scripts == stem]
                if not srcs:
                    # Shared script file (common scripts etc.): no source map; listed for review.
                    SHARED_SCRIPT_WARPS.append((c.ref, dst))
                    continue
                for src in srcs:
                    starts, why = _trigger_starts(src)
                    g = node_gates(stem, c.index, starts=starts, local_file=stem) if starts else None
                    if g is None or not g.reachable:
                        note = "untriggered: no event, init script or C trigger of the map reaches it"
                        status, gates = "uncertain", (Gate(KIND_UNCERTAIN, c.ref, note, False),)
                    else:
                        from platsim.availability.gates import _reach_cached

                        used = sorted({why[n] for n in starts if (stem, c.index) in _reach_cached(n, stem)})
                        note = "started by: " + "; ".join(used)
                        status, gates = ("post_game" if g.post_game else "open"), g.gates
                    edges.append(Edge(src, dst, kind, c.ref, status, tuple(gates), c.ref, note))
    return edges


_STATIONARY = re.compile(r"MOVEMENT_TYPE_(NONE|LOOK_|FACE_)")


def _object_openers(header: str, obj: Event) -> list[Opener]:
    """Script nodes that hide this object: SetFlag of its hidden_flag, or RemoveObject of its id
    in the map's scripts (RemoveObject sets the hidden flag: MapObject_SetFlagAndDeleteObject,
    src/scrcmd.c ScrCmd_RemoveObject)."""
    owners = headers_for_script_file()
    flag = obj.data.get("hidden_flag", "0")
    sites: list[tuple[str, int]] = []
    if flag and flag != "0":
        sites.extend(flag_set_sites().get(flag, ()))
    sf = load_script_file(map_headers()[header].scripts)
    for c in sf.commands:
        for p in c.prims:
            if p.op == "SCRCMD_REMOVEOBJECT" and p.operands[0].text == obj.data.get("id"):
                sites.append((sf.stem, c.index))
    out = []
    for stem, idx in dict.fromkeys(sites):
        out.append(Opener((stem, idx), load_script_file(stem).commands[idx].ref, _gates_for_node(stem, idx), owners.get(stem)))
    return out


def _warp_edges() -> list[Edge]:
    edges = []
    for name in map_header_names():
        if name not in map_headers():
            continue
        ev = events_of(name)
        for w in ev["warp"]:
            dst = w.data["dest_header_id"]
            if dst == DYNAMIC:
                continue
            blockers = [
                o for o in ev["object"] if o.x == w.x and o.z == w.z and _STATIONARY.match(o.data.get("movement_type", ""))
            ]
            if not blockers:
                status, gates, note, openers = "open", (), "", ()
            else:
                ops = []
                for o in blockers:
                    ops.extend(_object_openers(name, o))
                note = "object(s) on warp tile: " + ", ".join(f"{o.data['id']} (y={o.data.get('y')}) @{o.ref}" for o in blockers)
                if not ops:
                    gates = (Gate(KIND_UNCERTAIN, blockers[0].ref, "object_blocks_warp: " + note + "; no script hides it", False),)
                    status, openers = "uncertain", ()
                else:
                    status, gates, openers = "conditional", (), tuple(ops)
            edges.append(Edge(name, dst, "warp", w.ref, status, gates, None, note, openers))
    return edges


def _init_starts(header: str) -> list[tuple[str, int]]:
    """Command nodes of the map scripts started by its init script (OnTransition/OnLoad/...)."""
    h = map_headers()[header]
    path = DECOMP_ROOT / "res/field/scripts" / f"{h.init_scripts}.s"
    if not path.exists():
        return []
    init = load_script_file(h.init_scripts)
    ids = []
    for name, args, _ in init.init_entries:
        if name != "InitScriptEntry_OnFrameTable" and args:
            ids.append(parse_int(args[-1]))
    ids += [parse_int(c.args[2]) for c in init.commands if c.name == "InitScriptGoToIfEqual"]
    sf = load_script_file(h.scripts)
    out = []
    for sid in ids:
        if sid and sid > 0:
            f, i = resolve_script_id(sid, h.scripts)
            if f == sf.stem and i < len(sf.entries):
                out.append((f, sf.command_for_entry(i)))
    return out


def _moved_warps(edges: list[Edge]) -> list[Edge]:
    """`SetWarpEventPos index, x, z` (SCRCMD_SETWARPEVENTPOS) moves warp `index` of the running map.

    For each moved warp, with M = its move sites in the map's own scripts:
    - if the map's init scripts can finish *without* running M in the pre-game world, the warp
      can be at its event-data position before the Champion: unchanged (note added);
    - else, if they can only skip M when post-game branches are allowed, the warp is in place
      only after the Champion: `post_game` (e.g. Canalave's Harbor Inn door,
      scripts_canalave_city.s:107-116);
    - else (moved on every path, or moved by a non-init script), the warp's live position is the
      script's (x, z): if that tile and its neighbours are all collision it is closed
      (`uncertain`, warp_moved); otherwise unchanged with a note.
    Path questions use gates.can_finish_avoiding (constant propagation through SetVar included).
    """
    from platsim.availability.gates import _reach_cached, can_finish_avoiding

    status_for: dict[tuple[str, int], tuple[str, str, Ref]] = {}
    for name in map_header_names():
        h = map_headers().get(name)
        if h is None:
            continue
        sf = load_script_file(h.scripts)
        warps = events_of(name)["warp"]
        sites: dict[int, list] = {}
        for c in sf.commands:
            for p in c.prims:
                if p.op == "SCRCMD_SETWARPEVENTPOS":
                    i, x, z = (_int_operand(p, k) for k in range(3))
                    if i is not None and i < len(warps):
                        sites.setdefault(i, []).append((c, x, z))
        if not sites:
            continue
        all_starts = _init_starts(name)
        for i, lst in sites.items():
            avoid = frozenset((sf.stem, c.index) for c, _, _ in lst)
            # Only init scripts that can run a move of this warp matter.
            starts = [n for n in all_starts if avoid & _reach_cached(n, sf.stem)]
            refs = ", ".join(str(c.ref) for c, _, _ in lst)
            if starts and can_finish_avoiding(starts, sf.stem, avoid, pregame=True):
                status_for[(name, i)] = ("keep", f"SetWarpEventPos at {refs} is skipped on some pre-game path", lst[0][0].ref)
            elif starts and can_finish_avoiding(starts, sf.stem, avoid, pregame=False):
                status_for[(name, i)] = ("post_game", f"warp_moved: SetWarpEventPos at {refs} runs on every pre-game path; skipped only via post-game branches", lst[0][0].ref)
            else:
                tiles = _header_tiles(name)
                closed = all(not _near(tiles, x, z) for _, x, z in lst if x is not None and z is not None)
                why = f"warp_moved: SetWarpEventPos at {refs} relocates it" + (" onto collision tiles" if closed else " to a walkable spot")
                status_for[(name, i)] = ("uncertain" if closed else "keep", why, lst[0][0].ref)
    out = []
    for e in edges:
        if e.kind != "warp":
            out.append(e)
            continue
        idx = next((w.index for w in events_of(e.src)["warp"] if w.ref == e.ref), None)
        st = status_for.get((e.src, idx))
        if st is None:
            out.append(e)
            continue
        kind, why, ref = st
        note = (e.note + "; " if e.note else "") + why
        if kind == "keep" or e.status == "post_game":
            out.append(replace(e, note=note))
        elif kind == "post_game":
            out.append(replace(e, status="post_game", note=note, gates=e.gates + (Gate(KIND_REGION, ref, why, True),)))
        else:
            out.append(replace(e, status="uncertain", note=note, gates=e.gates + (Gate(KIND_UNCERTAIN, ref, why, False),)))
    return out


@cache
def hidden_location_sites() -> dict[str, tuple[tuple[str, int], ...]]:
    """HIDDEN_LOCATION_* -> EnableHiddenLocation (SCRCMD_SETHIDDENLOCATION <loc>, TRUE) sites."""
    out: dict[str, list] = {}
    for stem in all_script_stems():
        sf = load_script_file(stem)
        for c in sf.commands:
            for p in c.prims:
                if p.op == "SCRCMD_SETHIDDENLOCATION" and p.operands[1].text == "TRUE":
                    out.setdefault(p.operands[0].text, []).append((stem, c.index))
    return {k: tuple(v) for k, v in out.items()}


def _hidden_location_edges() -> list[Edge]:
    """Edges that exist only after EnableHiddenLocation: every header pair that touches a swapped
    cell in map_matrix_000 and includes the location's own header (HIDDEN_LOCATION_X ->
    MAP_HEADER_X by name). Source places: the neighbour's components in its border cell."""
    edges = []
    owners = headers_for_script_file()
    mx = load_matrix("map_matrix_000")
    for rv in reveals():
        loc_header = rv.location.replace("HIDDEN_LOCATION_", "MAP_HEADER_")
        openers = tuple(
            Opener(n, load_script_file(n[0]).commands[n[1]].ref, _gates_for_node(*n), owners.get(n[0]))
            for n in hidden_location_sites().get(rv.location, ())
        )
        for (r, c), _land in rv.cells:
            for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if not (0 <= rr < mx.height and 0 <= cc < mx.width):
                    continue
                a, b = mx.headers[r][c], mx.headers[rr][cc]
                if a == b or EVERYWHERE in (a, b) or loc_header not in (a, b):
                    continue
                for (h1, cell1), (h2, cell2) in (((a, (r, c)), (b, (rr, cc))), ((b, (rr, cc)), (a, (r, c)))):
                    note = f"cells {cell1}-{cell2}; {rv.location} ({rv.function} at {rv.ref})"
                    edges.append(Edge(h1, h2, "hidden_location", mx.ref(cell1[0]), "conditional", (), None, note, openers))
    return edges


DIST_WORLD_C = DECOMP_ROOT / "src" / "overlay009" / "ov9_02249960.c"


def _c_elevator_edges() -> list[Edge]:
    """Distortion World floor links from sDistWorldMapConnectionList (C, not event data)."""
    text = DIST_WORLD_C.read_text()
    i = text.index("sDistWorldMapConnectionList[DISTORTION_WORLD_MAP_COUNT] = {")
    j = text.index("};", i)
    base = text.count("\n", 0, i) + 1
    edges = []
    for m in re.finditer(r"\{\s*\.prevID = (\w+),\s*\.currID = (\w+),\s*\.nextID = (\w+)\s*\}", text[i:j]):
        line = base + text[i : i + m.start()].count("\n")
        prev, cur, nxt = m.groups()
        for dst in (prev, nxt):
            if dst != "MAP_HEADER_INVALID":
                edges.append(Edge(cur, dst, "c_elevator", Ref(rel(DIST_WORLD_C), line), "open", (), None, "sDistWorldMapConnectionList"))
    return edges


def _matrix_edges() -> list[Edge]:
    """Cell adjacency (T021): non-EVERYWHERE 4-neighbour cells of different headers.

    Cells already covered by a hidden-location edge are skipped here. Terrain evidence (see
    `border_evidence`) marks an edge `uncertain` (kind of uncertainty: terrain) when no walkable
    tile pair crosses the cell border, or when every walkable pair lies in a component with no
    arrival point (e.g. a decorative sea strip enclosed by cliffs). The tile model ignores
    waterfalls, rock-climb walls, ledges and bridge heights, so it only ever marks `uncertain`,
    never `post_game`.
    """
    hidden_cells = set()
    for rv in reveals():
        for cell, _ in rv.cells:
            hidden_cells.add(cell)
    edges = []
    for stem in sorted({h.matrix for h in map_headers().values()}):
        mx = load_matrix(stem)
        if mx.headers is None:
            continue
        for r in range(mx.height):
            for c in range(mx.width):
                a = mx.headers[r][c]
                if a == EVERYWHERE:
                    continue
                for rr, cc in ((r, c + 1), (r + 1, c)):
                    if rr >= mx.height or cc >= mx.width:
                        continue
                    b = mx.headers[rr][cc]
                    if b in (a, EVERYWHERE):
                        continue
                    if stem == "map_matrix_000" and ((r, c) in hidden_cells or (rr, cc) in hidden_cells):
                        loc_headers = {
                            rv.location.replace("HIDDEN_LOCATION_", "MAP_HEADER_")
                            for rv in reveals()
                            for cell, _ in rv.cells
                            if cell in ((r, c), (rr, cc))
                        }
                        if loc_headers & {a, b}:
                            continue
                    walk, anchored = border_evidence(stem, (r, c), (rr, cc))
                    note = f"cells ({r},{c})-({rr},{cc}); walkable border pairs {walk}, anchored {anchored}"
                    status, gates = "open", ()
                    if anchored == 0:
                        why = "no walkable tile pair crosses the border" if walk == 0 else "border tiles only in components with no arrival point"
                        gates = (Gate(KIND_UNCERTAIN, mx.ref(r), f"terrain: {why} ({note})", False),)
                        status = "uncertain"
                    for s_, d_ in ((a, b), (b, a)):
                        edges.append(Edge(s_, d_, "matrix", mx.ref(r), status, gates, None, note))
    return edges


# ---------------------------------------------------------------------------------------------
# Coord-event barriers


def _coord_barriers(edges: list[Edge]) -> list[Edge]:
    """Mark warps that only a post-game-gated coord event separates from the rest of the map.

    For each coord event whose script has a pruned post-game branch (gates.py), flood-fill the
    header's walkable tiles from its other entry points (tiles next to warps to *other* maps, and
    tiles on its border with another header) with the coord rectangle - and stationary objects -
    as walls. A warp reachable without the coord walls but not with them is behind the barrier:
    its edge becomes `uncertain` (coord_barrier), citing the coord event and the script's gates.
    """
    from platsim.availability.gates import POST_GAME_KINDS, _explore_cached, story_facts

    barrier_for: dict[tuple[str, Ref], list[Gate]] = {}
    for name in map_header_names():
        h = map_headers().get(name)
        if h is None:
            continue
        ev = events_of(name)
        gated = []
        for ce in ev["coord"]:
            sid = ce.data.get("script")
            if not isinstance(sid, int) or sid <= 0:
                continue
            f, entry = resolve_script_id(sid, h.scripts)
            fsf = load_script_file(f)
            if entry >= len(fsf.entries):
                continue
            ex = _explore_cached(((f, fsf.command_for_entry(entry)),), f, POST_GAME_KINDS, story_facts(True))
            pg = [g for _, _, g in ex.pruned if g.post_game]
            if pg:
                gated.append((ce, pg))
        if not gated:
            continue
        tiles = _header_tiles(name)
        if not tiles:
            continue
        objects = {(o.x, o.z) for o in ev["object"] if _STATIONARY.match(o.data.get("movement_type", ""))}
        warps = ev["warp"]
        for ce, pg in gated:
            walls = {(ce.x + dx, ce.z + dz) for dx in range(ce.data.get("width", 1)) for dz in range(ce.data.get("length", 1))}
            for w in warps:
                others = []
                for w2 in warps:
                    if w2.data["dest_header_id"] != w.data["dest_header_id"] and (w2.x, w2.z) not in walls:
                        others.extend(_near(tiles, w2.x, w2.z))
                others.extend(_border_tiles(name, tiles))
                if not others:
                    continue
                mine = set(_near(tiles, w.x, w.z))
                with_wall = _flood(tiles, others, walls | objects)
                without = _flood(tiles, others, objects - mine)
                if mine and (mine & without) and not (mine & with_wall):
                    note = f"coord_barrier: coord event {ce.ref} (script {ce.data.get('script')}) separates this warp"
                    detail = note + "; script gates: " + "; ".join(str(g) for g in pg[:3])
                    barrier_for.setdefault((name, w.ref), []).append(Gate(KIND_UNCERTAIN, ce.ref, detail, False))
    out = []
    for e in edges:
        key = (e.src, e.ref)
        if e.kind == "warp" and key in barrier_for and e.status in ("open", "conditional"):
            out.append(Edge(e.src, e.dst, e.kind, e.ref, "uncertain", e.gates + tuple(barrier_for[key]), e.trigger, e.note, e.openers))
        else:
            out.append(e)
    return out


def _border_tiles(header: str, tiles: dict) -> list[tuple[int, int]]:
    """Walkable tiles of this header next to a walkable tile of another header."""
    mx = load_matrix(map_headers()[header].matrix)
    if mx.headers is None:
        return []
    out = []
    for (x, z), ok in tiles.items():
        if not ok:
            continue
        for q in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if q in tiles:
                continue
            r, c = q[1] // 32, q[0] // 32
            if 0 <= r < mx.height and 0 <= c < mx.width and mx.headers[r][c] not in (header, EVERYWHERE):
                attrs = cell_attributes(mx, r, c)
                if attrs is not None and not tile_blocked(attrs[(q[1] % 32) * 32 + q[0] % 32]):
                    out.append((x, z))
                    break
    return out


# ---------------------------------------------------------------------------------------------
# Graph


@dataclass
class MapGraph:
    nodes: tuple[str, ...]
    edges: list[Edge]

    def __post_init__(self) -> None:
        self._by_src: dict[str, list[Edge]] = {}
        for e in self.edges:
            self._by_src.setdefault(e.src, []).append(e)
        self._cache: dict[tuple[str, bool], dict[str, list[Edge]]] = {}

    def reachable(self, start: str = START, strict: bool = True) -> dict[str, list[Edge]]:
        """Header -> the edge path that first reached it (empty for the start).

        `strict=True` cuts `uncertain` edges (use for phase decisions); `strict=False` opens them.
        Fixpoint: a `conditional` edge opens once one of its openers is pre-game and runs in a
        reached map (or in a shared script file).
        """
        key = (start, strict)
        if key in self._cache:
            return self._cache[key]
        reached: dict[str, list[Edge]] = {start: []}
        changed = True
        while changed:
            changed = False
            frontier = list(reached)
            while frontier:
                cur = frontier.pop()
                for e in self._by_src.get(cur, ()):
                    if e.dst in reached or not self._usable(e, reached, strict):
                        continue
                    reached[e.dst] = reached[cur] + [e]
                    frontier.append(e.dst)
                    changed = True
        self._cache[key] = reached
        return reached

    @staticmethod
    def _usable(e: Edge, reached: dict, strict: bool) -> bool:
        if e.status == "open":
            return True
        if e.status == "post_game":
            return False
        if e.status == "uncertain":
            if strict:
                return False
            return not e.openers or MapGraph._opened(e, reached)
        return MapGraph._opened(e, reached)

    @staticmethod
    def _opened(e: Edge, reached: dict) -> bool:
        for o in e.openers:
            if not o.gates.reachable or o.gates.post_game:
                continue
            if o.maps is None or any(m in reached for m in o.maps):
                return True
        return False

    def edges_into(self, header: str) -> list[Edge]:
        return [e for e in self.edges if e.dst == header and e.src != header]

    def cut_edges_into(self, header: str, strict: bool = True) -> list[Edge]:
        """Edges into `header` from a reached map that are not usable (why it is unreached)."""
        reached = self.reachable(strict=strict)
        return [e for e in self.edges_into(header) if e.src in reached and not self._usable(e, reached, strict)]

    def uncertain_maps(self) -> list[str]:
        """Headers reached only when uncertain edges are opened."""
        strict, loose = self.reachable(strict=True), self.reachable(strict=False)
        return [h for h in self.nodes if h in loose and h not in strict]

    def uncertain_edges(self) -> list[Edge]:
        return [e for e in self.edges if e.status == "uncertain"]


@cache
def build_graph() -> MapGraph:
    edges = _warp_edges() + _script_edges() + _hidden_location_edges() + _c_elevator_edges() + _matrix_edges()
    edges = _moved_warps(_coord_barriers(edges))
    return MapGraph(map_header_names(), edges)


def edge_gates(e: Edge) -> list[Gate]:
    """Gates explaining an edge's status, adding a `region` gate per post-game opener."""
    out = list(e.gates)
    if e.openers and all(o.gates.post_game or not o.gates.reachable for o in e.openers):
        for o in e.openers:
            for g in o.gates.gates:
                out.append(Gate(KIND_REGION, o.ref, f"opener of {e.ref} is post-game: {g}", True))
    return out
