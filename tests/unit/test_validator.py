"""T030/T031: legality validator, move sources and `platsim validate`.

Game facts used below (each copied from the decomp, path:line):
- Garchomp abilities [Sand Veil, none]: res/pokemon/garchomp/data.json:30.
- Gabite -> Garchomp EVO_LEVEL 48: res/pokemon/gabite/data.json:99-103.
- Magikarp -> Gyarados EVO_LEVEL 20: res/pokemon/magikarp/data.json:44-48; Magikarp level-up
  Tackle Lv 15, Flail Lv 30: res/pokemon/magikarp/data.json:38-39.
- Haunter -> Gengar EVO_TRADE: res/pokemon/haunter/data.json:110-111.
- Gible egg moves include Outrage and Iron Head: res/pokemon/gible/data.json:98,106.
- Bastiodon learns Iron Head at Lv 52 (res/pokemon/bastiodon/data.json:50), egg groups Monster
  (:29), 12.5% female (:25) - a valid father for Gible (Monster/Dragon, gible/data.json:29).
- Garchomp learns Fire Fang at Lv 1 (res/pokemon/garchomp/data.json learnset), but Garchomp only
  exists from Lv 48, so Fire Fang needs the move relearner
  (res/field/scripts/scripts_pastoria_city_east_house.s:53).
- Chimchar is starter option 1 (src/choose_starter/choose_starter_app.c:51): one of three.
- Infernape types Fire/Fighting (res/pokemon/infernape/data.json:10): no Draco Meteor
  (scripts_route_210_grandma_wilma_house.s:80-82 needs TYPE_DRAGON).
- NPC trade Chatot: res/npc_trades/charap_chatot.json (IVs 15/20/15/25 spe/25 spa/15 spd,
  personality 2151 -> NATURE_LONELY, ability slot 2 = Tangled Feet, Leppa Berry).
- Blast Burn: Route 228 starter tutor only (res/field/scripts/scripts_route_228_north_house.s),
  post-game per the ledger.
"""

import copy
import json
import subprocess
import sys

import pytest

from platsim import cli
from platsim.availability.ledger import build_ledger
from platsim.legality import movesources as MS
from platsim.legality.models import LegalityOptions, TeamCandidate, export_team
from platsim.legality.validator import showdown_name, validate
from platsim.pins import REPO_ROOT

FIX = REPO_ROOT / "tests" / "fixtures"

EXPECTED = {
    "legal_team": [],
    "illegal_postgame_tutor": ["MOVE_NOT_LEARNABLE"],
    "illegal_trade_evo": ["SPECIES_TRADE_EVOLUTION"],
    "illegal_tm_copies": ["TM_COPIES"],
    "illegal_stats": ["IV_INVALID"],
    "illegal_ability": ["ABILITY_INVALID"],
    "illegal_level_gap": ["LEVEL_GAP"],
}


@pytest.fixture(scope="module")
def led():
    return build_ledger()


@pytest.fixture(scope="module")
def egg_led(led):
    """Egg moves allowed (LegalityOptions; default off since 2026-10-08)."""
    return led.with_options(LegalityOptions(allow_egg_moves=True))


def _legal() -> dict:
    return json.loads((FIX / "legal_team.json").read_text())


def _codes(team, led) -> list[str]:
    return sorted(v.code for v in validate(team, led))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_fixture_yields_exactly_expected_codes(name, led):
    vs = validate(str(FIX / f"{name}.json"), led)
    assert sorted(v.code for v in vs) == EXPECTED[name], [v.message for v in vs]
    for v in vs:
        assert v.src, f"{v.code} has no src refs"
        assert v.message


def test_postgame_tutor_reason_names_route_228(led):
    (v,) = validate(str(FIX / "illegal_postgame_tutor.json"), led)
    assert "MOVE_BLAST_BURN" in v.message and "Route 228" in v.message and "post-game" in v.message


def test_trade_evo_reason_names_trade(led):
    (v,) = validate(str(FIX / "illegal_trade_evo.json"), led)
    assert "Haunter" in v.message and "EVO_TRADE" in v.message
    assert any("haunter/data.json" in s for s in v.src)


