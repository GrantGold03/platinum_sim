"""Adaptive Elite Four sampling for `platsim evaluate` (feature 021; specs/021-adaptive-e4-sampling/).

Full gauntlets run in request-seed index order until every Elite Four member's pass rate is proven (Wilson 95%
lower bound at or above `floor`); every full run that reaches Cynthia banks her `state_before`; the remaining runs
are Cynthia-only battles from banked states, drawn deterministically from the run index and the master seed with the
reserved battle index 98 (the top-up keeps 99). The clear rate becomes the Elite Four pass rate times Cynthia's
conditional win rate with a log-scale delta-method 95% interval (research R4). Results computed past the switch are
discarded so the result cannot depend on chunk size or worker count (R3). When the floor is never reached every run
is a full gauntlet and `evaluate` keeps the full method's statistics (FR-006).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

from platsim.sim.seeds import derive_seed
from platsim.stats import Z95, runs_needed, wilson_ci, wilson_half_width

E4 = ("aaron", "bertha", "flint", "lucian")
CHAMPION = "cynthia"
CYNTHIA_ONLY_BATTLE_INDEX = 98  # reserved in seeds.py; the top-up uses 99
MIN_BATCH = 64
DEFAULT_FLOOR = 0.98  # user decision 2026-11-03 after the 021 acceptance (0.99 switched only on the strongest team)
DEFAULT_SAMPLING = "adaptive"  # evaluate's default since 021 (user's go); evaluate_team keeps "full" for the optimizer's stages
FLOOR_MIN, FLOOR_MAX = 0.9, 1.0


# ---- pure functions -------------------------------------------------------------------------------------------

def cynthia_battle(result: dict) -> dict | None:
    for b in result["battles"]:
        if b["trainer"] == CHAMPION:
            return b
    return None


def switch_index(results: list[dict], floor: float, members=E4) -> int | None:
    """First k (count of runs consumed, in order) after which every member has been faced at least once and its
    Wilson 95% lower bound (won / faced) is at or above `floor`; None if never."""
    faced = {m: 0 for m in members}
    won = {m: 0 for m in members}
    for k, r in enumerate(results, start=1):
        for b in r["battles"]:
            t = b["trainer"]
            if t in faced:
                faced[t] += 1
                won[t] += bool(b["won"])
        if all(faced[m] > 0 and wilson_ci(won[m], faced[m], Z95)[0] >= floor for m in members):
            return k
    return None


def start_index(master: str, k: int, battle_index: int, n: int) -> int:
    """Which banked state Cynthia-only run k uses: the top-up's rule generalised (champion.py uses 99)."""
    if n <= 0:
        raise ValueError("no banked states")
    h = hashlib.sha256(f"{master}|{k}|{battle_index}|start_state".encode("utf-8")).hexdigest()
    return int(h, 16) % n


def e4_pass_stats(full_results: list[dict]) -> tuple[int, int]:
    """(full runs that reached Cynthia, full runs)."""
    return sum(1 for r in full_results if cynthia_battle(r) is not None), len(full_results)


def delta_interval(p1: float, n1: int, p2: float, n2: int, z: float = Z95) -> tuple[float, float]:
    """Log-scale delta method for a product of two independent proportions; [0, 0] when either is 0."""
    if p1 <= 0 or p2 <= 0 or n1 <= 0 or n2 <= 0:
        return (0.0, 0.0)
    var = (1 - p1) / (n1 * p1) + (1 - p2) / (n2 * p2)
    est = p1 * p2
    s = math.sqrt(var)
    return (est * math.exp(-z * s), min(1.0, est * math.exp(z * s)))


@dataclass(frozen=True)
class CompositeEstimate:
    reached: int
    full_runs: int
    cyn_wins: int
    cyn_battles: int
    e4_pass: float
    e4_ci95: tuple[float, float]
    cyn_rate: float
    estimate: float
    ci95: tuple[float, float]
    half_width: float


def composite_estimate(reached: int, full_runs: int, cyn_wins: int, cyn_battles: int) -> CompositeEstimate:
    e4 = reached / full_runs if full_runs else 0.0
    cyn = cyn_wins / cyn_battles if cyn_battles else 0.0
    ci = delta_interval(e4, full_runs, cyn, cyn_battles)
    return CompositeEstimate(reached, full_runs, cyn_wins, cyn_battles, e4,
                             wilson_ci(reached, full_runs) if full_runs else (0.0, 0.0), cyn, e4 * cyn, ci,
                             (ci[1] - ci[0]) / 2)


