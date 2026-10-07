"""T014 item extraction tests. Values copied from pokeplatinum/res/items/data/*.json."""

from platsim.decomp.items import load_items, tm_moves


def test_tm_hm_moves():
    tm = tm_moves()
    assert tm["TM01"] == "MOVE_FOCUS_PUNCH"  # res/items/data/tm01.json:30
    assert tm["TM26"] == "MOVE_EARTHQUAKE"  # res/items/data/tm26.json:30
    assert tm["TM92"] == "MOVE_TRICK_ROOM"  # res/items/data/tm92.json:30
    assert tm["HM08"] == "MOVE_ROCK_CLIMB"  # res/items/data/hm08.json:30
    # generated/items.txt:329-428: ITEM_TM01..ITEM_TM92 then ITEM_HM01..ITEM_HM08 = 100 items
    assert len(tm) == 100


def test_hold_effects():
    items = load_items()
    # res/items/data/leftovers.json:17
    assert items["ITEM_LEFTOVERS"].hold_effect == "HOLD_EFFECT_HP_RESTORE_GRADUAL"
    # res/items/data/lucky_egg.json:17
    assert items["ITEM_LUCKY_EGG"].hold_effect == "HOLD_EFFECT_EXP_UP"


def test_unused_items_skipped():
    items = load_items()
    # itemproc.c has_data skips ITEM_UNUSED_*; generated/items.txt has 469 lines, 22 ITEM_UNUSED_*
    # names and the MAX_ITEMS sentinel -> 446 items with data (= files in res/items/data).
    assert not any(k.startswith("ITEM_UNUSED_") for k in items)
    assert len(items) == 446
    # Positive control: the enum does contain unused names, so the filter has something to skip.
    from platsim.decomp.constants import load_enum

    assert sum(k.startswith("ITEM_UNUSED_") for k in load_enum("items").values) == 22
