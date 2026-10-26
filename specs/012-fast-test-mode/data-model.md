# Data model: Fast test mode

No program data changes. The feature adds one log and two derived sets, all inside a pytest session.

## Worker-start record (one line of the session log)

| Field | Meaning |
|---|---|
| `test` | pytest node id of the test running when the worker started (from the environment variable set before its setup) |
| `marked` | `1` if that test carries `battle_sim`, else `0` |
| `fixture` | `<baseid>::<name>` of the fixture being set up at that moment (its defining location plus its name; two fixtures may share a name, e.g. `pool` in `test_champion_topup.py` and `test_ability_screen.py`), or empty when the start happened in the test body or teardown |
| `pid` | process id of the stand-in (tells starts apart; not compared) |

Tab-separated, appended by the stand-in; written only when an argument resolves to `sim/worker.mjs`. A test that
starts several workers writes several lines.

## Derived sets (computed by `conftest.py` at the end of each test and of the session)

- **Starter fixtures**: `<baseid>::<name>` values that appear in any record.
- **Reaches the worker** (per test): the test has a record with its own id, or one of the fixtures pytest resolved
  for it (matched on defining location and name, never name alone) is a starter fixture.
- **Under-marked**: an unmarked test that reaches the worker. Fails at its teardown when its own record exists;
  otherwise (shared fixture set up by another test) fails the session at the end.
- **Over-marked**: a marked test that ran, passed and does not reach the worker. Fails the session at the end.
  Marked tests that failed, were skipped or are expected failures are not judged (they may stop before the worker).
- **Started outside a test**: a record with an empty `test` (e.g. a start during collection). Fails the session.

## Validation rules

- Every record with `marked = 0` produces a failure that names the test (FR-003).
- Fast set ∪ battle set = collected tests; no test in both (SC-002): enforced by the marker being either present
  or absent.
