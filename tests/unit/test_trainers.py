"""T017 League opponents: parties copied from pokeplatinum/res/trainers/data/*.json, and the
TrainerData_BuildParty port (src/trainer_data.c:176-316).

research.md R3 gives trainer IDs, AI flags and bag items but lists no personalities or natures,
so the personality cross-check is done here with an independent LCRNG jump-ahead
(closed-form affine composition) instead of the step-by-step port.
"""

import pytest

from platsim.decomp.trainers import LCRNG, load_league, trainer_personality

AI3 = ["AI_FLAG_BASIC", "AI_FLAG_EVAL_ATTACK", "AI_FLAG_EXPERT"]
FR = "ITEM_FULL_RESTORE"

# (species, level, held item, moves) copied from each file's "party" array.
EXPECTED = {
    # res/trainers/data/elite_four_aaron.json:4 items, :8 ai_flags, :14 party
    "TRAINER_ELITE_FOUR_AARON": (261, AI3, [FR, FR], [
        ("SPECIES_YANMEGA", 49, "ITEM_NONE", ["MOVE_AIR_SLASH", "MOVE_BUG_BUZZ", "MOVE_U_TURN", "MOVE_DOUBLE_TEAM"]),
        ("SPECIES_SCIZOR", 49, "ITEM_NONE", ["MOVE_IRON_HEAD", "MOVE_X_SCISSOR", "MOVE_NIGHT_SLASH", "MOVE_QUICK_ATTACK"]),
        ("SPECIES_VESPIQUEN", 50, "ITEM_NONE", ["MOVE_ATTACK_ORDER", "MOVE_DEFEND_ORDER", "MOVE_HEAL_ORDER", "MOVE_POWER_GEM"]),
        ("SPECIES_HERACROSS", 51, "ITEM_NONE", ["MOVE_MEGAHORN", "MOVE_CLOSE_COMBAT", "MOVE_NIGHT_SLASH", "MOVE_STONE_EDGE"]),
        ("SPECIES_DRAPION", 53, "ITEM_SITRUS_BERRY", ["MOVE_X_SCISSOR", "MOVE_CROSS_POISON", "MOVE_ICE_FANG", "MOVE_AERIAL_ACE"]),
    ]),
    # res/trainers/data/elite_four_bertha.json:4 items, :8 ai_flags
    "TRAINER_ELITE_FOUR_BERTHA": (262, AI3, [FR, FR], [
        ("SPECIES_WHISCASH", 50, "ITEM_NONE", ["MOVE_EARTH_POWER", "MOVE_AQUA_TAIL", "MOVE_ZEN_HEADBUTT", "MOVE_SANDSTORM"]),
        ("SPECIES_GLISCOR", 53, "ITEM_NONE", ["MOVE_EARTHQUAKE", "MOVE_ICE_FANG", "MOVE_FIRE_FANG", "MOVE_THUNDER_FANG"]),
        ("SPECIES_HIPPOWDON", 52, "ITEM_NONE", ["MOVE_EARTHQUAKE", "MOVE_STONE_EDGE", "MOVE_CRUNCH", "MOVE_YAWN"]),
        ("SPECIES_GOLEM", 52, "ITEM_NONE", ["MOVE_EARTHQUAKE", "MOVE_FIRE_PUNCH", "MOVE_THUNDER_PUNCH", "MOVE_SANDSTORM"]),
        ("SPECIES_RHYPERIOR", 55, "ITEM_SITRUS_BERRY", ["MOVE_EARTHQUAKE", "MOVE_ROCK_WRECKER", "MOVE_MEGAHORN", "MOVE_AVALANCHE"]),
    ]),
    # res/trainers/data/elite_four_flint.json:4 items, :8 ai_flags
    "TRAINER_ELITE_FOUR_FLINT": (263, AI3, [FR, FR], [
        ("SPECIES_HOUNDOOM", 52, "ITEM_NONE", ["MOVE_FLAMETHROWER", "MOVE_SLUDGE_BOMB", "MOVE_DARK_PULSE", "MOVE_SUNNY_DAY"]),
        ("SPECIES_FLAREON", 55, "ITEM_NONE", ["MOVE_OVERHEAT", "MOVE_GIGA_IMPACT", "MOVE_QUICK_ATTACK", "MOVE_WILL_O_WISP"]),
        ("SPECIES_RAPIDASH", 53, "ITEM_NONE", ["MOVE_FLARE_BLITZ", "MOVE_SOLAR_BEAM", "MOVE_BOUNCE", "MOVE_SUNNY_DAY"]),
        ("SPECIES_INFERNAPE", 55, "ITEM_NONE", ["MOVE_FLARE_BLITZ", "MOVE_THUNDER_PUNCH", "MOVE_MACH_PUNCH", "MOVE_EARTHQUAKE"]),
        ("SPECIES_MAGMORTAR", 57, "ITEM_SITRUS_BERRY", ["MOVE_FLAMETHROWER", "MOVE_THUNDERBOLT", "MOVE_SOLAR_BEAM", "MOVE_HYPER_BEAM"]),
    ]),
    # res/trainers/data/elite_four_lucian.json:4 items, :8 ai_flags (+ AI_FLAG_SETUP_FIRST_TURN)
    "TRAINER_ELITE_FOUR_LUCIAN": (264, AI3 + ["AI_FLAG_SETUP_FIRST_TURN"], [FR, FR], [
        ("SPECIES_MR_MIME", 53, "ITEM_NONE", ["MOVE_PSYCHIC", "MOVE_THUNDERBOLT", "MOVE_REFLECT", "MOVE_LIGHT_SCREEN"]),
        ("SPECIES_ESPEON", 55, "ITEM_NONE", ["MOVE_PSYCHIC", "MOVE_SHADOW_BALL", "MOVE_QUICK_ATTACK", "MOVE_SIGNAL_BEAM"]),
        ("SPECIES_BRONZONG", 54, "ITEM_NONE", ["MOVE_PSYCHIC", "MOVE_GYRO_BALL", "MOVE_EARTHQUAKE", "MOVE_CALM_MIND"]),
        ("SPECIES_ALAKAZAM", 56, "ITEM_NONE", ["MOVE_PSYCHIC", "MOVE_ENERGY_BALL", "MOVE_FOCUS_BLAST", "MOVE_RECOVER"]),
        ("SPECIES_GALLADE", 59, "ITEM_SITRUS_BERRY", ["MOVE_DRAIN_PUNCH", "MOVE_PSYCHO_CUT", "MOVE_LEAF_BLADE", "MOVE_STONE_EDGE"]),
    ]),
    # res/trainers/data/champion_cynthia.json:4 items (4x Full Restore), :10 ai_flags
    "TRAINER_CHAMPION_CYNTHIA": (267, AI3, [FR, FR, FR, FR], [
        ("SPECIES_SPIRITOMB", 58, "ITEM_NONE", ["MOVE_DARK_PULSE", "MOVE_PSYCHIC", "MOVE_SILVER_WIND", "MOVE_SHADOW_BALL"]),
        ("SPECIES_ROSERADE", 58, "ITEM_NONE", ["MOVE_ENERGY_BALL", "MOVE_SLUDGE_BOMB", "MOVE_TOXIC", "MOVE_EXTRASENSORY"]),
        ("SPECIES_TOGEKISS", 60, "ITEM_NONE", ["MOVE_AIR_SLASH", "MOVE_AURA_SPHERE", "MOVE_WATER_PULSE", "MOVE_SHOCK_WAVE"]),
        ("SPECIES_LUCARIO", 60, "ITEM_NONE", ["MOVE_AURA_SPHERE", "MOVE_EXTREME_SPEED", "MOVE_SHADOW_BALL", "MOVE_STONE_EDGE"]),
        ("SPECIES_MILOTIC", 58, "ITEM_NONE", ["MOVE_SURF", "MOVE_ICE_BEAM", "MOVE_MIRROR_COAT", "MOVE_DRAGON_PULSE"]),
        ("SPECIES_GARCHOMP", 62, "ITEM_SITRUS_BERRY", ["MOVE_DRAGON_RUSH", "MOVE_EARTHQUAKE", "MOVE_FLAMETHROWER", "MOVE_GIGA_IMPACT"]),
    ]),
}


