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