def extension_kind(reached: int, full_runs: int, cyn_wins: int, cyn_battles: int, target: float,
                   floor_met: bool) -> str:
    """Which kind of run the half-width extension should add next (research R5): "cynthia_only" while Cynthia-only
    runs can still bring the composite half-width under `target` (the half-width with Cynthia's variance term set to
    zero is below it), otherwise "full"."""
    if not floor_met or full_runs == 0 or reached == 0 or cyn_battles == 0:
        return "full"
    e4 = reached / full_runs
    cyn = cyn_wins / cyn_battles
    if e4 >= 1.0:  # the Elite Four part carries no variance in the delta model; only Cynthia's term remains
        return "cynthia_only"
    var_e4 = (1 - e4) / (full_runs * e4)
    s = math.sqrt(var_e4)
    hw_floor = e4 * cyn * (math.exp(Z95 * s) - math.exp(-Z95 * s)) / 2
    return "cynthia_only" if hw_floor < target else "full"


def cynthia_only_request(team: list[dict], master: str, k: int, bank: list[dict], player_policy: str,
                         opponent_policy: str, battle_style: str = "set") -> dict:
    return {"op": "gauntlet", "team": team, "seed": derive_seed(master, k, CYNTHIA_ONLY_BATTLE_INDEX),
            "player_policy": player_policy, "opponent_policy": opponent_policy, "trainers": [CHAMPION],
            "start_state": bank[start_index(master, k, CYNTHIA_ONLY_BATTLE_INDEX, len(bank))],
            "stop_on_loss": True, "log": "summary", "battle_style": battle_style}


# ---- pool-driving ---------------------------------------------------------------------------------------------

@dataclass
class AdaptiveRuns:
    full_results: list[dict]
    cynthia_only_results: list[dict]
    switch_run: int | None
    discarded: int
    bank: list[dict]
    extension: dict = field(default_factory=lambda: {"full": 0, "cynthia_only": 0})
    target_met: bool | None = None
    discarded_cynthia_only: int = 0
    borderline_extended: bool = False  # 022: runs were added while the interval straddled the threshold

    @property
    def n_runs(self) -> int:
        return len(self.full_results) + len(self.cynthia_only_results)


def _log(msg: str) -> None:
    import sys
    print(f"platsim evaluate [adaptive]: {msg}", file=sys.stderr, flush=True)