def test_order_and_parties():
    league = load_league()
    assert [t.const for t in league] == list(EXPECTED)
    for t in league:
        tid, ai, bag, party = EXPECTED[t.const]
        assert t.trainer_id == tid  # research.md R3 IDs = generated/trainers.txt line - 1
        assert t.ai_flags == ai
        assert t.bag_items == bag
        assert not t.double_battle
        assert [(m.species, m.level, m.held_item, m.moves) for m in t.party] == party


def test_ivs_and_ability_slot():
    for t in load_league():
        for m in t.party:
            # iv_scale 250 in every party entry; 250*31/255 = 7750/255 = 30 (integer division)
            assert m.iv_scale == 250
            assert m.iv == 30
            # genderMod 120/136 is even and occupies the low byte -> personality & 1 == 0 -> slot 1
            assert m.personality & 0xFF in (120, 136)
            assert m.ability_slot == 1


def test_class_ids_and_gender_mod():
    # generated/trainer_classes.txt:66-70 -> class ids 65..69 (header.trainerType)
    # include/data/trainer_class_genders.h:71-75: Bertha and Cynthia female (120), others male (136)
    got = {t.const: (t.class_id, t.party[0].personality & 0xFF) for t in load_league()}
    assert got == {
        "TRAINER_ELITE_FOUR_AARON": (65, 136),
        "TRAINER_ELITE_FOUR_BERTHA": (66, 120),
        "TRAINER_ELITE_FOUR_FLINT": (67, 136),
        "TRAINER_ELITE_FOUR_LUCIAN": (68, 136),
        "TRAINER_CHAMPION_CYNTHIA": (69, 120),
    }


