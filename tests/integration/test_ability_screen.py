"""T060: a real ability screen (FR-008c) on the reference team, plus every reason code.

Real `node sim/worker.mjs` workers; player `greedy-v1`, opponent `decomp-ai` (research R8). Run with -s
for timings.
"""

import json
import time
from pathlib import Path

import pytest

from platsim.budget import get_preset
from platsim.optimizer.abilities import choose_ability
from platsim.sim.pool import WorkerPool

TEAM = json.loads((Path(__file__).parents[1] / "fixtures" / "reference_team.json").read_text())["builds"]
LUXRAY = 2  # res/pokemon/luxray/data.json:30 [ABILITY_RIVALRY, ABILITY_INTIMIDATE]; both engine-checked
STARAPTOR = 1  # res/pokemon/staraptor/data.json:30 [ABILITY_INTIMIDATE, ABILITY_NONE]


@pytest.fixture(scope="module")
def pool():
    with WorkerPool() as p:
        yield p


def test_real_screen_quick_preset(pool):
    assert TEAM[LUXRAY]["species"] == "luxray"
    t0 = time.perf_counter()
    c = choose_ability(pool, TEAM, LUXRAY, seed="t060", budget="quick")
    dt = time.perf_counter() - t0
    n = get_preset("quick").ability_screen
    s = c.stats
    print(f"luxray screen: {c.ability} {c.reason} rates {s['clear_rate']} only {s['only_cleared_by']} "
          f"p={s['p_value']:.4g} ({2 * n} gauntlets in {dt:.1f}s)")
    assert s["n_paired"] == n and s["abilities"] == ["ABILITY_RIVALRY", "ABILITY_INTIMIDATE"]
    assert s["player_policy"] == "greedy-v1" and s["opponent_policy"] == "decomp-ai"
    assert c.reason in ("tested_better", "tie_default")
    if c.reason == "tie_default":
        assert c.ability == "ABILITY_RIVALRY" and s["p_value"] >= s["alpha"]
    else:
        assert s["p_value"] < s["alpha"] and c.ability == s["verdict"]


def test_screen_is_deterministic(pool):
    a = choose_ability(pool, TEAM, LUXRAY, seed="t060-det", runs=24)
    b = choose_ability(pool, TEAM, LUXRAY, seed="t060-det", runs=24)
    assert a == b
    assert a.stats["seeds"]["master"] == "t060-det|ability-screen|slot2"


def test_single_ability_spends_no_runs():
    c = choose_ability(None, TEAM, STARAPTOR, seed="t060")  # pool None: would raise if a run were attempted
    assert c == ("ABILITY_INTIMIDATE", "single_ability", None)


def test_no_effect_ability_spends_no_runs():
    team = [dict(b) for b in TEAM]
    # res/pokemon/skuntank/data.json:30 [ABILITY_STENCH, ABILITY_AFTERMATH]; Stench has no engine ref
    team[5] = dict(team[5], species="skuntank", ability="ABILITY_STENCH")
    c = choose_ability(None, team, 5, seed="t060")
    assert (c.ability, c.reason) == ("ABILITY_AFTERMATH", "other_no_battle_effect")


def test_npc_trade_fixed_by_personality():
    # res/npc_trades/charap_chatot.json:18 "personality": 2151 (odd -> slot 2);
    # res/pokemon/chatot/data.json:30 [ABILITY_KEEN_EYE, ABILITY_TANGLED_FEET]
    team = [dict(b) for b in TEAM]
    team[5] = dict(team[5], species="chatot", ability="ABILITY_KEEN_EYE",
                   source="npc_trade:SPECIES_CHATOT@MAP_HEADER_ETERNA_CITY_CONDOMINIUMS_1F")
    c = choose_ability(None, team, 5, seed="t060")
    assert (c.ability, c.reason) == ("ABILITY_TANGLED_FEET", "fixed_by_trade")
    assert c.stats["personality"] == 2151 and c.stats["ability_slot"] == 2
