"""Feature 029: resist berries ranked by the League damage they would block, weighed against the member's own Defense or
Special Defense, and the top two appended after each moveset's existing items (spec FR-006, FR-007; research R5)."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from types import SimpleNamespace

import pytest

from platsim import pins
from platsim.optimizer import candidates as C

SNAPSHOT = pins.REPO_ROOT / "specs" / "029-h4-resist-berries" / "evidence" / "candidates-main.json"
B2 = ["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"]
BERRIES = {"occa_berry", "passho_berry", "wacan_berry", "rindo_berry", "yache_berry", "chople_berry", "kebia_berry",
           "shuca_berry", "coba_berry", "payapa_berry", "tanga_berry", "charti_berry", "kasib_berry", "haban_berry",
           "colbur_berry", "babiri_berry", "chilan_berry"}


def _helper():
    path = pins.REPO_ROOT / "specs" / "029-h4-resist-berries" / "scripts" / "attribution.py"
    spec = importlib.util.spec_from_file_location("attribution_029", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["attribution_029"] = mod
    spec.loader.exec_module(mod)
    return mod


def _without_031(mc):
    """031 appends King's Rock and adds flinch_item extra sets; this feature's check ignores them."""
    keep = [ms for ms in mc.movesets if mc.extra_kind.get(ms) != "flinch_item"]
    dropped = len(mc.movesets) - len(keep)
    return dataclasses.replace(
        mc, movesets=keep, extras=mc.extras - dropped,
        item_extras={k: v for k, v in mc.item_extras.items() if k in keep},
        extra_kind={k: v for k, v in mc.extra_kind.items() if k in keep},
        extras_by_kind={k: v for k, v in mc.extras_by_kind.items() if k != "flinch_item"},
        items_extra={k: [i for i in v if i != "kings_rock"] for k, v in mc.items_extra.items()})


@pytest.fixture(scope="module")
def led():
    from platsim.availability.ledger import build_ledger
    from platsim.legality.models import LegalityOptions

    return build_ledger().with_options(LegalityOptions())


def test_every_berry_is_offerable_by_hold_effect(led):
    for t in ("FIRE", "WATER", "ELECTRIC", "GRASS", "ICE", "FIGHT", "POISON", "GROUND", "FLYING", "PSYCHIC", "BUG", "ROCK",
              "GHOST", "DRAGON", "DARK", "STEEL"):
        assert C._item_for_effect(f"HOLD_EFFECT_WEAKEN_SE_{t}", led) in BERRIES, t
    assert C._item_for_effect("HOLD_EFFECT_WEAKEN_NORMAL", led) == "chilan_berry"


def test_ranking_on_known_members(led):
    assert C.resist_berry_ranking("SPECIES_GARCHOMP", 50, led)[0][0] == "yache_berry"  # 4x Ice
    assert C.resist_berry_ranking("SPECIES_WEAVILE", 50, led)[0][0] == "chople_berry"  # 4x Fighting
    rotom = [k for k, _ in C.resist_berry_ranking("SPECIES_ROTOM", 50, led)]
    assert "shuca_berry" not in rotom  # Levitate: Ground cannot hit it
    values = [v for _, v in C.resist_berry_ranking("SPECIES_INFERNAPE", 50, led)]
    assert values == sorted(values, reverse=True) and all(v > 0 for v in values)


def _synthetic(monkeypatch, tmp_path, defence, sp_defence):
    """One League mon with Atk = SpA and two equally strong super-effective moves on a Grass member: Ice Punch (physical
    Ice 75/100) and Signal Beam (special Bug 75/100); every other League party empty."""
    real = C.MS.by_constant()
    stats = {"hp": 80, "atk": 100, "def": 80, "spa": 100, "spd": 80, "spe": 80}
    fakes = {
        "SPECIES_TEST_FOE": SimpleNamespace(types=["TYPE_NORMAL", "TYPE_NORMAL"], base_stats=stats, abilities=["ABILITY_NONE", None]),
        "SPECIES_TEST_ME": SimpleNamespace(types=["TYPE_GRASS", "TYPE_GRASS"], abilities=["ABILITY_OVERGROW", None],
                                           base_stats={**stats, "def": defence, "spd": sp_defence}),
    }
    monkeypatch.setattr(C.MS, "by_constant", lambda: {**real, **fakes})
    parties = {k: [] for k in C.GAUNTLET_KEYS}
    parties[C.GAUNTLET_KEYS[0]] = [{"species": "SPECIES_TEST_FOE", "moves": ["MOVE_ICE_PUNCH", "MOVE_SIGNAL_BEAM"], "level": 50}]
    path = tmp_path / "trainers.json"
    path.write_text(json.dumps({"trainers": [{"key": k, "party": p} for k, p in parties.items()]}))
    monkeypatch.setattr(C, "TRAINERS_JSON", path)


def test_high_defense_low_special_defense_ranks_the_special_threat_first(led, monkeypatch, tmp_path):
    _synthetic(monkeypatch, tmp_path, defence=150, sp_defence=50)
    ranking = C.resist_berry_ranking("SPECIES_TEST_ME", 50, led)
    assert [k for k, _ in ranking] == ["tanga_berry", "yache_berry"]  # Bug (special) before Ice (physical)
    assert ranking[0][1] == pytest.approx(3 * ranking[1][1])  # 150/50: the special hit lands three times as hard


def test_high_special_defense_low_defense_ranks_the_physical_threat_first(led, monkeypatch, tmp_path):
    _synthetic(monkeypatch, tmp_path, defence=50, sp_defence=150)
    assert [k for k, _ in C.resist_berry_ranking("SPECIES_TEST_ME", 50, led)] == ["yache_berry", "tanga_berry"]


def test_top_two_appended_last_after_shell_bell_on_b2(led):
    consts = C.resolve_species(B2, led)
    for c in consts:
        top = [k for k, _ in C.resist_berry_ranking(c, 100, led)[:2]]
        mc = C.member_candidates(c, C.variants(c, led)[0], 48, led, team=tuple(consts))
        for ms, extra in mc.items_extra.items():
            has_attack = any(C.is_attack(C.load_moves()[m]) or m in C.OFFERED_VARIABLE for m in ms)
            if has_attack:
                plain = [i for i in extra if i != "kings_rock"]  # 031 appends King's Rock after the berries
                assert plain[-len(top) - 1:] == ["shell_bell", *top], (c, ms, extra)
            assert not BERRIES & set(mc.items[ms])  # never among the existing candidates


def test_only_the_appended_items_change_over_the_36_members(led):
    A = _helper()
    snap = json.loads(SNAPSHOT.read_text())
    assert len(snap) == 36
    for key, rec in snap.items():
        recs = A.attribute(rec, _without_031(A.recompute(rec, led)))  # 031's additions checked in its own test
        assert all(r["cause"] == "appended" for r in recs), (key, recs)
