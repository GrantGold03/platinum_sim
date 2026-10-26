# Contract: test modes and the battle-test split

## Commands

| Purpose | Command | Gate |
|---|---|---|
| Fast mode (iterate) | `uv run pytest -q -m "not battle_sim"` | not sufficient for a merge |
| Battle set only | `uv run pytest -q -m battle_sim` | not sufficient for a merge |
| Full suite (merge gate) | `uv run pytest -q` and `node --test sim/test/*.test.mjs` | required before every merge |

The README lists all three with the merge rule (FR-002, FR-007).

## Marker

- Name: `battle_sim`; description in `pyproject.toml`: "starts the battle worker (node sim/worker.mjs), directly, via
  a fixture, or in a child process; excluded by the fast mode".
- On a test when, and only when, it reaches the worker (data-model.md). Module-level `pytestmark` only in files where
  every test reaches it.

## Failure messages (exact wording may vary; the meaning and the test id are fixed)

- Unmarked start (at the test's teardown, any run):
  `<test id> started the battle worker (sim/worker.mjs) but is not marked battle_sim. Add
  @pytest.mark.battle_sim, or stop it from starting the worker.`
- Unmarked test reusing a fixture that started the worker (session end, any run):
  `<test id> uses fixture <name>, which starts the battle worker, but is not marked battle_sim.`
- Started outside any test (session end, any run):
  `the battle worker was started outside any test (fixture <fixture or none>).`
- Over-marked (session end, any run):
  `<test id> is marked battle_sim but never reached the battle worker in this run. Remove the mark.`

## How a failure shows

The unmarked-start failure is raised at the test's teardown, so pytest prints it as `ERROR <test id>` (not `FAILED`).
That meets FR-003: the run's exit code is non-zero and the test is named. The session-end failures print in the
terminal summary and set a non-zero exit code.

## What does not change

- Every test's own assertions and outcome; `src/` and `sim/` (code hashes unchanged); the Node test suite.
- Other Node programs (`sim/dump_dex.mjs`, `sim/seeds.mjs`, `sim/version.mjs`, inline `node -e`, `test_pool.py`'s
  stand-in worker) pass through the stand-in unlogged.