# --- move sources -------------------------------------------------------------------------------


def _opt(species, oid, led):
    return next(o for o in MS.source_options(species, led) if o.id == oid)


def test_pre_evolution_move_must_be_below_evolution_level(led):
    o = _opt("SPECIES_GYARADOS", "wild_slot:SPECIES_MAGIKARP@MAP_HEADER_CANALAVE_CITY", led)
    kinds = {c.source_kind: c.detail for c in MS.sources("SPECIES_GYARADOS", "MOVE_TACKLE", 57, led, o)}
    assert kinds.get("pre_evo_level_up") == "Pre-evolution level-up (Magikarp Lv 15)"
    # Flail is Magikarp Lv 30 >= evolution level 20: not learnable (no relearner as Gyarados either)
    assert MS.sources("SPECIES_GYARADOS", "MOVE_FLAIL", 57, led, o) == []
    assert any("Lv 30" in w for w in MS.explain("SPECIES_GYARADOS", "MOVE_FLAIL", 57, led, o))


def test_relearner_and_level_up_provenance(led):
    o = _opt("SPECIES_GARCHOMP", "wild_slot:SPECIES_GABITE@MAP_HEADER_VICTORY_ROAD_1F", led)
    assert o.min_level == 48
    fire = MS.sources("SPECIES_GARCHOMP", "MOVE_FIRE_FANG", 57, led, o)
    assert [c.source_kind for c in fire] == ["relearner"]
    assert MS.uses_of(fire[0]) == {"ITEM_HEART_SCALE": 1}
    assert "scripts_pastoria_city_east_house.s" in fire[0].availability_ref
    crunch = MS.sources("SPECIES_GARCHOMP", "MOVE_CRUNCH", 57, led, o)
    assert crunch[0].source_kind == "level_up" and crunch[0].detail == "Level-up Lv 48"


def test_egg_move_needs_breeding_and_records_father(egg_led):
    led = egg_led  # this test is about egg moves: allow_egg_moves on
    bred = _opt("SPECIES_GARCHOMP", "breed:SPECIES_GIBLE@MAP_HEADER_POKEMON_DAY_CARE", led)
    eggs = [c for c in MS.sources("SPECIES_GARCHOMP", "MOVE_IRON_HEAD", 57, led, bred) if c.source_kind == "egg"]
    assert eggs and "father:" in eggs[0].detail
    assert "daycare.c" in eggs[0].availability_ref
    wild = _opt("SPECIES_GARCHOMP", "wild_slot:SPECIES_GABITE@MAP_HEADER_VICTORY_ROAD_1F", led)
    assert not [c for c in MS.sources("SPECIES_GARCHOMP", "MOVE_IRON_HEAD", 57, led, wild) if c.source_kind == "egg"]
    # Negative with a reason: no pre-Champion father learns Outrage by a non-egg method.
    assert MS.sources("SPECIES_GARCHOMP", "MOVE_OUTRAGE", 57, led, bred) == []
    assert any("no pre-Champion father" in w for w in MS.explain("SPECIES_GARCHOMP", "MOVE_OUTRAGE", 57, led, bred))


def test_egg_moves_off_by_default(led, egg_led):
    """Default LegalityOptions: no egg-move source at all, with a reason naming the flag; the same
    bred option still exists (a Day-Care egg is a species source either way)."""
    assert led.options == LegalityOptions() and not led.options.allow_egg_moves
    bred = _opt("SPECIES_GARCHOMP", "breed:SPECIES_GIBLE@MAP_HEADER_POKEMON_DAY_CARE", led)
    assert MS.sources("SPECIES_GARCHOMP", "MOVE_IRON_HEAD", 57, led, bred) == []
    assert any("--allow-egg-moves" in w for w in MS.explain("SPECIES_GARCHOMP", "MOVE_IRON_HEAD", 57, led, bred))
    # positive control: the same query with the flag on finds the egg move
    on = _opt("SPECIES_GARCHOMP", "breed:SPECIES_GIBLE@MAP_HEADER_POKEMON_DAY_CARE", egg_led)
    assert [c.source_kind for c in MS.sources("SPECIES_GARCHOMP", "MOVE_IRON_HEAD", 57, egg_led, on)] == ["egg"]
    # the view is one object per option set and shares the ledger's facts
    assert led.with_options(LegalityOptions(allow_egg_moves=True)) is egg_led and egg_led.entries is led.entries
    assert led.with_options(None) is led and egg_led.with_options(LegalityOptions()) is led


