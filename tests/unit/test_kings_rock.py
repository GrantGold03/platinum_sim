"""Feature 031: King's Rock / Razor Fang offered as one option with two copies, appended for sets with an affected move, and a
multi-hit extra set where the multi-hit move is live (spec FR-002 to FR-004; research R2 to R4)."""

from __future__ import annotations

import importlib.util
import json
import sys

import pytest

from platsim import pins
from platsim.optimizer import candidates as C

SNAPSHOT = pins.REPO_ROOT / "specs" / "031-h4-kings-rock" / "evidence" / "candidates-main.json"
B2 = ["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"]
B5 = ["torterra", "magnezone", "clefable", "lumineon", "gallade", "spiritomb"]


def _helper():
    path = pins.REPO_ROOT / "specs" / "031-h4-kings-rock" / "scripts" / "attribution.py"
    spec = importlib.util.spec_from_file_location("attribution_031", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["attribution_031"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def led():
    from platsim.availability.ledger import build_ledger
    from platsim.legality.models import LegalityOptions

    return build_ledger().with_options(LegalityOptions())


def test_affected_moves_and_the_fifteen_multi_hit_moves():
    assert C.kings_rock_affected("MOVE_TACKLE") and C.kings_rock_affected("MOVE_AIR_SLASH")
    assert not C.kings_rock_affected("MOVE_SWORDS_DANCE")
    multi = sorted(m for m in C.load_moves() if C.kings_rock_multi_hit(m))
    assert len(multi) == 15 and "MOVE_BONE_RUSH" in multi and "MOVE_TRIPLE_KICK" not in multi


def test_appended_last_only_for_sets_with_an_affected_move(led):
    assert C.extra_item_candidates("SPECIES_GARCHOMP", ("MOVE_EARTHQUAKE", "MOVE_DRAGON_CLAW"), led)[-1] == "kings_rock"
    assert "kings_rock" not in C.extra_item_candidates("SPECIES_GARCHOMP", ("MOVE_SWORDS_DANCE", "MOVE_PROTECT"), led)
    consts = C.resolve_species(B2, led)
    for c in consts:
        mc = C.member_candidates(c, C.variants(c, led)[0], 48, led, team=tuple(consts))
        for ms, extra in mc.items_extra.items():
            assert (extra[-1:] == ["kings_rock"]) == any(C.kings_rock_affected(m) for m in ms), (c, ms, extra)


def test_multi_hit_extra_where_live_and_a_reason_where_dead(led):
    consts = C.resolve_species(B5, led)
    by = {c: C.member_candidates(c, C.variants(c, led)[0], 48, led, team=tuple(consts)) for c in consts}
    tort = by["SPECIES_TORTERRA"]
    fl = [ms for ms, kind in tort.extra_kind.items() if kind == "flinch_item"]
    assert len(fl) == 1 and "MOVE_BULLET_SEED" in fl[0] and "MOVE_WOOD_HAMMER" not in fl[0]  # same-type swap
    assert tort.item_extras[fl[0]] == "kings_rock" and tort.items[fl[0]][0] == "kings_rock"
    clef = by["SPECIES_CLEFABLE"]
    assert not any(k == "flinch_item" for k in clef.extra_kind.values())
    assert "dead" in clef.dropped_extras["flinch_item"]["reason"]


def test_two_holders_get_one_of_each_item_and_a_third_is_refused(led):
    from platsim.optimizer import resources as R

    consts = C.resolve_species(B2, led)
    mcs = [C.member_candidates(c, C.variants(c, led)[0], 48, led, team=tuple(consts)) for c in consts]
    base = R.repair(tuple(R.MemberSpec(c, "own", mc.movesets[0], None) for c, mc in zip(consts, mcs)), [48] * 6, led,
                    [mc.ranked for mc in mcs])
    assert not isinstance(base, R.Refusal), base
    specs = [R.MemberSpec(s.species, s.variant, s.moves, None) for s in base[0]]
    def holding(n):
        return tuple(R.MemberSpec(s.species, s.variant, s.moves, "kings_rock" if i < n else None) for i, s in enumerate(specs))
    two = R.realize(holding(2), [48] * 6, led)
    assert not isinstance(two, R.Refusal), two
    assert [b.held_item for b in two.team.builds[:2]] == ["kings_rock", "razor_fang"]
    three = R.realize(holding(3), [48] * 6, led)
    assert isinstance(three, R.Refusal)


def test_with_gliscor_only_one_flinch_item_fits(led):
    from platsim.optimizer import resources as R

    names = ["gliscor", "garchomp", "infernape", "staraptor", "rotom", "floatzel"]
    consts = C.resolve_species(names, led)
    mcs = [C.member_candidates(c, C.variants(c, led)[0], 48, led, team=tuple(consts)) for c in consts]
    base = R.repair(tuple(R.MemberSpec(c, "own", mc.movesets[0], None) for c, mc in zip(consts, mcs)), [48] * 6, led,
                    [mc.ranked for mc in mcs])
    assert not isinstance(base, R.Refusal), base
    specs = [R.MemberSpec(s.species, s.variant, s.moves, None) for s in base[0]]
    one = tuple(R.MemberSpec(s.species, s.variant, s.moves, "kings_rock" if i == 1 else None) for i, s in enumerate(specs))
    two = tuple(R.MemberSpec(s.species, s.variant, s.moves, "kings_rock" if i in (1, 2) else None) for i, s in enumerate(specs))
    assert not isinstance(R.realize(one, [48] * 6, led), R.Refusal)
    assert isinstance(R.realize(two, [48] * 6, led), R.Refusal), "Gliscor's evolution used the Razor Fang"


def test_only_appended_items_and_flinch_extras_change_over_the_36_members(led):
    A = _helper()
    snap = json.loads(SNAPSHOT.read_text())
    assert len(snap) == 36
    for key, rec in snap.items():
        recs = A.attribute(rec, A.recompute(rec, led))
        assert all(r["cause"] in ("appended", "appended_extra") for r in recs), (key, recs)


def test_every_extra_kind_the_candidates_produce_is_known_to_the_screen(led):
    """031: B5 quick failed with KeyError 'flinch_item' in the screen's per-kind count (run.EXTRA_KINDS lacked the new kind)."""
    from platsim.optimizer import run

    consts = C.resolve_species(B5, led)
    kinds = set()
    for c in consts:
        mc = C.member_candidates(c, C.variants(c, led)[0], 48, led, team=tuple(consts))
        kinds |= set(mc.extra_kind.values())
    assert "flinch_item" in kinds
    assert kinds <= set(run.EXTRA_KINDS), kinds - set(run.EXTRA_KINDS)
