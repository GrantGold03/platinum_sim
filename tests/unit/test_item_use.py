"""Feature 013: single-use held items, read from the decomp (platsim.decomp.item_use).

Check values (research R4, read by hand from the decomp, path:line under pokeplatinum/):
- Focus Sash (HOLD_EFFECT_ENDURE) is removed after it holds the holder at 1 HP:
  res/battle/scripts/subscripts/subscript_move_followup_message.s:17-18 (CheckItemHoldEffect CHECK_NOT_HAVE ...
  HOLD_EFFECT_ENDURE, then RemoveItem). Focus Band (HOLD_EFFECT_MAYBE_ENDURE) takes the same script and is kept.
- Power Herb (HOLD_EFFECT_CHARGE_SKIP): effects/effect_script_0039.s:7,13 -> subscript_item_skip_charge_turn.s:20.
- White Herb, Mental Herb, Berry Juice and the berries: battle_lib.c BattleSystem_TriggerHeldItem cases ->
  subscript_held_item_* -> subscript_pluck_check.s:6.
- Quick Claw shares subscript_check_quick_claw.s; only the Custap Berry branch removes (:26-28).
- Moves spending an item (not a hold effect): effect_script_0222.s:8 (Natural Gift), effect_script_0233.s:18
  (Fling), subscript_pluck.s:10 (Pluck / Bug Bite, include/data/move_side_effect_subscripts.h:142).
- Berries: "fieldPocket": "POCKET_BERRIES" in res/items/data/<item>.json; berry_juice.json is POCKET_MEDICINE.
"""

from __future__ import annotations

import json
import re
import shutil

import pytest

from platsim.decomp import item_use as U
from platsim.decomp.items import ITEMS_DIR, load_items
from platsim.pins import DECOMP_ROOT

EXCLUDED = {"ITEM_FOCUS_SASH", "ITEM_WHITE_HERB", "ITEM_MENTAL_HERB", "ITEM_POWER_HERB", "ITEM_BERRY_JUICE"}
NOT_SINGLE_USE = ["ITEM_LEFTOVERS", "ITEM_FOCUS_BAND", "ITEM_QUICK_CLAW", "ITEM_STICKY_BARB", "ITEM_SILK_SCARF",
                  "ITEM_NONE"]


@pytest.fixture(scope="module")
def uses():
    return U.item_uses()


def test_positive_controls(uses):
    sash = uses["ITEM_FOCUS_SASH"]
    assert sash.single_use and not sash.berry
    assert any("subscript_move_followup_message.s" in r for r in sash.evidence)
    sitrus = uses["ITEM_SITRUS_BERRY"]
    assert sitrus.single_use and sitrus.berry
    for const in EXCLUDED:
        assert uses[const].single_use and not uses[const].berry, const


def test_negative_controls(uses):
    for const in NOT_SINGLE_USE:
        assert not uses[const].single_use, const
        assert uses[const].evidence == [], const


def test_excluded_set(uses):
    # SC-002: exactly the items found by hand (research R4); a new member must be checked and listed first.
    assert {c for c, u in uses.items() if u.single_use and not u.berry} == EXCLUDED


def test_berry_rule(uses):
    pocket = set()
    for const, it in load_items().items():
        if json.loads((ITEMS_DIR / f"{it.key}.json").read_text()).get("fieldPocket") == "POCKET_BERRIES":
            pocket.add(const)
    assert len(pocket) == 64
    assert {c for c, u in uses.items() if u.berry} == pocket
    assert not uses["ITEM_BERRY_JUICE"].berry


def test_evidence_points_at_real_lines(uses):
    ok = re.compile(r"RemoveItem|case HOLD_EFFECT_|CheckItemHoldEffect|CompareVarToValue|CompareMonDataToValue|"
                    r"ItemEffect\s*==")
    for const, u in uses.items():
        assert bool(u.evidence) == u.single_use, const
        for ref in u.evidence:
            path, line = ref.rsplit(":", 1)
            text = (DECOMP_ROOT / path).read_text().splitlines()[int(line) - 1]
            assert ok.search(text), (const, ref, text)
        if u.single_use:
            assert any("RemoveItem" in (DECOMP_ROOT / r.rsplit(":", 1)[0]).read_text().splitlines()[
                int(r.rsplit(":", 1)[1]) - 1] for r in u.evidence), const


def test_same_hold_effect_same_verdict(uses):
    by_effect: dict[str, set[bool]] = {}
    for u in uses.values():
        by_effect.setdefault(u.hold_effect, set()).add(u.single_use)
    assert all(len(v) == 1 for v in by_effect.values())
    assert by_effect["HOLD_EFFECT_NONE"] == {False}


def test_every_remove_site_accounted_for():
    sites, _, move_driven = U.remove_sites()
    assert len(sites) == 11  # grep -rn RemoveItem res/battle/scripts
    assert {r.rsplit("/", 1)[1] for r in move_driven} == {
        "effect_script_0222.s:8", "effect_script_0233.s:18", "subscript_pluck.s:10"}
    assert all(sites[r] for r in sites if r not in move_driven)


def test_unattributed_remove_raises(tmp_path):
    # Positive control for the completeness gate: an extra RemoveItem that no hold effect or move reaches.
    clean, root = tmp_path / "clean", tmp_path / "scripts"
    shutil.copytree(U.SCRIPTS_DIR, clean)
    shutil.copytree(U.SCRIPTS_DIR, root)
    U.remove_sites(clean)  # an unchanged copy reads cleanly (readers are cached per root)
    target = root / "subscripts" / "subscript_battle_won.s"
    text = target.read_text()
    assert "_000:\n" in text
    target.write_text(text.replace("_000:\n", "_000:\n    RemoveItem BTLSCR_ATTACKER\n", 1))
    assert "subscript_battle_won" not in U._move_reachable(root)  # parses the edited tree (cached per root)
    with pytest.raises(U.ItemUseReadError, match="subscript_battle_won.s"):
        U.remove_sites(root)


def test_is_excluded_single_use():
    assert U.is_excluded_single_use("ITEM_FOCUS_SASH")
    assert U.is_excluded_single_use("focus_sash")
    assert not U.is_excluded_single_use("sitrus_berry")
    assert not U.is_excluded_single_use("leftovers")
    assert not U.is_excluded_single_use(None)
    assert not U.is_excluded_single_use("no_such_item")
