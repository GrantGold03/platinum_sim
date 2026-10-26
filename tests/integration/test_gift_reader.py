"""Controls for the NPC-gift reader (`sources.npc_gift_entries`): the four script patterns of research R1
(G1 a value set in a called routine, G2 a random offset added to an item, G3 an item copied from a saved
variable, G4 an item picked from a C table and given with a variable AddItem).

Each expected set is read from the decomp text by a different route than the reader uses (a regex over the
script lines or the item ids), and every cited line is re-read so a wrong citation fails the test.
"""

import json
import re
from pathlib import Path

import pytest

from platsim.availability import sources as S
from platsim.availability.ledger import build_ledger
from platsim.decomp.items import load_items
from platsim.pins import DECOMP_ROOT, REPO_ROOT

SCRIPTS = "res/field/scripts"
R221 = f"{SCRIPTS}/scripts_route_221_house.s"
PASTORIA = f"{SCRIPTS}/scripts_pastoria_city_southwest_house.s"
AMITY = f"{SCRIPTS}/scripts_amity_square.s"
BASELINE = REPO_ROOT / "runs/011-evidence/availability-main.json"  # git-ignored; written on main's code


def _line(path: str, line: int, needle: str) -> None:
    text = (DECOMP_ROOT / path).read_text().splitlines()[line - 1]
    assert needle in text, f"{path}:{line} is {text!r}, expected {needle!r}"


def _text(path: str) -> str:
    return (DECOMP_ROOT / path).read_text()


@pytest.fixture(scope="module")
def gifts():
    return S.npc_gift_entries()


@pytest.fixture(scope="module")
def led():
    return build_ledger()


def _given_at(gifts, path: str, line: int) -> set[str]:
    ref = f"{path}:{line}"
    return {e.subject for e in gifts if e.src and e.src[0] == ref}


def test_g1_value_set_in_called_routine(gifts):
    """Route 221 house: the item is set in Route221House_SetReward* (reached by CallIfEq) and given at :39."""
    _line(R221, 39, "Common_GiveItemQuantityNoLineFeed")
    _line(R221, 28, "CallIfEq VAR_ROUTE_221_HOUSE_REWARD_INDEX, 0, Route221House_SetRewardBlackBelt")
    expected = set(re.findall(r"SetVar VAR_0x8004, (ITEM_\w+)", _text(R221)))
    assert expected == {"ITEM_BLACK_BELT", "ITEM_EXPERT_BELT", "ITEM_FOCUS_SASH"}
    assert _given_at(gifts, R221, 39) == expected


def test_g2_random_offset_added_to_an_item(gifts):
    """Pastoria SW house: GetRandom VAR_0x8004, 17 then AddVar VAR_0x8004, ITEM_OCCA_BERRY (:15-16), given at :20."""
    _line(PASTORIA, 15, "GetRandom VAR_0x8004, 17")
    _line(PASTORIA, 16, "AddVar VAR_0x8004, ITEM_OCCA_BERRY")
    _line(PASTORIA, 20, "Common_GiveItemQuantityNoLineFeed")
    by_id = {it.id: it.const for it in load_items().values()}
    base = next(it.id for it in load_items().values() if it.const == "ITEM_OCCA_BERRY")
    expected = {by_id[base + k] for k in range(17)}
    assert len(expected) == 17 and "ITEM_OCCA_BERRY" in expected
    assert _given_at(gifts, PASTORIA, 20) == expected


def _amity_pickup_berries() -> set[str]:
    return set(re.findall(r"SetVar VAR_FOLLOWER_MON_PICKUP_ITEM_ID, (ITEM_\w+)", _text(AMITY)))


def test_g3_item_copied_from_a_saved_variable(gifts):
    """Amity Square partner pickup: the berry is stored in VAR_FOLLOWER_MON_PICKUP_ITEM_ID (:311-344), copied
    into the item variable (:356) and given at :375."""
    _line(AMITY, 356, "SetVar LOCAL_VAR_ITEM_OR_ACCESSORY_ID, VAR_FOLLOWER_MON_PICKUP_ITEM_ID")
    _line(AMITY, 375, "Common_GiveItemQuantityNoLineFeed")
    expected = _amity_pickup_berries()
    assert len(expected) == 9
    assert _given_at(gifts, AMITY, 375) == expected


def test_g4_item_from_a_c_table_given_by_variable_additem(gifts):
    """Amity Square Gift Man: GetAmitySquareBerryOrAccessoryIDFromMan (:923) picks from a C table whose items
    are the same 9 berries as the pickup (scrcmd_amity_square.c); given by AddItem with variables at :940."""
    _line(AMITY, 923, "GetAmitySquareBerryOrAccessoryIDFromMan")
    _line(AMITY, 940, "AddItem LOCAL_VAR_ITEM_OR_ACCESSORY_ID, LOCAL_VAR_ITEM_OR_ACCESSORY_COUNT")
    assert _given_at(gifts, AMITY, 940) == _amity_pickup_berries()
    assert not [e for e in gifts if not e.subject.startswith("ITEM_")]


