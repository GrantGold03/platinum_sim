"""T025/T026: positive and negative controls for the availability ledger.

Every expected value cites the decomp line it was copied from; `_line` re-reads that line so a
wrong citation fails the test (the citation is itself checked).
"""

import json
import re

import pytest

from platsim.availability import gates as G
from platsim.availability import sources as S
from platsim.availability.ledger import NEVER, POST, PRE, build_ledger
from platsim.availability.mapgraph import build_graph, map_header_names, map_headers
from platsim.decomp.scripts import load_script_file
from platsim.pins import DECOMP_ROOT

SCRIPTS = "res/field/scripts"


def _line(path: str, line: int, needle: str) -> None:
    text = (DECOMP_ROOT / path).read_text().splitlines()[line - 1]
    assert needle in text, f"{path}:{line} is {text!r}, expected {needle!r}"


def _cmd(stem: str, line: int):
    return next(c for c in load_script_file(stem).commands if c.ref.line == line)


@pytest.fixture(scope="module")
def led():
    return build_ledger()


def _entries(led, **kw):
    out = []
    for c in led.entries:
        e = c.entry
        if all(
            (getattr(e, k) == v) if not callable(v) else v(getattr(e, k))
            for k, v in kw.items()
        ):
            out.append(c)
    return out


def _site_entries(led, src: str):
    return [c for c in led.entries if src in c.entry.src]


# ---------------------------------------------------------------------------------------------
# Must be post-game


def test_fight_area_and_survival_area_not_reached(led):
    # scripts_snowpoint_city.s:183 FLAG_GAME_COMPLETED check guards the ship at :210.
    _line(f"{SCRIPTS}/scripts_snowpoint_city.s", 210, "TakeShipFromSnowpoint DIR_EAST, MAP_HEADER_FIGHT_AREA")
    for h in ("MAP_HEADER_FIGHT_AREA", "MAP_HEADER_SURVIVAL_AREA"):
        assert h not in led.reached
    assert "MAP_HEADER_SNOWPOINT_CITY" in led.reached  # positive control


def test_survival_area_and_route_228_tutors_post_game(led):
    # scripts_survival_area_north_house.s:42 opens TUTOR_LOCATION_SURVIVAL_AREA;
    # scripts_route_228_north_house.s:76 OpenMoveTutorMenu (starter ultimate moves).
    _line(f"{SCRIPTS}/scripts_survival_area_north_house.s", 42, "TUTOR_LOCATION_SURVIVAL_AREA")
    _line(f"{SCRIPTS}/scripts_route_228_north_house.s", 76, "OpenMoveTutorMenu")
    assert not led.tutor_available("SURVIVAL_AREA")
    assert not led.tutor_available("ROUTE_228")
    tut = _entries(led, kind="tutor", detail="SURVIVAL_AREA")
    assert tut and all(c.phase == POST for c in tut)
    assert all(any("not reachable" in r for r in c.reasons) for c in tut)


def test_foppa_magikarp_trade_post_game(led):
    # scripts_route_226_house.s:44 InitNPCTrade NPC_TRADE_FOPPA_MAGIKARP (Route 226, post-game area)
    _line(f"{SCRIPTS}/scripts_route_226_house.s", 44, "InitNPCTrade NPC_TRADE_FOPPA_MAGIKARP")
    trades = _entries(led, kind="npc_trade", subject="SPECIES_MAGIKARP")
    assert len(trades) == 1 and trades[0].phase == POST
    assert not any(s["kind"] == "npc_trade" for s in led.species_sources("SPECIES_MAGIKARP"))
    assert any(s["kind"] == "wild_slot" for s in led.species_sources("SPECIES_MAGIKARP"))  # positive control


def test_super_rod_and_its_slots_post_game(led):
    # scripts_fight_area.s:432 SetVar VAR_0x8004, ITEM_SUPER_ROD (Fight Area only)
    _line(f"{SCRIPTS}/scripts_fight_area.s", 432, "ITEM_SUPER_ROD")
    assert led.item_copies("ITEM_SUPER_ROD") == 0
    rods = [c for c in led.entries if c.entry.detail.startswith("super_rod")]
    assert rods and all(c.phase == POST for c in rods)
    good = [c for c in led.entries if c.entry.detail.startswith("good_rod")]
    assert any(c.phase == PRE for c in good)  # positive control: scripts_route_209.s:136 Good Rod


