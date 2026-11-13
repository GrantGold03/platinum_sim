# Contract: candidates by marginal coverage (`platsim.optimizer.candidates`)

- `pool_by_marginal(cands: list[str], vals: dict[str, list[float]], scores: dict[str, float], size=POOL) -> list[str]`:
  greedy; first by score; then max marginal gain, ties by score then name; cost preference (R3) at each step.
- `marginal(move, moveset, vals) -> float`; `dead_moves(moveset, vals) -> list[str]`; `live_moves(cands, vals, scores) -> list[str]`.
- `rank_sets(pool, vals, scores, size=4) -> list[tuple]`: key `(-coverage, -Σ marginal, -Σ score, combo)`.
- `choose_sets(ranked, k, cands, vals, scores) -> (sets, one_apart, no_live_reason)`: passes 1 to 3 of R2 with dead-move
  replacement; deterministic.
- `member_candidates(const, variant, ref_level, led, k=K_MOVESETS, team=None, unavailable=frozenset())`: `unavailable`
  moves are removed from `legal` before pruning; the 024 and 025 extras use the same pool and ranking.
- Unchanged: `dominates`, `prune`, `move_value`, `extra_item_candidates`, `held_item_candidates`, the screen kinds.
- Controls (unit tests): Infernape L48 B2: no Fire Punch in any offered set, no dead move, Grass Knot in a set, three sets with
  `one_apart` non-empty; Floatzel and Weavile: Brick Break in the pool and a set, no dead move; Rotom: sets equal today's,
  `no_live_reason` set; Garchomp and Staraptor: sets equal today's; Solar Beam not chosen when Grass Knot is available
  (synthetic: without Grass Knot, Solar Beam is); a synthetic member whose marginal pool ≠ score pool.
