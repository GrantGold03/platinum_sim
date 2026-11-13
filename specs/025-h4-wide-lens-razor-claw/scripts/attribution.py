"""025 T015: attribute every difference between a pre-feature candidate snapshot and the branch's lists (spec FR-006).

`attribute(snap_member, mc)` compares one snapshot record (movesets, setup, pool, ranked, items) with a MemberCandidates
and returns one record per difference with a `cause`:
  dominated  a move missing from the branch's pool, ranked list or sets that the branch's pruned map marks "dominated by"
  appended   a set present only in the branch that is an item-conditioned extra, a 024 variable-power extra, or an item
             candidate the branch appended (`items_extra`) to an existing set
  crit_term  a membership or order change among surviving (non-dominated) moves: the crit term re-ranked them
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
    # sets
    for ms in base_old:
        if ms in new_sets:
            continue
        gone = [m for m in ms if m in dom]
        if gone:
            out.append({"kind": "moveset", "cause": "dominated", "set": list(ms), "moves": gone})
        elif set(ms) <= set(mc.pool) | dom:
            out.append({"kind": "moveset", "cause": "crit_term", "set": list(ms), "note": "today's set re-ranked out"})
        else:
            out.append({"kind": "moveset", "cause": "defect", "set": list(ms), "note": "set gone without a dominance reason"})
    for ms in base_new:
        if ms not in set(base_old):
            if set(ms) <= set(snap["pool"]) | set(mc.pool):
                out.append({"kind": "moveset", "cause": "crit_term", "set": list(ms), "note": "a set re-ranked in"})
            else:
                out.append({"kind": "moveset", "cause": "defect", "set": list(ms), "note": "a new base set from outside the pools"})
    for ms in [tuple(x) for x in mc.movesets[n_base_new:]]:
        if ms in item_extra_sets or any(m in getattr(mc, "variable_offered", []) for m in ms):
            continue  # appended kinds are expected and not listed per set
        out.append({"kind": "moveset", "cause": "defect", "set": list(ms), "note": "an appended set of unknown kind"})
    # pool
    old_pool, new_pool = list(snap["pool"]), list(mc.pool)
    for m in old_pool:
        if m not in new_pool:
            out.append({"kind": "pool", "cause": "dominated" if m in dom else "crit_term", "moves": [m],
                        "note": "left the pool"})
    for m in new_pool:
        if m not in old_pool:
            out.append({"kind": "pool", "cause": "crit_term", "moves": [m], "note": "entered the pool"})
    if [m for m in old_pool if m in new_pool] != [m for m in new_pool if m in old_pool]:
        out.append({"kind": "pool", "cause": "crit_term", "note": "order among surviving pool moves"})
    # ranked (membership of the combos)
    old_ranked = {tuple(c) for c in snap["ranked"]}
    new_ranked = {tuple(c) for c in mc.ranked}
    for c in old_ranked - new_ranked:
        gone = [m for m in c if m in dom]
        out.append({"kind": "ranked", "cause": "dominated" if gone else "crit_term", "set": list(c), "moves": gone})
    if old_ranked - new_ranked == set() and new_ranked - old_ranked == set() and [tuple(c) for c in snap["ranked"]] != [tuple(c) for c in mc.ranked]:
        out.append({"kind": "ranked", "cause": "crit_term", "note": "order among the same combos"})
    # items of surviving sets
    items_extra = getattr(mc, "items_extra", {})
    for key, old_items in snap["items"].items():
        ms = tuple(key.split("|"))
        if ms not in mc.items:
            continue
        new_items = list(mc.items[ms])
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
