# Validation log: feature 024 variable-power moves

Branch `024-variable-power-moves` from `main` cf4a9ff, main checkout. Times US Eastern. Nothing is copied from the archived
007 to 010 branches (FR-011); their findings were read as hypotheses only.

## T001 Setup (11:59 AM EST)

`git diff --stat main -- src sim tests pyproject.toml` lines: 0 (the branch's code equals `main`, so the pre-feature side can
run here). Before-values (all three expected to change by the end):

```
sim_code_hash platsim_code_hash: sha256:c07be275722f26cf900d810cb52e577b15321cd1c8a7df2f26f196568d5af493 sha256:92793dc145501bae565639b5827c6b6c7a9c3113a48347d7e445ab0248b2370f
divergence_ledger_version: sha256:baeaf406c676c665
```

## T002 Pre-feature side (12:00:45 to 12:09:26 PM EST, alone, exit 0; code identical to `main`)

`acceptance.py --side main --workers 16` (evidence `runs/024-evidence/`, copies in `evidence/pre/`):

- B2 quick on today's code (`runs/024-evidence/b2-main`): species ['garchomp', 'infernape', 'staraptor', 'rotom', 'floatzel', 'weavile'], levels [51, 52, 52, 53, 52, 53], clear
  0.9300 [0.9042, 0.9492] (n 500, 2 confirm attempts), expected
  average final level 52.79, wall 365.9 s, variable-power members: none (as expected: today's
  code offers none). Code: `platsim_code_hash` sha256:92793dc14550..., `sim_code_hash` sha256:c07be275722f...,
  `repo_commit` c949d408109c7d61398689a8f59a88d180502df0. The same levels and clear rate as feature 023's `b2quick-shift` run of this job.
- Identity evaluations (`ident-main/ref`, `ident-main/b2main`; 200 runs, quick, seed 024-ident): written for the comparison
  after the code change (volatile fields removed: code hashes, repo commit, ledger version and entries).
- Candidate snapshot `evidence/b2-candidates-main.json`: the six B2 member variants (all `own`) at the job's reference level 48,
  each with the call arguments, 3 movesets, the setup set, the first 210 ranked combos and the pool.