def _iron_head(d: dict) -> dict:
    g = d["builds"][1]
    g["moves"][2] = {"move": "iron_head", "source_kind": "egg", "detail": "Egg move (father: Bastiodon - Level-up Lv 52)"}
    return d


def test_egg_move_rejected_by_default_and_accepted_with_the_flag(led):
    d = _iron_head(_legal())  # bred Garchomp with the egg move Iron Head
    (v,) = validate(d, led)
    assert v.code == "EGG_MOVE_NOT_ALLOWED" and "MOVE_IRON_HEAD" in v.message and "--allow-egg-moves" in v.message
    assert any("daycare.c" in s for s in v.src)
    assert validate(_iron_head(_legal()), led, options=LegalityOptions(allow_egg_moves=True)) == []
    # declared `egg` for a move that is learnable another way is still an egg move: rejected, naming the others
    d = _legal()
    d["builds"][1]["moves"][2] = {"move": "crunch", "source_kind": "egg", "detail": "Egg move"}
    (v,) = validate(d, led)
    assert v.code == "EGG_MOVE_NOT_ALLOWED" and "level_up" in v.message


def test_bastiodon_is_a_valid_iron_head_father(led):
    # Positive control for the father search: Bastiodon is obtainable, can be male, shares Monster.
    assert MS.source_options("SPECIES_BASTIODON", led)
    f = MS.find_father("SPECIES_GIBLE", ("SPECIES_GIBLE", "SPECIES_GABITE", "SPECIES_GARCHOMP"), "MOVE_IRON_HEAD", led)
    assert f is not None


def test_draco_meteor_needs_dragon_type(led):
    o = _opt("SPECIES_GARCHOMP", "wild_slot:SPECIES_GABITE@MAP_HEADER_VICTORY_ROAD_1F", led)
    assert [c.source_kind for c in MS.sources("SPECIES_GARCHOMP", "MOVE_DRACO_METEOR", 57, led, o)] == ["tutor"]
    assert MS.sources("SPECIES_INFERNAPE", "MOVE_DRACO_METEOR", 57, led) == []


def test_tm_detail_format_and_hm_unlimited(led):
    o = _opt("SPECIES_GYARADOS", "wild_slot:SPECIES_MAGIKARP@MAP_HEADER_CANALAVE_CITY", led)
    (hm,) = [c for c in MS.sources("SPECIES_GYARADOS", "MOVE_WATERFALL", 57, led, o) if c.source_kind == "hm"]
    assert hm.detail.startswith("HM07 - ") and hm.detail.endswith("(unlimited)") and MS.uses_of(hm) == {}


def test_trade_evolution_species_have_no_options(led):
    assert MS.source_options("SPECIES_GENGAR", led) == []
    assert MS.source_options("SPECIES_HAUNTER", led)  # positive control: Haunter itself is obtainable


# --- validator rules --------------------------------------------------------------------------


def test_level_below_minimum(led):
    d = _legal()
    g = d["builds"][1]
    g["source"] = "wild_slot:SPECIES_GABITE@MAP_HEADER_VICTORY_ROAD_1F"
    g["moves"] = [{"move": "dragon_claw", "source_kind": "pre_evo_level_up", "detail": "Pre-evolution level-up (Gabite Lv 33)"}]
    g["start_level"] = 47
    assert _codes(d, led) == ["LEVEL_BELOW_MINIMUM"]
    g["start_level"] = 48
    assert _codes(d, led) == []


def test_declared_source_kind_must_match(led):
    d = _legal()
    d["builds"][1]["moves"][3]["source_kind"] = "level_up"  # Fire Fang: relearner only
    assert _codes(d, led) == ["MOVE_SOURCE_MISMATCH"]


