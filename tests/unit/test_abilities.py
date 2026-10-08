"""T060: battle-effect classification of abilities (FR-008c) and the no-run branches of choose_ability.

Every expected ref below was read in the decomp at the pinned commit (path:line cited).
"""

import json

import pytest

from platsim.extract import DEFAULT_OUT
from platsim.optimizer import abilities as AB


@pytest.fixture(scope="module")
def table():
    return AB.battle_effect_table()


def _refs(table, name):
    return table["abilities"][name]["battle_refs"]


# --- positive controls: abilities the battle engine checks --------------------------------------------

@pytest.mark.parametrize("name, ref", [
    # src/battle/battle_lib.c:3801  `&& Battler_Ability(battleCtx, battler) == ABILITY_INTIMIDATE) {`
    ("ABILITY_INTIMIDATE", "src/battle/battle_lib.c:3801"),
    # src/battle/battle_lib.c:2600  `if (Battler_IgnorableAbility(battleCtx, attacker, defender, ABILITY_LEVITATE) == TRUE`
    ("ABILITY_LEVITATE", "src/battle/battle_lib.c:2600"),
    # res/battle/scripts/subscripts/subscript_hazards_check.s:8  `CheckAbility CHECK_HAVE, BTLSCR_SWITCHED_MON, ABILITY_LEVITATE, _085`
    ("ABILITY_LEVITATE", "res/battle/scripts/subscripts/subscript_hazards_check.s:8"),
    # src/battle/battle_controller_player.c:2927  `if (WEATHER_IS_SAND && Battler_IgnorableAbility(..., ABILITY_SAND_VEIL) == TRUE) {`
    ("ABILITY_SAND_VEIL", "src/battle/battle_controller_player.c:2927"),
    # src/battle/battle_lib.c:3555  `case ABILITY_SPEED_BOOST:` (BattleSystem_TriggerTurnEndAbility)
    ("ABILITY_SPEED_BOOST", "src/battle/battle_lib.c:3555"),
])
def test_battle_effect_controls(table, name, ref):
    assert table["abilities"][name]["has_battle_effect"] is True
    assert ref in _refs(table, name)


@pytest.mark.parametrize("name, ref", [
    # res/battle/scripts/subscripts/subscript_recoil_1_2.s:5  `CheckAbility CHECK_HAVE, BTLSCR_ATTACKER, ABILITY_ROCK_HEAD, _...`
    ("ABILITY_ROCK_HEAD", "res/battle/scripts/subscripts/subscript_recoil_1_2.s:5"),
    # res/battle/scripts/effects/effect_script_0269.s:5  `CheckAbility CHECK_NOT_HAVE, BTLSCR_ATTACKER, ABILITY_RECKLESS, _008`
    ("ABILITY_RECKLESS", "res/battle/scripts/effects/effect_script_0269.s:5"),
    # res/battle/scripts/subscripts/subscript_badly_poison.s:9 (Leaf Guard blocks status in sun)
    ("ABILITY_LEAF_GUARD", "res/battle/scripts/subscripts/subscript_badly_poison.s:9"),
])
def test_script_only_abilities_count(table, name, ref):
    """These are implemented ONLY in battle scripts: a C-only scan would call them no-effect."""
    refs = _refs(table, name)
    assert table["abilities"][name]["has_battle_effect"] is True
    assert ref in refs
    assert all(r.startswith("res/battle/scripts/") for r in refs), refs


def test_script_only_set_is_nonempty(table):
    only_scripts = [n for n, a in table["abilities"].items()
                    if a["battle_refs"] and all(r.startswith("res/battle/scripts/") for r in a["battle_refs"])]
    # Found at T060: Suction Cups, Inner Focus, Liquid Ooze, Rock Head, Steadfast, Anger Point, Poison Heal,
    # Leaf Guard, Reckless (9).
    assert len(only_scripts) >= 9, only_scripts


# --- negative controls: outside-battle-only abilities -------------------------------------------------

def test_illuminate_overworld_only(table):
    a = table["abilities"]["ABILITY_ILLUMINATE"]
    assert a["has_battle_effect"] is False and a["battle_refs"] == []
    # src/overlay006/wild_encounters.c:1336  `... firstMonAbility == ABILITY_ILLUMINATE) {` (encounter rate)
    assert "src/overlay006/wild_encounters.c:1336" in a["other_refs"]


def test_stench_only_ai_and_overworld(table):
    """Control for the trainer-AI exclusion: Stench is referenced by the AI script but not by the engine."""
    a = table["abilities"]["ABILITY_STENCH"]
    assert a["has_battle_effect"] is False
    # src/battle/trainer_ai/script.s:1372  `IfLoadedEqualTo ABILITY_STENCH, ScoreMinus10`
    assert "src/battle/trainer_ai/script.s:1372" in a["other_refs"]
    # src/overlay006/wild_encounters.c:1346  `... || firstMonAbility == ABILITY_STENCH) {`
    assert "src/overlay006/wild_encounters.c:1346" in a["other_refs"]


def test_counts_and_no_effect_set(table):
    assert table["counts"] == {"abilities": 123, "has_battle_effect": 121, "no_battle_effect": 2}
    assert {n for n, a in table["abilities"].items() if not a["has_battle_effect"]} == {
        "ABILITY_STENCH", "ABILITY_ILLUMINATE"}
    assert "ABILITY_NONE" not in table["abilities"]