def test_all_swarm_slots_post_game(led):
    # scripts_sandgem_town_counterpart_house_1f.s:59 GoToIfUnset FLAG_GAME_COMPLETED before
    # EnableSwarms at :62 (the only EnableSwarms site).
    _line(f"{SCRIPTS}/scripts_sandgem_town_counterpart_house_1f.s", 59, "FLAG_GAME_COMPLETED")
    _line(f"{SCRIPTS}/scripts_sandgem_town_counterpart_house_1f.s", 62, "EnableSwarms")
    swarms = [c for c in led.entries if c.entry.detail == "swarm"]
    assert len(swarms) > 100
    assert all(c.phase == POST for c in swarms)


def test_poke_radar_slots_follow_the_national_dex(led):
    # T025 listed Poke Radar slots as post-game under research R2's premise "National Dex =>
    # post-game". That premise is refuted (see test_national_dex_verdict): ITEM_POKE_RADAR is
    # given at scripts_sandgem_town_pokemon_research_lab.s:562, right after SetNationalDexEnabled
    # (:539), behind CheckLocalDexCompleted (:56). So radar slots are exactly as available as the
    # National Dex: every reachable one needs it.
    _line(f"{SCRIPTS}/scripts_sandgem_town_pokemon_research_lab.s", 562, "ITEM_POKE_RADAR")
    radar_item = [c for c in _entries(led, subject="ITEM_POKE_RADAR") if c.entry.kind == "npc_item_gift"]
    assert len(radar_item) == 1 and radar_item[0].needs_national_dex
    radar = [c for c in led.entries if c.entry.detail == "poke radar"]
    assert radar
    pre = [c for c in radar if c.phase == PRE]
    assert all(c.needs_national_dex for c in pre)
    # Spec FR-003a (user decision 2026-10-07): National Dex sources are excluded even though the
    # decomp verdict says the National Dex is obtainable pre-Champion.
    from platsim.availability.ledger import ALLOW_NATIONAL_DEX
    assert led.national_dex["pre_champion"] is True and ALLOW_NATIONAL_DEX is False
    assert pre == []


@pytest.mark.parametrize(
    "species,stem,line",
    [
        ("SPECIES_REGICE", "scripts_iceberg_ruins", 47),
        ("SPECIES_REGISTEEL", "scripts_iron_ruins", 47),
        ("SPECIES_REGIROCK", "scripts_rock_peak_ruins", 47),
        ("SPECIES_REGIGIGAS", "scripts_snowpoint_temple_b5f", 51),
        ("SPECIES_HEATRAN", "scripts_stark_mountain_room_3", 83),
    ],
)
def test_post_game_legendaries(led, species, stem, line):
    _line(f"{SCRIPTS}/{stem}.s", line, f"StartLegendaryBattle {species}")
    statics = _site_entries(led, f"{SCRIPTS}/{stem}.s:{line}")
    assert statics and all(c.phase == POST for c in statics)
    assert led.species_sources(species) == []


# ---------------------------------------------------------------------------------------------
# Must be pre-Champion


def test_route_212_and_snowpoint_tutors(led):
    # scripts_route_212_house.s:56 / scripts_snowpoint_city_east_house.s:77 open the shard tutors.
    _line(f"{SCRIPTS}/scripts_route_212_house.s", 56, "TUTOR_LOCATION_ROUTE_212")
    _line(f"{SCRIPTS}/scripts_snowpoint_city_east_house.s", 77, "TUTOR_LOCATION_SNOWPOINT_CITY")
    assert led.tutor_available("ROUTE_212")
    assert led.tutor_available("SNOWPOINT_CITY")


def test_snowpoint_tutor_has_no_gate(led):
    # T026: no flag / var / badge / game-completed check on the path to :77
    # (scripts_snowpoint_city_east_house.s:50-77), and the Hiker's hidden_flag is "0"
    # (events_snowpoint_city_east_house.json).
    tut = _entries(led, kind="tutor", detail="SNOWPOINT_CITY")
    assert tut and all(c.phase == PRE and c.entry.gates == [] for c in tut)
    surv = _entries(led, kind="tutor", detail="SURVIVAL_AREA")
    assert surv and all(c.phase == POST for c in surv)  # positive control: the check can say no


