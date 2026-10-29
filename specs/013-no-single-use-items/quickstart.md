# Quickstart: validating H2 (no single-use held items)

Run from the repo root on branch `013-no-single-use-items`. Record outputs in `validation-log.md`. Evidence goes under
`runs/013-evidence/` (git-ignored). Do not commit while the suite or the B2 run is going (`repo_commit` is cached
per process).

## 1. Baseline on `main` (before any code change)

1. `git switch main && uv run platsim extract`.
2. Capture the B1-B5 held-item candidates (same 93-entry set and script method as 011 T004) →
   `runs/013-evidence/main-candidates.json`.
3. `uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 013-sc005
   --out runs/013-evidence/sc005-main` (about 25 min, local).
4. `git switch 013-no-single-use-items && uv run platsim extract`.

## 2. Classifier

- `uv run pytest -q tests/unit/test_item_use.py` passes. It shows the positive controls (Focus Sash single-use and
  not a berry; Sitrus single-use and a berry), the not-single-use set, and that the reader raises on an
  unattributed `RemoveItem` (checked by feeding it a copied script with one extra site).
- Print the excluded set (`single_use and not berry`) and compare it with research R4. List any extra item, with its
  decomp check.

## 3. Candidate rule

- `uv run pytest -q tests/unit/test_optimizer_candidates.py` passes, including the guard test: an injected
  `focus_sash` is filtered out, and with the filter off it would appear.
- Re-capture the B1-B5 candidates on the branch → `runs/013-evidence/branch-candidates.json`. Expect the same keys,
  0 entries differing.

## 4. Same-seed B2

- Same command as 1.3 with `--out runs/013-evidence/sc005-branch`, after the code is committed and pushed.
- Field-by-field diff of `result.json`: only `/platsim_code_hash` and `/repo_commit` differ.

## 5. Gates

- `uv run pytest -q -m "not battle_sim"` (fast mode, about 10 min) and `(cd sim && node --test test/*.test.mjs)` (314 tests on `main`) pass.
  Paste the summary lines into the log.
