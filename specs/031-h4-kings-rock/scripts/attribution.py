"""031 (from 029; appended items may gain kings_rock at the end; new extras only of kind flinch_item). 029 (from 028; appended items may gain up to two resist berries after Shell Bell). 028 (from 027): compare candidate lists; 028 adds the appended-item rule (Shell Bell). 027: compare the extra candidate sets of a pre-feature snapshot with the branch's (spec FR-007, FR-009; research R4).

`record_of(mc, call)` is the snapshot record: base sets, their items, the setup set, and every extra set with its kind, item
and dead moves judged under its own valuation (the item-conditioned values for a Wide Lens or Razor Claw set; the logic of
evidence/pre/extras_dead_probe.py). `attribute(rec, mc)` returns one record per difference:
  defect       any difference in a base set, a base set's item list or the setup set (FR-007: they must not change), or an
               offered extra keeping a dead move without a recorded filler reason
  extras_rule  an extra set added, removed or changed, the branch's extra being all-live under its own valuation or carrying a
               recorded filler reason
`dead_in_extras(rec)` counts the dead moves of a record's extras. Shared by tests and scripts/acceptance.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

RESIST_BERRIES = ['babiri_berry', 'charti_berry', 'chilan_berry', 'chople_berry', 'coba_berry', 'colbur_berry', 'haban_berry', 'kasib_berry', 'kebia_berry', 'occa_berry', 'passho_berry', 'payapa_berry', 'rindo_berry', 'shuca_berry', 'tanga_berry', 'wacan_berry', 'yache_berry']  # 029: the 17 resist berries

REPO = Path(__file__).resolve().parents[3]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))


def _effect(item):
    from platsim.optimizer import candidates as C
    return {"wide_lens": C.ACCURACY_UP_EFFECT, "razor_claw": C.CRITRATE_UP_EFFECT}.get(item)


def extras_of(mc) -> list[dict]:
    from platsim.optimizer import candidates as C
    n_base = len(mc.movesets) - mc.extras
    out = []
    for ms in mc.movesets[n_base:]:
        item = mc.item_extras.get(ms)
        eff = _effect(item)
        vals = {m: C.move_value(mc.species, m, mc.ref_level, item_effect=eff) for m in ms}
        out.append({"set": list(ms), "kind": mc.extra_kind.get(ms, "variable_power"), "item": item,
                    "dead": C.dead_moves(ms, vals),
                    "filler_reason": (getattr(mc, "filler_reasons", {}) or {}).get(ms)})
    return out


def record_of(mc, call: dict) -> dict:
    n_base = len(mc.movesets) - mc.extras
    base = [list(ms) for ms in mc.movesets[:n_base]]
    return {"call": call, "level": mc.ref_level, "base_sets": base,
            "base_items": {"|".join(ms): list(mc.items[tuple(ms)]) for ms in base},
            "setup_moveset": list(mc.setup_moveset) if mc.setup_moveset else None,
            "extras": extras_of(mc), "extras_by_kind": dict(mc.extras_by_kind),
            "items_extra": {"|".join(ms): list(v) for ms, v in mc.items_extra.items()},
            "dropped_extras": dict(getattr(mc, "dropped_extras", {}) or {})}


def dead_in_extras(rec: dict, only_unexplained: bool = False) -> int:
    return sum(len(e["dead"]) for e in rec["extras"] if not (only_unexplained and e.get("filler_reason")))


def attribute(rec: dict, mc) -> list[dict]:
    new = record_of(mc, rec["call"])
    out = []
    if new["base_sets"] != rec["base_sets"]:
        out.append({"kind": "base_sets", "cause": "defect", "note": f"{rec['base_sets']} -> {new['base_sets']}"})
    if new["base_items"] != rec["base_items"]:
        out.append({"kind": "base_items", "cause": "defect", "note": "base-set item lists changed"})
    if new["setup_moveset"] != rec["setup_moveset"]:
        out.append({"kind": "setup", "cause": "defect", "note": f"{rec['setup_moveset']} -> {new['setup_moveset']}"})
    # 028: the extras must be unchanged (sets, kinds, items); appended items may only gain Shell Bell at the end
    # 031: the pre-feature extras unchanged; new extras only of kind flinch_item (cause "appended_extra")
    old_ex = [(e["set"], e["kind"], e["item"]) for e in rec["extras"]]
    new_ex = [(e["set"], e["kind"], e["item"]) for e in new["extras"] if e["kind"] != "flinch_item"]
    if old_ex != new_ex:
        out.append({"kind": "extras", "cause": "defect", "note": "extra sets changed"})
    for e in new["extras"]:
        if e["kind"] == "flinch_item":
            ok = e["item"] == "kings_rock"
            out.append({"kind": "extra", "cause": "appended_extra" if ok else "defect", "set": e["set"], "note": f"flinch_item extra held with {e['item']}"})
    old_ie = rec.get("items_extra", {})
    for key, items in new["items_extra"].items():
        before = old_ie.get(key)
        if before is None:
            out.append({"kind": "items_extra", "cause": "defect", "set": key, "note": "a set without a pre-feature record"})
        elif items == before:
            continue
        elif items == before + ["kings_rock"]:  # 031
            out.append({"kind": "items_extra", "cause": "appended", "set": key, "note": "kings_rock appended"})
        else:
            out.append({"kind": "items_extra", "cause": "defect", "set": key, "note": f"{before} -> {items}"})
    old = {(tuple(e["set"]), e["kind"]) for e in rec["extras"]}
    for e in new["extras"]:
        key = (tuple(e["set"]), e["kind"])
        if e["dead"] and not e["filler_reason"]:
            out.append({"kind": "extra", "cause": "defect", "set": e["set"], "note": f"dead {e['dead']} without a filler reason"})
        elif key not in old and e["kind"] != "flinch_item":
            out.append({"kind": "extra", "cause": "defect", "set": e["set"], "note": f"{e['kind']} added or changed (031: only flinch_item may be new)"})
    newkeys = {(tuple(e["set"]), e["kind"]) for e in new["extras"]}
    for s, kind in old - newkeys:
        out.append({"kind": "extra", "cause": "extras_rule", "set": list(s), "note": f"{kind} removed"})
    return out


def recompute(snapshot_record: dict, led):
    from platsim.optimizer import candidates as C
    call = snapshot_record["call"]
    v = next(x for x in C.variants(call["species"], led) if x.key == call["variant"])
    return C.member_candidates(call["species"], v, call["ref_level"], led, k=call["k"], team=tuple(call["team"]))


def attribute_snapshot(snapshot: dict) -> dict[str, list[dict]]:
    from platsim.availability.ledger import build_ledger
    from platsim.legality.models import LegalityOptions

    led = build_ledger().with_options(LegalityOptions())
    return {key: attribute(rec, recompute(rec, led)) for key, rec in snapshot.items()}