def test_tm76_from_oreburgh_gym(led):
    # scripts_oreburgh_city_gym.s:47 SetVar VAR_0x8004, ITEM_TM76
    _line(f"{SCRIPTS}/scripts_oreburgh_city_gym.s", 47, "ITEM_TM76")
    gifts = _site_entries(led, f"{SCRIPTS}/scripts_oreburgh_city_gym.s:48") or [
        c for c in _entries(led, subject="ITEM_TM76", kind="npc_item_gift")
    ]
    assert gifts and all(c.phase == PRE for c in gifts)
    assert led.tm_copies("TM76") == 1


@pytest.mark.parametrize(
    "species,trade,stem,line",
    [
        ("SPECIES_ABRA", "NPC_TRADE_KAZZA_ABRA", "scripts_oreburgh_city_north_house_1f", 29),
        ("SPECIES_CHATOT", "NPC_TRADE_CHARAP_CHATOT", "scripts_eterna_city_condominiums_1f", 114),
        ("SPECIES_HAUNTER", "NPC_TRADE_GASPAR_HAUNTER", "scripts_snowpoint_city_west_house", 46),
    ],
)
def test_pre_champion_npc_trades(led, species, trade, stem, line):
    _line(f"{SCRIPTS}/{stem}.s", line, f"InitNPCTrade {trade}")
    srcs = [s for s in led.species_sources(species) if s["kind"] == "npc_trade"]
    assert len(srcs) == 1
    fm = srcs[0]["fixed_mon"]
    assert fm["is_traded"] and fm["ivs"] and fm["personality"] is not None
    # res/npc_trades/<name>.json personality -> nature = personality % 25 (src/pokemon.c Pokemon_GetNatureOf)
    data = json.loads((DECOMP_ROOT / "res/npc_trades" / f"{trade.removeprefix('NPC_TRADE_').lower()}.json").read_text())
    assert fm["personality"] == data["personality"] and fm["held_item"] == data["heldItem"]


@pytest.mark.parametrize(
    "species,kind,stem,line,needle",
    [
        ("SPECIES_RIOLU", "egg", "scripts_iron_island_b2f_left_room", 245, "GiveEgg SPECIES_RIOLU"),
        ("SPECIES_TOGEPI", "egg", "scripts_eterna_city", 1089, "GiveEgg SPECIES_TOGEPI"),
        ("SPECIES_EEVEE", "gift", "scripts_hearthome_city_northwest_house", 38, "GivePokemon SPECIES_EEVEE"),
        ("SPECIES_PORYGON", "gift", "scripts_veilstone_city_northeast_house", 39, "GivePokemon SPECIES_PORYGON"),
        ("SPECIES_ROTOM", "static", "scripts_old_chateau_back_middle_west_room", 24, "StartWildBattle SPECIES_ROTOM"),
        ("SPECIES_SPIRITOMB", "static", "scripts_route_209", 78, "StartWildBattle SPECIES_SPIRITOMB"),
        ("SPECIES_GIRATINA", "static", "scripts_distortion_world_giratina_room", 69, "StartGiratinaOriginBattle SPECIES_GIRATINA"),
        ("SPECIES_UXIE", "static", "scripts_acuity_cavern", 33, "StartLegendaryBattle SPECIES_UXIE"),
        ("SPECIES_AZELF", "static", "scripts_valor_cavern", 47, "StartLegendaryBattle SPECIES_AZELF"),
    ],
)
def test_pre_champion_gifts_eggs_statics(led, species, kind, stem, line, needle):
    _line(f"{SCRIPTS}/{stem}.s", line, needle)
    site = f"{SCRIPTS}/{stem}.s:{line}"
    srcs = [s for s in led.species_sources(species) if s["kind"] == kind and site in s["src"]]
    assert srcs, f"{species} from {site} is not pre-Champion"


