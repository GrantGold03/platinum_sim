"""Team-level allocation of contested single-copy resources (feature 026, story 3; contracts/allocation.md, research R6).

A member's candidate lists (optimizer/candidates.py) are built member by member, but the game's single-copy TMs, evolution
items and held items are shared by the team: on the B2 team Garchomp's first set takes the only Earthquake and Stone Edge
TMs, every all-live Infernape set needs one of them, and the repair step then silently gives Infernape a worse set. Here:

1. `needs`: the single-copy resources a member's first set consumes (the cheapest source per move at the level; HMs are
   never consumed by the game and never counted).
2. `contested`: a resource wanted by more first sets than it has copies. Each contender's gain is the coverage its first
   set loses without the resource's moves; the top `copies` contenders by gain (ties by slot) keep it, the others' lists are
   rebuilt with those moves `unavailable`.
3. `remaining`: after every first set is charged, a resource with no copy left is unavailable to every other member's
   non-first sets too (FR-015), so their lists are rebuilt as well; the loop repeats until no first set changes (bounded by
   the number of single-copy resources).

The record names every contested resource, its contenders with gains, who received it and who was rebuilt; `run.py`
stores it in the prune stage and the optimizer's provenance. The repair step and the independent validator still check
every team (Constitution III); this only changes which sets are offered.
"""

from __future__ import annotations

from collections import Counter

from platsim.legality import movesources as MS
from platsim.optimizer import candidates as C
from platsim.optimizer import resources as R


_USES_CACHE: dict[tuple, dict[str, int]] = {}
_LEGAL_CACHE: dict[tuple, list[str]] = {}


def _legal(variant, level: int, led) -> list[str]:
    k = (id(led), variant.species, variant.key, level)
    if k not in _LEGAL_CACHE:
        _LEGAL_CACHE[k] = C.legal_moves(variant, level, led)
    return _LEGAL_CACHE[k]


def _cheapest_uses(species: str, variant, move: str, level: int, led) -> dict[str, int]:
    """The resources of the cheapest source of `move` for this member: none if any source consumes nothing (memoised per
    ledger object: the source lookup is the expensive part of the allocation)."""
    k = (id(led), species, variant.key, move, level)
    if k in _USES_CACHE:
        return dict(_USES_CACHE[k])
    best: dict[str, int] | None = None
    for opt in variant.options(led):
        for choice in MS.sources(species, move, level, led, opt):
            uses = {r: n for r, n in MS.uses_of(choice).items() if R.copies(r, led) != R.UNLIMITED}
            if not uses:
                _USES_CACHE[k] = {}
                return {}
            if best is None or sum(uses.values()) < sum(best.values()):
                best = uses
    _USES_CACHE[k] = dict(best or {})
    return dict(best or {})


def needs(species: str, variant, moveset, level: int, led) -> dict[str, int]:
    """Single-copy resources a moveset consumes for this member (summed over its moves)."""
    out: Counter = Counter()
    for m in moveset:
        out.update(_cheapest_uses(species, variant, m, level, led))
    return dict(out)


def moves_needing(species: str, variant, moves, level: int, led, resource: str) -> set[str]:
    return {m for m in moves if resource in _cheapest_uses(species, variant, m, level, led)}


def _first(mcs: dict) -> tuple[str, C.MemberCandidates]:
    return next(iter(mcs.items()))


def contested(cands: list[dict], consts, level: int, led) -> dict[str, list[int]]:
    """{resource: [slots whose first set needs it]} for resources wanted by more first sets than copies."""
    wants: dict[str, list[int]] = {}
    for slot, mcs in enumerate(cands):
        vkey, mc = _first(mcs)
        for r in needs(consts[slot], mc.variant, mc.movesets[0], mc.ref_level, led):
            wants.setdefault(r, []).append(slot)
    out = {}
    for r, slots in wants.items():
        copies = R.copies(r, led, tuple(consts))
        if copies != R.UNLIMITED and len(slots) > int(copies):
            out[r] = slots
    return out


def remaining(cands: list[dict], consts, level: int, led) -> dict[str, int]:
    """Copies left per single-copy resource after every member's first set is charged."""
    used: Counter = Counter()
    for slot, mcs in enumerate(cands):
        vkey, mc = _first(mcs)
        used.update(needs(consts[slot], mc.variant, mc.movesets[0], mc.ref_level, led))
    out = {}
    for r, n in used.items():
        copies = R.copies(r, led, tuple(consts))
        if copies != R.UNLIMITED:
            out[r] = int(copies) - n
    return out


