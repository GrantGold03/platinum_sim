"""Feature 028: Shell Bell offered by hold effect, appended after each moveset's existing items (spec FR-005 to FR-007)."""

from __future__ import annotations

import importlib.util
import json
import sys

import pytest

from platsim import pins
from platsim.optimizer import candidates as C

SNAPSHOT = pins.REPO_ROOT / "specs" / "028-h4-shell-bell" / "evidence" / "candidates-main.json"
B2 = ["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"]


def _helper():
    path = pins.REPO_ROOT / "specs" / "028-h4-shell-bell" / "scripts" / "attribution.py"
    spec = importlib.util.spec_from_file_location("attribution_028", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["attribution_028"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def led():
    from platsim.availability.ledger import build_ledger
    from platsim.legality.models import LegalityOptions

    return build_ledger().with_options(LegalityOptions())


def test_shell_bell_is_offered_by_hold_effect_with_one_copy(led):
    it = C._item_for_effect(C.HP_RESTORE_ON_DMG_EFFECT, led)
    assert it == "shell_bell"
    assert C._item_copies(led, "ITEM_SHELL_BELL") == 1


def test_appended_last_for_every_set_with_an_attack_on_b2(led):
    consts = C.resolve_species(B2, led)
    for c in consts:
        mc = C.member_candidates(c, C.variants(c, led)[0], 48, led, team=tuple(consts))
        for ms, extra in mc.items_extra.items():
            has_attack = any(C.is_attack(C.load_moves()[m]) or m in C.OFFERED_VARIABLE for m in ms)
            assert (extra[-1:] == ["shell_bell"]) == has_attack, (c, ms, extra)
            assert "shell_bell" not in mc.items[ms]  # never among the existing candidates


def test_only_the_appended_items_change_over_the_36_members(led):
    A = _helper()
    snap = json.loads(SNAPSHOT.read_text())
    assert len(snap) == 36
    for key, rec in snap.items():
        recs = A.attribute(rec, A.recompute(rec, led))
        defects = [r for r in recs if r["cause"] == "defect"]
        assert not defects, (key, defects)
        assert all(r["cause"] in ("appended",) for r in recs), (key, recs)


def test_a_second_shell_bell_is_refused(led):
    from platsim.optimizer import resources as R

    consts = C.resolve_species(B2, led)
    mcs = [C.member_candidates(c, C.variants(c, led)[0], 48, led, team=tuple(consts)) for c in consts]
    base = R.repair(tuple(R.MemberSpec(c, "own", mc.movesets[0], None) for c, mc in zip(consts, mcs)), [48] * 6, led,
                    [mc.ranked for mc in mcs])
    assert not isinstance(base, R.Refusal), base
    specs = [R.MemberSpec(s.species, s.variant, s.moves, None) for s in base[0]]
    one = tuple(R.MemberSpec(s.species, s.variant, s.moves, "shell_bell" if i == 0 else None) for i, s in enumerate(specs))
    two = tuple(R.MemberSpec(s.species, s.variant, s.moves, "shell_bell" if i < 2 else None) for i, s in enumerate(specs))
    assert not isinstance(R.realize(one, [48] * 6, led), R.Refusal)
    refused = R.realize(two, [48] * 6, led)
    assert isinstance(refused, R.Refusal) and "shell_bell" in refused.reason
