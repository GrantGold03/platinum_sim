# Quickstart: validating feature 026

1. **Pre-feature side, before any code change** (alone, about 10 min): `uv run python specs/026-marginal-coverage-sets/scripts/acceptance.py --side main --workers 16 > runs/026-evidence/acceptance-main.txt`
   → `runs/026-evidence/b2-main`, `ident-main/{ref,b2main}`, `evidence/candidates-main.json` (36 members) with the dead
   moves per set recorded.
2. **Unit tests**: `uv run pytest -q tests/unit/test_marginal_coverage.py tests/unit/test_optimizer_candidates.py tests/unit/test_variable_power.py tests/unit/test_h4_items.py tests/unit/test_reports.py -m "not battle_sim"`.
3. **Hand check**: `uv run python specs/026-marginal-coverage-sets/scripts/hand_check.py > runs/026-evidence/b2-candidates-branch.txt`:
   the six B2 species' sets, pools, dead moves per set (expected none except Rotom, listed with its reason), the one-apart
   sets, the allocation on the B2 team.
4. **Branch side, alone (about 20 min)**: `uv run python specs/026-marginal-coverage-sets/scripts/acceptance.py --side branch --workers 16 --runs 2000 > runs/026-evidence/acceptance.txt`
   → both winners, the screen overlap and extras by kind, the identity rows, the equal-levels row, the attributed diff (no
   defect; `marginal_pool` verified by recomputing both pools), the dead-moves table before and after, the allocation record,
   zero repair notes for the baseline; the FR-012 verdict.
5. **Gates**: Node suite green; full pytest green; `sim_code_hash` and the ledger version unchanged, `platsim_code_hash`
   changed; the report of a stored pre-026 result still reads (no `member_notes`).
