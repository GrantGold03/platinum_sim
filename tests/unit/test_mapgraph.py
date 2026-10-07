"""T021/T022: map graph, gates and pre-Champion reachability.

Every expected value cites the decomp line it was copied from.
"""

import pytest

from platsim.availability.gates import (
    KIND_GAME_COMPLETED,
    KIND_NATIONAL_DEX,
    condition_table,
    label_gates,
    node_gates,
    story_facts,
)
from platsim.availability.mapgraph import START, build_graph, map_header_names, map_headers
from platsim.decomp.scripts import load_script_file

# generated/map_headers.txt lines 36, 48, 68, 92, 123, 134, 155-157, 168
GYMS = [
    "MAP_HEADER_CANALAVE_CITY_GYM",
    "MAP_HEADER_OREBURGH_CITY_GYM",
    "MAP_HEADER_ETERNA_CITY_GYM",
    "MAP_HEADER_HEARTHOME_CITY_GYM_LEADER_ROOM",
    "MAP_HEADER_PASTORIA_CITY_GYM",
    "MAP_HEADER_VEILSTONE_CITY_GYM",
    "MAP_HEADER_SUNYSHORE_CITY_GYM_ROOM_1",
    "MAP_HEADER_SUNYSHORE_CITY_GYM_ROOM_2",
    "MAP_HEADER_SUNYSHORE_CITY_GYM_ROOM_3",
    "MAP_HEADER_SNOWPOINT_CITY_GYM",
]
# generated/map_headers.txt lines 245-247
VICTORY_ROAD = ["MAP_HEADER_VICTORY_ROAD_1F", "MAP_HEADER_VICTORY_ROAD_2F", "MAP_HEADER_VICTORY_ROAD_B1F"]
# generated/map_headers.txt lines 173-188 (plus 484, 496, 497: the pokecenter basements/2F)
LEAGUE_PREFIX = "MAP_HEADER_POKEMON_LEAGUE"


@pytest.fixture(scope="module")
def graph():
    return build_graph()


def _cmd(stem, line):
    sf = load_script_file(stem)
    return next(c for c in sf.commands if c.ref.line == line)


def test_nodes_come_from_generated_list():
    names = map_header_names()
    # generated/map_headers.txt:1 MAP_HEADER_EVERYWHERE, :412 MAP_HEADER_TWINLEAF_TOWN, :593 last header
    assert names[0] == "MAP_HEADER_EVERYWHERE"
    assert names[411] == "MAP_HEADER_TWINLEAF_TOWN" == START
    assert len(names) == 593
    # include/data/map_headers.h:3674-3684 Snowpoint City's archives
    h = map_headers()["MAP_HEADER_SNOWPOINT_CITY"]
    assert (h.scripts, h.events, h.matrix, h.ref.line) == (
        "scripts_snowpoint_city",
        "events_snowpoint_city",
        "map_matrix_000",
        3674,
    )


def test_condition_table_parsed():
    # src/scrcmd.c:744-752: row 1 (==) is {FALSE, TRUE, FALSE}, row 5 (!=) is {TRUE, FALSE, TRUE}
    t = condition_table()
    assert t[1] == (False, True, False) and t[5] == (True, False, True)


def test_snowpoint_ship_is_post_game():
    # res/field/scripts/scripts_snowpoint_city.s:210 TakeShipFromSnowpoint ... MAP_HEADER_FIGHT_AREA,
    # reached only past :183 GoToIfUnset FLAG_GAME_COMPLETED.
    sf = load_script_file("scripts_snowpoint_city")
    ship = _cmd("scripts_snowpoint_city", 210)
    g = node_gates(sf.stem, ship.index, local_file=sf.stem)
    assert g.reachable and g.post_game and g.post_game_by_flag
    assert [(x.kind, x.ref.line, x.requires) for x in g.gates] == [(KIND_GAME_COMPLETED, 183, "FLAG_GAME_COMPLETED=1")]


def test_positive_and_negative_gate_controls():
    # National Dex gate: res/field/scripts/scripts_snowpoint_city.s:34-35 (GetNationalDexEnabled, GoToIfEq ..., TRUE)
    g = label_gates("scripts_snowpoint_city", "SnowpointCity_CheckAllowEnterTemple", local_file="scripts_snowpoint_city")
    assert g.post_game and any(x.kind == KIND_NATIONAL_DEX and x.ref.line == 35 for x in g.gates)
    # Negative control: Route 201 starter gift (res/field/scripts/scripts_route_201.s:286) is pre-game.
    c = _cmd("scripts_route_201", 286)
    g = node_gates("scripts_route_201", c.index, local_file="scripts_route_201")
    assert g.reachable and not g.post_game


