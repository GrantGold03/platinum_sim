"""Loss causes (T069; spec User Story 2 "which Champion Pokemon most often cause losses";
data-model.md EvaluationReport `loss_causes`).

For every lost battle we record which opponent Pokemon were on the field at the moment the
player's last member fainted, and tally them per trainer. The result is the report's
`loss_causes` list (`LossCause(trainer, opponent_mon, losses)`, shape used by the xlsx/csv writers).

Where the information comes from. The worker's `log: "summary"` result (contracts/worker-protocol.md,
sim/gauntlet.mjs) carries per battle only `trainer, won, end, turns, seed, log_hash, state_before`;
it does not say who was on the field. So the field is read from the Showdown battle log
(`log: "full"`), in Python, by `field_at_last_faint`. `sim/**` is not changed for this.

To avoid shipping a full log for every one of thousands of gauntlets, `replay_requests` builds, for
each lost battle of a summary run, a one-battle request that re-plays exactly that battle:
`trainers: [trainer]`, `seeds: [battle seed]`, `start_state: state_before`, same policies,
`log: "full"`. `collect_loss_causes` checks that the replay's `log_hash` equals the original
battle's `log_hash` (the hash of the timestamp-stripped log, sim/gauntlet.mjs `hashLog`), so a
replay that is not the same battle is an error, never a silently wrong tally.

Log parsing (Showdown protocol, pokemon-showdown/sim/SIM-PROTOCOL.md):
  `|switch|p2a: NICK|Species, L62, F|hp`, `|drag|...` and `|replace|...` put a Pokemon on the
  field at position `p2a`; `|faint|p1a: NICK` is a faint. The player is side `p1`
  (sim/team.mjs P1_NAME), the opponent `p2`. The opponent mon is named by the species in the
  details field, mapped to a data/generated species key.

A lost battle in which no player Pokemon fainted (turn limit, or a tie with members left) is
tallied under the pseudo-mon `"(<end>)"`, e.g. `"(turn_limit)"`, so it is counted, not dropped.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import cache

from platsim import pins

from .json_report import LossCause

PLAYER = "p1"
OPPONENT = "p2"
_ENTER = re.compile(r"^\|(switch|drag|replace)\|(p[12][a-c]): ?[^|]*\|([^|]*)")
_FAINT = re.compile(r"^\|faint\|(p[12])[a-c]: ?")


def to_id(name: str) -> str:
    """Showdown's toID: lowercase, keep [a-z0-9] only."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


@cache
def _species_by_id() -> dict[str, str]:
    path = pins.REPO_ROOT / "data" / "generated" / "species.json"
    keys = json.loads(path.read_text(encoding="utf-8"))["species"]
    return {to_id(k): k for k in keys}


def species_key(showdown_species: str) -> str:
    """Showdown species name ("Mr. Mime") -> data/generated key ("mr_mime"); toID if unknown."""
    sid = to_id(showdown_species)
    return _species_by_id().get(sid, sid)


@dataclass(frozen=True)
class FaintField:
    opponents: tuple[str, ...]  # opponent species (Showdown names) on the field at that moment
    player_mon: str | None  # the player's last Pokemon to faint (Showdown species name)
    fainted: bool  # False when no player Pokemon fainted in the log


def field_at_last_faint(lines: Sequence[str]) -> FaintField:
    """Opponent Pokemon on the field when the player's LAST member fainted (singles or doubles)."""
    active: dict[str, str] = {}  # position ("p2a") -> species
    snap: FaintField | None = None
    for line in lines:
        m = _ENTER.match(line)
        if m:
            active[m.group(2)] = m.group(3).split(",")[0].strip()
            continue
        f = _FAINT.match(line)
        if f and f.group(1) == PLAYER:
            pos = line.split("|")[2].split(":")[0].strip()
            opp = tuple(active[p] for p in sorted(active) if p.startswith(OPPONENT))
            snap = FaintField(opponents=opp, player_mon=active.get(pos), fainted=True)
    if snap is None:
        opp = tuple(active[p] for p in sorted(active) if p.startswith(OPPONENT))
        return FaintField(opponents=opp, player_mon=None, fainted=False)
    return snap