def run_adaptive(pool, team: list[dict], *, master: str, min_runs: int, max_runs: int, target: float | None,
                 player_policy: str, floor: float, opponent_policy: str = "decomp-ai", on_batch=None,
                 borderline_threshold: float | None = None, borderline_max_runs: int | None = None,
                 battle_style: str = "set") -> AdaptiveRuns:
    """The adaptive run loop (021 research R3, R5). `pool` needs `.map(requests)` and `.size`. Feature 022:
    `borderline_threshold` adds runs while the interval straddles it (the optimizer's confirm stage), up to
    `min(max_runs, borderline_max_runs)`, choosing each batch's kind by the extension rule and stopping at the first run
    after which the interval no longer straddles (the rest discarded)."""
    if not FLOOR_MIN <= floor <= FLOOR_MAX:
        raise ValueError(f"floor must be in [{FLOOR_MIN}, {FLOOR_MAX}], got {floor}")
    chunk = max(MIN_BATCH, getattr(pool, "size", 1) * 8)
    faced = {m: 0 for m in E4}
    won = {m: 0 for m in E4}
    full: list[dict] = []
    cyn: list[dict] = []
    bank: list[dict] = []
    switch: int | None = None
    discarded = 0
    discarded_cyn = 0
    next_full = 0  # next full-run request index
    next_cyn = 0  # next Cynthia-only run counter
    extension = {"full": 0, "cynthia_only": 0}

    def full_req(i: int) -> dict:
        return {"op": "gauntlet", "team": team, "seed": derive_seed(master, i, 0), "player_policy": player_policy,
                "opponent_policy": opponent_policy, "stop_on_loss": True, "log": "summary", "battle_style": battle_style}

    def check(r: dict, what: str) -> None:
        if not r.get("ok"):
            raise RuntimeError(f"{what} failed: {r.get('error')}")
        if r.get("battle_style", "set") != battle_style:  # 023
            raise RuntimeError(f"worker played {r.get('battle_style', 'set')}, requested {battle_style}")
        if (r["player_policy"], r["opponent_policy"]) != (player_policy, opponent_policy):
            raise RuntimeError(f"worker ran {r['player_policy']}/{r['opponent_policy']}, requested "
                               f"{player_policy}/{opponent_policy}")

    def proven() -> bool:
        return all(faced[m] > 0 and wilson_ci(won[m], faced[m], Z95)[0] >= floor for m in E4)

    def consume_full(r: dict) -> None:
        """Count one full run (in order): counters, bank."""
        nonlocal next_full
        full.append(r)
        next_full += 1
        for b in r["battles"]:
            t = b["trainer"]
            if t in faced:
                faced[t] += 1
                won[t] += bool(b["won"])
        cb = cynthia_battle(r)
        if cb is not None:
            if "state_before" not in cb:
                raise RuntimeError("Cynthia battle without state_before (log mode must be summary)")
            bank.append(cb["state_before"])

    def cyn_stats() -> tuple[int, int]:
        wins = sum(bool(cynthia_battle(r)["won"]) for r in full if cynthia_battle(r) is not None)
        wins += sum(bool(r["battles"][0]["won"]) for r in cyn)
        battles = sum(1 for r in full if cynthia_battle(r) is not None) + len(cyn)
        return wins, battles

    def current_stats() -> tuple[float, float, float]:
        """(estimate, lower, upper) of the current interval: Wilson before a switch, the composite after."""
        if switch is None:
            wins = sum(bool(r["cleared"]) for r in full)
            if not full:
                return 0.0, 0.0, 1.0
            lo, hi = wilson_ci(wins, len(full))
            return wins / len(full), lo, hi
        reached, n_full = e4_pass_stats(full)
        w, b = cyn_stats()
        c = composite_estimate(reached, n_full, w, b)
        return c.estimate, c.ci95[0], c.ci95[1]

    def current_hw() -> float:
        est, lo, hi = current_stats()
        return (hi - lo) / 2

    # Phase A: full gauntlets until the switch or min_runs
    while switch is None and len(full) < min_runs:
        size = min(chunk, min_runs - len(full))
        rs = pool.map([full_req(i) for i in range(next_full, next_full + size)])
        for r in rs:
            check(r, "gauntlet")
            if switch is None:
                consume_full(r)
                if proven():
                    switch = len(full)
            else:
                discarded += 1
        if on_batch:
            on_batch(len(full) + len(cyn), sum(bool(r["cleared"]) for r in full))
    if switch is not None:
        _log(f"Elite Four proven after {switch} full runs (floor {floor}); {len(bank)} banked states; "
             f"{discarded} results past the switch discarded")

    def run_cyn(count: int, stop_when_target_met: bool) -> int:
        """Request `count` Cynthia-only runs in order; returns the number counted."""
        nonlocal next_cyn, discarded_cyn
        rs = pool.map([cynthia_only_request(team, master, next_cyn + j, bank, player_policy, opponent_policy, battle_style)
                       for j in range(count)])
        counted = 0
        done = False
        for r in rs:
            check(r, "Cynthia-only run")
            (b,) = r["battles"]
            if b["trainer"] != CHAMPION:
                raise RuntimeError(f"Cynthia-only run fought {b['trainer']!r}")
            if done:
                discarded_cyn += 1
                continue
            cyn.append(r)
            next_cyn += 1
            counted += 1
            if stop_when_target_met and target is not None and current_hw() <= target:
                done = True
        return counted

    # Phase B: Cynthia-only runs to min_runs
    while switch is not None and len(full) + len(cyn) < min_runs:
        size = min(chunk, min_runs - len(full) - len(cyn))
        run_cyn(size, stop_when_target_met=False)
        if on_batch:
            on_batch(len(full) + len(cyn), sum(bool(r["cleared"]) for r in full))

    # Extension to the half-width target (clarification 2 / R5)
    extended = False
    if target is not None:
        while current_hw() > target and len(full) + len(cyn) < max_runs:
            extended = True
            reached, n_full = e4_pass_stats(full)
            w, b = cyn_stats()
            kind = extension_kind(reached, n_full, w, b, target, switch is not None)
            room = max_runs - len(full) - len(cyn)
            if kind == "cynthia_only":
                size = min(max(MIN_BATCH, chunk), room)
                _log(f"half-width {current_hw():.4f} > {target}: adding up to {size} Cynthia-only runs")
                extension["cynthia_only"] += run_cyn(size, stop_when_target_met=True)
            else:
                wins = sum(bool(r["cleared"]) for r in full)
                p_hat = wins / len(full) if full else 0.5
                size = min(max(runs_needed(p_hat, target) - len(full), MIN_BATCH), room)
                _log(f"half-width {current_hw():.4f} > {target}: adding up to {size} full gauntlets")
                rs = pool.map([full_req(i) for i in range(next_full, next_full + size)])
                done = False
                for r in rs:
                    check(r, "gauntlet")
                    if done:
                        discarded += 1
                        continue
                    consume_full(r)
                    extension["full"] += 1
                    if switch is None and proven():
                        switch = len(full)
                        _log(f"Elite Four proven after {switch} full runs during the extension")
                        done = True  # the rest of the chunk is discarded; the loop re-decides the kind
                    elif current_hw() <= target:
                        done = True
            if on_batch:
                on_batch(len(full) + len(cyn), sum(bool(r["cleared"]) for r in full))
    # Borderline extension (022): while the interval straddles the threshold, up to the cap
    borderline_extended = False
    if borderline_threshold is not None:
        cap = max_runs if borderline_max_runs is None else min(max_runs, borderline_max_runs)

        def straddles() -> bool:
            _, lo, hi = current_stats()
            return lo < borderline_threshold <= hi

        while straddles() and len(full) + len(cyn) < cap:
            borderline_extended = True
            est, lo, hi = current_stats()
            reached, n_full = e4_pass_stats(full)
            w, b = cyn_stats()
            # the half-width that would stop the straddle: the estimate's distance from the threshold
            needed = max(abs(est - borderline_threshold), 1e-6)
            kind = extension_kind(reached, n_full, w, b, needed, switch is not None)
            total = len(full) + len(cyn)
            size = min(max(total // 2, MIN_BATCH), cap - total)
            _log(f"interval [{lo:.4f}, {hi:.4f}] straddles the threshold {borderline_threshold} at n={total}: "
                 f"adding up to {size} {'Cynthia-only runs' if kind == 'cynthia_only' else 'full gauntlets'}")
            if kind == "cynthia_only":
                rs = pool.map([cynthia_only_request(team, master, next_cyn + j, bank, player_policy, opponent_policy, battle_style)
                               for j in range(size)])
                done = False
                for r in rs:
                    check(r, "Cynthia-only run")
                    if done:
                        discarded_cyn += 1
                        continue
                    cyn.append(r)
                    next_cyn += 1
                    extension["cynthia_only"] += 1
                    if not straddles():
                        done = True
            else:
                rs = pool.map([full_req(i) for i in range(next_full, next_full + size)])
                done = False
                for r in rs:
                    check(r, "gauntlet")
                    if done:
                        discarded += 1
                        continue
                    consume_full(r)
                    extension["full"] += 1
                    if switch is None and proven():
                        switch = len(full)
                        _log(f"Elite Four proven after {switch} full runs during the borderline extension")
                        done = True
                    elif not straddles():
                        done = True
            if on_batch:
                on_batch(len(full) + len(cyn), sum(bool(r["cleared"]) for r in full))
        if straddles():
            _log(f"interval still straddles the threshold {borderline_threshold} at the cap n={len(full) + len(cyn)}: "
                 "borderline (not qualified)")
    target_met = None if target is None else current_hw() <= target
    return AdaptiveRuns(full, cyn, switch, discarded, bank, extension, target_met, discarded_cyn, borderline_extended)


__all__ = ["AdaptiveRuns", "CHAMPION", "CYNTHIA_ONLY_BATTLE_INDEX", "CompositeEstimate", "DEFAULT_FLOOR", "DEFAULT_SAMPLING", "E4",
           "FLOOR_MAX", "FLOOR_MIN", "composite_estimate", "cynthia_battle", "cynthia_only_request",
           "delta_interval", "e4_pass_stats", "extension_kind", "run_adaptive", "start_index", "switch_index"]
