"""Move tutors (T015).

Shard tutors: pokeplatinum/res/pokemon/move_tutors.json; array order = bit index of each species'
tutor bitmask (tools/dataproc/src/speciesproc.c post_init / emit_tutorables). Each
TUTOR_LOCATION_* is mapped to the field script that opens that tutor's menu
(`ShowMoveTutorMoveSelectionMenu ..., TUTOR_LOCATION_X`) and from the script to its map header
(include/data/map_headers.h `.scriptsArchiveID`).

Script tutors (hard-coded in field scripts):
- Draco Meteor, scripts_route_210_grandma_wilma_house.s: Dragon-type party member with max
  friendship that does not know the move.
- Starter ultimate moves, scripts_route_228_north_house.s: the 12 species are parsed from
  Route228NorthHouse_CheckFinalStageStarter; each label's VAR_RESULT value selects the move via
  Route228NorthHouse_TryTeachUltimateMove. Requires max friendship.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from platsim.decomp._util import line_of, lines, ref
from platsim.decomp.constants import rel
from platsim.pins import DECOMP_ROOT

MOVE_TUTORS = DECOMP_ROOT / "res" / "pokemon" / "move_tutors.json"
SCRIPTS_DIR = DECOMP_ROOT / "res" / "field" / "scripts"
MAP_HEADERS_H = DECOMP_ROOT / "include" / "data" / "map_headers.h"
DRACO_SCRIPT = SCRIPTS_DIR / "scripts_route_210_grandma_wilma_house.s"
ULTIMATE_SCRIPT = SCRIPTS_DIR / "scripts_route_228_north_house.s"


@dataclass
class Tutor:
    move: str
    location: str  # TUTOR_LOCATION_* suffix, or DRACO_METEOR / ROUTE_228
    shard_cost: dict[str, int] | None
    extra_requirement: list[str]
    species: list[str] | None  # restricts who can learn (script tutors); None = per-species bitmask
    bit_index: int | None  # index in move_tutors.json (shard tutors only)
    map_header: str | None
    script: str | None
    src: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@cache
def map_header_for_script(stem: str) -> tuple[str, str]:
    """MAP_HEADER_* whose scriptsArchiveID is `stem`, with the ref of that line."""
    src = lines(MAP_HEADERS_H)
    header = None
    for lineno, text in enumerate(src, start=1):
        if m := re.match(r"\s*\[(MAP_HEADER_\w+)\]\s*=\s*\{", text):
            header = m.group(1)
        elif re.match(rf"\s*\.scriptsArchiveID = {re.escape(stem)},\s*$", text):
            if header is None:
                break
            return header, f"{rel(MAP_HEADERS_H)}:{lineno}"
    raise ValueError(f"no map header uses scripts {stem}")


@cache
def _tutor_location_scripts() -> dict[str, tuple[Path, int]]:
    out: dict[str, tuple[Path, int]] = {}
    for path in sorted(SCRIPTS_DIR.glob("*.s")):
        for lineno, text in enumerate(lines(path), start=1):
            m = re.match(r"\s*ShowMoveTutorMoveSelectionMenu\s+\w+,\s*(TUTOR_LOCATION_\w+)", text)
            if m:
                loc = m.group(1)
                if loc in out and out[loc][0] != path:
                    raise ValueError(f"{loc} opened from two scripts")
                out.setdefault(loc, (path, lineno))
    return out


def _script_location(path: Path) -> tuple[str, str]:
    return map_header_for_script(path.stem)


@cache
def shard_tutors() -> list[Tutor]:
    data = json.loads(MOVE_TUTORS.read_text())
    locs = _tutor_location_scripts()
    out = []
    for i, e in enumerate(data):
        loc_const = e["location"]
        script_path, script_line = locs[loc_const]
        header, header_ref = _script_location(script_path)
        out.append(
            Tutor(
                move=e["move"],
                location=loc_const.removeprefix("TUTOR_LOCATION_"),
                shard_cost={
                    "red": int(e["redCost"]),
                    "blue": int(e["blueCost"]),
                    "yellow": int(e["yellowCost"]),
                    "green": int(e["greenCost"]),
                },
                extra_requirement=[],
                species=None,
                bit_index=i,
                map_header=header,
                script=script_path.name,
                src=[
                    ref(MOVE_TUTORS, f'"move": "{e["move"]}"'),
                    f"{rel(script_path)}:{script_line}",
                    header_ref,
                ],
            )
        )
    return out


def _require(path: Path, pattern: str) -> int:
    for lineno, text in enumerate(lines(path), start=1):
        if re.search(pattern, text):
            return lineno
    raise ValueError(f"{rel(path)}: expected a line matching {pattern!r}")


@cache
def draco_meteor_tutor() -> Tutor:
    p = DRACO_SCRIPT
    dragon = _require(p, r"GoToIfEq VAR_0x8004, TYPE_DRAGON, Route210GrandmaWilmaHouse_SelectedDragonType")
    friend = _require(p, r"GoToIfLt VAR_RESULT, MAX_FRIENDSHIP_VALUE, Route210GrandmaWilmaHouse_DoesntFullyTrustYou")
    teach = _require(p, r"OpenMoveTutorMenu VAR_0x8000, MOVE_DRACO_METEOR")
    header, header_ref = _script_location(p)
    return Tutor(
        move="MOVE_DRACO_METEOR",
        location="DRACO_METEOR",
        shard_cost=None,
        extra_requirement=["type:TYPE_DRAGON", "friendship:MAX_FRIENDSHIP_VALUE"],
        species=None,
        bit_index=None,
        map_header=header,
        script=p.name,
        src=[f"{rel(p)}:{dragon}", f"{rel(p)}:{friend}", f"{rel(p)}:{teach}", header_ref],
    )


def _label_body(path: Path, label: str) -> list[tuple[int, str]]:
    src = lines(path)
    start = line_of(path, f"{label}:")
    body = []
    for lineno in range(start + 1, len(src) + 1):
        text = src[lineno - 1].strip()
        if re.match(r"^\w+:$", text):
            break
        if text:
            body.append((lineno, text))
        if text in ("Return", "End") or text.startswith("GoTo "):
            break
    return body


@cache
def starter_ultimate_tutors() -> list[Tutor]:
    """One Tutor per ultimate move, each listing the species allowed by the script."""
    p = ULTIMATE_SCRIPT
    # species -> label -> VAR_RESULT value
    value_species: dict[int, list[tuple[str, int]]] = {}
    for lineno, text in _label_body(p, "Route228NorthHouse_CheckFinalStageStarter"):
        m = re.fullmatch(r"GoToIfEq VAR_0x8001, (SPECIES_\w+), (\w+)", text)
        if not m:
            continue
        body = _label_body(p, m.group(2))
        v = next(re.fullmatch(r"SetVar VAR_RESULT, (\d+)", t) for _, t in body if t.startswith("SetVar"))
        value_species.setdefault(int(v.group(1)), []).append((m.group(1), lineno))
    # value -> move, via TryTeachUltimateMove dispatch on VAR_0x8002
    value_move: dict[int, tuple[str, int]] = {}
    fallthrough_label = None
    dispatch_start = line_of(p, "GoToIfEq VAR_0x8002, 1, Route228NorthHouse_AskTeach")
    src = lines(p)
    seen_values = []
    for lineno in range(dispatch_start, len(src) + 1):
        text = src[lineno - 1].strip()
        if m := re.fullmatch(r"GoToIfEq VAR_0x8002, (\d+), (\w+)", text):
            seen_values.append((int(m.group(1)), m.group(2)))
            continue
        if m := re.fullmatch(r"GoTo (\w+)", text):
            fallthrough_label = m.group(1)
        break
    remaining = sorted(set(value_species) - {v for v, _ in seen_values})
    if fallthrough_label is None or len(remaining) != 1:
        raise ValueError(f"{rel(p)}: cannot resolve ultimate-move dispatch")
    for v, label in seen_values + [(remaining[0], fallthrough_label)]:
        body = _label_body(p, label)
        lineno, text = next((ln, t) for ln, t in body if t.startswith("SetVar VAR_0x8003"))
        value_move[v] = (text.split(",")[1].strip(), lineno)
    friend = _require(p, r"GoToIfLt VAR_RESULT, MAX_FRIENDSHIP_VALUE, Route228NorthHouse_NotBondedEnough")
    header, header_ref = _script_location(p)
    out = []
    for v in sorted(value_species):
        move, move_line = value_move[v]
        out.append(
            Tutor(
                move=move,
                location="ROUTE_228",
                shard_cost=None,
                extra_requirement=["friendship:MAX_FRIENDSHIP_VALUE"],
                species=[s for s, _ in value_species[v]],
                bit_index=None,
                map_header=header,
                script=p.name,
                src=[f"{rel(p)}:{ln}" for _, ln in value_species[v]]
                + [f"{rel(p)}:{move_line}", f"{rel(p)}:{friend}", header_ref],
            )
        )
    return out


def load_tutors() -> list[Tutor]:
    return [*shard_tutors(), draco_meteor_tutor(), *starter_ultimate_tutors()]
