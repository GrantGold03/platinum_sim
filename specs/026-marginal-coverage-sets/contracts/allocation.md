# Contract: contested resources across the team (`platsim.optimizer.allocation`, story 3)

- `needs(species, variant, moveset, level, led) -> dict[str, int]`: the resources of the cheapest source per move.
- `remaining(cands, consts, level, led) -> dict[str, int]`: copies left per single-copy resource after every member's first
  set is charged (HMs never counted: never consumed).
- `allocate(consts, variants, ref_level, led, cands) -> (cands, record)`: step 1, contested = wanted by more first sets than
  copies (held-item candidates are not counted); gain per contender = coverage(first set) − coverage(best all-live set with the
  resource's moves unavailable); top `copies` by gain (ties by slot) keep it; the others' lists are rebuilt with `unavailable`
  extended. Step 2, moves needing a resource with zero copies left, charged to other members' first sets, become `unavailable`
  for that member; rebuild; loop to step 1 until no first set changes (bounded by the number of single-copy resources).
  `record` per resource: copies, contenders with gains, given_to, rebuilt, unavailable per species. Post-condition: every
  offered set of every member realizes beside the others' first sets at the reference level (`resources.realize`, no Refusal)
  and `resources.repair` on any single-slot deviation of first sets returns no notes.
- `run._build_cands` calls `allocate`; the prune stage stores `allocation`; `_optimizer_provenance` carries it.
- Expected on B2 quick: TM26 and TM71 contested by Garchomp and Infernape, each resolved by gain; zero repair notes for the
  baseline and for the single-slot deviations of first sets (the acceptance counts `baseline_repairs` and the screen's
  `dropped` reasons mentioning repair).
- Out of scope: joint optimisation; changes to `resources.realize`/`repair`.
