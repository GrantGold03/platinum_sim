# Validation log: feature 025 H4, Wide Lens and Razor Claw

Branch `025-h4-wide-lens-razor-claw` from `main` 3a91eac, main checkout. Times US Eastern.

## T001 Setup (12:54 PM EST)

`git diff --stat main -- src sim tests pyproject.toml` lines: 0 (the branch's code equals `main`, so the pre-feature side can
run here). Before-values (only `platsim_code_hash` is expected to change; `sim/` gains a test file only, outside the hash):

```
sim_code_hash platsim_code_hash: sha256:e968ff0f403539460e6c0260db6253ad971d1a3eb7c02feaa8c9fbe393e74b7d sha256:eb92dee26412cbc7226f65d030a30df0a914b267f9506a67fa78064246edde42
divergence_ledger_version: sha256:feb2a48ef2e1dd08
```

## T002 Pre-feature side (12:55:39 to 1:04:39 PM EST, alone, exit 0; code identical to `main`)

`acceptance.py --side main --workers 16` (adapted from 024's; evidence `runs/025-evidence/`, copies in `evidence/pre/`):

- B2 quick on today's code (`runs/025-evidence/b2-main`): species ['garchomp', 'infernape', 'staraptor', 'rotom', 'floatzel', 'weavile'], levels [51, 52, 52, 53, 52, 53], clear 0.9300
  [0.9042, 0.9492] (n 500, 2 attempts), expected average final level
  52.79, wall 380.4 s, no member holds Wide Lens or Razor Claw (as expected). Code
  `platsim_code_hash` sha256:eb92dee26412..., `repo_commit` 741f519cd379. The same winner, levels and clear rate as
  feature 024's acceptance of this job.
- Identity evaluations `ident-main/{ref,b2main}` (200 runs, quick, seed 025-ident) for the comparison after the code change.
- Snapshot `evidence/candidates-main.json`: 36 member variants (B2's six at reference level 48; every B1 to B5 member at its
  recorded level) with the call arguments, movesets, setup, the full ranked list, pool, pruned map, scores and items per set.

