"""T015 tutor tests. Values copied from pokeplatinum/res/pokemon/move_tutors.json and the scripts."""

from platsim.decomp.tutors import (
    draco_meteor_tutor,
    load_tutors,
    shard_tutors,
    starter_ultimate_tutors,
)


def test_shard_tutor_count_and_order():
    t = shard_tutors()
    assert len(t) == 38  # res/pokemon/move_tutors.json: 38 objects
    assert [x.bit_index for x in t] == list(range(38))


def test_dive_route_212():
    dive = shard_tutors()[0]
    # res/pokemon/move_tutors.json:3-8
    assert dive.move == "MOVE_DIVE"
    assert dive.location == "ROUTE_212"
    assert dive.shard_cost == {"red": 2, "blue": 4, "yellow": 2, "green": 0}
    # res/field/scripts/scripts_route_212_house.s:56 opens TUTOR_LOCATION_ROUTE_212
    assert dive.script == "scripts_route_212_house.s"
    assert dive.map_header == "MAP_HEADER_ROUTE_212_HOUSE"


def test_superpower_survival_area():
    (sp,) = [t for t in shard_tutors() if t.move == "MOVE_SUPERPOWER"]
    # res/pokemon/move_tutors.json:59-64
    assert sp.location == "SURVIVAL_AREA"
    assert sp.shard_cost == {"red": 8, "blue": 0, "yellow": 0, "green": 0}
    assert sp.map_header == "MAP_HEADER_SURVIVAL_AREA_NORTH_HOUSE"


def test_draco_meteor():
    t = draco_meteor_tutor()
    # scripts_route_210_grandma_wilma_house.s:110 (friendship), :131 (TYPE_DRAGON), :117 (teach)
    assert t.move == "MOVE_DRACO_METEOR"
    assert "type:TYPE_DRAGON" in t.extra_requirement
    assert "friendship:MAX_FRIENDSHIP_VALUE" in t.extra_requirement
    assert t.map_header == "MAP_HEADER_ROUTE_210_GRANDMA_WILMA_HOUSE"


def test_route_228_starter_species():
    by_move = {t.move: t.species for t in starter_ultimate_tutors()}
    # res/field/scripts/scripts_route_228_north_house.s:86-97 (species -> VAR_RESULT 1/2/3)
    # and :47-49, :55/:62/:69 (1 -> Blast Burn, 2 -> Hydro Cannon, else Frenzy Plant)
    assert by_move == {
        "MOVE_BLAST_BURN": ["SPECIES_CHARIZARD", "SPECIES_TYPHLOSION", "SPECIES_BLAZIKEN", "SPECIES_INFERNAPE"],
        "MOVE_HYDRO_CANNON": ["SPECIES_BLASTOISE", "SPECIES_FERALIGATR", "SPECIES_SWAMPERT", "SPECIES_EMPOLEON"],
        "MOVE_FRENZY_PLANT": ["SPECIES_VENUSAUR", "SPECIES_MEGANIUM", "SPECIES_SCEPTILE", "SPECIES_TORTERRA"],
    }
    assert sum(len(v) for v in by_move.values()) == 12
    assert all(t.map_header == "MAP_HEADER_ROUTE_228_NORTH_HOUSE" for t in starter_ultimate_tutors())


def test_all_tutors():
    assert len(load_tutors()) == 38 + 1 + 3
