"""Feature 024: variable-power moves offered by the optimizer (spec FR-005, FR-006, FR-006a; SC-001, SC-003).

- decomp/weights.py pins (Snorlax 4600, Pikachu 60, Flareon 250) and Node parity (sim/variable_power.mjs) for every League
  party species; the weight tier on both sides of every limit; Gyro Ball; Return 102.
- candidates.variable_power per opponent (Grass Knot: Rhyperior 120, Flareon 40; Gyro Ball slow vs fast).
- The not-offered list never appears in any B2 candidate set.
- The additive prefix: today's lists (the pre-feature snapshot, evidence/b2-candidates-main.json, taken on main's code) are a
  prefix of the new lists for all six B2 species; extras exist where a variable move is legal.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from platsim import pins
from platsim.decomp.weights import gyro_ball_power, return_power, species_weight_hg, weight_tier_power
from platsim.optimizer import candidates as C

SNAPSHOT = pins.REPO_ROOT / "specs" / "024-variable-power-moves" / "evidence" / "b2-candidates-main.json"


def test_weight_pins_and_tiers():
    assert species_weight_hg("SPECIES_SNORLAX") == 4600
    assert species_weight_hg("SPECIES_PIKACHU") == 60
    assert species_weight_hg("SPECIES_FLAREON") == 250  # exactly on the 250 limit: the game gives 40 (ledger entry)
    assert species_weight_hg("SPECIES_RHYPERIOR") == 2828
    for w, p in [(1, 20), (100, 20), (101, 40), (250, 40), (251, 60), (500, 60), (501, 80), (1000, 80), (1001, 100),
                 (2000, 100), (2001, 120), (4600, 120)]:
        assert weight_tier_power(w) == p, w
    assert gyro_ball_power(100, 436) == 110 and gyro_ball_power(100, 512) == 129
    assert gyro_ball_power(100, 1000) == 150 and gyro_ball_power(1000, 10) == 1 and gyro_ball_power(0, 100) == 0
    assert return_power(255) == 102 and return_power(0) == 0


def test_weights_match_the_node_helper_for_every_league_species():
    species = sorted({o.species for o in C.league_opponents()})
    script = ("import('./sim/variable_power.mjs').then(m => { const out = {}; for (const s of process.argv.slice(1)) "
              "out[s] = m.speciesWeightHg(s); console.log(JSON.stringify(out)); })")
    p = subprocess.run(["node", "-e", script, *species], cwd=pins.REPO_ROOT, capture_output=True, text=True, check=True)
    node = json.loads(p.stdout.strip().splitlines()[-1])
    assert len(node) == len(species) >= 20
    assert {s: species_weight_hg(s) for s in species} == node


def _opp(species: str) -> C.LeagueOpponent:
    return next(o for o in C.league_opponents() if o.species == species)


def test_variable_power_per_opponent():
    rhyperior, flareon, lucario = _opp("SPECIES_RHYPERIOR"), _opp("SPECIES_FLAREON"), _opp("SPECIES_LUCARIO")
    assert C.variable_power("MOVE_GRASS_KNOT", "SPECIES_INFERNAPE", 48, rhyperior) == 120
    assert C.variable_power("MOVE_GRASS_KNOT", "SPECIES_INFERNAPE", 48, flareon) == 40
    assert C.variable_power("MOVE_LOW_KICK", "SPECIES_INFERNAPE", 48, flareon) == 40
    assert C.variable_power("MOVE_RETURN", "SPECIES_GARCHOMP", 48, lucario) == 102
    slow = C.variable_power("MOVE_GYRO_BALL", "SPECIES_BRONZONG", 48, _opp("SPECIES_GARCHOMP"))
    fast = C.variable_power("MOVE_GYRO_BALL", "SPECIES_WEAVILE", 48, _opp("SPECIES_BRONZONG"))
    assert slow > fast >= 1
    assert C.variable_power("MOVE_EARTHQUAKE", "SPECIES_GARCHOMP", 48, lucario) is None
    vals = C.move_value("SPECIES_INFERNAPE", "MOVE_GRASS_KNOT", 48)
    assert len(vals) == len(C.league_opponents()) and all(v >= 0 for v in vals)


@pytest.fixture(scope="module")
def snapshot_and_lists():
    from platsim.availability.ledger import build_ledger
    from platsim.legality.models import LegalityOptions

    snap = json.loads(SNAPSHOT.read_text())
    led = build_ledger().with_options(LegalityOptions())
    out = {}
    for key, s in snap.items():
        call = s["call"]
        v = next(v for v in C.variants(call["species"], led) if v.key == call["variant"])
        out[key] = (s, C.member_candidates(call["species"], v, call["ref_level"], led, k=call["k"], team=tuple(call["team"])))
    return out


def _attribution():
    """specs/025-h4-wide-lens-razor-claw/scripts/attribution.py imported by path (registered in sys.modules: the 019 lesson)."""
    import importlib.util
    import sys

    path = pins.REPO_ROOT / "specs" / "026-marginal-coverage-sets" / "scripts" / "attribution.py"  # 026: adds marginal_pool
    spec = importlib.util.spec_from_file_location("attribution_026", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["attribution_026"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_todays_candidates_differ_from_024s_only_by_attributed_causes(snapshot_and_lists):
    # 024 pinned today's lists as a prefix of the new ones. 025 (the crit term in every move value, the widened dominance
    # rule, the item-conditioned extras) changes them; every difference from the 024 snapshot must be attributed to one
    # of those causes by the shared helper (also used by the 025 acceptance), never a "defect".
    attribution = _attribution()
    assert len(snapshot_and_lists) == 6
    for key, (s, mc) in snapshot_and_lists.items():
        records = attribution.attribute(s, mc)
        defects = [r for r in records if r["cause"] == "defect"]
        assert not defects, (key, defects)
        n = len(mc.movesets) - mc.extras
        assert 1 <= n <= C.K_MOVESETS, key
        assert sum(mc.extras_by_kind.values()) == mc.extras, key
        if mc.variable_offered:
            assert mc.extras_by_kind.get("variable_power", 0) >= 1, key
            for extra in mc.movesets[n:]:
                if mc.extra_kind.get(extra) == "variable_power":
                    assert any(m in C.OFFERED_VARIABLE for m in extra), (key, extra)
        else:
            assert mc.extras_by_kind.get("variable_power", 0) == 0, key


def test_not_offered_moves_never_appear(snapshot_and_lists):
    banned = {m for m in C.NOT_OFFERED_VARIABLE if m.startswith("MOVE_")}
    for key, (_, mc) in snapshot_and_lists.items():
        for ms in mc.movesets + mc.ranked:
            assert not (set(ms) & banned), (key, ms)
        assert set(mc.variable_offered) <= C.OFFERED_VARIABLE