def test_egg_move_on_a_wild_member_is_not_learnable(led, egg_led):
    for lg in (led, egg_led):  # not bred: never an egg move, flag or not
        d = _iron_head(_legal())
        d["builds"][1]["source"] = "wild_slot:SPECIES_GABITE@MAP_HEADER_VICTORY_ROAD_1F"
        assert _codes(d, lg) == ["MOVE_NOT_LEARNABLE"]


def test_npc_trade_fixed_values_enforced(led):
    d = _legal()
    c = d["builds"][4]
    c.update(nature="Hardy", ivs={k: 15 for k in c["ivs"]}, ability="ABILITY_KEEN_EYE")
    assert _codes(d, led) == ["ABILITY_FIXED_BY_TRADE", "IV_INVALID", "NATURE_INVALID"]


def test_starter_choice_is_exclusive(led):
    d = _legal()
    d["builds"][5] = copy.deepcopy(d["builds"][0])
    assert _codes(d, led) == ["SOURCE_EXHAUSTED"]


def test_single_copy_item_on_two_members(led):
    d = _legal()
    assert led.item_copies("ITEM_MASTER_BALL") == 1  # ledger value, not typed game data
    d["builds"][0]["held_item"] = "master_ball"
    d["builds"][1]["held_item"] = "master_ball"
    assert _codes(d, led) == ["ITEM_COPIES"]


def test_unavailable_item_and_team_size(led):
    d = _legal()
    assert led.item_copies("ITEM_CHOICE_BAND") == 0  # ledger value
    d["builds"][0]["held_item"] = "choice_band"
    del d["builds"][5]
    assert _codes(d, led) == ["ITEM_UNAVAILABLE", "TEAM_SIZE"]


def test_showdown_export_is_accepted(led):
    team = TeamCandidate.from_dict(_legal())
    text = export_team(team, name_of=showdown_name)
    assert "Infernape" in text and "Close Combat" in text
    assert validate(text, led) == []
    ivs15 = "IVs: 15 HP / 15 Atk / 15 Def / 15 SpA / 15 SpD / 15 Spe"
    assert ivs15 in text
    bad = text.replace(ivs15, "IVs: 31 HP / 31 Atk / 31 Def / 31 SpA / 31 SpD / 31 Spe", 1)
    assert _codes(bad, led) == ["IV_INVALID"]


# --- independence from the optimizer ----------------------------------------------------------


def test_validator_does_not_import_optimizer():
    probe = (
        "import sys, json\n"
        "from platsim.legality.validator import validate\n"
        "vs = validate(sys.argv[1])\n"
        "print(json.dumps({'n': len(vs), 'opt': sorted(m for m in sys.modules if m.startswith('platsim.optimizer'))}))\n"
    )
    r = subprocess.run([sys.executable, "-c", probe, str(FIX / "legal_team.json")], capture_output=True, text=True, check=True)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out == {"n": 0, "opt": []}
    # positive control: the same probe sees the optimizer package when it is imported
    r2 = subprocess.run([sys.executable, "-c", "import sys, platsim.optimizer; print([m for m in sys.modules if m.startswith('platsim.optimizer')])"],
                        capture_output=True, text=True, check=True)
    assert "platsim.optimizer" in r2.stdout


# --- CLI (T031) -----------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_cli_validate_exit_codes(name, led, capsys):
    rc = cli.main(["validate", str(FIX / f"{name}.json")])
    out = capsys.readouterr().out
    if EXPECTED[name]:
        assert rc == 2
        assert "ILLEGAL" in out
        for code in EXPECTED[name]:
            assert f"{code}: " in out
    else:
        assert rc == 0 and "legal (no violations)" in out


def test_cli_validate_missing_file(capsys):
    assert cli.main(["validate", str(FIX / "does_not_exist.json")]) == 1
    assert "no such file" in capsys.readouterr().err


# --- 003: new rules and the Leftovers team rule (spec FR-008–FR-011, SC-004; quickstart V4) -----

