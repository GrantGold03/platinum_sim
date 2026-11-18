# Quickstart: validating feature 027

1. **Pre-feature side, before any code change** (alone, about 10 min): `uv run python specs/027-extras-dead-moves/scripts/acceptance.py --side main --workers 16 > runs/027-evidence/acceptance-main.txt`
   → `b2-main`, `ident-main/{ref,b2main}`, `evidence/candidates-main.json` with dead moves per extra set (own valuation).
2. **Unit tests**: `uv run pytest -q tests/unit/test_extras_dead_moves.py tests/unit/test_marginal_coverage.py tests/unit/test_h4_items.py tests/unit/test_variable_power.py -m "not battle_sim"`.
3. **Hand check**: `uv run python specs/027-extras-dead-moves/scripts/hand_check.py > runs/027-evidence/b2-candidates-branch.txt`:
   each B2 member's extras with dead moves (expected none or a recorded filler), dropped-extras shortfalls, generation time.
4. **Branch side, alone (about 20 min)**: `uv run python specs/027-extras-dead-moves/scripts/acceptance.py --side branch --workers 16 --runs 2000 > runs/027-evidence/acceptance.txt`
   → winners, extras by kind, identity rows, equal levels, attributed diff (base differences are defects), dead-moves-in-extras
   table; the merge verdict.
5. **Gates**: Node suite; full pytest; `sim` diff empty; sim hash and ledger unchanged; platsim hash changed.