def test_conservative_engine_refs_with_no_gauntlet_effect(table):
    """Pickup / Honey Gather (end-of-battle item, src/battle/battle_script.c:7797 / :7825 in
    BtlCmd_GenerateEndOfBattleItem) and Run Away (fleeing, battle_lib.c:3194) are engine refs, so they
    count as battle effects (conservative: they get tested)."""
    assert "src/battle/battle_script.c:7797" in _refs(table, "ABILITY_PICKUP")
    assert table["abilities"]["ABILITY_PICKUP"]["battle_contexts"] == ["BtlCmd_GenerateEndOfBattleItem"]
    assert "src/battle/battle_script.c:7825" in _refs(table, "ABILITY_HONEY_GATHER")
    assert "src/battle/battle_lib.c:3194" in _refs(table, "ABILITY_RUN_AWAY")


# --- the scanner itself ------------------------------------------------------------------------------

def test_raw_number_scan_empty_and_patterns_can_hit(table):
    assert table["raw_number_scan"]["hits"] == []
    # positive controls: the same patterns DO hit raw-number forms
    assert AB._RAW_SCRIPT.search("    CheckAbility CHECK_HAVE, BTLSCR_ATTACKER, 69, _043")
    assert AB._RAW_SCRIPT_MONDATA.search("CompareMonDataToValue OPCODE_EQU, BTLSCR_DEFENDER, BATTLEMON_ABILITY, 26, _1")
    assert AB._RAW_C.search("if (battleCtx->battleMons[battler].ability == 26) {")
    assert AB._RAW_C.search("if (ability != 0x1A)")
    assert not AB._RAW_C.search("if (ability == ABILITY_LEVITATE)")


def test_comments_do_not_count():
    lines = AB.strip_comments("x = 1; // ABILITY_STENCH\n/* ABILITY_ILLUMINATE\n ABILITY_PICKUP */ y = ABILITY_RUN_AWAY;", "c")
    assert len(lines) == 3
    joined = "\n".join(lines)
    assert "ABILITY_STENCH" not in joined and "ABILITY_ILLUMINATE" not in joined and "ABILITY_PICKUP" not in joined
    assert "ABILITY_RUN_AWAY" in lines[2]


def test_generated_file_matches(table):
    on_disk = json.loads((DEFAULT_OUT / "abilities_battle.json").read_text())
    assert on_disk == json.loads(json.dumps(table))


# --- choose_ability branches that spend no runs ------------------------------------------------------

def _build(species, ability, source="wild_slot:X"):
    return {"species": species, "source": source, "start_level": 50, "moves": [], "ability": ability,
            "ability_reason": "tie_default", "held_item": None, "nature": "Hardy",
            "ivs": {k: 15 for k in ("hp", "atk", "def", "spa", "spd", "spe")},
            "evs": {k: 85 for k in ("hp", "atk", "def", "spa", "spd", "spe")}}


def test_single_ability_no_runs():
    # res/pokemon/staraptor/data.json:30 "abilities": ["ABILITY_INTIMIDATE", "ABILITY_NONE"]
    c = AB.choose_ability(None, [_build("staraptor", "ABILITY_INTIMIDATE")], 0, seed="t")
    assert c == ("ABILITY_INTIMIDATE", "single_ability", None)


@pytest.mark.parametrize("species, want", [
    ("skuntank", "ABILITY_AFTERMATH"),     # res/pokemon/skuntank/data.json:30 [STENCH, AFTERMATH]
    ("lanturn", "ABILITY_VOLT_ABSORB"),    # res/pokemon/lanturn/data.json:30 [VOLT_ABSORB, ILLUMINATE]
    ("starmie", "ABILITY_NATURAL_CURE"),   # res/pokemon/starmie/data.json:30 [ILLUMINATE, NATURAL_CURE]
])
def test_other_no_battle_effect_no_runs(species, want):
    c = AB.choose_ability(None, [_build(species, "")], 0, seed="t")
    assert c.ability == want and c.reason == "other_no_battle_effect"
    assert sum(c.stats["battle_effect"].values()) == 1


def test_both_effect_needs_pool():
    with pytest.raises(ValueError, match="WorkerPool"):
        AB.choose_ability(None, [_build("luxray", "ABILITY_RIVALRY")], 0, seed="t")


class _StubPool:
    """Clears every run when the screened member has `winner`; the other ability clears none."""

    hello = {"policies": ["greedy-v1"], "opponent_policies": ["decomp-ai"], "decomp_commit": "x", "showdown_commit": "y"}

    def __init__(self, slot, winner):
        self.slot, self.winner, self.requests = slot, winner, []

    def map(self, reqs):
        self.requests += reqs
        return [{"ok": True, "player_policy": r["player_policy"], "opponent_policy": r["opponent_policy"],
                 "cleared": r["team"][self.slot]["ability"] == self.winner} for r in reqs]


@pytest.mark.parametrize("winner", ["ABILITY_RIVALRY", "ABILITY_INTIMIDATE"])
def test_tested_better_branch_with_stub_pool(winner):
    p = _StubPool(0, winner)
    c = AB.choose_ability(p, [_build("luxray", "ABILITY_RIVALRY")], 0, seed="s", budget="quick")
    assert (c.ability, c.reason) == (winner, "tested_better")
    assert c.stats["n_paired"] == 100 and len(p.requests) == 200  # quick preset: 100 per ability
    seeds = [r["seed"] for r in p.requests]
    assert seeds[:100] == seeds[100:]  # paired
    assert all(r["player_policy"] == "greedy-v1" and r["opponent_policy"] == "decomp-ai" for r in p.requests)
