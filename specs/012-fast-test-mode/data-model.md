# Data model: Fast test mode

No program data changes. The feature adds one log and two derived sets, all inside a pytest session.

## Worker-start record (one line of the session log)

| Field | Meaning |
|---|---|
| `test` | pytest node id of the test running when the worker started (from the environment variable set before its setup) |
| `marked` | `1` if that test carries `battle_sim`, else `0` |
| `fixture` | name of the fixture being set up at that moment, or empty when the start happened in the test body or teardown |
| `pid` | process id of the stand-in (tells starts apart; not compared) |

Tab-separated, appended by the stand-in; written only when an argument resolves to `sim/worker.mjs`. A test that
starts several workers writes several lines.

## Derived sets (computed by `conftest.py` at the end of each test and of the session)

- **Starter fixtures**: fixture names that appear in any record.
- **Reaches the worker** (per test): the test has a record with its own id, or its fixture closure
  (`item.fixturenames`) contains a starter fixture.
- **Under-marked**: an unmarked test that reaches the worker. Fails at its teardown when its own record exists;
  otherwise (shared fixture set up by another test) fails the session at the end.
- **Over-marked**: a marked test that ran, passed and does not reach the worker. Fails the session at the end.

## Validation rules

- Every record with `marked = 0` produces a failure that names the test (FR-003).
- Fast set ∪ battle set = collected tests; no test in both (SC-002): enforced by the marker being either present
  or absent.