def _coverage_of(mc: C.MemberCandidates, moveset) -> float:
    vals = [C.move_value(mc.species, m, mc.ref_level) for m in moveset]
    return C.coverage(vals)


def _rebuild(const: str, mcs: dict, led, team, unavailable: frozenset) -> dict:
    out = {}
    for vkey, mc in mcs.items():
        out[vkey] = C.member_candidates(const, mc.variant, mc.ref_level, led, team=team, unavailable=unavailable)
    return out


def allocate(consts, led, cands: list[dict], max_rounds: int | None = None) -> tuple[list[dict], dict]:
    """Resolve contested single-copy resources across the team (R6 steps 1 to 3b). Returns the rebuilt candidate lists
    and the record {resource: {copies, contenders: [[species, gain]], given_to, rebuilt, unavailable: {species: [moves]}}}."""
    team = tuple(consts)
    cands = list(cands)
    unavailable: list[set[str]] = [set(mc.unavailable) for mcs in cands for _, mc in [_first(mcs)]]
    record: dict[str, dict] = {}
    level = max(_first(mcs)[1].ref_level for mcs in cands)
    rounds = 0
    limit = max_rounds if max_rounds is not None else 2 * max(1, len(set().union(*(needs(consts[s], _first(mcs)[1].variant, _first(mcs)[1].movesets[0], _first(mcs)[1].ref_level, led).keys() for s, mcs in enumerate(cands))))) + 2
    while rounds < limit:
        rounds += 1
        changed = False
        # step 1: first-set contention by gain
        for r, slots in contested(cands, consts, level, led).items():
            copies = int(R.copies(r, led, team))
            gains = []
            for slot in slots:
                vkey, mc = _first(cands[slot])
                lost = moves_needing(consts[slot], mc.variant, mc.movesets[0], mc.ref_level, led, r)
                alt = C.member_candidates(consts[slot], mc.variant, mc.ref_level, led, team=team,
                                          unavailable=frozenset(unavailable[slot] | lost))
                gain = _coverage_of(mc, mc.movesets[0]) - (_coverage_of(alt, alt.movesets[0]) if alt.movesets else 0.0)
                gains.append((slot, gain))
            gains.sort(key=lambda sg: (-sg[1], sg[0]))
            keep = [s for s, _ in gains[:copies]]
            rec = record.setdefault(r, {"copies": copies, "contenders": [], "given_to": [], "rebuilt": [], "unavailable": {}})
            rec["contenders"] = [[consts[s], round(g, 1)] for s, g in gains]
            rec["given_to"] = [consts[s] for s in keep]
            for slot, _ in gains[copies:]:
                vkey, mc = _first(cands[slot])
                lost = moves_needing(consts[slot], mc.variant, sorted(set(mc.pool) | set(mc.movesets[0]) | set(mc.variable_offered)), mc.ref_level, led, r)
                lost |= moves_needing(consts[slot], mc.variant, _legal(mc.variant, mc.ref_level, led), mc.ref_level, led, r)
                if not lost <= unavailable[slot]:
                    unavailable[slot] |= lost
                    cands[slot] = _rebuild(consts[slot], cands[slot], led, team, frozenset(unavailable[slot]))
                    rec["rebuilt"].append(consts[slot])
                    rec["unavailable"][consts[slot]] = sorted(lost)
                    changed = True
        # step 2 (3b): resources with no copy left after the first sets are charged are unavailable to the other members
        for r, left in remaining(cands, consts, level, led).items():
            if left > 0:
                continue
            for slot, mcs in enumerate(cands):
                vkey, mc = _first(mcs)
                if r in needs(consts[slot], mc.variant, mc.movesets[0], mc.ref_level, led):
                    continue  # its own first set holds a copy
                lost = moves_needing(consts[slot], mc.variant, _legal(mc.variant, mc.ref_level, led), mc.ref_level, led, r)
                if lost and not lost <= unavailable[slot]:
                    unavailable[slot] |= lost
                    cands[slot] = _rebuild(consts[slot], cands[slot], led, team, frozenset(unavailable[slot]))
                    rec = record.setdefault(r, {"copies": int(R.copies(r, led, team)), "contenders": [], "given_to": [], "rebuilt": [], "unavailable": {}})
                    rec["rebuilt"].append(consts[slot])
                    rec["unavailable"][consts[slot]] = sorted(lost)
                    changed = True
        if not changed:
            break
    return cands, {r: record[r] for r in sorted(record)}


__all__ = ["allocate", "contested", "needs", "remaining"]
