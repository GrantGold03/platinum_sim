"""T056: policy strength benchmark (research R7, spec FR-013, Constitution IV), extended for expectimax2-v2.

On the policy benchmark team (tests/fixtures/policy_benchmark_team.json) run N paired full-League gauntlets
(same seeds, `stop_on_loss` true, opponent policy `decomp-ai`) for the player policies `greedy-v1`,
`expectimax2-v1` and `expectimax2-v2`, through the worker pool (src/platsim/sim/pool.py). The paired
clear outcomes are compared with the exact McNemar test (src/platsim/stats.py):
  - expectimax2-v1 vs greedy-v1: the recorded T056 comparison, unchanged (same seed master, same
    policy), so its numbers stay reproducible; it must still clear more often with p < 0.05;
  - expectimax2-v2 vs greedy-v1: v2 must clear more often with p < 0.05.
On the policy-reversal team (tests/fixtures/policy_reversal_team.json, where v1 lost to greedy) the second
test runs greedy-v1 and expectimax2-v2 paired and requires that v2 is NOT significantly worse (McNemar
p >= 0.05 or v2 ahead). It never relabels a policy.

N defaults to 2,000 for the benchmark team (the task's count) and 400 for the reversal team.
PLATSIM_STRENGTH_N / PLATSIM_REVERSAL_N override them for quick local checks; the numbers used are
printed. PLATSIM_STRENGTH_WORKERS sets the pool size (default os.cpu_count()). Run with `-s` to see the
report (rates, Wilson 95% CIs, discordant pairs, p-values, run time and gauntlets/s per policy).
"""

from __future__ import annotations

import json
import os
import time

from platsim import pins
from platsim.sim.pool import WorkerPool
from platsim.sim.seeds import derive_seed
from platsim.stats import mcnemar_exact, wilson_ci

# This team is NOT legal (Alakazam is trade-only, its sources are placeholders; see the T028-T031
# entry in validation-log.md). It is used only to compare player policies, and it keeps the recorded
# T056 numbers reproducible. It was named reference_team.json until T069-T071, which replaced
# reference_team.json with a legal team.
FIXTURE = pins.REPO_ROOT / "tests" / "fixtures" / "policy_benchmark_team.json"
REVERSAL_FIXTURE = pins.REPO_ROOT / "tests" / "fixtures" / "policy_reversal_team.json"
SPECIES = pins.REPO_ROOT / "data" / "generated" / "species.json"
POLICIES = ("greedy-v1", "expectimax2-v1", "expectimax2-v2")
OPPONENT = "decomp-ai"
MASTER = "t056-policy-strength"
REVERSAL_MASTER = "x2v2-reversal"


def _team():
    return json.loads(FIXTURE.read_text())["team"]


def test_reference_team_moves_are_own_level_up_moves():
    """Cheap sanity check of the fixture (formal legality is T029/T030's job)."""
    species = json.loads(SPECIES.read_text())["species"]
    team = _team()
    assert len(team) == 6
    for b in team:
        rec = species[b["species"]]
        learn = {}
        for lvl, mv in rec["learnset_level"]:
            learn.setdefault(mv.removeprefix("MOVE_").lower(), lvl)
        assert b["ability"] in rec["abilities"], b
        for mc in b["moves"]:
            assert mc["move"] in learn and learn[mc["move"]] <= b["start_level"], (b["species"], mc)
        assert set(b["ivs"].values()) == {15} and set(b["evs"].values()) == {85} and b["nature"] == "Hardy"
    # positive control: a move Infernape cannot learn by level up is rejected by the same check
    learn = {mv.removeprefix("MOVE_").lower() for _, mv in species["infernape"]["learnset_level"]}
    assert "surf" not in learn and "close_combat" in learn