def test_turnback_cave_giratina_room_is_conservatively_cut(led):
    # scripts_turnback_cave_giratina_room.s:35 is a second Giratina. Turnback Cave's room-to-room
    # moves are not in the warp/matrix data the map graph reads (only Sendoff Spring -> entrance,
    # events_sendoff_spring.json:33), so the room is not reached even in loose mode: conservative.
    _line(f"{SCRIPTS}/scripts_turnback_cave_giratina_room.s", 35, "StartLegendaryBattle SPECIES_GIRATINA")
    assert "MAP_HEADER_TURNBACK_CAVE_ENTRANCE" in led.reached
    assert "MAP_HEADER_TURNBACK_CAVE_GIRATINA_ROOM" not in led.reached


def test_gyms_victory_road_league_reachable(led):
    # generated/map_headers.txt: gym, Victory Road and Pokemon League headers (see test_mapgraph)
    names = map_header_names()
    gyms = [n for n in names if re.search(r"_GYM(_ROOM_\d|_LEADER_ROOM)?$", n)]
    league = [n for n in names if n.startswith("MAP_HEADER_POKEMON_LEAGUE")]
    vr = ["MAP_HEADER_VICTORY_ROAD_1F", "MAP_HEADER_VICTORY_ROAD_2F", "MAP_HEADER_VICTORY_ROAD_B1F"]
    assert len(league) == 19 and len(gyms) >= 8
    assert [n for n in gyms + league + vr if n not in led.reached] == []


def test_veilstone_3f_tms_unlimited(led):
    # scripts_veilstone_store_3f.s:91/:95 PokeMartSpecialtiesWithGreeting VEILSTONE_3F_UP/DOWN,
    # stocks include/data/mart_items.h VeilstoneDeptStoreStock_3F_UP/DOWN.
    _line(f"{SCRIPTS}/scripts_veilstone_store_3f.s", 91, "MART_SPECIALTIES_ID_VEILSTONE_3F_UP")
    _line(f"{SCRIPTS}/scripts_veilstone_store_3f.s", 95, "MART_SPECIALTIES_ID_VEILSTONE_3F_DOWN")
    lists = S.mart_lists()
    tms = [i for name in ("VeilstoneDeptStoreStock_3F_UP", "VeilstoneDeptStoreStock_3F_DOWN") for i, *_ in lists[name] if i.startswith("ITEM_TM")]
    assert len(tms) == 13
    for tm in tms:
        assert led.tm_copies(tm) == "unlimited", tm
    assert led.tm_copies("TM26") == 1  # positive control: a single-copy TM (finite count)


# ---------------------------------------------------------------------------------------------
# National Dex verdict (OPEN item 1)


def test_national_dex_verdict(led):
    nd = led.national_dex
    # The only grant: scripts_sandgem_town_pokemon_research_lab.s:539 SetNationalDexEnabled,
    # behind CheckLocalDexCompleted at :56 (src/pokedex.c Pokedex_LocalDexCompleted).
    _line(f"{SCRIPTS}/scripts_sandgem_town_pokemon_research_lab.s", 539, "SetNationalDexEnabled")
    _line(f"{SCRIPTS}/scripts_sandgem_town_pokemon_research_lab.s", 56, "CheckLocalDexCompleted")
    _line("src/pokedex.c", 28, "sExcludedMonsLocal[] = {}")
    assert nd["grant"]["ref"] == f"{SCRIPTS}/scripts_sandgem_town_pokemon_research_lab.s:539"
    # the grant's only post-game-style gate is the dex condition itself
    assert {g["kind"] for g in nd["grant"]["gates"] if g["post_game"]} == {G.KIND_NATIONAL_DEX}
    assert nd["grant"]["pre_game_without_national_dex_branches"]
    assert nd["condition"]["dex_size"] == 210
    assert nd["missing"] == []
    assert nd["pre_champion"] is True
    # witnesses for the hardest species: Victory Road 1F trainers (events_victory_road_1f.json:104/121/172)
    assert "events_victory_road_1f.json:104" in nd["witnesses"]["SPECIES_GENGAR"][0]
    assert "pokemon_mansion_office.s:306" in nd["witnesses"]["SPECIES_MANAPHY"][0]


