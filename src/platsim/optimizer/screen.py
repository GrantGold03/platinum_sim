"""Successive-halving screen over candidate teams (T063; research.md R8 "Search" step 2 and
"Policy per stage": screening uses `greedy-v1`).

- All candidates play at the SAME start-level vector and on the SAME seeds (paired, FR-019).
- Round r adds `rounds[r]` new gauntlets per surviving candidate (preset: standard 100 -> 200 -> 400,
  thorough 200 -> 400 -> 800, quick 50 -> 100 -> 200). Run index i of the screen uses request seed
  derive_seed(f"{seed}|screen", i, 0); round r uses indices [sum(rounds[:r]), sum(rounds[:r+1])), so
  survivors accumulate 100, 300, 700 paired runs (standard).
- Score = (gauntlets cleared, battles won) summed over all runs so far, higher is better; ties go to the
  lower candidate index (deterministic). Battles won breaks ties because greedy-v1 is weak and many
  candidates may clear rarely at the screening level.
- After each round the top third is kept (ceil(n/3), at least 2: the confirm stage needs a winner and a
  runner-up). After the last round the two best are the finalists.
- `stop_on_loss` true, `log` "none", opponent `decomp-ai`. Results are consumed in request order, so the
  outcome does not depend on the number of workers.

Screening ranks; it never qualifies a team. Qualification and every reported rate use expectimax2-v1
(levels.py, run.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from platsim.sim.seeds import derive_seed

SCREEN_POLICY = "greedy-v1"
OPPONENT_POLICY = "decomp-ai"


@dataclass
class ScreenResult:
    order: list[int]  # final ranking of the last round's survivors (candidate indices), best first
    scores: dict[int, tuple[int, int, int]]  # candidate -> (cleared, battles won, runs)
    rounds: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"order": self.order, "scores": {str(k): list(v) for k, v in self.scores.items()},
                "rounds": self.rounds}

    @classmethod
    def from_dict(cls, d: dict) -> ScreenResult:
        return cls(list(d["order"]), {int(k): tuple(v) for k, v in d["scores"].items()}, list(d["rounds"]))


def successive_halving(pool, teams: list[list[dict]], *, seed: str, rounds: tuple[int, ...], progress=None) -> ScreenResult:
    """`teams`: worker teams (evaluate.worker_team output), one per candidate."""
    master = f"{seed}|screen"
    alive = list(range(len(teams)))
    scores = {i: (0, 0, 0) for i in alive}
    trace = []
    start = 0
    planned = sum(r * max(2, math.ceil(len(teams) / 3 ** k)) for k, r in enumerate(rounds))
    done = 0
    for r, n in enumerate(rounds):
        idx = range(start, start + n)
        reqs = [{"op": "gauntlet", "team": teams[c], "seed": derive_seed(master, i, 0), "player_policy": SCREEN_POLICY,
                 "opponent_policy": OPPONENT_POLICY, "stop_on_loss": True, "log": "none"} for c in alive for i in idx]
        res = pool.map(reqs)
        for k, c in enumerate(alive):
            chunk = res[k * n:(k + 1) * n]
            for x in chunk:
                if not x.get("ok"):
                    raise RuntimeError(f"screen gauntlet failed: {x.get('error')}")
                if (x["player_policy"], x["opponent_policy"]) != (SCREEN_POLICY, OPPONENT_POLICY):
                    raise RuntimeError(f"worker ran {x['player_policy']}/{x['opponent_policy']}")
            cl = sum(bool(x["cleared"]) for x in chunk)
            bw = sum(sum(bool(b["won"]) for b in x["battles"]) for x in chunk)
            s = scores[c]
            scores[c] = (s[0] + cl, s[1] + bw, s[2] + n)
        done += n * len(alive)
        ranked = sorted(alive, key=lambda c: (-scores[c][0], -scores[c][1], c))
        keep = ranked if r == len(rounds) - 1 else ranked[:max(2, math.ceil(len(ranked) / 3))]
        trace.append({"round": r + 1, "runs_this_round": n, "run_indices": [start, start + n - 1],
                      "candidates": len(alive), "kept": keep,
                      "ranking": [[c, *scores[c]] for c in ranked]})
        if progress:
            progress(done, planned, ranked[0], scores[ranked[0]], r + 1)
        alive = keep
        start += n
    return ScreenResult(alive, scores, trace)


__all__ = ["SCREEN_POLICY", "ScreenResult", "successive_halving"]