def test_literal_gift_unchanged(gifts):
    """Negative control in the repo: a plain literal gift keeps its item, count and once flag."""
    _line(f"{SCRIPTS}/scripts_canalave_city_gym.s", 55, "Common_GiveItemQuantity")
    es = [e for e in gifts if e.src == [f"{SCRIPTS}/scripts_canalave_city_gym.s:55"]]
    assert [(e.subject, e.quantity, e.once_flag) for e in es] == [("ITEM_TM91", 1, "FLAG_RECEIVED_BYRON_TM91")]


def test_unrelated_items_stay_unavailable(led):
    assert led.item_copies("ITEM_LIECHI_BERRY") == 0
    assert led.item_copies("ITEM_CHOICE_BAND") == 0


def test_every_baseline_gift_still_produced(gifts):
    """Every npc_item_gift entry that main's reader produced is still produced unchanged (same subject, map,
    quantity, source). The baseline is git-ignored evidence; without it this check cannot run."""
    if not BASELINE.exists():
        pytest.skip(f"baseline evidence {BASELINE} not present (git-ignored; written by task T002)")
    base = [e for e in json.loads(BASELINE.read_text())["entries"] if e["kind"] == "npc_item_gift"]
    now = {(e.subject, e.map_header, str(e.quantity), tuple(e.src)) for e in gifts}
    missing = [(e["subject"], e["map_header"], e["quantity"], e["src"]) for e in base
               if (e["subject"], e["map_header"], str(e["quantity"]), tuple(e["src"])) not in now]
    assert not missing, missing


def test_daily_random_level_gift_counts_one_copy_each(gifts):
    """Route 221 house: a daily gift that needs a party Pokemon at the day's random level
    (GetDailyRandomLevel, :15) counts 1 copy of each item, not unlimited (user, 2026-10-14)."""
    _line(R221, 15, "GetDailyRandomLevel VAR_0x8000")
    es = [e for e in gifts if e.src == [f"{R221}:39"]]
    assert es and {e.quantity for e in es} == {1}
    assert len({e.once_flag for e in es}) == len({e.subject for e in es})  # one acquisition per item
    assert all(e.once_flag_src == [f"{R221}:15"] for e in es)


def test_plain_daily_gift_stays_unlimited(gifts):
    """Negative control: Pastoria's daily berry has no level check, so main's daily rule (unlimited) holds."""
    _line(PASTORIA, 19, "SetFlag FLAG_DAILY_RECEIVED_PASTORIA_CITY_SOUTHWEST_HOUSE_RANDOM_BERRY")
    es = [e for e in gifts if e.src == [f"{PASTORIA}:20"]]
    assert es and {e.quantity for e in es} == {S.UNLIMITED}


# Reason text (contracts/explain-text.md): plain English, no project labels; decomp citations allowed.
FORBIDDEN = [r"\b0\d\d\b", r"\bT\d{3}\b", r"\bFR-\d+", r"\bSC-\d+", r"\bR\d\b", r"dataflow", r"call stack",
             r"Return-aware", r"AddVar", r"save-var", r"saved variable", r"C table", r"sentinel", r"once flag",
             r"guards this give"]
NEW_SITES = ("Route 221 House", "Pastoria City Southwest House", "Amity Square")


def _label_problems(line: str) -> list[str]:
    reason = line.split("  [")[0]  # the bracketed refs are citations
    bad = [p for p in FORBIDDEN if re.search(p, reason, re.I)]
    if not re.search(r"\[[^\]]*res/field/scripts/\w+\.s:\d+", line):
        bad.append("no decomp file:line")
    return bad


def test_label_check_rejects_project_labels():
    """Positive control for the check below: a made-up line with a task id and an implementation word."""
    line = "- [pre_champion] npc_item_gift at Route 221 House, quantity 1: daily (T053 dataflow)  [res/field/scripts/x.s:1]"
    assert set(_label_problems(line)) >= {r"\bT\d{3}\b", "dataflow"}


@pytest.mark.parametrize("item", ["focus_sash", "occa_berry", "belue_berry"])
def test_new_source_reasons_are_plain(item):
    from platsim.explain import explain

    lines = [ln for ln in explain(f"item:{item}").lines if "npc_item_gift" in ln and any(s in ln for s in NEW_SITES)]
    assert lines, f"{item}: no source line at the new sites"
    for ln in lines:
        assert not _label_problems(ln), (ln, _label_problems(ln))
    if item == "focus_sash":
        assert any("random level" in ln and "1 copy" in ln for ln in lines), lines
