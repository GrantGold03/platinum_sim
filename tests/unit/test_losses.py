"""T069: loss causes from synthetic gauntlet results and Showdown logs (report/losses.py).

The logs below are synthetic but use the Showdown protocol line shapes the worker emits
(pokemon-showdown/sim/SIM-PROTOCOL.md: `|switch|POKEMON|DETAILS|HP STATUS`, `|faint|POKEMON`).
"""

from __future__ import annotations

import pytest

from platsim.report.json_report import LossCause
from platsim.report.losses import (
    LostBattle,
    ReplayMismatch,
    cause_of,
    collect_loss_causes,
    field_at_last_faint,
    lost_battles,
    replay_requests,
    species_key,
    tally,
)

LOG_CYNTHIA_LOSS = [
    "|player|p1|Player|",
    "|switch|p1a: INFERNAPE|Infernape, L58, M|180/180",
    "|switch|p2a: SPIRITOMB|Spiritomb, L58, F|150/150",
    "|turn|1",
    "|switch|p2a: GARCHOMP|Garchomp, L62, F|220/220",
    "|faint|p1a: INFERNAPE",
    "|switch|p1a: GYARADOS|Gyarados, L58, M|200/200",
    "|drag|p2a: MILOTIC|Milotic, L58, F|190/190",  # Roar/Whirlwind style entry also counts
    "|faint|p2a: MILOTIC",
    "|switch|p2a: MR. MIME|Mr. Mime, L58, M|120/120",
    "|faint|p1a: GYARADOS",  # the player's LAST faint: Mr. Mime is on the field
    "|win|Opponent",
]


def test_field_at_last_faint_uses_the_last_player_faint():
    ff = field_at_last_faint(LOG_CYNTHIA_LOSS)
    assert ff.fainted and ff.opponents == ("Mr. Mime",) and ff.player_mon == "Gyarados"
    # positive control: cut the log after the first player faint -> Garchomp was on the field
    first = field_at_last_faint(LOG_CYNTHIA_LOSS[:6])
    assert first.opponents == ("Garchomp",) and first.player_mon == "Infernape"


def test_opponent_faint_does_not_count_and_no_faint_is_flagged():
    only_opp = ["|switch|p1a: X|Luxray, L58|1/1", "|switch|p2a: Y|Golem, L52|1/1", "|faint|p2a: Y"]
    ff = field_at_last_faint(only_opp)
    assert not ff.fainted and ff.opponents == ("Golem",)


def test_species_key_maps_showdown_names_to_generated_keys():
    assert species_key("Garchomp") == "garchomp"
    assert species_key("Mr. Mime") == "mr_mime"  # data/generated key has the underscore


def test_tally_counts_once_per_battle_and_orders_by_gauntlet():
    causes = [("cynthia", ["garchomp"]), ("cynthia", ["garchomp", "garchomp"]), ("cynthia", ["milotic"]),
              ("aaron", ["drapion"])]
    out = tally(causes, ["aaron", "bertha", "flint", "lucian", "cynthia"])
    assert out == [LossCause("aaron", "drapion", 1), LossCause("cynthia", "garchomp", 2),
                   LossCause("cynthia", "milotic", 1)]
    assert [c.to_dict() for c in out][0] == {"trainer": "aaron", "opponent_mon": "drapion", "losses": 1}


def _battle(trainer, won, h, end=None):
    return {"trainer": trainer, "won": won, "end": end or ("win" if won else "loss"), "turns": 10,
            "seed": f"sodium,{trainer}", "log_hash": h, "state_before": {"levels": [58]}}


def _result(battles):
    return {"ok": True, "cleared": all(b["won"] for b in battles) and len(battles) == 5, "battles": battles,
            "player_policy": "expectimax2-v1", "opponent_policy": "decomp-ai", "turn_limit": 1000}


RESULTS = [
    _result([_battle("aaron", True, "h0"), _battle("bertha", False, "h1")]),
    _result([_battle(t, True, f"w{t}") for t in ("aaron", "bertha", "flint", "lucian", "cynthia")]),
    _result([_battle("aaron", True, "h2"), _battle("bertha", True, "h3"), _battle("flint", True, "h4"),
             _battle("lucian", True, "h5"), _battle("cynthia", False, "h6", end="turn_limit")]),
]


def test_lost_battles_and_replay_requests():
    lost = lost_battles(RESULTS)
    assert [(lb.run, lb.battle, lb.record["trainer"]) for lb in lost] == [(0, 1, "bertha"), (2, 4, "cynthia")]
    reqs = replay_requests([{"species": "luxray"}], RESULTS, lost)
    assert reqs[0]["trainers"] == ["bertha"] and reqs[0]["seeds"] == ["sodium,bertha"]
    assert reqs[0]["start_state"] == {"levels": [58]} and reqs[0]["log"] == "full"
    assert reqs[1]["player_policy"] == "expectimax2-v1" and reqs[1]["opponent_policy"] == "decomp-ai"


def test_collect_with_fake_runner_and_hash_check():
    bertha_log = ["|switch|p1a: A|Luxray, L58|1/1", "|switch|p2a: B|Rhyperior, L55|1/1", "|faint|p1a: A", "|win|Opp"]
    cyn_log = ["|switch|p1a: A|Luxray, L58|1/1", "|switch|p2a: B|Garchomp, L62|1/1", "|tie"]

    def runner(reqs):
        logs = {"bertha": (bertha_log, "h1"), "cynthia": (cyn_log, "h6")}
        return [{"ok": True, "battles": [{"trainer": r["trainers"][0], "won": False,
                                          "log_hash": logs[r["trainers"][0]][1]}],
                 "log": [logs[r["trainers"][0]][0]]} for r in reqs]

    out = collect_loss_causes(runner, [], RESULTS, ["aaron", "bertha", "flint", "lucian", "cynthia"])
    assert out == [LossCause("bertha", "rhyperior", 1), LossCause("cynthia", "(turn_limit)", 1)]
    # positive control for the hash check: a replay that is not the same battle is an error
    lb = LostBattle(0, 1, RESULTS[0]["battles"][1])
    bad = {"ok": True, "battles": [{"trainer": "bertha", "won": False, "log_hash": "other"}], "log": [bertha_log]}
    with pytest.raises(ReplayMismatch):
        cause_of(lb, bad)
