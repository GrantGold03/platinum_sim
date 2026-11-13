"""026 T001 (from 025 T015): attribute every difference between a pre-feature candidate snapshot and the branch's lists (spec FR-006).

`attribute(snap_member, mc)` compares one snapshot record (movesets, setup, pool, ranked, items) with a MemberCandidates
and returns one record per difference with a `cause`:
  dominated  a move missing from the branch's pool, ranked list or sets that the branch's pruned map marks "dominated by"
  appended   a set present only in the branch that is an item-conditioned extra, a 024 variable-power extra, or an item
             candidate the branch appended (`items_extra`) to an existing set
  crit_term  a membership or order change among surviving (non-dominated) moves: the crit term re-ranked them
             (the setup set is attributed the same way: a dominated move gone or a pool entrant after one left is
             "dominated", a re-rank within the pool "crit_term")
  marginal_pool  (026) a pool entrant whose marginal gain to the pool before it is positive, a pool leaver that adds no
             more than every entrant did, a set change among moves of the new pool that removed a dead move or was accepted
             one apart (mc.one_apart); verified by recomputation, not by label
  defect     anything else (a move gone without a dominance reason, a set gone, an item removed)
`attribute_snapshot(snapshot)` recomputes member_candidates from each record's `call` and attributes all of them.
Shared by tests/unit/test_variable_power.py and scripts/acceptance.py so both apply one rule.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))


def coverage(vals: list[list[float]]) -> float:
    return sum(max(col) for col in zip(*vals)) if vals else 0.0


def marginal(move: str, moveset, vals: dict) -> float:
    full = coverage([vals[m] for m in moveset])
    rest = coverage([vals[m] for m in moveset if m != move])
    return full - rest


def dead_moves_of(mc, vals: dict | None = None) -> dict[str, list[str]]:
    """{'|'.join(set): [moves with zero marginal contribution]} for every offered set (own computation from move_value)."""
    from platsim.optimizer import candidates as C
    out = {}
    v = vals if vals is not None else {}
    for ms in mc.movesets:
        for m in ms:
            if m not in v:
                v[m] = C.move_value(mc.species, m, mc.ref_level)
        out["|".join(ms)] = [m for m in ms if marginal(m, ms, v) <= 0]
    return out


def dead_table(snap: dict, mc) -> dict:
    return {"before": snap.get("dead_moves", {}), "after": dead_moves_of(mc)}


def _vals_for(mc, moves) -> dict:
    from platsim.optimizer import candidates as C
    return {m: C.move_value(mc.species, m, mc.ref_level) for m in moves}


def _dominated(mc) -> set[str]:
    return {m for m, why in mc.pruned.items() if "dominated by" in why}


def attribute(snap: dict, mc) -> list[dict]:
    out: list[dict] = []
    dom = _dominated(mc)
    new_sets = {tuple(ms) for ms in mc.movesets}
    old_sets = [tuple(ms) for ms in snap["movesets"]]
    extras_old = int(snap.get("extras", 0))
    item_extra_sets = set(getattr(mc, "item_extras", {}).keys())
    n_base_new = len(mc.movesets) - getattr(mc, "extras", 0)
    base_new = [tuple(ms) for ms in mc.movesets[:n_base_new]]
    base_old = old_sets[:len(old_sets) - extras_old]
    # the crit term can re-rank a member's sets only where the pool changed or a high-critical-ratio move competes (a uniform
    # stage-0 term is a common factor and moves nothing); otherwise a vanished set is unexplained
    from platsim.optimizer import candidates as C
    mv = C.load_moves()
    pool_changed = list(snap["pool"]) != list(mc.pool)
    crit_competes = any(C.is_high_crit(mv[m].effect) for m in set(snap["pool"]) | set(mc.pool))
    # sets
    for ms in base_old:
        if ms in new_sets:
            continue
        gone = [m for m in ms if m in dom]
        dead_before = set(snap.get("dead_moves", {}).get("|".join(ms), []))
        if gone:
            out.append({"kind": "moveset", "cause": "dominated", "set": list(ms), "moves": gone})
        elif dead_before or pool_changed:
            out.append({"kind": "moveset", "cause": "marginal_pool", "set": list(ms),
                        "note": "today's set gone: " + ("it carried dead moves " + str(sorted(dead_before)) if dead_before else "the pool changed by the marginal rule")})
        elif pool_changed or crit_competes:
            out.append({"kind": "moveset", "cause": "crit_term", "set": list(ms),
                        "note": "today's set re-ranked out" + (" (pool changed)" if pool_changed else " (a high-crit move competes)")})
        else:
            out.append({"kind": "moveset", "cause": "defect", "set": list(ms), "note": "set gone with the pool unchanged and no crit competitor"})
    one_apart = {tuple(x) for x in getattr(mc, "one_apart", [])}
    any_dead_before = any(snap.get("dead_moves", {}).values())
    for ms in base_new:
        if ms not in set(base_old):
            if set(ms) <= set(mc.pool) and (pool_changed or ms in one_apart or any_dead_before):
                out.append({"kind": "moveset", "cause": "marginal_pool", "set": list(ms),
                            "note": "a set accepted by the marginal rule" + (" (one apart)" if ms in one_apart else "")})
            elif set(ms) <= set(mc.pool) and (pool_changed or crit_competes):
                out.append({"kind": "moveset", "cause": "crit_term", "set": list(ms), "note": "a set re-ranked in"})
            else:
                out.append({"kind": "moveset", "cause": "defect", "set": list(ms), "note": "a new base set without a pool change or crit competitor"})
    for ms in [tuple(x) for x in mc.movesets[n_base_new:]]:
        if ms in item_extra_sets or any(m in getattr(mc, "variable_offered", []) for m in ms):
            continue  # appended kinds are expected and not listed per set
        out.append({"kind": "moveset", "cause": "defect", "set": list(ms), "note": "an appended set of unknown kind"})
    # setup set (the top attacks with the setup move): a pool entrant after a dominated move left, or a crit-term re-rank
    old_setup = snap.get("setup_moveset")
    new_setup = list(mc.setup_moveset) if mc.setup_moveset else None
    if old_setup != new_setup:
        if old_setup and new_setup:
            gone = [m for m in old_setup if m not in new_setup]
            came = [m for m in new_setup if m not in old_setup]
            if any(m in dom for m in gone):
                out.append({"kind": "setup", "cause": "dominated", "set": new_setup, "moves": [m for m in gone if m in dom]})
            elif any(m not in snap["pool"] for m in came) and any(m in dom for m in snap["pool"]):
                out.append({"kind": "setup", "cause": "dominated", "set": new_setup, "moves": came,
                            "note": "a pool entrant after a dominated move left the pool"})
            elif set(came) <= set(mc.pool) and list(snap["pool"]) != list(mc.pool):
                out.append({"kind": "setup", "cause": "marginal_pool", "set": new_setup, "moves": came})
            elif set(came) <= set(mc.pool):
                out.append({"kind": "setup", "cause": "crit_term", "set": new_setup, "moves": came})
            else:
                out.append({"kind": "setup", "cause": "defect", "set": new_setup, "note": f"setup set changed: {old_setup} -> {new_setup}"})
        else:
            out.append({"kind": "setup", "cause": "defect", "note": f"setup set appeared or vanished: {old_setup} -> {new_setup}"})
    # pool (026): a pool built by marginal contribution is verified by recomputation: an entrant must have added coverage to
    # the pool before it (in the branch's pool order); a leaver must add no more to the new pool than the smallest entrant gain
    old_pool, new_pool = list(snap["pool"]), list(mc.pool)
    left_dominated = any(m in dom for m in old_pool if m not in new_pool)
    pv = _vals_for(mc, set(old_pool) | set(new_pool))
    entrants = [m for m in new_pool if m not in old_pool]
    gains = {}
    for m in entrants:
        before = new_pool[:new_pool.index(m)]
        gains[m] = coverage([pv[x] for x in before + [m]]) - coverage([pv[x] for x in before])
    marginal_rule = bool(entrants) and all(g > 0 for g in gains.values())
    min_gain = min(gains.values()) if gains else 0.0
    for m in old_pool:
        if m not in new_pool:
            if m in dom:
                out.append({"kind": "pool", "cause": "dominated", "moves": [m], "note": "left the pool"})
            elif marginal_rule and marginal(m, new_pool + [m], pv) <= min_gain + 1e-9:
                out.append({"kind": "pool", "cause": "marginal_pool", "moves": [m], "note": "left the pool: adds no more than the entrants"})
            elif not marginal_rule:
                out.append({"kind": "pool", "cause": "crit_term", "moves": [m], "note": "left the pool"})
            else:
                out.append({"kind": "pool", "cause": "defect", "moves": [m], "note": "left the pool although it adds more than an entrant"})
    for m in entrants:
        if gains[m] > 0:
            out.append({"kind": "pool", "cause": "marginal_pool", "moves": [m], "note": f"entered the pool: gain {gains[m]:.0f}"})
        elif left_dominated:
            out.append({"kind": "pool", "cause": "dominated", "moves": [m], "note": "entered the pool after a dominated move left"})
        else:
            out.append({"kind": "pool", "cause": "defect", "moves": [m], "note": "entered the pool with zero gain"})
    if [m for m in old_pool if m in new_pool] != [m for m in new_pool if m in old_pool]:
        out.append({"kind": "pool", "cause": "marginal_pool" if old_pool != new_pool else "crit_term",
                    "note": "order among surviving pool moves"})
    # ranked (membership of the combos)
    snap_ranked = snap.get("ranked", snap.get("ranked_prefix", []))  # 024's snapshot stored today's prefix only
    old_ranked = {tuple(c) for c in snap_ranked}
    new_ranked = {tuple(c) for c in mc.ranked}
    for c in old_ranked - new_ranked:
        gone = [m for m in c if m in dom]
        left = [m for m in c if m not in mc.pool]
        out.append({"kind": "ranked", "cause": "dominated" if gone else ("marginal_pool" if left else "crit_term"), "set": list(c), "moves": gone or left})
    if old_ranked - new_ranked == set() and new_ranked - old_ranked == set() and [tuple(c) for c in snap_ranked] != [tuple(c) for c in mc.ranked]:
        out.append({"kind": "ranked", "cause": "crit_term", "note": "order among the same combos"})
    # items of surviving sets
    items_extra = getattr(mc, "items_extra", {})
    item_extras = getattr(mc, "item_extras", {})
    for key, old_items in snap.get("items", {}).items():
        ms = tuple(key.split("|"))
        if ms not in mc.items:
            continue
        new_items = list(mc.items[ms])
        if ms in item_extras:
            # a set the crit term re-ranked out of today's list (attributed above) and the item valuation re-added as an
            # item-conditioned extra: its items are the conditioning item first, then its usual list (FR-001a)
            if new_items[0] != item_extras[ms] or new_items[1:1 + len(old_items)] != list(old_items):
                out.append({"kind": "items", "cause": "defect", "set": list(ms),
                            "note": f"item-conditioned set's items not item + today's: {old_items} -> {new_items}"})
            else:
                out.append({"kind": "items", "cause": "appended", "set": list(ms), "note": f"re-added as a {item_extras[ms]} set"})
            continue
        if new_items[:len(old_items)] != list(old_items):
            out.append({"kind": "items", "cause": "defect", "set": list(ms), "note": f"today's items changed: {old_items} -> {new_items}"})
        extra = new_items[len(old_items):]
        if extra and not set(extra) <= set(items_extra.get(ms, [])) | set(extra):
            out.append({"kind": "items", "cause": "defect", "set": list(ms), "note": f"unexpected appended items {extra}"})
    return out


def attribute_snapshot(snapshot: dict) -> dict[str, list[dict]]:
    from platsim.availability.ledger import build_ledger
    from platsim.legality.models import LegalityOptions
    from platsim.optimizer import candidates as C

    led = build_ledger().with_options(LegalityOptions())
    out = {}
    for key, s in snapshot.items():
        call = s["call"]
        v = next(v for v in C.variants(call["species"], led) if v.key == call["variant"])
        mc = C.member_candidates(call["species"], v, call["ref_level"], led, k=call["k"], team=tuple(call["team"]))
        out[key] = attribute(s, mc)
    return out
