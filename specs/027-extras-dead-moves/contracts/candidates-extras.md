# Contract: extras under the dead-move rule (`platsim.optimizer.candidates`)

- `choose_sets(ranked, k, cands, vals, scores, cost_tier=None, exclude=frozenset(), require=None)`: unchanged behaviour when
  `exclude` and `require` are omitted; with them, repaired sets in `exclude` and sets failing `require` are never accepted.
- `member_candidates(...)`: variable-power extras via `choose_sets(..., exclude=chosen, require=has_live_variable)` over the plain
  valuation; item extras via `choose_sets(..., exclude=offered so far, require=item_matters)` over the item valuation; each kind
  in today's order (variable-power, Wide Lens, Razor Claw); items, kinds and `extra_kind` as today.
- `run._member_notes`: the chosen set's `filler_reasons` entry, else `no_live_reason`.
- Controls (unit tests): Infernape (B2, level 48) no extra contains Fire Punch and no extra keeps a dead move with a live
  replacement; Garchomp's variable-power extras all carry a live variable move; a synthetic member whose repaired extra
  duplicates a base set gets it excluded; a synthetic filler extra carries its reason; base sets, items and setup sets of the
  six B2 members equal 026's snapshot.
