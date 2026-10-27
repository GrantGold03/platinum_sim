"""T057: Cynthia top-up (src/platsim/sim/champion.py) over real `node sim/worker.mjs` workers.

Player policy `greedy-v1` (T049). The opponent policy is whatever the worker reports (at the time
of writing `placeholder-default`, Showdown's `default` choice, not the decomp trainer AI); the test
prints it and the champion result records it, so these numbers are not a real evaluation.

The team is tests/integration/test_worker.py TEAM with every start_level overridden: 55 so that
every run reaches Cynthia and she wins only part of the time (so the CI rule, not just the count
rule, decides when to stop), and 5 so that nobody gets past Aaron. These are simulator test
inputs, not legal in-game sets. Run with `-s` to see the counts.
"""

import json
from collections import Counter

import pytest

from platsim.budget import get_preset
from platsim.sim.champion import CHAMPION, ChampionTopupError, champion_topup
from platsim.sim.pool import WorkerPool
from platsim.sim.seeds import derive_seed

from test_worker import TEAM

pytestmark = pytest.mark.battle_sim  # 012: every test here starts the battle worker

FULL_RUNS = 200
MASTER = "t057"


def team_at(level):
    return [dict(b, start_level=level) for b in TEAM]


def full_requests(team, master=MASTER, n=FULL_RUNS, log="summary"):
    return [{"op": "gauntlet", "team": team, "seed": derive_seed(master, i, 0), "player_policy": "greedy-v1",
             "stop_on_loss": True, "log": log} for i in range(n)]


class CountingPool:
    def __init__(self, pool):
        self.pool, self.calls, self.requests = pool, 0, []

    def map(self, reqs):
        self.calls += 1
        self.requests.extend(reqs)
        return self.pool.map(reqs)


@pytest.fixture(scope="module")
def pool():
    with WorkerPool(8) as p:
        yield p


@pytest.fixture(scope="module")
def strong(pool):
    team = team_at(55)
    results = pool.map(full_requests(team))
    assert all(r["ok"] for r in results)
    return team, results


def test_counts_meet_rule_on_real_run(pool, strong):
    team, full = strong
    cp = CountingPool(pool)
    res = champion_topup(cp, team, full, master_seed=MASTER, budget="standard")
    counts = Counter(b["trainer"] for r in full for b in r["battles"])
    print("\nopponent_policy:", full[0]["opponent_policy"], "player_policy:", full[0]["player_policy"])
    print("full-run battle counts:", dict(counts))
    print("champion:", json.dumps(res.to_dict()))
    assert counts[CHAMPION] > 0  # positive control for the zero-reach test: this team reaches her
    assert res.status == "met" and res.target_met and not res.cap_hit
    assert res.reached == counts[CHAMPION]
    assert res.other_battles == {t: c for t, c in counts.items() if t != CHAMPION}
    assert set(res.other_battles) == {"aaron", "bertha", "flint", "lucian"}
    assert res.battles == res.reached + res.topup_battles
    assert len(cp.requests) >= res.topup_battles  # extras past the stopping point are discarded
    assert res.battles > max(res.other_battles.values())
    assert res.half_width <= get_preset("standard").ci_half_width == 0.02
    assert res.ci_target_met is True and res.count_rule_met is True
    assert res.ci95[0] <= res.rate <= res.ci95[1]
    assert res.player_policy == "greedy-v1" and res.opponent_policy == full[0]["opponent_policy"]
    # The top-up requests are Cynthia-only, start from recorded states and use battle index 99.
    states = [b["state_before"] for r in full for b in r["battles"] if b["trainer"] == CHAMPION]
    for k, req in enumerate(cp.requests[:res.topup_battles]):
        assert req["trainers"] == ["cynthia"] and req["seed"] == derive_seed(MASTER, k, 99)
        assert req["start_state"] in states
    assert res.distinct_start_states > 1  # drawn from several states, not one


def test_deterministic_for_fixed_seed(strong):
    team, full = strong
    with WorkerPool(3) as p3:  # different worker count and fresh processes
        a = champion_topup(p3, team, full, master_seed=MASTER, budget="standard").to_dict()
    with WorkerPool(5) as p5:
        b = champion_topup(p5, team, full, master_seed=MASTER, budget="standard").to_dict()
        # Positive control: another master seed gives other top-up battles.
        c = champion_topup(p5, team, full, master_seed=MASTER + "-other", budget="standard").to_dict()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert (c["topup_battles"], c["topup_wins"]) != (a["topup_battles"], a["topup_wins"])


def test_zero_reach_runs_no_topup(pool):
    full = pool.map(full_requests(team_at(5)))
    counts = Counter(b["trainer"] for r in full for b in r["battles"])
    print("\nweak team full-run counts:", dict(counts))
    assert counts[CHAMPION] == 0 and counts["aaron"] == FULL_RUNS  # verified from the results
    cp = CountingPool(pool)
    res = champion_topup(cp, team_at(5), full, master_seed=MASTER, budget="standard")
    assert cp.calls == 0  # no top-up battle was run
    assert res.status == "no_reach" and res.reached == 0 and res.battles == 0
    assert res.rate is None and res.ci95 is None and not res.target_met


def test_cap_hit_is_reported(pool, strong):
    team, full = strong
    res = champion_topup(pool, team, full, master_seed=MASTER, budget="standard", max_topup=10)
    print("\ncap-hit:", json.dumps(res.to_dict()))
    assert res.status == "cap_hit" and res.cap_hit and not res.target_met
    assert res.topup_battles == 10 and res.battles == res.reached + 10
    # 10 top-ups cannot bring the half-width to 0.02 (runs_needed is ~2,000 at the rates seen here),
    # so the CI rule is the one that fails; the count rule alone does not make it "met".
    assert res.ci_target_met is False and res.half_width > 0.02


def test_quick_preset_uses_count_rule_only(pool, strong):
    team, full = strong
    res = champion_topup(pool, team, full, master_seed=MASTER, budget="quick")
    assert res.target_half_width is None and res.ci_target_met is None
    assert res.status == "met" and res.battles == max(res.other_battles.values()) + 1


def test_missing_state_before_is_an_error(pool):
    full = pool.map(full_requests(team_at(55), n=4, log="none"))
    with pytest.raises(ChampionTopupError, match="state_before"):
        champion_topup(pool, team_at(55), full, master_seed=MASTER, budget="standard")
