"""T056: policy strength benchmark (research R7, spec FR-013, Constitution IV).

On the policy benchmark team (tests/fixtures/policy_benchmark_team.json) run N paired full-League gauntlets
(same seeds, `stop_on_loss` true, opponent policy `decomp-ai`) for the player policies
`greedy-v1` and `expectimax2-v1`, through the worker pool (src/platsim/sim/pool.py). The paired
clear outcomes are compared with the exact McNemar test (src/platsim/stats.py); the test passes
only if `expectimax2-v1` clears more often with p < 0.05. It never relabels a policy.

N defaults to 2,000 (the task's count). PLATSIM_STRENGTH_N overrides it for quick local checks;
the number used is printed. PLATSIM_STRENGTH_WORKERS sets the pool size (default os.cpu_count()).
Run with `-s` to see the report (rates, Wilson 95% CIs, discordant pairs, p-value, run time and
gauntlets/s per policy).
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
SPECIES = pins.REPO_ROOT / "data" / "generated" / "species.json"
POLICIES = ("greedy-v1", "expectimax2-v1")
OPPONENT = "decomp-ai"
MASTER = "t056-policy-strength"


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


def test_expectimax2_beats_greedy_paired():
    n = int(os.environ.get("PLATSIM_STRENGTH_N", "2000"))
    workers = int(os.environ.get("PLATSIM_STRENGTH_WORKERS", str(os.cpu_count() or 1)))
    team = _team()
    seeds = [derive_seed(MASTER, i, 0) for i in range(n)]
    outcomes: dict[str, list[bool]] = {}
    timing: dict[str, float] = {}
    with WorkerPool(workers) as pool:
        assert set(POLICIES) <= set(pool.hello["policies"])
        assert OPPONENT in pool.hello["opponent_policies"]
        for pol in POLICIES:
            reqs = [{"op": "gauntlet", "id": f"{pol}-{i}", "team": team, "seed": s, "player_policy": pol,
                     "opponent_policy": OPPONENT, "stop_on_loss": True, "log": "none"} for i, s in enumerate(seeds)]
            t0 = time.perf_counter()
            res = pool.map(reqs)
            timing[pol] = time.perf_counter() - t0
            assert all(r["ok"] for r in res), [r for r in res if not r["ok"]][:3]
            assert all(r["player_policy"] == pol and r["opponent_policy"] == OPPONENT for r in res)
            # paired: battle 1 of request i used the same seed (sim/gauntlet.mjs deriveSeed(seed, 0, 0)) for both policies
            assert [r["battles"][0]["seed"] for r in res] == [derive_seed(s, 0, 0) for s in seeds]
            outcomes[pol] = [bool(r["cleared"]) for r in res]
        hello = pool.hello

    cmp = mcnemar_exact(outcomes["expectimax2-v1"], outcomes["greedy-v1"])
    lines = [f"T056 policy strength: n={n} paired gauntlets, opponent={OPPONENT}, workers={workers}, "
             f"seed master={MASTER!r}, decomp={hello['decomp_commit'][:12]}, showdown={hello['showdown_commit'][:12]}"]
    for pol in POLICIES:
        k = sum(outcomes[pol])
        lo, hi = wilson_ci(k, n)
        lines.append(f"  {pol:15s} cleared {k}/{n} = {k / n:.4f}  Wilson95 [{lo:.4f}, {hi:.4f}]  "
                     f"time {timing[pol]:.1f}s  {n / timing[pol]:.2f} gauntlets/s")
    lines.append(f"  McNemar exact: expectimax2-only={cmp.a_only} greedy-only={cmp.b_only} p={cmp.p_value:.3g} "
                 f"verdict={cmp.verdict}")
    print("\n".join(lines))
    assert cmp.verdict == "A" and cmp.p_value < 0.05, "\n".join(lines)
