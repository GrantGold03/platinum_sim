# Contract: contested resources across the team (`platsim.optimizer.allocation`, story 3)

- `needs(species, variant, moveset, level, led) -> dict[str, int]`: the resources of the cheapest source per move.
- `allocate(consts, variants, ref_level, led, cands, required_hms=()) -> (cands, record)`: contested = wanted by more members
  than copies (held-item candidates are not counted; required HMs keep theirs); gain per contender = coverage(first set) −
  coverage(best all-live set with the resource's moves unavailable); top `copies` by gain (ties by slot) keep it; the others'
  lists are rebuilt with `unavailable` extended; loop until stable (bounded by the number of resources); `record` per
  resource: copies, contenders with gains, given_to, rebuilt.
- `run._build_cands` calls `allocate`; the prune stage stores `allocation`; `_optimizer_provenance` carries it.
- Expected on B2 quick: TM26 and TM71 contested by Garchomp and Infernape, each resolved by gain; zero repair notes for the
  baseline and for the single-slot deviations of first sets (the acceptance counts `baseline_repairs` and the screen's
  `dropped` reasons mentioning repair).
- Out of scope: joint optimisation; changes to `resources.realize`/`repair`.