def _paired(team, policies, n, master, workers):
    seeds = [derive_seed(master, i, 0) for i in range(n)]
    outcomes: dict[str, list[bool]] = {}
    timing: dict[str, float] = {}
    with WorkerPool(workers) as pool:
        assert set(policies) <= set(pool.hello["policies"])
        assert OPPONENT in pool.hello["opponent_policies"]
        for pol in policies:
            reqs = [{"op": "gauntlet", "id": f"{pol}-{i}", "team": team, "seed": s, "player_policy": pol,
                     "opponent_policy": OPPONENT, "stop_on_loss": True, "log": "none"} for i, s in enumerate(seeds)]
            t0 = time.perf_counter()
            res = pool.map(reqs)
            timing[pol] = time.perf_counter() - t0
            assert all(r["ok"] for r in res), [r for r in res if not r["ok"]][:3]
            assert all(r["player_policy"] == pol and r["opponent_policy"] == OPPONENT for r in res)
            # paired: battle 1 of request i used the same seed (sim/gauntlet.mjs deriveSeed(seed, 0, 0)) for every policy
            assert [r["battles"][0]["seed"] for r in res] == [derive_seed(s, 0, 0) for s in seeds]
            outcomes[pol] = [bool(r["cleared"]) for r in res]
        hello = pool.hello
    return outcomes, timing, hello


def _report(title, n, master, workers, hello, outcomes, timing, pairs):
    lines = [f"{title}: n={n} paired gauntlets, opponent={OPPONENT}, workers={workers}, "
             f"seed master={master!r}, decomp={hello['decomp_commit'][:12]}, showdown={hello['showdown_commit'][:12]}"]
    for pol in outcomes:
        k = sum(outcomes[pol])
        lo, hi = wilson_ci(k, n)
        lines.append(f"  {pol:15s} cleared {k}/{n} = {k / n:.4f}  Wilson95 [{lo:.4f}, {hi:.4f}]  "
                     f"time {timing[pol]:.1f}s  {n / timing[pol]:.2f} gauntlets/s")
    cmps = {}
    for a, b in pairs:
        cmp = mcnemar_exact(outcomes[a], outcomes[b])
        cmps[(a, b)] = cmp
        lines.append(f"  McNemar exact {a} vs {b}: {a}-only={cmp.a_only} {b}-only={cmp.b_only} p={cmp.p_value:.3g} "
                     f"verdict={cmp.verdict}")
    return "\n".join(lines), cmps


def test_expectimax2_beats_greedy_paired():
    n = int(os.environ.get("PLATSIM_STRENGTH_N", "2000"))
    workers = int(os.environ.get("PLATSIM_STRENGTH_WORKERS", str(os.cpu_count() or 1)))
    outcomes, timing, hello = _paired(_team(), POLICIES, n, MASTER, workers)
    pairs = [("expectimax2-v1", "greedy-v1"), ("expectimax2-v2", "greedy-v1"), ("expectimax2-v2", "expectimax2-v1")]
    text, cmps = _report("T056 policy strength", n, MASTER, workers, hello, outcomes, timing, pairs)
    print(text)
    for pair in pairs[:2]:
        assert cmps[pair].verdict == "A" and cmps[pair].p_value < 0.05, text


def test_expectimax2_v2_not_worse_than_greedy_on_reversal_team():
    n = int(os.environ.get("PLATSIM_REVERSAL_N", "400"))
    workers = int(os.environ.get("PLATSIM_STRENGTH_WORKERS", str(os.cpu_count() or 1)))
    team = json.loads(REVERSAL_FIXTURE.read_text())["team"]
    outcomes, timing, hello = _paired(team, ("greedy-v1", "expectimax2-v2"), n, REVERSAL_MASTER, workers)
    text, cmps = _report("policy reversal team", n, REVERSAL_MASTER, workers, hello, outcomes, timing,
                         [("expectimax2-v2", "greedy-v1")])
    print(text)
    cmp = cmps[("expectimax2-v2", "greedy-v1")]
    assert not (cmp.verdict == "B" and cmp.p_value < 0.05), text
