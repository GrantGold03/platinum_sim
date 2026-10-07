"""T018: field-script parser. Every expected value cites the decomp line it was copied from."""

import pytest

from platsim.decomp.scripts import (
    all_script_stems,
    expand,
    load_script_file,
    resolve_script_id,
    script_ranges,
    successors,
)


def _cmd_at(stem: str, line: int):
    sf = load_script_file(stem)
    hits = [c for c in sf.commands if c.ref.line == line]
    assert len(hits) == 1, (stem, line, hits)
    return sf, hits[0]


def test_every_script_file_parses_and_resolves_labels():
    stems = all_script_stems()
    # res/field/scripts/scripts.order lists 1124 script files; positive control that the glob saw them.
    assert len(stems) >= 1124
    n_commands = 0
    for stem in stems:
        sf = load_script_file(stem)
        n_commands += len(sf.commands)
        for i in range(len(sf.commands)):
            successors(sf, i)  # raises KeyError on an unknown label
    assert n_commands > 40000


def test_script_entry_index_is_order():
    # res/field/scripts/scripts_visible_items.s:5-8: 4th ScriptEntry is VisibleItems_OreburghGateB1F_TM01
    sf = load_script_file("scripts_visible_items")
    assert sf.entry_label(3) == "VisibleItems_OreburghGateB1F_TM01"
    assert sf.entries[3][1].line == 8
    # res/field/scripts/scripts_snowpoint_city.s:17: 12th entry
    assert load_script_file("scripts_snowpoint_city").entry_label(11) == "SnowpointCity_SailorSSSpiral"


def test_visible_item_tm01():
    # res/field/events/events_oreburgh_gate_b1f.json:177 uses script 7003;
    # include/script_manager.h:95 SCRIPT_ID_OFFSET_VISIBLE_ITEMS 7000 -> entry 3.
    stem, entry = resolve_script_id(7003, "scripts_oreburgh_gate_b1f")
    assert (stem, entry) == ("scripts_visible_items", 3)
    sf = load_script_file(stem)
    first = sf.commands[sf.command_for_entry(entry)]
    cmds = sf.commands[first.index : first.index + 3]
    # res/field/scripts/scripts_visible_items.s:354-356
    assert [(c.name, c.args, c.ref.line) for c in cmds] == [
        ("SetVar", ("VAR_0x8008", "ITEM_TM01"), 354),
        ("SetVar", ("VAR_0x8009", "1"), 355),
        ("GoTo", ("VisibleItems_TryGiveItem",), 356),
    ]
    goto = successors(sf, cmds[2].index)
    assert len(goto) == 1 and goto[0].kind == "goto"
    assert goto[0].index == sf.labels["VisibleItems_TryGiveItem"]


def test_route201_starter_given_at_level_5():
    # res/field/scripts/scripts_route_201.s:286  GivePokemon VAR_0x8000, 5, ITEM_NONE, VAR_RESULT
    _, c = _cmd_at("scripts_route_201", 286)
    assert c.name == "GivePokemon"
    assert c.args == ("VAR_0x8000", "5", "ITEM_NONE", "VAR_RESULT")
    assert c.ops == ("SCRCMD_GIVEPOKEMON",)


def test_script_id_ranges():
    # include/script_manager.h:90,95,96 and src/script_manager.c:56,57,62,248-251
    assert resolve_script_id(2000, None) == ("scripts_common", 0)
    assert resolve_script_id(7000, None) == ("scripts_visible_items", 0)
    assert resolve_script_id(8000, None) == ("scripts_hidden_items", 0)
    assert resolve_script_id(1, "scripts_snowpoint_city") == ("scripts_snowpoint_city", 0)
    assert resolve_script_id(1999, "scripts_snowpoint_city") == ("scripts_snowpoint_city", 1998)
    assert resolve_script_id(0, None) == ("scripts_unk_0402", 0)
    common = next(r for r in script_ranges() if r.file == "scripts_common")
    assert (common.threshold, str(common.ref)) == (2000, "src/script_manager.c:62")
    with pytest.raises(ValueError):
        resolve_script_id(5, None)


def test_common_alias_resolves_to_scripts_common():
    # asm/macros/scrcmd.inc:5318-5320 Common_GiveItemQuantity = CallCommonScript 0x7FC;
    # res/field/scripts/scripts_common.s:73 ScriptEntry CommonScript_AddItemQuantity @ 0x7FC.
    prims = expand("Common_GiveItemQuantity", ())
    assert [p.op for p in prims] == ["SCRCMD_CALLCOMMONSCRIPT"]
    stem, entry = resolve_script_id(int(prims[0].operands[0].text, 0), None)
    sf = load_script_file(stem)
    assert stem == "scripts_common" and sf.entry_label(entry) == "CommonScript_AddItemQuantity"
    assert sf.entries[entry][1].line == 73


def test_conditional_branch_and_call_common_successors():
    # res/field/scripts/scripts_snowpoint_city.s:183 GoToIfUnset FLAG_GAME_COMPLETED, ...ILookForward...
    sf, c = _cmd_at("scripts_snowpoint_city", 183)
    assert [p.op for p in c.prims] == ["SCRCMD_CHECKFLAG", "SCRCMD_GOTOIF"]
    kinds = {(s.kind, s.index) for s in successors(sf, c.index)}
    assert kinds == {("branch", sf.labels["SnowpointCity_ILookForwardToAGreatTrainer"]), ("next", c.index + 1)}
    # A command using a Common_* alias gets a call_common successor into scripts_common.
    found = False
    for stem in ("scripts_snowpoint_city", "scripts_jubilife_city", "scripts_oreburgh_city"):
        f = load_script_file(stem)
        for cmd in f.commands:
            if cmd.name.startswith("Common_"):
                succ = successors(f, cmd.index)
                assert any(s.kind == "call_common" and s.file == "scripts_common" for s in succ)
                found = True
    assert found  # positive control: at least one Common_* use was checked


def test_fall_through_into_next_label():
    # res/field/scripts/scripts_route_224.s:27-28: ClearFlag, then label Route224_DontHideProfOak.
    sf, c = _cmd_at("scripts_route_224", 27)
    assert sf.labels["Route224_DontHideProfOak"] == c.index + 1
    assert [s.kind for s in successors(sf, c.index)] == ["next"]


def test_end_and_return_have_no_successors():
    # res/field/scripts/scripts_route_224.s:29 End (after Route224_DontHideProfOak:)
    sf, c = _cmd_at("scripts_route_224", 29)
    assert c.name == "End" and successors(sf, c.index) == []


def test_in_range_macro_unrolls():
    # asm/macros/scrcmd.inc:5030-5036 GoToIfInRange recurses once per value
    prims = expand("GoToIfInRange", ("VAR_X", "1", "3", "L"))
    assert [p.op for p in prims] == ["SCRCMD_COMPAREVARTOVALUE", "SCRCMD_GOTOIF"] * 3


def test_ship_macro_expands_to_boat_cutscene():
    # res/field/scripts/scripts_snowpoint_city.s:210 TakeShipFromSnowpoint DIR_EAST, MAP_HEADER_FIGHT_AREA, 623, 434
    # asm/macros/scrcmd.inc:3392-3394
    _, c = _cmd_at("scripts_snowpoint_city", 210)
    assert c.ops == ("SCRCMD_PLAYBOATCUTSCENE",)
    assert c.prims[0].operands[2].text == "MAP_HEADER_FIGHT_AREA"