def test_national_dex_negative_control(led):
    # Without trainer battles and scripted previews the dex cannot be completed: the check can fail.
    from platsim.availability.ledger import _base_phase, _regional_dex

    owned = {c.entry.subject for c in led.entries if c.phase == PRE and not c.needs_national_dex and c.entry.kind in ("wild_slot", "gift", "egg", "static", "roamer", "npc_trade")}
    dex = {s for s, _ in _regional_dex()}
    assert "SPECIES_MANAPHY" in dex - owned  # only seen via DrawPokemonPreview, never owned


# ---------------------------------------------------------------------------------------------
# Event-only items and maps (OPEN item 2)


def test_event_only_items_come_from_mystery_gift_handlers():
    items = G.event_only_items()
    # src/scrcmd_mystery_gift.c:540, :582, :628, :670 Bag_TryAddItem in Init*Event
    assert set(items) == {"ITEM_MEMBER_CARD", "ITEM_OAKS_LETTER", "ITEM_SECRET_KEY", "ITEM_AZURE_FLUTE"}
    for item, ref in items.items():
        _line(ref.path, ref.line, item)


def test_event_only_gate_fires_on_rotom_wall():
    # scripts_team_galactic_eterna_building_1f.s:93 CheckItem ITEM_SECRET_KEY -> :108 RemoveObject wall
    _line(f"{SCRIPTS}/scripts_team_galactic_eterna_building_1f.s", 93, "CheckItem ITEM_SECRET_KEY")
    c = _cmd("scripts_team_galactic_eterna_building_1f", 108)
    ng = G.node_gates(c.file, c.index, local_file=c.file)
    assert ng.reachable and ng.post_game and ng.post_game_by_flag
    assert any(g.kind == G.KIND_EVENT_ONLY for g in ng.gates)


def test_event_maps_not_reachable(led):
    # Newmoon Island: ship at scripts_canalave_city.s:546, menu entry only if
    # FLAG_TRAVELED_TO_NEWMOON_ISLAND (:505), set only in the Harbor Inn dream
    # (scripts_canalave_city_harbor_inn.s:61) started by the frame table row
    # VAR_DARKRAI_EVENT_STATE == 1 (scripts_init_canalave_city_harbor_inn.s:9), set at :42 behind
    # the Member Card (:26) and distribution-event (:31) checks.
    _line(f"{SCRIPTS}/scripts_canalave_city.s", 546, "MAP_HEADER_NEWMOON_ISLAND")
    _line(f"{SCRIPTS}/scripts_canalave_city_harbor_inn.s", 61, "SetFlag FLAG_TRAVELED_TO_NEWMOON_ISLAND")
    _line(f"{SCRIPTS}/scripts_init_canalave_city_harbor_inn.s", 9, "InitScriptGoToIfEqual VAR_DARKRAI_EVENT_STATE, 1, 2")
    facts = G.story_facts(True)
    assert "FLAG_TRAVELED_TO_NEWMOON_ISLAND" in facts.post_flags
    assert 1 not in facts.pre_values("VAR_DARKRAI_EVENT_STATE")
    for h in (
        "MAP_HEADER_NEWMOON_ISLAND",
        "MAP_HEADER_NEWMOON_ISLAND_FOREST",
        "MAP_HEADER_CANALAVE_CITY_HARBOR_INN",
        "MAP_HEADER_ROTOMS_ROOM",
        "MAP_HEADER_FLOWER_PARADISE",
        "MAP_HEADER_SEABREAK_PATH",
        "MAP_HEADER_HALL_OF_ORIGIN",
    ):
        assert h not in led.reached, h
    assert "MAP_HEADER_CANALAVE_CITY" in led.reached  # positive control
    for sp in ("SPECIES_DARKRAI", "SPECIES_SHAYMIN", "SPECIES_ARCEUS"):
        assert led.species_sources(sp) == []


def test_dual_slot_unobtainable(led):
    # src/overlay006/dual_slot_encounters.c: slots 8/9 come from the GBA cartridge (FR-005).
    dual = [c for c in led.entries if c.entry.detail.startswith("dual-slot")]
    assert dual and all(c.phase == NEVER for c in dual)


# ---------------------------------------------------------------------------------------------
# T026 items


