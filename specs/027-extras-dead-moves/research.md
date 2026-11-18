# Research: Dead moves in the extra candidate sets

## R1. Reusing 026's selection for the extras, base sets unchanged

- **Finding**: `choose_sets(ranked, k, cands, vals, scores)` repairs each ranked combo (`_repaired`: dead moves replaced by the
  legal move adding the most coverage, 026 cost tiers), re-ranks, and accepts sets two apart, one apart only where the two-apart
  candidate carries a dead move. The 024 extras today: combos of `pool ∪ variable` with at least one variable move, sorted by
  `_rank_key`, two apart, not in `chosen`. The 025 item extras: per conditioning item, an item-valued marginal pool, `rank_sets`,
  two apart, not in `chosen ∪ extras ∪ earlier picks`.
- **Decision**: `choose_sets(..., exclude=frozenset(), require=None)`: repaired sets in `exclude` are skipped; `require(set) ->
  bool` filters candidates before acceptance. Defaults reproduce the base call exactly (a unit test pins base sets, items and
  setup set against `specs/026-marginal-coverage-sets/evidence/candidates-branch.json`, the 026 snapshot, and the acceptance
  re-checks all 36 members). The base-set pin compares with this feature's own pre-feature snapshot (T002, today's code),
  calling each record with its stored arguments (B2 at the quick job's reference level, 47, not a fixed 48). Variable-power extras: `choose_sets(ranked_extra, k, cands, vals, scores, exclude=set(chosen),
  require=has_live_variable)`. Item extras: `choose_sets(ranked_i, k, cands, vals_i, sc_i, exclude=chosen ∪ extras ∪ picked,
  require=item_matters)` under the item valuation.
- **Alternatives**: a separate extras selector (duplicates 026's logic; rejected).

## R2. The defining checks (FR-005, owner's decision: drop and list)

- **Variable-power**: `has_live_variable(set)` ⇔ some offered variable move in the set is not in `dead_moves(set, vals)`. The
  repair may replace a dead variable move by a live non-variable move; such a set then fails the check and is not offered (its
  coverage is a non-variable set already available to the base walk).
- **Item**: `item_matters(set)` ⇔ the set contains a move whose value the item changes: Wide Lens, a move with 0 < accuracy <
  100; Razor Claw, any damaging move (the crit term always moves, so for Razor Claw the check always passes and only the
  duplicate rule can drop a set). "Ranks no differently from the base sets" is made testable
  this way, plus FR-004's duplicate rule (a repaired item set equal to a base set is excluded).
- **Dropped extras**: every ranked candidate that `require` rejects or that duplicates an offered set is not recorded (there are
  hundreds); what is recorded is each kind's shortfall: `dropped_extras[kind] = {"offered": n, "reason": ...}` when fewer than `k`
  are offered, with the reason "no further set whose variable move is live" / "no further set the item changes" / "only
  duplicates of offered sets remain".

## R3. Per-set filler reasons and the report note

- **Finding**: `MemberCandidates.no_live_reason` is one string per member; `run._member_notes` writes it for the chosen set's dead
  moves. Extras can keep a filler under their own valuation.
- **Decision**: `filler_reasons: dict[set, str]` for every offered set (base and extra) with a dead move; `no_live_reason` stays as
  026 defined it (base sets) so 026's tests and snapshot fields do not move; `_member_notes` reads `filler_reasons[set]` first,
  then `no_live_reason`. `dead_moves` gains the extras, each under its own valuation.

## R4. The attribution change

- **Decision**: 026's helper is copied; any difference in a base set, its items or the setup set is a `defect`; extra-set
  differences are `extras_rule` when the branch's extra is all-live (or carries a recorded filler) under its own valuation, else
  `defect`; a per-member table of dead moves in extras before/after (the probe's logic).

## R5. Expected effect and size

- The recount: 208 dead moves in 324 extra sets, 29 of 36 members. Expected after: 0 outside members with recorded fillers;
  fewer extras where kinds run out (Garchomp's Return set expected to be replaced by another live Return set or dropped).
- The screen's extra count may fall (fewer variable-power and item extras); the screen's kinds and order are unchanged.
- About 16 tasks, two stories, one layer.
