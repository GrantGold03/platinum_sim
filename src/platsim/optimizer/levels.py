"""Start-level search (T064; spec FR-015, FR-016; research.md R8 "Search" step 3, "Qualification rule",
"Policy per stage": the level search uses the strong player, now `expectimax2-v2`).

Level vectors
-------------
`floors[i]` is member i's lowest legal start level (resources.member_floor: source minimum level and
every move legal). At uniform level U the vector is L_i(U) = max(U, floors[i]). U is searched in
[max(1, max(floors) - 10), 100] so the START gap is at most 10 (a heuristic bound: the FINAL gap, the
real constraint, is checked on simulated final levels).

Testing one level vector (`LevelSearch.test`)
---------------------------------------------
Full gauntlets with expectimax2-v2 vs decomp-ai, stop_on_loss. Run i uses request seed
derive_seed(f"{seed}|levels", i, 0) for EVERY vector, so all points are paired. Runs are added in
order: first `n0`, then doubling up to `cap` (standard 200 -> 800, thorough 400 -> 1,600, quick
50 -> 100). After each batch:
  - FAIL(gap) if some cleared run's final level gap (max - min) exceeds 10 (FR-016; same statistic as
    the confirm stage's `final_level_gap_max`);
  - PASS if the Wilson 95% lower bound >= threshold;
  - FAIL if the Wilson upper bound < threshold;
  - at the cap: PASS iff the clear rate >= threshold + margin (margin = the preset CI target, 0.02 for
    quick/standard, 0.015 thorough) - borderline points (R8) are resolved conservatively so that the
    confirm stage (>= 2,000 runs) is likely to qualify; otherwise FAIL.
The decision for a vector depends only on in-order results, so it is independent of worker count.
Every tested point is memoised (team spec + levels -> n, wins, gap, mean final average level,
decision) and checkpointed by the caller, so a resumed job does not re-run points.

Search
------
1. Bisection on U: probe the start U0 (the screening level); gallop upward (+4, +8, ...) until a PASS
   (U = 100 failing means no qualifying team in the search bounds), or downward until a FAIL, then
   bisect to the lowest passing U (pass/fail assumed monotone in U).
2. Per-member descent ("water-filling"): repeatedly take the member with the HIGHEST current start
   level (ties: lowest slot) that is not frozen and above its floor, and test the vector with that member
   one level lower (start gap kept <= 10). PASS: keep it. FAIL: freeze that member at its level. Stop
   when every member is frozen or at its floor. Lowering the highest member first keeps the team
   balanced, which matters because the FINAL gap (<= 10) binds: a first version that bisected members one
   at a time in slot order let early members drop far and then blocked later ones on the gap (observed in
   the quick smoke run, 2026-10-07).
The objective (FR-016) is the expected final average level; lowering a start level never raises the
final levels of the others' share, so the search minimises start levels under the PASS rule, and every
PASS point records its simulated mean final average level. The final pick is re-checked by the
confirm stage (run.py) with >= the preset's confirm runs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from platsim.sim.seeds import derive_seed
from platsim.stats import wilson_ci

POLICY = "expectimax2-v3"  # 007 T065 (was expectimax2-v2; v1 before the policy-reversal fix)
OPPONENT_POLICY = "decomp-ai"
MAX_GAP = 10
LEVEL_RUNS = {"standard": (200, 800), "thorough": (400, 1600), "quick": (50, 100)}


@dataclass
class Point:
    levels: list[int]
    n: int
    wins: int
    gap: int | None  # max final-level gap over cleared runs
    avg_final: float | None  # mean final average level over cleared runs
    decision: str  # pass | fail | fail_gap

    @property
    def rate(self) -> float:
        return self.wins / self.n if self.n else 0.0

    @property
    def passed(self) -> bool:
        return self.decision == "pass"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rate"] = self.rate
        d["ci95"] = list(wilson_ci(self.wins, self.n))
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Point:
        return cls(list(d["levels"]), d["n"], d["wins"], d["gap"], d["avg_final"], d["decision"])


def team_key(spec_json: list[dict]) -> str:
    return hashlib.sha256(json.dumps(spec_json, sort_keys=True).encode()).hexdigest()[:16]


class LevelSearch:
    """`build(levels) -> worker team | None` turns a level vector into a worker team (None: illegal at
    those levels). `memo` is a dict persisted by the caller; `on_point(point)` is called after every
    new point (checkpoint + progress)."""

    def __init__(self, pool, build, floors: list[int], *, seed: str, budget: str, threshold: float, margin: float,
                 key: str, memo: dict, on_point=None, on_batch=None):
        self.pool, self.build, self.floors = pool, build, list(floors)
        self.master = f"{seed}|levels"
        self.n0, self.cap = LEVEL_RUNS[budget]
        self.threshold, self.margin, self.key = threshold, margin, key
        self.memo, self.on_point, self.on_batch = memo, on_point, on_batch
        self.points: list[Point] = []

    # -- one vector -----------------------------------------------------------------------------
    def vector(self, u: int) -> list[int]:
        return [max(u, f) for f in self.floors]

    def _decide(self, w: int, n: int, gap: int | None, final: bool) -> str | None:
        if gap is not None and gap > MAX_GAP:
            return "fail_gap"
        lo, hi = wilson_ci(w, n)
        if lo >= self.threshold:
            return "pass"
        if hi < self.threshold:
            return "fail"
        if final:
            return "pass" if w / n >= self.threshold + self.margin else "fail"
        return None

    def test(self, levels: list[int]) -> Point:
        levels = [int(x) for x in levels]
        mk = f"{self.key}|{','.join(map(str, levels))}"
        if mk in self.memo:
            p = Point.from_dict(self.memo[mk])
            self.points.append(p)
            return p
        team = self.build(levels)
        if team is None:
            p = Point(levels, 0, 0, None, None, "fail_illegal")
        else:
            results: list[dict] = []
            n_target = self.n0
            decision = None
            while decision is None:
                reqs = [{"op": "gauntlet", "team": team, "seed": derive_seed(self.master, i, 0), "player_policy": POLICY,
                         "opponent_policy": OPPONENT_POLICY, "stop_on_loss": True, "log": "none"}
                        for i in range(len(results), n_target)]
                for r in self.pool.map(reqs):
                    if not r.get("ok"):
                        raise RuntimeError(f"level-search gauntlet failed: {r.get('error')}")
                    if (r["player_policy"], r["opponent_policy"]) != (POLICY, OPPONENT_POLICY):
                        raise RuntimeError(f"worker ran {r['player_policy']}/{r['opponent_policy']}")
                    results.append(r)
                w = sum(bool(r["cleared"]) for r in results)
                cleared = [r["final_levels"] for r in results if r["cleared"]]
                gap = max((max(fl) - min(fl) for fl in cleared), default=None)
                if self.on_batch:
                    self.on_batch(levels, len(results), w)
                decision = self._decide(w, len(results), gap, len(results) >= self.cap)
                n_target = min(self.cap, n_target * 2)
            avg = sum(sum(fl) / len(fl) for fl in cleared) / len(cleared) if cleared else None
            p = Point(levels, len(results), w, gap, avg, decision)
        self.memo[mk] = p.to_dict()
        self.points.append(p)
        if self.on_point:
            self.on_point(p)
        return p

    # -- search ---------------------------------------------------------------------------------
    def bisect_uniform(self, u0: int) -> tuple[int | None, Point | None]:
        """Lowest passing U (and its point), or (None, None) if U = 100 fails."""
        lo_bound = max(1, max(self.floors) - MAX_GAP)
        u0 = min(100, max(lo_bound, u0))
        cache: dict[int, Point] = {}

        def t(u: int) -> Point:
            if u not in cache:
                cache[u] = self.test(self.vector(u))
            return cache[u]

        if t(u0).passed:
            pass_u, fail_u = u0, None
            step = 4
            while fail_u is None:
                u = pass_u - step
                if u < lo_bound:
                    fail_u = lo_bound - 1
                    break
                if t(u).passed:
                    pass_u, step = u, step * 2
                else:
                    fail_u = u
        else:
            fail_u, pass_u = u0, None
            step = 4
            while pass_u is None:
                u = min(100, fail_u + step)
                if t(u).passed:
                    pass_u = u
                elif u == 100:
                    return None, None
                else:
                    fail_u, step = u, step * 2
        while pass_u - fail_u > 1:
            mid = (pass_u + fail_u) // 2
            if t(mid).passed:
                pass_u = mid
            else:
                fail_u = mid
        return pass_u, cache[pass_u]

    def descend(self, levels: list[int], point: Point) -> tuple[list[int], Point, list[dict]]:
        levels = list(levels)
        best = point
        trace = []
        frozen: set[int] = set()
        while True:
            open_ = [i for i in range(len(levels)) if i not in frozen and levels[i] > self.floors[i]]
            if not open_:
                break
            i = max(open_, key=lambda j: (levels[j], -j))
            cand = list(levels)
            cand[i] -= 1
            if max(cand) - min(cand) > MAX_GAP:
                frozen.add(i)
                trace.append({"slot": i + 1, "level": levels[i], "result": "frozen: start gap would exceed 10"})
                continue
            p = self.test(cand)
            trace.append({"slot": i + 1, "try": cand[i], "levels": cand, "decision": p.decision})
            if p.passed:
                levels, best = cand, p
            else:
                frozen.add(i)
        return levels, best, trace


__all__ = ["LEVEL_RUNS", "LevelSearch", "POLICY", "Point", "team_key"]
