"""T032/T035 end-to-end: Python drives `node sim/worker.mjs` over NDJSON (contracts/worker-protocol.md).

Runs `hello` and one full 5-trainer gauntlet. The test asks for `placeholder-default` (Showdown's
`default` choice) on both sides on purpose, to check the protocol rather than the AI; it asserts that
name is reported, so a placeholder result can never pass for a real evaluation. Run with `-s` to see the gauntlet result.
"""

import json
import subprocess

import pytest

from platsim.pins import DECOMP_COMMIT, REPO_ROOT, SHOWDOWN_COMMIT
from platsim.sim.seeds import derive_seed

pytestmark = pytest.mark.battle_sim  # 012: every test here starts the battle worker

STATS = ("hp", "atk", "def", "spa", "spd", "spe")


def build(species, level, moves, ability, item=None):
    return {"species": species, "source": "smoke", "start_level": level,
            "moves": [{"move": m, "source_kind": "level_up", "detail": ""} for m in moves],
            "ability": ability, "ability_reason": "single_ability", "held_item": item, "nature": "Hardy",
            "ivs": dict.fromkeys(STATS, 15), "evs": dict.fromkeys(STATS, 85)}


TEAM = [
    build("garchomp", 62, ["earthquake", "dragon_claw", "crunch", "fire_fang"], "ABILITY_SAND_VEIL", "lucky_egg"),
    build("lucario", 60, ["aura_sphere", "dark_pulse", "dragon_pulse", "extreme_speed"], "ABILITY_STEADFAST"),
    build("gyarados", 60, ["waterfall", "ice_fang", "earthquake", "dragon_dance"], "ABILITY_INTIMIDATE", "sitrus_berry"),
    build("alakazam", 60, ["psychic", "shadow_ball", "energy_ball", "calm_mind"], "ABILITY_SYNCHRONIZE", "exp_share"),
    build("magnezone", 60, ["thunderbolt", "flash_cannon", "tri_attack", "thunder_wave"], "ABILITY_MAGNET_PULL"),
    build("roserade", 60, ["energy_ball", "sludge_bomb", "shadow_ball", "extrasensory"], "ABILITY_NATURAL_CURE"),
]


def test_worker_hello_and_gauntlet():
    reqs = [
        {"id": 1, "op": "hello"},
        {"id": 2, "op": "gauntlet", "team": TEAM, "seed": derive_seed("smoke", 0, 0),
         "player_policy": "placeholder-default", "opponent_policy": "placeholder-default",
         "trainers": ["aaron", "bertha", "flint", "lucian", "cynthia"],
         "stop_on_loss": True, "log": "summary"},
        {"id": 3, "op": "gauntlet", "team": [build("notamon", 5, ["tackle"], "ABILITY_NONE")], "seed": "sodium," + "0" * 32},
        {"id": 4, "op": "nope"},
    ]
    proc = subprocess.run(["node", str(REPO_ROOT / "sim" / "worker.mjs")],
                          input="".join(json.dumps(r) + "\n" for r in reqs),
                          capture_output=True, text=True, timeout=120, check=False)
    assert proc.returncode == 0, proc.stderr
    out = {r["id"]: r for r in map(json.loads, proc.stdout.splitlines())}
    assert set(out) == {1, 2, 3, 4}

    hello = out[1]
    assert hello["ok"] and hello["showdown_commit"] == SHOWDOWN_COMMIT
    assert hello["decomp_commit"] == DECOMP_COMMIT
    ledger = REPO_ROOT / "data" / "divergences.json"  # T053; "none" when absent
    assert hello["divergence_ledger_version"] == (json.loads(ledger.read_text())["version"] if ledger.exists() else "none")
    assert hello["decomp_data_hash"].startswith("sha256:")
    # Code version (sim/version.mjs): the same scheme computed in Python over the same files.
    from platsim.version import sim_code_hash

    assert hello["sim_code_hash"] == sim_code_hash()
    assert hello["node_version"] == subprocess.run(["node", "--version"], capture_output=True, text=True,
                                                   check=True).stdout.strip()

    g = out[2]
    assert g["ok"], g
    assert g["player_policy"] == "placeholder-default" and g["opponent_policy"] == "placeholder-default"
    assert 1 <= len(g["battles"]) <= 5 and len(g["final_levels"]) == 6
    assert all("state_before" in b and b["log_hash"].startswith("sha256:") for b in g["battles"])
    assert g["cleared"] == (len(g["battles"]) == 5 and all(b["won"] for b in g["battles"]))
    print(json.dumps({k: v for k, v in g.items() if k != "exp_events"} | {"exp_events": len(g["exp_events"])}))

    assert out[3] == {"id": 3, "ok": False, "error": {"kind": "invalid_team", "detail": "unknown species notamon"}}
    assert out[4]["ok"] is False and out[4]["error"]["kind"] == "internal"
