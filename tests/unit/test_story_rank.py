"""003 T033: map story rank (research R9) - badge-staged tile reachability.

Expected values are decomp-derived claims (research R9 "Positive controls"):
- field move -> badge: pokeplatinum/src/field_move_tasks.c:326-631 (`PlayerHasRequiredBadge`);
- gym order: leaders' top party level, res/trainers/data/leader_*.json (14, 22, 26, 32, 37, 41,
  44, 50), and the GiveBadge sites in res/field/scripts/scripts_*_gym*.s;
- Route 209 blockade: FLAG_HIDE_HEARTHOME_CITY_ROUTE_209_BLOCKADE, set at
  scripts_hearthome_city_gym_leader_room.s:83 after GiveBadge BADGE_ID_RELIC (:71), hides two
  objects of events_hearthome_city.json (:309, :324).
"""

import pytest

from platsim.availability import story_rank as SR

EXPECTED_GYM_ORDER = (
    "BADGE_ID_COAL",
    "BADGE_ID_FOREST",
    "BADGE_ID_RELIC",
    "BADGE_ID_COBBLE",
    "BADGE_ID_FEN",
    "BADGE_ID_MINE",
    "BADGE_ID_ICICLE",
    "BADGE_ID_BEACON",
)


@pytest.fixture(scope="module")
def ranks():
    return SR.build_story_rank()


@pytest.fixture(scope="module")
def ranks_step1():
    return SR.build_story_rank(story_blockers=False)


def test_field_move_badges_from_c_and_scripts_agree():
    fm = SR.field_move_badges()
    # src/field_move_tasks.c:332, 373, 414, 463, 504, 545, 590, 631
    assert fm == {
        "MOVE_CUT": "BADGE_ID_FOREST",
        "MOVE_FLY": "BADGE_ID_COBBLE",
        "MOVE_SURF": "BADGE_ID_FEN",
        "MOVE_STRENGTH": "BADGE_ID_MINE",
        "MOVE_DEFOG": "BADGE_ID_RELIC",
        "MOVE_ROCK_SMASH": "BADGE_ID_COAL",
        "MOVE_WATERFALL": "BADGE_ID_BEACON",
        "MOVE_ROCK_CLIMB": "BADGE_ID_ICICLE",
    }


def test_field_move_cross_check_fails_loudly():
    """Positive control: a script pairing that disagrees with the C table raises."""
    with pytest.raises(ValueError):
        SR._cross_check({"MOVE_CUT": "BADGE_ID_FOREST"}, {"MOVE_CUT": ("BADGE_ID_COAL", "x.s:1")})


def test_gym_order_from_leader_levels():
    order = SR.gym_order()
    assert tuple(g.badge for g in order) == EXPECTED_GYM_ORDER
    levels = [g.top_level for g in order]
    assert levels == sorted(levels) and len(set(levels)) == 8
    assert order[0].leader == "TRAINER_LEADER_ROARK" and order[0].top_level == 14
    assert order[-1].leader == "TRAINER_LEADER_VOLKNER" and order[-1].top_level == 50


def test_obstacles_parsed():
    obs = SR.obstacles()
    by_move: dict[str, int] = {}
    for o in obs:
        by_move[o.move] = by_move.get(o.move, 0) + 1
    # res/field/events/*.json: script 10000 x49, 10001 x590, 10002 x49
    assert by_move == {"MOVE_CUT": 49, "MOVE_ROCK_SMASH": 590, "MOVE_STRENGTH": 49}


@pytest.mark.parametrize(
    "header, expected",
    [
        ("MAP_HEADER_TWINLEAF_TOWN", 0),
        ("MAP_HEADER_ROUTE_201", 0),
        ("MAP_HEADER_ROUTE_204_NORTH", 1),  # behind Ravaged Path's Rock Smash rocks (Coal)
        ("MAP_HEADER_ROUTE_209", 3),  # Hearthome blockade cleared with Relic
        ("MAP_HEADER_ROUTE_218_GATE_TO_CANALAVE_CITY", 5),  # across Route 218's sea: Surf (Fen)
        ("MAP_HEADER_CANALAVE_CITY", 5),
        ("MAP_HEADER_ROUTE_220", 5),
        ("MAP_HEADER_VICTORY_ROAD_1F", 8),  # Waterfall on Route 223 needs Beacon
        ("MAP_HEADER_WAYWARD_CAVE_B1F", 1),  # hidden entrance under the Cycling Road (Bicycle)
    ],
)
def test_controls(ranks, header, expected):
    assert ranks[header]["badges_needed"] == expected


