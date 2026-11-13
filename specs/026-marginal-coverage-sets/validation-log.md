# Validation log: feature 026 Candidate sets by marginal coverage

Branch `026-marginal-coverage-sets` from `main` 7c466ae, main checkout. Times US Eastern.

## T001 Setup (about 5:25 PM EST)

`git diff --stat main -- src sim tests pyproject.toml` lines: 0 (the branch's code equals `main`, so the pre-feature side can
run here). Before-values (only `platsim_code_hash` is expected to change; `sim/` must not change at all):

```
sim_code_hash platsim_code_hash: sha256:e968ff0f403539460e6c0260db6253ad971d1a3eb7c02feaa8c9fbe393e74b7d sha256:047562351ac92cdec4042061850daaea072437bdc2bc5dffd2c21c4eda867142
divergence_ledger_version: sha256:feb2a48ef2e1dd08
```

Scripts under `scripts/`: `acceptance.py` (025's: evidence `runs/026-evidence`, identity seed `026-ident`; the snapshot records
dead moves per set, `one_apart`, `no_live_reason` and the candidate-generation time for the six B2 species (SC-006); the
branch side adds the dead-moves table, the allocation record, the baseline-repair and screen-repair counts, and the pass rule
also requires 0 baseline repairs and 0 dead moves outside no-live-move members), `attribution.py` (025's plus `coverage`,
`marginal`, `dead_moves_of`, `dead_table`, and the cause `marginal_pool` verified by recomputation: an entrant's gain to the
pool before it must be positive, a leaver must add no more than the smallest entrant gain, a set change among the new pool's
moves that removed a dead move or was accepted one apart), `equal_levels.py` (master `026-equal|B2`), `hand_check.py` (025's
plus dead moves per set, `one_apart`, `no_live_reason`, the generation time, the allocation record when the code has it).
Smoke on today's code: the helper lists Flamethrower and Fire Punch as dead in Infernape's second set.

## T002 Pre-feature side (5:32:25 to 5:42:10 PM EST, alone, exit 0; code identical to `main` 7c466ae)

`acceptance.py --side main --workers 16` (evidence `runs/026-evidence/`, copies in `evidence/pre/`):

- B2 quick on today's code (`b2-main`): levels [51, 52, 52, 52, 53, 53], clear 0.9380 [0.9133, 0.956] (n 500, 2 attempts),
  wall 429.0 s: the same winner as feature 025's branch run (same code). Its Infernape carries Fire Blast / Flamethrower /
  Close Combat / Fire Punch.
- Candidate generation, six B2 species at level 48: **0.9 s** (SC-006 baseline; the unit tests' 38 s include the ledger build).
- Identity evaluations `ident-main/{ref,b2main}` (200 runs, quick, seed 026-ident).
- Snapshot `evidence/candidates-main.json`: 36 member variants with the dead moves per set computed by the helper:
  **335 dead-move entries** across the 36 members' offered sets (base and extras); Infernape's second set lists Flamethrower
  and Fire Punch, as the spec's evidence says.

## T003 to T010 Code and controls (5:45 to 6:20 PM EST)

`candidates.py`: `marginal`, `dead_moves` (tie-aware: of two moves with equal values the one first by name is live, the
other dead), `live_moves`, `takeover`, `cost_tier`, `prefer_cost_free`, `pool_by_marginal`, `rank_sets`, `_repaired`,
`choose_sets`, `filler_reason`; `member_candidates(..., unavailable=frozenset())` with one value table over attacks and the
offered variable moves, the marginal pool, the 024 and 025 extras over the same pool and ranking; `MemberCandidates.dead_moves`,
`no_live_reason`, `one_apart`, `unavailable` in `summary()`.

Three design corrections found at implementation, each by a real-member control (recorded for the docs task, T018):

1. **The cost class splits into two tiers for pool entry.** The single rule (a cost move refused wherever a cost-free move
   already hits the opponent) locked Close Combat out of Staraptor's pool (its self stat drop is a "cost") while a candidate-only
   rule let Fly in over Aerial Ace. Turn costs (charge turn, recharge, lock-in, delayed hit, first-turn-only, sleep-only,
   fails-when-hit, the user faints: `TURN_COST_EFFECTS`) enter only for an opponent no cost-free move hits at all; damage costs
   (recoil, self stat drops, crash damage) are compared with cost-free candidates only. Dominance keeps the single class.
2. **A set is never dropped for a lower-coverage all-live set.** With a hard all-live rule, Staraptor's Return / Close Combat /
   Aerial Ace (which cover every League opponent, so any fourth move is dead) lost to today's weaker set without Return. Now
   the ranked sets have their dead moves replaced where a live legal move exists, are re-ranked by coverage, and a set keeps a
   dead move only when no live replacement exists (the filler, listed with the reason). FR-004a (option B) is applied as
   stated: a one-apart all-live set replaces a two-apart set only when that set carries a dead move and the all-live set is at
   least as good as its live part; a two-apart all-live set is kept (Garchomp's sets 2 and 3 stay today's).
3. **The marginal-sum tie-break is dropped** (FR-003): a filler that backs nothing up maximises the other moves' marginals, so
   it preferred the weakest filler (Quick Attack over Pluck); the key is today's (coverage, standalone sum, name).

Also found: "live" is set-relative, so the spec's premise that Infernape has five live moves was wrong (Flamethrower is live in
a set without Fire Blast); Infernape gets three all-live sets two apart with Grass Knot in each, no one-apart set needed. And
Staraptor's lists change (the spec's SC-002 expected "unchanged"): Return is a same-type 102-power move on a Normal type, so
it enters the pool and the first set; Fly and Giga Impact (turn costs) stay out.

B2 at level 48 on the branch (`evidence/b2-candidates-branch.txt`, generation 1.4 s for six, SC-006 vs 0.9 s before):
Garchomp's three sets unchanged; Infernape Fire Blast / Close Combat / Earthquake / Grass Knot, Flamethrower / Close Combat /
Stone Edge / Grass Knot, Fire Blast / Focus Blast / Stone Edge / Grass Knot (no Fire Punch, no dead move); Staraptor Return /
Aerial Ace / Close Combat + Pluck (filler, listed), Return / Wing Attack / Close Combat + Secret Power (filler), then today's
first set; Rotom unchanged, listed ("its two strongest moves cover every League opponent"); Floatzel Waterfall / Ice Beam /
Crunch / Brick Break and two Return sets; Weavile Ice Punch / Night Slash / Aerial Ace / Brick Break and two more, all live.

Attributed diff over the 36 snapshot members (the helper recomputes the pool gains): marginal_pool 7781, appended 166,
crit_term 34, **defects 0**. Dead moves in base sets: 92 before (335 over all sets), **0 after outside the 9 listed members**
(Staraptor ×4, Rotom ×2, Chatot, Milotic, Magnezone); the appended sets (024 variable-power, 025 item-conditioned) keep 215
dead-move entries: FR-007 applies only the pool and ranking rule to them (recorded; a candidate refinement for a later feature).

```
uv run pytest -q tests/unit/test_marginal_coverage.py tests/unit/test_optimizer_candidates.py tests/unit/test_variable_power.py tests/unit/test_h4_items.py -m "not battle_sim"
  → 48 passed + (after the helper's filler-tail rule) 20 passed, exit 0 (15 new tests)
```

Fast suite (`runs/026-evidence/fast.log`, 6:03:10 to 6:13:07 PM EST): `617 passed, 32 deselected, 4 xfailed, 1 warning in
594.96s`, exit 0.