POST_MON = LegalityOptions(allow_post_game_pokemon=True)
POST_ITEMS = LegalityOptions(allow_post_game_items=True)
OUTSIDE = LegalityOptions(allow_unobtainable_pokemon=True)


def _build(species: str, level: int, view) -> dict:
    """A legal Build made by the optimizer's realize, with one level-up move the species knows."""
    from platsim.optimizer import resources as R

    sp = MS.by_constant()[species]
    move = next(mv for n, mv in sp.learnset_level if n <= 10)
    real = R.realize((R.MemberSpec(species, "own", (move,)),), [level], view)
    assert not isinstance(real, R.Refusal), real.reason
    return real.team.builds[0].to_dict()


def _with_leftovers(d: dict, slots) -> dict:
    d = copy.deepcopy(d)
    for i in slots:
        d["builds"][i]["held_item"] = "leftovers"
    return d


def test_leftovers_needs_munchlax_or_snorlax(led):
    base = _legal()
    assert validate(base, led) == []  # positive control
    one = _with_leftovers(base, [0])
    assert _codes(one, led) == ["LEFTOVERS_NEEDS_MUNCHLAX"]
    v = validate(one, led)[0]
    assert "Munchlax" in v.message and "FR-" not in v.message
    for mon in ("SPECIES_MUNCHLAX", "SPECIES_SNORLAX"):
        d = copy.deepcopy(base)
        d["builds"][4] = _build(mon, 57, led)  # replaces the NPC-trade Chatot
        assert validate(d, led) == [], mon
        assert validate(_with_leftovers(d, [0, 1, 2]), led) == [], mon  # any member, any number


def test_leftovers_with_post_game_items_is_one_copy(led):
    view = led.with_options(POST_ITEMS)
    base = _legal()
    assert validate(_with_leftovers(base, [0]), view) == []  # Victory Road item ball
    assert "LEFTOVERS_NEEDS_MUNCHLAX" in _codes(_with_leftovers(base, [0, 1]), view)


def _post_only(led) -> str:
    from platsim.availability.ledger import POST

    acq = ("wild_slot", "gift", "egg", "static", "roamer", "npc_trade")
    phases: dict[str, set] = {}
    for c in led.entries:
        if c.entry.kind in acq:
            phases.setdefault(c.entry.subject, set()).add(c.phase)
    view = led.with_options(POST_MON)
    return next(s for s, p in sorted(phases.items()) if p == {POST} and MS.source_options(s, view)
                and not MS.source_options(s, led))


def test_post_game_pokemon_rule(led):
    x = _post_only(led)
    view = led.with_options(POST_MON)
    d = _legal()
    d["builds"][4] = _build(x, 57, view)
    assert "SPECIES_UNAVAILABLE" in _codes(d, led), x
    assert validate(d, view) == [], (x, [v.message for v in validate(d, view)])


def test_unobtainable_pokemon_rule(led):
    view = led.with_options(OUTSIDE)
    opts = MS.source_options("SPECIES_BULBASAUR", view)
    assert opts and opts[-1].kind == "outside_platinum" and opts[-1].min_level == 1
    assert "Unavailable in Platinum" in opts[-1].detail
    assert not MS.source_options("SPECIES_BULBASAUR", led)
    d = _legal()
    d["builds"][4] = _build("SPECIES_BULBASAUR", 57, view)
    assert "SPECIES_UNAVAILABLE" in _codes(d, led)
    assert validate(d, view) == []
    # A dual-slot pokemon (Caterpie: only other-cartridge entries) uses its real encounter levels.
    cat = MS.source_options("SPECIES_CATERPIE", view)
    assert any(o.kind == "wild_slot" and "dual-slot" in o.detail and o.min_level > 1 for o in cat)
    assert not MS.source_options("SPECIES_CATERPIE", led)


def test_postgame_tutor_is_legal_with_post_game_items(led):
    path = str(FIX / "illegal_postgame_tutor.json")
    assert _codes(path, led) == ["MOVE_NOT_LEARNABLE"]
    assert validate(path, led.with_options(POST_ITEMS)) == []