@pytest.mark.parametrize("header", ["MAP_HEADER_RAVAGED_PATH", "MAP_HEADER_ROUTE_218"])
def test_entrance_regions_are_stage_0(ranks, header):
    """Decomp-derived (disagrees with research R9's 1 / 5, see the xfail below): a map ranks by
    its earliest region. Ravaged Path's south entrance (events_ravaged_path.json warp 0 at
    (19,50)) opens onto 36 TILE_BEHAVIOR_CAVE_FLOOR tiles (TILE_BEHAVIOR_FLAG_ENCOUNTER,
    src/map_tile_behavior.c:15) before the first Rock Smash rock; Route 218's Jubilife gate
    (warp at (121,758)) opens onto 124 land / bridge tiles (no grass) before the sea."""
    assert ranks[header]["badges_needed"] == 0


@pytest.mark.xfail(strict=True, reason="R9 expects 1 / 5; the entrance regions are walkable at stage 0 (see above)")
@pytest.mark.parametrize("header, expected", [("MAP_HEADER_RAVAGED_PATH", 1), ("MAP_HEADER_ROUTE_218", 5)])
def test_r9_whole_map_claims(ranks, header, expected):
    assert ranks[header]["badges_needed"] == expected


def test_step1_and_step2_differ(ranks, ranks_step1):
    """Story blockers move Route 209 later: the Hearthome blockade (Relic) is what ranks it 3."""
    assert ranks_step1["MAP_HEADER_ROUTE_209"]["badges_needed"] < ranks["MAP_HEADER_ROUTE_209"]["badges_needed"] == 3


@pytest.mark.xfail(strict=True, reason=(
    "step 1 gives 1: Hearthome is reached at stage 1 through Route 207's bike slope, because the "
    "Bicycle counts once the Cycle Shop is reached; its giver is shown by a var-driven story chain "
    "(scripts_team_galactic_eterna_building_4f.s:75) that is not modelled"))
def test_step1_control_route_209(ranks_step1):
    """R9: without story blockers Route 209 opens with Cut (Forest): rank 2."""
    assert ranks_step1["MAP_HEADER_ROUTE_209"]["badges_needed"] == 2


def test_gym_maps_rank_below_their_badge(ranks):
    order = SR.gym_order()
    for i, g in enumerate(order):
        got = [ranks[m]["badges_needed"] for m in g.maps if ranks[m]["badges_needed"] is not None]
        assert got, f"{g.badge}: no gym map reachable ({g.maps})"
        assert min(got) <= i, f"{g.badge} gym {g.maps} ranks {got}, badge stage {i + 1}"


def test_gym_maps_first_reachable_never_after_their_stage(ranks):
    order = SR.gym_order()
    first = [min(ranks[m]["badges_needed"] for m in g.maps if ranks[m]["badges_needed"] is not None) for g in order]
    # Coal, Forest, Mine, Icicle gyms open exactly at their stage (the field-move gates hold).
    assert [first[i] for i in (0, 1, 5, 6)] == [0, 1, 5, 6], first


@pytest.mark.xfail(strict=True, reason=(
    "gives [0, 1, 1, 3, 3, 5, 6, 3]: var-driven story gates are not modelled (Bicycle at stage 1 "
    "opens Hearthome early; Valor Lakefront's Sunyshore blackout pushback, "
    "VAR_VALOR_LAKEFRONT_BLOCK_SUNYSHORE_STATE, is open; Veilstone and Pastoria tie at 3)"))
def test_gym_order_matches_first_reachable_order(ranks):
    order = SR.gym_order()
    first = [min(ranks[m]["badges_needed"] for m in g.maps if ranks[m]["badges_needed"] is not None) for g in order]
    assert first == list(range(8)), first


def test_rank_reads_generated_file(tmp_path, ranks):
    path = tmp_path / "story_rank.json"
    path.write_text(__import__("json").dumps(SR.story_rank_json()))
    SR._load.cache_clear()
    try:
        assert SR.rank("MAP_HEADER_ROUTE_209", path=path) == (3, ranks["MAP_HEADER_ROUTE_209"]["hops"])
        assert SR.rank("MAP_HEADER_NOT_A_MAP", path=path) == (None, None)
    finally:
        SR._load.cache_clear()
