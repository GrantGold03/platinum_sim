"""007 T008: move classification from decomp effect scripts (spec FR-001-FR-004, research R1)."""

import re

import pytest

from platsim.decomp.moves import load_moves
from platsim.optimizer import move_classes as MC
from platsim.pins import REPO_ROOT


def test_every_move_classifies():
    cats = {}
    for const in load_moves():
        cats[const] = MC.move_class(const).category  # raises on an unknown damaging script
    assert len(cats) > 450
    assert {c for c in cats.values()} >= set(MC.STATUS_CATEGORIES) | {"attack", "variable_attack", "foe_drop", "fixed_damage"}


def test_rule_constants_exist_in_decomp():
    effects = set(MC.effect_index())
    for e in MC.RULES:
        assert e in effects, e
    for e in MC.EXCLUDED_ATTACK_EFFECTS:
        assert e in effects, e


@pytest.mark.parametrize("move,cat", [
    ("MOVE_SCREECH", "foe_drop"), ("MOVE_GROWL", "foe_drop"), ("MOVE_SAND_ATTACK", "foe_drop"),
    ("MOVE_CAPTIVATE", "foe_drop"), ("MOVE_TICKLE", "foe_drop"),
    ("MOVE_SEISMIC_TOSS", "fixed_damage"), ("MOVE_NIGHT_SHADE", "fixed_damage"), ("MOVE_SONIC_BOOM", "fixed_damage"),
    ("MOVE_DRAGON_RAGE", "fixed_damage"), ("MOVE_SUPER_FANG", "fixed_damage"), ("MOVE_ENDEAVOR", "fixed_damage"),
    ("MOVE_PSYWAVE", "fixed_damage"),
    ("MOVE_MAGNITUDE", "variable_attack"),  # effect is named BATTLE_EFFECT_PSYWAVE: a name rule would get it wrong
    ("MOVE_RETURN", "variable_attack"), ("MOVE_HIDDEN_POWER", "variable_attack"), ("MOVE_LOW_KICK", "variable_attack"),
    ("MOVE_GYRO_BALL", "variable_attack"),
    ("MOVE_FRUSTRATION", "conditional_attack"), ("MOVE_FLAIL", "conditional_attack"), ("MOVE_FLING", "conditional_attack"),
    ("MOVE_FISSURE", "conditional_attack"), ("MOVE_EXPLOSION", "conditional_attack"),
    ("MOVE_SWORDS_DANCE", "self_boost"), ("MOVE_DRAGON_DANCE", "self_boost"), ("MOVE_CALM_MIND", "self_boost"),
    ("MOVE_BELLY_DRUM", "self_boost"), ("MOVE_CURSE", "self_boost"), ("MOVE_DOUBLE_TEAM", "self_boost"),
    ("MOVE_THUNDER_WAVE", "inflict_status"), ("MOVE_TOXIC", "inflict_status"), ("MOVE_HYPNOSIS", "inflict_status"),
    ("MOVE_WILL_O_WISP", "inflict_status"), ("MOVE_YAWN", "inflict_status"),
    ("MOVE_LEECH_SEED", "leech_seed"),
    ("MOVE_RECOVER", "recovery"), ("MOVE_REST", "recovery"), ("MOVE_ROOST", "recovery"), ("MOVE_SYNTHESIS", "recovery"),
    ("MOVE_WISH", "recovery"), ("MOVE_AQUA_RING", "recovery"), ("MOVE_INGRAIN", "recovery"),
    ("MOVE_PROTECT", "protection"), ("MOVE_DETECT", "protection"), ("MOVE_ENDURE", "protection"), ("MOVE_SUBSTITUTE", "protection"),
    ("MOVE_REFLECT", "screen"), ("MOVE_LIGHT_SCREEN", "screen"), ("MOVE_SAFEGUARD", "screen"),
    ("MOVE_RAIN_DANCE", "weather"), ("MOVE_SUNNY_DAY", "weather"), ("MOVE_SANDSTORM", "weather"), ("MOVE_HAIL", "weather"),
    ("MOVE_HELPING_HAND", "no_effect_singles"), ("MOVE_TELEPORT", "no_effect_singles"), ("MOVE_SPLASH", "no_effect_singles"),
    ("MOVE_FOLLOW_ME", "no_effect_singles"),
    ("MOVE_DEFOG", "other"), ("MOVE_TAUNT", "other"), ("MOVE_SWAGGER", "other"), ("MOVE_STEALTH_ROCK", "other"),
    ("MOVE_MEMENTO", "sacrifice"), ("MOVE_COUNTER", "reactive"), ("MOVE_SPIT_UP", "reactive"),
    ("MOVE_EARTHQUAKE", "attack"), ("MOVE_BEAT_UP", "attack"),
])
def test_category_positive_controls(move, cat):
    assert MC.move_class(move).category == cat


def test_fixed_damage_is_exactly_six_effects():
    effs = {MC.move_class(m).effect for m in load_moves() if MC.move_class(m).category == "fixed_damage"}
    assert effs == {"BATTLE_EFFECT_LEVEL_DAMAGE_FLAT", "BATTLE_EFFECT_20_DAMAGE_FLAT", "BATTLE_EFFECT_40_DAMAGE_FLAT",
                    "BATTLE_EFFECT_HALVE_HP", "BATTLE_EFFECT_SET_HP_EQUAL_TO_USER",
                    "BATTLE_EFFECT_RANDOM_DAMAGE_1_TO_150_LEVEL"}


def test_foe_drops_match_expectimax2_plus_captivate():
    text = (REPO_ROOT / "sim" / "policy" / "expectimax2.mjs").read_text()
    body = text[text.index("const FOE_DROPS = {"):]
    body = body[:body.index("};")]
    player = {f"BATTLE_EFFECT_{n}" for n in re.findall(r"(\w+): \{", body)}
    derived = {MC.move_class(m).effect for m in load_moves() if MC.move_class(m).category == "foe_drop"}
    assert derived == player | {"BATTLE_EFFECT_SP_ATK_DOWN_2_OPPOSITE_GENDER"}


def test_foe_drop_reason_cites_stage_reset():
    assert "battle_lib.c:97-100" in MC.move_class("MOVE_SCREECH").reason
