"""Cynthia top-up (T057; FR-017, FR-018, SC-003; research.md R8 "Champion share").

With `stop_on_loss`, only runs that beat all four Elite Four members reach Cynthia, so the full
runs alone give her the fewest battles. `champion_topup` fixes that:

1. From the full gauntlet results of one candidate (worker responses, `log` "summary" or
   "full", in run order) it counts every trainer's battles and collects the `state_before` of
   every Cynthia battle.
2. If no full run reached Cynthia it returns `status="no_reach"` and runs nothing: a start state
   is never invented.
3. Otherwise it runs Cynthia-only gauntlets (`trainers: ["cynthia"]`, op 4 `start_state`).
   - Top-up k uses request seed `derive_seed(master, k, 99)`; battle index 99 is reserved for
     the top-up (seeds.py), so these never collide with full-run seeds.
   - Its start state is drawn with replacement from the collected states. The index is
     `int(sha256(f"{master}|{k}|99|start_state")) % len(states)`: deterministic, independent of
     batching and worker count.
   - Policies are taken from the full results (they must all agree) so the top-up plays the same
     matchup.
4. Cynthia's count is her full-run battles plus the top-up battles (data-model.md
   `champion_battles`). Top-ups are consumed in index order and it stops at the FIRST k where
   both hold:
   - Wilson half-width <= the budget preset's `ci_half_width` (`quick` has no target, so only
     the count rule applies there);
   - her battle count > every other trainer's battle count in the full runs.
   Batches may compute a few extra battles past that point; they are discarded, so the result
   does not depend on batch size or the number of workers.
5. Top-up battles are capped at `max_topup` (default MAX_TOPUP_BATTLES). If the cap is reached
   first, `status="cap_hit"` and `target_met=False`; the target is never claimed.

The returned rate is P(win | reached Cynthia). It is NOT the gauntlet clear rate, which comes
from the full runs only.

The caller must pass the same `team` that produced `full_results`; the worker responses do not
echo the team, so this module cannot check it.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import asdict, dataclass, field

from platsim.budget import get_preset
from platsim.sim.seeds import SCHEME, derive_seed
from platsim.stats import runs_needed, wilson_ci, wilson_half_width

CHAMPION = "cynthia"
TOPUP_BATTLE_INDEX = 99  # reserved in seeds.py
# Documented maximum of top-up battles per candidate. Worst case for the CI rule is p = 0.5:
# runs_needed(0.5, 0.015) = 4,268 (thorough) and runs_needed(0.5, 0.02) = 2,401 (standard). The
# count rule needs more than the busiest Elite Four member, i.e. more than the full-run count
# (>= 5,000 for thorough confirm). 50,000 is 10x the thorough confirm minimum; hitting it is
# reported as `cap_hit`, never as the target being met.
MAX_TOPUP_BATTLES = 50_000
MIN_BATCH = 64


class ChampionTopupError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChampionResult:
    status: str  # "met" | "cap_hit" | "no_reach"
    budget_preset: str
    target_half_width: float | None  # None for `quick`
    master_seed: str
    seed_scheme: str
    player_policy: str
    opponent_policy: str
    reached: int  # full runs that reached Cynthia (= her full-run battles)
    full_wins: int
    topup_battles: int
    topup_wins: int
    battles: int  # full + top-up, the reported `champion_battles`
    wins: int
    rate: float | None  # P(win | reached Cynthia); None when nobody reached her
    ci95: tuple[float, float] | None
    half_width: float | None
    other_battles: dict[str, int] = field(default_factory=dict)  # full-run counts per E4 member
    max_topup: int = MAX_TOPUP_BATTLES
    ci_target_met: bool | None = None  # None when the preset has no target or nobody reached her
    count_rule_met: bool = False
    target_met: bool = False  # both rules held (never True when status is cap_hit / no_reach)
    cap_hit: bool = False
    distinct_start_states: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ci95"] = list(self.ci95) if self.ci95 else None
        return d


def _start_index(master: str, k: int, n_states: int) -> int:
    h = hashlib.sha256(f"{master}|{k}|{TOPUP_BATTLE_INDEX}|start_state".encode("utf-8")).hexdigest()
    return int(h, 16) % n_states


def _one_policy(values: set, what: str) -> str:
    if len(values) != 1:
        raise ChampionTopupError(f"full results mix {what}s: {sorted(map(str, values))}")
    return next(iter(values))


def _summarise_full(full_results: list[dict]):
    counts: Counter[str] = Counter()
    wins = 0
    states: list[dict] = []
    players, opponents = set(), set()
    for i, r in enumerate(full_results):
        if not r.get("ok"):
            raise ChampionTopupError(f"full result {i} is an error response: {r.get('error')}")
        players.add(r.get("player_policy"))
        opponents.add(r.get("opponent_policy"))
        for b in r["battles"]:
            counts[b["trainer"]] += 1
            if b["trainer"] == CHAMPION:
                if "state_before" not in b:
                    raise ChampionTopupError(f"full result {i}: Cynthia battle has no state_before "
                                             "(run the full gauntlets with log 'summary' or 'full')")
                states.append(b["state_before"])
                wins += bool(b["won"])
    return counts, wins, states, _one_policy(players, "player_policy"), _one_policy(opponents, "opponent_policy")


def champion_topup(pool, team: list[dict], full_results: list[dict], *, master_seed: str | int,
                   budget: str, max_topup: int = MAX_TOPUP_BATTLES) -> ChampionResult:
    """Run the Cynthia top-up for one candidate. `pool` is a `WorkerPool` (anything with `map`)."""
    if not full_results:
        raise ChampionTopupError("no full results")
    if max_topup < 0:
        raise ValueError(f"max_topup must be >= 0, got {max_topup}")
    preset = get_preset(budget)
    target = preset.ci_half_width
    master = str(master_seed)
    counts, full_wins, states, player_policy, opponent_policy = _summarise_full(full_results)
    reached = counts.get(CHAMPION, 0)
    others = {t: c for t, c in sorted(counts.items()) if t != CHAMPION}
    count_bar = max(others.values(), default=0)  # her count must exceed this
    base = dict(budget_preset=preset.name, target_half_width=target, master_seed=master, seed_scheme=SCHEME,
                player_policy=player_policy, opponent_policy=opponent_policy, reached=reached,
                full_wins=full_wins, other_battles=others, max_topup=max_topup)

    if reached == 0:
        return ChampionResult(status="no_reach", topup_battles=0, topup_wins=0, battles=0, wins=0,
                              rate=None, ci95=None, half_width=None, **base)

    def rules(w: int, n: int) -> tuple[bool | None, bool]:
        ci_ok = None if target is None else wilson_half_width(w, n) <= target
        return ci_ok, n > count_bar

    def request(k: int) -> dict:
        return {"op": "gauntlet", "team": team, "seed": derive_seed(master, k, TOPUP_BATTLE_INDEX),
                "player_policy": player_policy, "opponent_policy": opponent_policy,
                "trainers": [CHAMPION], "start_state": states[_start_index(master, k, len(states))],
                "stop_on_loss": True, "log": "none"}

    n, w, k = reached, full_wins, 0
    ci_ok, count_ok = rules(w, n)
    done = ci_ok is not False and count_ok
    while not done and k < max_topup:
        # Size the next batch from what the rules still need at the current estimate.
        need = count_bar + 1 - n
        if target is not None:
            p_hat = min(max(w / n, 0.0), 1.0)
            need = max(need, runs_needed(p_hat, target) - n)
        size = min(max(need, MIN_BATCH), max_topup - k)
        resps = pool.map([request(k + j) for j in range(size)])
        for resp in resps:
            if not resp.get("ok"):
                raise ChampionTopupError(f"top-up {k} failed: {resp.get('error')}")
            if (resp.get("player_policy"), resp.get("opponent_policy")) != (player_policy, opponent_policy):
                raise ChampionTopupError(f"top-up {k} ran with policies {resp.get('player_policy')!r}/"
                                         f"{resp.get('opponent_policy')!r}, full runs used "
                                         f"{player_policy!r}/{opponent_policy!r}")
            (b,) = resp["battles"]
            if b["trainer"] != CHAMPION:
                raise ChampionTopupError(f"top-up {k} fought {b['trainer']!r}, not {CHAMPION}")
            k += 1
            n += 1
            w += bool(b["won"])
            ci_ok, count_ok = rules(w, n)
            if ci_ok is not False and count_ok:
                done = True
                break

    return ChampionResult(
        status="met" if done else "cap_hit", topup_battles=k, topup_wins=w - full_wins, battles=n, wins=w,
        rate=w / n, ci95=wilson_ci(w, n), half_width=wilson_half_width(w, n), ci_target_met=ci_ok,
        count_rule_met=count_ok, target_met=done, cap_hit=not done,
        distinct_start_states=len({_start_index(master, j, len(states)) for j in range(k)}), **base)


__all__ = ["CHAMPION", "MAX_TOPUP_BATTLES", "ChampionResult", "ChampionTopupError", "TOPUP_BATTLE_INDEX",
           "champion_topup"]