@dataclass(frozen=True)
class LostBattle:
    run: int  # index of the gauntlet result
    battle: int  # index of the battle inside that result
    record: dict  # the summary battle record (trainer, won, end, seed, log_hash, state_before)


def lost_battles(results: Iterable[dict]) -> list[LostBattle]:
    out = []
    for i, r in enumerate(results):
        if not r.get("ok", True):
            raise ValueError(f"result {i} is an error response: {r.get('error')}")
        for j, b in enumerate(r["battles"]):
            if not b["won"]:
                out.append(LostBattle(i, j, b))
    return out


def replay_requests(team: list[dict], results: Sequence[dict], lost: Sequence[LostBattle]) -> list[dict]:
    """One-battle `log: "full"` requests that re-play each lost battle exactly."""
    reqs = []
    for lb in lost:
        r, b = results[lb.run], lb.record
        if "state_before" not in b:
            raise ValueError(f"result {lb.run} battle {lb.battle}: no state_before (run with log 'summary' or 'full')")
        reqs.append({"op": "gauntlet", "team": team, "trainers": [b["trainer"]], "seeds": [b["seed"]],
                     "start_state": b["state_before"], "player_policy": r["player_policy"],
                     "opponent_policy": r["opponent_policy"], "stop_on_loss": True, "log": "full",
                     **({"turn_limit": r["turn_limit"]} if "turn_limit" in r else {})})
    return reqs


class ReplayMismatch(RuntimeError):
    pass


def cause_of(lb: LostBattle, replay: dict) -> tuple[str, list[str]]:
    """(trainer, opponent species keys) for one lost battle from its full-log replay."""
    if not replay.get("ok"):
        raise ReplayMismatch(f"replay of result {lb.run} battle {lb.battle} failed: {replay.get('error')}")
    (rb,) = replay["battles"]
    if rb["log_hash"] != lb.record["log_hash"] or rb["won"] != lb.record["won"]:
        raise ReplayMismatch(f"replay of result {lb.run} battle {lb.battle} ({lb.record['trainer']}) is not the same "
                             f"battle: log_hash {rb['log_hash']} != {lb.record['log_hash']}")
    (lines,) = replay["log"]
    ff = field_at_last_faint(lines)
    if not ff.fainted:
        return lb.record["trainer"], [f"({lb.record.get('end', 'no_faint')})"]
    return lb.record["trainer"], [species_key(s) for s in ff.opponents] or ["(none)"]


def tally(causes: Iterable[tuple[str, Sequence[str]]], trainer_order: Sequence[str] = ()) -> list[LossCause]:
    """Count (trainer, opponent mon) over lost battles. A mon counts once per lost battle.
    Sorted by trainer (gauntlet order when given), then losses descending, then name."""
    c: Counter[tuple[str, str]] = Counter()
    for trainer, mons in causes:
        for mon in dict.fromkeys(mons):
            c[(trainer, mon)] += 1
    order = {t: i for i, t in enumerate(trainer_order)}
    keys = sorted(c, key=lambda k: (order.get(k[0], len(order)), k[0], -c[k], k[1]))
    return [LossCause(trainer=t, opponent_mon=m, losses=c[(t, m)]) for t, m in keys]


def collect_loss_causes(run_map: Callable[[list[dict]], list[dict]], team: list[dict], results: Sequence[dict],
                        trainer_order: Sequence[str] = ()) -> list[LossCause]:
    """Replay every lost battle of `results` with `run_map` (e.g. `WorkerPool.map`) and tally."""
    lost = lost_battles(results)
    if not lost:
        return []
    replays = run_map(replay_requests(team, results, lost))
    return tally((cause_of(lb, rp) for lb, rp in zip(lost, replays, strict=True)), trainer_order)


__all__ = ["FaintField", "LostBattle", "ReplayMismatch", "cause_of", "collect_loss_causes", "field_at_last_faint",
           "lost_battles", "replay_requests", "species_key", "tally", "to_id"]
