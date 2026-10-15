"""007 T042/T045: held-item offering with moves (spec FR-006, FR-009, FR-011, FR-013)."""

import pytest

from platsim.decomp.items import load_items
from platsim.legality.models import LegalityOptions
from platsim.optimizer import candidates as C
from platsim.optimizer import item_classes as IC
from platsim.optimizer import move_classes as MC

POL = MC.ALT_POLICY
B4 = ("SPECIES_ROSERADE", "SPECIES_BLISSEY", "SPECIES_GLISCOR", "SPECIES_MILOTIC", "SPECIES_BRONZONG", "SPECIES_LUCARIO")
HE = {i.key: i.hold_effect for i in load_items().values()}


def items(ledger, sp, moves, team=B4):
    return IC.items_for(sp, moves, team, ledger, POL)


def test_light_clay_only_with_screens(ledger):
    assert "light_clay" in items(ledger, "SPECIES_BRONZONG", ("MOVE_REFLECT", "MOVE_GYRO_BALL", "MOVE_EARTHQUAKE", "MOVE_HYPNOSIS"))
    assert "light_clay" not in items(ledger, "SPECIES_BRONZONG", ("MOVE_PSYCHIC", "MOVE_GYRO_BALL", "MOVE_EARTHQUAKE", "MOVE_HYPNOSIS"))


def test_damp_rock_only_with_rain_dance_and_chesto_only_with_rest(ledger):
    assert "damp_rock" in items(ledger, "SPECIES_MILOTIC", ("MOVE_RAIN_DANCE", "MOVE_SURF", "MOVE_ICE_BEAM", "MOVE_RECOVER"))
    assert "damp_rock" not in items(ledger, "SPECIES_MILOTIC", ("MOVE_TOXIC", "MOVE_SURF", "MOVE_ICE_BEAM", "MOVE_RECOVER"))
    assert "chesto_berry" in items(ledger, "SPECIES_MILOTIC", ("MOVE_REST", "MOVE_SURF", "MOVE_ICE_BEAM", "MOVE_TOXIC"))
    assert "chesto_berry" not in items(ledger, "SPECIES_MILOTIC", ("MOVE_RECOVER", "MOVE_SURF", "MOVE_ICE_BEAM", "MOVE_TOXIC"))


def test_black_sludge_only_for_poison_types(ledger):
    assert "black_sludge" in items(ledger, "SPECIES_ROSERADE", ("MOVE_SLUDGE_BOMB", "MOVE_ENERGY_BALL", "MOVE_TOXIC", "MOVE_LEECH_SEED"))
    assert "black_sludge" not in items(ledger, "SPECIES_MILOTIC", ("MOVE_RECOVER", "MOVE_SURF", "MOVE_ICE_BEAM", "MOVE_TOXIC"))


def test_choice_specs_only_with_all_attack_sets(ledger):
    b1 = ("SPECIES_INFERNAPE", "SPECIES_STARAPTOR", "SPECIES_LUXRAY", "SPECIES_GARCHOMP", "SPECIES_GYARADOS", "SPECIES_GARDEVOIR")
    att = ("MOVE_PSYCHIC", "MOVE_SHADOW_BALL", "MOVE_THUNDERBOLT", "MOVE_ENERGY_BALL")
    assert "choice_specs" in items(ledger, "SPECIES_GARDEVOIR", att, b1)
    assert "choice_specs" not in items(ledger, "SPECIES_GARDEVOIR", att[:3] + ("MOVE_CALM_MIND",), b1)


def test_no_post_champion_item_is_offered(ledger):
    for sp in B4:
        for key in IC.offerable_items(sp, B4, ledger):
            it = next(i for i in load_items().values() if i.key == key)
            assert ledger.item_copies(it.const) != 0 or key == "leftovers", key
    assert "choice_band" not in IC.offerable_items("SPECIES_LUCARIO", B4, ledger)


def test_type_boost_tie_rule(ledger):
    # Splash Plate (unlimited) beats Mystic Water (1 copy) by copies; with both unlimited (post-game items),
    # the classic item wins over the Plate (FR-011, research R2.6).
    att = ("MOVE_SURF", "MOVE_ICE_BEAM", "MOVE_RECOVER", "MOVE_TOXIC")
    got = [k for k in items(ledger, "SPECIES_MILOTIC", att) if HE[k] in ("HOLD_EFFECT_STRENGTHEN_WATER", "HOLD_EFFECT_ARCEUS_WATER")]
    assert got == ["splash_plate"], got
    post = ledger.with_options(LegalityOptions(allow_post_game_items=True))
    got2 = [k for k in IC.items_for("SPECIES_MILOTIC", att, B4, post, POL)
            if HE[k] in ("HOLD_EFFECT_STRENGTHEN_WATER", "HOLD_EFFECT_ARCEUS_WATER")]
    assert got2 == ["mystic_water"], got2


def test_offered_items_are_modelled_and_skipped_ones_listed(ledger):
    for c in B4:
        v = C.variants(c, ledger)[0]
        mc = C.member_candidates(c, v, 55, ledger, team=B4)
        offered = IC.items_for(c, mc.movesets[0], B4, ledger, POL)
        assert all(MC.item_modelled(POL, HE[k]) for k in offered)
        for key in IC.offerable_items(c, B4, ledger):
            if not MC.item_modelled(POL, HE[key]):
                assert mc.excluded_items[key].startswith("not offered: not modelled"), key
    print("skipped (B4 Roserade):", sorted(C.member_candidates("SPECIES_ROSERADE", C.variants("SPECIES_ROSERADE", ledger)[0], 55,
                                                                ledger, team=B4).excluded_items))
