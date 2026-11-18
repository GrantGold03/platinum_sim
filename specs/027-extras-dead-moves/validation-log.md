# Validation log: feature 027 Dead moves in the extra candidate sets

Branch `027-extras-dead-moves` from `main` 63d6329, main checkout. Times US Eastern.

## T001 Setup (11:47 AM EST, 2026-11-18)

`git diff --stat main -- src sim tests pyproject.toml`: 0 lines. Before-values:

```
sim_code_hash platsim_code_hash: sha256:e968ff0f403539460e6c0260db6253ad971d1a3eb7c02feaa8c9fbe393e74b7d sha256:844bb323589a59fa48de45af7403f93f48e053498a7e60c4dc956e3fcb69037e
divergence_ledger_version: sha256:feb2a48ef2e1dd08 (026's last result; unchanged since)
```

Scripts: `attribution.py` (new for 027: `record_of` stores base sets, their items, the setup set and every extra with kind,
item and dead moves under its own valuation; `attribute` makes any base-set, base-item or setup difference a defect, and an
offered extra keeping a dead move without a filler reason a defect; other extra changes are `extras_rule`),
`acceptance.py` (026's: evidence `runs/027-evidence`, identity seed `027-ident`, `member_notes` volatile, the snapshot
through the 027 helper, both timings (six members; the full team build with the allocation, SC-006); pass also requires 0
base defects, 0 dead moves in extras without a filler reason, and the team build within 10 s), `equal_levels.py` (master
`027-equal|B2`), `hand_check.py`. Positive control on today's code: the helper reports 34 dead moves in the six B2 members'
extras at level 48 and marks them as defects.

## T002 Pre-feature side (11:47:59 to 11:59:24 AM EST, alone, exit 0; code identical to `main` 63d6329)

- B2 quick on today's code: levels [52, 50, 50, 50, 51, 53], clear 0.9440 [0.9203, 0.961] (n 500, 2 attempts), wall 517.5 s:
  the same winner as feature 026's branch acceptance (same candidate code).
- Generation, B2 at the job's reference level 47: six members 1.2 s; the full team build with the allocation 4.7 s (SC-006
  baseline).
- Identity evaluations `ident-main/{ref,b2main}` (200 runs, quick, seed 027-ident).
- Snapshot `evidence/candidates-main.json`: 36 records; **324 extra sets, 208 dead moves under each set's own valuation, 140 sets
  with one, 29 members**: the SC-001 baseline (the same totals as the level-48 recount).
