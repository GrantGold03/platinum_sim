import re

import pytest

from platsim.decomp.constants import load_enum, load_names, mask_names


def test_species_line_index():
    # pokeplatinum/generated/species.txt: line 1 SPECIES_NONE, line 446 SPECIES_GARCHOMP,
    # lines 495/496 SPECIES_EGG / SPECIES_BAD_EGG.
    sp = load_enum("species")
    assert sp["SPECIES_NONE"] == 0
    assert sp["SPECIES_BULBASAUR"] == 1
    assert sp["SPECIES_GARCHOMP"] == 445
    assert sp["SPECIES_EGG"] == 494
    assert sp["SPECIES_BAD_EGG"] == 495
    assert str(sp.refs["SPECIES_GARCHOMP"]) == "generated/species.txt:446"


def test_other_enums():
    assert load_enum("abilities")["ABILITY_NONE"] == 0
    assert load_enum("abilities")["ABILITY_STENCH"] == 1
    assert load_enum("pokemon_types")["TYPE_MYSTERY"] == 9


def test_explicit_literal_values():
    # generated/gender_ratios.txt line 2: GENDER_RATIO_FEMALE_12_5 = 31
    assert load_enum("gender_ratios")["GENDER_RATIO_FEMALE_12_5"] == 31


def test_aliases_follow_c_enum_semantics():
    # Positive control: flag names embed their own hex value, e.g. FLAG_UNK_0x0041 after
    # `MAP_LOCAL_FLAGS_END = FLAG_MAP_LOCAL_0x40` must be 0x41.
    flags = load_enum("vars_flags")
    pattern = re.compile(r"^FLAG_UNK_0x([0-9A-Fa-f]{4})$")
    checked = 0
    for name, value in flags.values.items():
        m = pattern.match(name)
        if m:
            assert value == int(m.group(1), 16), name
            checked += 1
    assert checked > 50  # the check actually ran over many names
    assert flags["VARS_START"] == 16384
    assert flags["VAR_0x8000"] == 0x8000


def test_masks_are_refused():
    assert "ai_flags" in mask_names()
    with pytest.raises(ValueError, match="mask"):
        load_enum("ai_flags")
    names = [n for n, _ in load_names("ai_flags")]
    assert names[:2] == ["AI_FLAG_NONE", "AI_FLAG_BASIC"]
