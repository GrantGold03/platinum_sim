# Quickstart: validating H3 (damage-boosting held items)

From the repo root. Evidence goes in `runs/014-evidence/` (git-ignored) and results in `validation-log.md`. Do not
commit, switch branches or run `extract` while an optimization, the comparison or a suite is running.

## 1. Baseline on `main` (`3078dad` or later, before any code change)

1. `git switch main && uv run platsim extract`.
2. B1-B5 candidates with the 013 snapshot script method → `runs/014-evidence/main-candidates.json`. Positive
   control: equal to `runs/013-evidence/branch-candidates.json` (93 entries; H2 changed no candidate).
3. `/usr/bin/time uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed
   014-b2 --out runs/014-evidence/b2-main` (about 20 min).
4. `git switch 014-damage-boost-items && uv run platsim extract`.

## 2. Candidate rule

- `uv run pytest -q tests/unit/test_optimizer_candidates.py` passes, covering the contract table
  (`contracts/held-item-candidates.md`), the Expert Belt copy test and the report-source test.
- B1-B5 candidates on the branch → `branch-candidates.json`. Every difference is an added `expert_belt` /
  `wise_glasses` at the end of a list; movesets unchanged (SC-001).

## 3. B2

- The same optimize command with `--out runs/014-evidence/b2-branch`, after the code is committed and pushed. Record
  both wall times and the ratio (SC-005), and which members hold which items.
- `uv run python <scratchpad>/equal_levels.py runs/014-evidence/b2-main runs/014-evidence/b2-branch`: both final
  teams at the branch team's start levels, 2,000 paired runs, McNemar exact, mean final levels (research R5). Pass:
  `main` not significantly better, and the branch's average final level not higher (SC-004).

## 4. Gates

- `uv run pytest -q -m "not battle_sim"` and `(cd sim && node --test test/*.test.mjs)` pass (SC-006).
- `platsim explain item:expert_belt` / `item:wise_glasses` show their sources (FR-008).