def test_lcrng_hand_worked():
    # include/math_util.h:8-9: multiplier 1103515245, increment 24691; src/math_util.c:80-84.
    # seed 1000: 1000*1103515245 + 24691 = 1103515269691; mod 2^32 = 4003641915;
    # >> 16 = 61090. Personality with class id 1, male: (61090 << 8) + 136 = 15639176;
    # 15639176 % 25 = 1 (NATURE_LONELY).
    assert LCRNG(1000).next() == 61090
    assert trainer_personality(0, 0, 1000, 0, 1, False) == 15639176
    # class id 0: no LCRNG call, rnd is the seed itself: (1000 << 8) + 120 = 256120
    assert trainer_personality(0, 0, 1000, 0, 0, True) == 256120


def _jump(seed: int, n: int) -> int:
    """Independent cross-check: state after n LCRNG steps via affine-map squaring."""
    mul, inc = 1103515245, 24691  # include/math_util.h:8-9
    a, c = 1, 0  # accumulated map x -> a*x + c
    pa, pc = mul, inc  # map for 2^k steps
    while n:
        if n & 1:
            a, c = (pa * a) % 2**32, (pa * c + pc) % 2**32
        pa, pc = (pa * pa) % 2**32, (pa * pc + pc) % 2**32
        n >>= 1
    return (a * seed + c) % 2**32


def test_personality_cross_check():
    from platsim.decomp.constants import load_enum

    sp = load_enum("species")
    for t in load_league():
        female = t.class_id in (66, 69)
        for m in t.party:
            seed = m.iv_scale + m.level + sp[m.species] + t.trainer_id
            expect = ((_jump(seed, t.class_id) >> 16) << 8) + (120 if female else 136)
            assert m.personality == expect, (t.const, m.species)
            assert m.nature == load_enum("natures").name_of(expect % 25, "NATURE_")


@pytest.mark.parametrize("const,species,personality,nature", [
    # Values produced by this port; garchomp seed = 250 + 62 + 445 + 267 = 1024, 69 LCRNG steps.
    ("TRAINER_CHAMPION_CYNTHIA", "SPECIES_GARCHOMP", 12572024, "NATURE_QUIRKY"),
    ("TRAINER_ELITE_FOUR_AARON", "SPECIES_YANMEGA", 14014344, "NATURE_RASH"),
])
def test_known_personalities(const, species, personality, nature):
    (t,) = [t for t in load_league() if t.const == const]
    (m,) = [m for m in t.party if m.species == species]
    assert (m.personality, m.nature) == (personality, nature)
