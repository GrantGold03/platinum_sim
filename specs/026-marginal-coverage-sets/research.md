# Research: Candidate sets by marginal coverage

## R1. The marginal pool and the live/dead definitions on the real lists

- **Finding** (probe on main after 025, B2 at level 48, `specs/026-marginal-coverage-sets/evidence/` once copied; the
  numbers in the spec's Overview table): dead moves in today's sets for Infernape, Rotom, Floatzel, Weavile; a greedy marginal
  pool changes Infernape (Solar Beam enters for Whiscash), Floatzel and Weavile (Brick Break enters), leaves Garchomp and
  Staraptor unchanged, cannot help Rotom. A marginal-contribution tie-break alone changes nothing (every leftover pool move of
  Infernape contributes zero).
- **Decision**: `pool_by_marginal(cands, vals, scores)`: start with the top standalone score; repeat until 10: the move with the
  highest `coverage(pool + [m]) - coverage(pool)`, ties by score then name; `cands` = pruned legal attacks ∪ offered variable
  moves (024's `OFFERED_VARIABLE` that the member learns). `marginal(m, set)`, `dead(m, set)` (marginal 0), `live(m)` (best
  against at least one opponent given the member's top two by score) as the spec defines.
- **Alternatives**: a defence-aware value (out of scope); a minimum-gain threshold (the owner's definition is strict: any
  positive gain counts; recorded).

## R2. Set selection with the FR-004a relaxation

- **Decision**: `rank_sets(pool, vals, scores)` key `(-coverage, -sum of marginals, -sum of scores, combo)`. `choose_sets`:
  walk the ranked list; for each combo replace its dead moves (given the other three) by the legal move with the highest
  marginal contribution, cost preference of R3, not already in the set, re-checked after each replacement; accept the result in
  pass 1 if all-live and at least two moves apart from every accepted set; after the list, pass 2 accepts all-live sets one
  apart; pass 3 (only if still fewer than k) accepts sets with dead moves two apart as today and records the member as
  no-live-move with the reason; pass 3 walks the list under today's key (coverage, then the standalone sum), so a no-live-move
  member's sets are unchanged (SC-002). Duplicates skipped. `one_apart` records the sets accepted in pass 2.
- **Rationale**: one deterministic walk; the probe's Infernape (five live moves) yields three all-live sets one apart; Rotom
  falls to pass 3 with the reason.
- **Setup set**: the best three by coverage from the pool, then the dead-move replacement among those three, then the setup move.

## R3. The cost preference

- **Decision**: when choosing a pool entrant or a replacement, candidates with positive marginal contribution are split into
  cost (`effect_class(effect) == "cost"`, the 025 `EFFECT_COSTS` table) and cost-free; the takeover set of a candidate is the
  opponents where it would become the best move; the best cost move is taken only if its takeover set has an opponent that no
  cost-free candidate takes over; otherwise the best cost-free candidate. Grass Knot (variable, cost-free) beats Solar Beam
  (charge turn) for Whiscash and Gastrodon.

## R4. The 024 and 025 extras under the same rule

- **Decision**: the variable-power extras rank combos over the marginal pool ∪ offered variable moves with at least one variable
  move, by R2's key, diverse among themselves, not already offered (variable moves may now be in base sets); the 025
  item-conditioned extras build a marginal pool under the item valuation and rank by R2's key. `extra_item_candidates` and the
  screen kinds unchanged.

## R5. The attribution extension (cause `marginal_pool`)

- **Decision**: `attribute()` recomputes, on the branch code and the snapshot's call, the old score pool (top 10 by score) and
  the new marginal pool; a pool entrant is `marginal_pool` when its marginal contribution to the pool before it was positive, a
  pool leaver when its marginal contribution to the new pool is zero; a set change whose moves lie in the new pool and that
  removed a dead move or was accepted one apart (`one_apart`) is `marginal_pool`; the 025 causes (dominated, crit_term,
  appended) remain; anything else is `defect`. The helper also reports per member the dead moves in the snapshot's sets and in
  the branch's sets (the table of FR-011).
- **Rationale**: a label that every pool change earns by definition would make the check empty.

## R6. The allocation of contested resources (story 3)

- **Finding**: `resources.realize` already counts single-copy TMs, evolution items and held items per member in slot order and
  `repair` walks the ranked list on refusal; a move's resources come from `movesources.sources(species, move, level, led,
  option)` → `uses_of(choice)`; copies from `resources.copies`. On B2, Garchomp (slot 1) takes TM26 and TM71; Infernape's
  all-live sets all need one of them.
- **Decision**: `allocation.allocate(consts, variants, level, led, cands)`: (1) for each member, the resources its
  first set needs (the cheapest source per move at the level: the first `sources` choice whose uses are affordable alone;
  a move with a resource-free source needs nothing; HMs are never consumed, so never counted); (2) a resource is contested when
  the members needing it outnumber its copies; (3) for each contested resource, each contender's gain = coverage of
  its first set minus the coverage of its best all-live set with the resource's moves excluded (computed by
  `member_candidates(..., unavailable={moves needing it})`); the top `copies` contenders by gain (ties by slot) keep it; the
  others get `unavailable` extended and their lists rebuilt; (3b) **remaining copies**: the copies left per single-copy
  resource after every member's first set is charged; for each member, every move whose only sources need a resource with zero
  copies left, charged to *other* members' first sets, becomes `unavailable` for that member and its list is rebuilt (a member's
  own first set never makes its own moves unavailable); because a rebuild can change a first set (the pool is greedy, removing a
  move can shift later picks), return to (2) until no first set changes, bounded by the number of single-copy resources;
  (4) the record `{resource: {copies, contenders: [(species, gain)], given_to: [...], rebuilt: [...], unavailable: {species:
  [moves]}}}` goes into the prune stage and provenance. Post-condition: every offered set, extra and setup set of every member is
  buildable beside the other members' first sets at the reference level, so the screen's single-slot deviations need no repair;
  the screen's randomly combined teams (two members' non-first sets) and level differences may still reach the repair step,
  which the acceptance counts and reports.
- **Alternatives**: resource-aware `repair` only (rejected by the owner); full joint optimisation over sets × resources (too
  large; the greedy gain rule is enough for single-copy TMs).

## R7. The report note and the importer

- **Finding**: `team_txt.team_text` returns `export_team` (Showdown format); `legality.models.import_team` splits on blank
  lines and raises on unknown lines; `evaluate.summary_text` is the human summary; the xlsx Team sheet lists members.
- **Decision**: `EvaluationReport.member_notes: list[str]` (default empty; `from_dict` tolerates absence); the optimizer fills it
  from the winner's candidate summaries ("Rotom: Thunder and Ominous Wind are filler: no better option, its two strongest moves
  cover every League opponent"); `team_text` appends a blank line and a block whose first line is `Notes:`; `import_team` skips
  a block whose first line starts with `Notes:` (one guard, tested by the round trip); `summary_text` prints the notes;
  the xlsx Team sheet gains a Note column. `evaluate` of a user-supplied team has no candidate summary and no notes.

## R8. Size and the split rule

- **Decision**: three stories, about 28 tasks expected. If `/speckit-tasks` exceeds about 30 tasks or story 3 needs changes in
  `resources.realize`/`repair`, story 3 becomes feature 027 (the allocation module and its tests), and this feature ships
  stories 1 and 2 with the B2 limitation recorded.