def test_unknown_encounter_files_unused():
    # res/field/encounters/encounters_unknown_533..557.json: no map header names them
    # (include/data/map_headers.h .wildEncountersArchiveID).
    used = {h.encounters for h in map_headers().values()}
    assert "encounters_route_201" in used  # positive control
    unknown = {p.stem for p in (DECOMP_ROOT / "res/field/encounters").glob("encounters_unknown_*.json")}
    assert len(unknown) == 25
    assert not unknown & used


def test_honey_tree_headers(led):
    # src/overlay005/honey_tree.c:41-63 sHoneyTreeMapHeaderIDs (21 trees)
    _line("src/overlay005/honey_tree.c", 42, "MAP_HEADER_ROUTE_205_SOUTH")
    _line("src/overlay005/honey_tree.c", 62, "MAP_HEADER_FLOAROMA_MEADOW")
    hs = [h for h, _ in S.honey_tree_headers()]
    assert len(hs) == 21 and hs[0] == "MAP_HEADER_ROUTE_205_SOUTH" and hs[-1] == "MAP_HEADER_FLOAROMA_MEADOW"
    honey = [c for c in led.entries if c.entry.detail.startswith("honey tree")]
    assert {c.entry.map_header for c in honey} == set(hs)
    assert any(c.phase == PRE for c in honey) and all("ITEM_HONEY" in c.entry.requires_items for c in honey)
    assert led.species_sources("SPECIES_MUNCHLAX")  # rare table, encounters_honey_tree.json


def test_victory_road_and_league_not_badge_gated(led):
    # No CheckBadgeAcquired / CountBadgesAcquired on any edge of the path to Victory Road or the
    # League; the League door guard (scripts_pokemon_league_north_pokecenter_1f.s:36-51) steps
    # aside unconditionally. Field-move badges (src/field_move_tasks.c) are not modelled; all
    # eight badges are pre-Champion anyway.
    g = build_graph()
    reached = g.reachable(strict=True)
    for h in ("MAP_HEADER_VICTORY_ROAD_1F", "MAP_HEADER_POKEMON_LEAGUE"):
        path = reached[h]
        assert path
        assert not [x for e in path for x in e.gates if x.kind in (G.KIND_BADGE, G.KIND_BADGE_COUNT)]
    # positive control: badge gates are recorded where they exist (badge-tier mart stock)
    assert any(any(x["kind"] == "badge_count" for x in c.entry.gates) for c in led.entries if c.entry.kind == "shop")


def test_pp_restore_between_battles(led):
    pp = led.derived["pp_restore"]
    # No mart list sells Ether / Max Ether / Elixir / Max Elixir / Leppa (include/data/mart_items.h);
    # none of their hidden-item flags is re-hidden daily (src/script_manager.c:542-556).
    lists = S.mart_lists()
    sold = {i for name, v in lists.items() if name != "__index__" for i, *_ in v}
    assert "ITEM_POTION" in sold  # positive control
    for it in ("ITEM_ETHER", "ITEM_MAX_ETHER", "ITEM_ELIXIR", "ITEM_MAX_ELIXIR", "ITEM_LEPPA_BERRY"):
        assert it not in sold
        assert it in pp["items"]
    for it in ("ITEM_ETHER", "ITEM_MAX_ETHER", "ITEM_ELIXIR", "ITEM_MAX_ELIXIR"):
        assert pp["items"][it] != "unlimited"
    # Leppa: an initial berry patch (include/data/berry_init.h) and replanting, whose yield is
    # clamped to >= 2 (src/berry_patches.c CalcBerryYield) -> unlimited.
    assert pp["items"]["ITEM_LEPPA_BERRY"] == "unlimited"
    assert pp["value"] is True
    data = json.loads((DECOMP_ROOT.parent / "data/generated/availability.json").read_text())
    assert data["pp_restore_between_battles"]["value"] is True


def test_every_entry_has_source_refs(led):
    bad = [c for c in led.entries if not c.entry.src or not all(re.match(r"^[\w./-]+(:\d+)?$", s) for s in c.entry.src)]
    assert bad == []
    assert all(c.phase in (PRE, POST, NEVER) for c in led.entries)
    for c in led.entries:
        if c.phase != PRE:
            assert c.reasons, c.entry