def test_national_dex_premise_is_not_script_derived():
    # research R2 rule 1 treats National Dex as post-game. The grant itself
    # (res/field/scripts/scripts_sandgem_town_pokemon_research_lab.s:539 SetNationalDexEnabled) is
    # behind CheckLocalDexCompleted (:56), not FLAG_GAME_COMPLETED: the premise is an input, and
    # NodeGates.post_game_by_flag reports results without it.
    c = _cmd("scripts_sandgem_town_pokemon_research_lab", 539)
    g = node_gates(c.file, c.index, local_file=c.file)
    assert c.name == "SetNationalDexEnabled" and g.reachable and not g.post_game


def test_derived_flag_victory_road_collector():
    # res/field/scripts/scripts_victory_road_1f.s:11-14: the collector is hidden only after
    # FLAG_GAME_COMPLETED + National Dex; it stands on warp 6 (events_victory_road_1f.json:260, x 45 z 33).
    assert "FLAG_HIDE_VICTORY_ROAD_1F_COLLECTOR" in story_facts(True).post_flags
    c = _cmd("scripts_victory_road_1f", 14)
    assert node_gates(c.file, c.index, local_file=c.file).post_game


def test_battle_zone_not_reachable_and_cut_edge_cites_snowpoint(graph):
    for strict in (True, False):
        reached = graph.reachable(strict=strict)
        assert "MAP_HEADER_FIGHT_AREA" not in reached
        assert "MAP_HEADER_SNOWPOINT_CITY" in reached  # positive control: the ship's port is reached
    cut = graph.cut_edges_into("MAP_HEADER_FIGHT_AREA")
    assert cut, "positive control: there must be a cut edge into the Fight Area"
    assert {(e.kind, e.status, str(e.ref)) for e in cut} == {
        ("ship", "post_game", "res/field/scripts/scripts_snowpoint_city.s:210")
    }
    assert all(any(g.ref.line == 183 and g.kind == KIND_GAME_COMPLETED for g in e.gates) for e in cut)
    # every edge into the Fight Area is either this ship or comes from a map that is not reached
    reached = graph.reachable()
    for e in graph.edges_into("MAP_HEADER_FIGHT_AREA"):
        assert e.src not in reached or e in cut


@pytest.mark.parametrize("strict", [True, False])
def test_gyms_victory_road_and_league_reachable(graph, strict):
    reached = graph.reachable(strict=strict)
    league = [n for n in map_header_names() if n.startswith(LEAGUE_PREFIX)]
    assert len(league) == 19  # generated/map_headers.txt:173-188, 484, 496, 497
    missing = [n for n in GYMS + VICTORY_ROAD + league if n not in reached]
    assert missing == []


def test_victory_road_back_rooms_are_not_pre_game(graph):
    # The VR 1F -> 1F_ROOM_1 warp (events_victory_road_1f.json:259) is blocked by the collector.
    reached = graph.reachable(strict=True)
    assert "MAP_HEADER_VICTORY_ROAD_1F_ROOM_1" not in reached
    edge = next(e for e in graph.edges_into("MAP_HEADER_VICTORY_ROAD_1F_ROOM_1") if e.src == "MAP_HEADER_VICTORY_ROAD_1F")
    assert edge.status == "conditional" and str(edge.ref) == "res/field/events/events_victory_road_1f.json:259"
    assert all(o.gates.post_game for o in edge.openers)


def test_uncertain_maps_are_listed(graph):
    # Uncertainty is explicit: maps reached only when uncertain edges are opened.
    unc = graph.uncertain_maps()
    assert "MAP_HEADER_SNOWPOINT_TEMPLE_1F" in unc  # coord barrier, scripts_snowpoint_city.s:28-37
    assert "MAP_HEADER_ROUTE_224" in unc  # terrain-only League adjacency
    for e in graph.uncertain_edges():
        assert e.gates and all(g.ref.path and g.ref.line > 0 for g in e.gates)
