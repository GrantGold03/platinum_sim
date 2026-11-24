# Quickstart: validate feature 031

1. `cd sim && node --test test/kings_rock.test.mjs`: engine cases per condition.
2. `uv run pytest -q tests/unit/test_kings_rock.py`: offers, extras, copies and substitution.
3. Acceptance (alone): 031's `acceptance.py --side main` before the change, `--side branch --runs 2000` after; pass per the 029 rules.
4. Measurement (alone, report only): B3 quick on the branch, then the paired script on the winner with and without the flinch item.
