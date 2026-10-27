---
description: "Tasks for 012 fast test mode without the battle simulations"
---

# Tasks: Fast test mode without the battle simulations

**Input**: `specs/012-fast-test-mode/` (spec.md, plan.md, research.md R1-R8, data-model.md, contracts/test-modes.md,
quickstart.md)

**Tests**: requested by the spec (FR-004 guard test with positive controls; FR-005 both-direction check).

**Rules for every task**: no change to `src/` or `sim/` (FR-008). Temp files only under pytest's basetemp or the
session scratchpad. Never commit while a full run is going (011 lesson: `repo_commit` is cached per process). Never
`git commit -a` (the user's `.claude/scheduled_tasks.lock` deletion stays out). Push every commit that touches tests.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Create `runs/012-evidence/` (confirm `git check-ignore runs/012-evidence` prints it) and
  `specs/012-fast-test-mode/validation-log.md` with headings per task; record the start commit (`git rev-parse HEAD`)
- [X] T002 Baseline, recorded in `specs/012-fast-test-mode/validation-log.md`: `uv run pytest --collect-only -q`
  count (expect 522), and `uv run python -c "from platsim import version; print(version.platsim_code_hash(),
  version.sim_code_hash())"` (`src/platsim/version.py:81,85`) for the FR-008 comparison at T016

## Phase 2: Foundational (the detection; blocks US1)

- [X] T003 Register `battle_sim` in `pyproject.toml` `[tool.pytest.ini_options] markers`, next to `browser`, with the
  description from `contracts/test-modes.md`
- [X] T004 Write the stand-in `tests/node_shim/node` (POSIX `sh`, executable bit committed: `git update-index
  --chmod=+x`): for each argument, if it resolves (`realpath -m`, relative to `$PWD`) to `$PLATSIM_WORKER_SCRIPT`,
  append one tab-separated line `test, marked, fixture, pid` (data-model.md) from `$PLATSIM_TEST_ID`,
  `$PLATSIM_TEST_MARKED`, `$PLATSIM_FIXTURE`, `$$` to `$PLATSIM_WORKER_LOG` (skip logging only if
  `$PLATSIM_WORKER_LOG` is unset; an empty `$PLATSIM_TEST_ID` is still logged, see T007); then always
  `exec "$PLATSIM_REAL_NODE" "$@"` (exec, not a child: `test_web_shutdown.py` counts child processes with
  `pgrep -P`, so no extra process may appear). Fail loudly (exit 127 with a message) if `$PLATSIM_REAL_NODE` is unset
- [X] T005 Write the plugin `tests/_battle_split.py` (loaded by `tests/conftest.py` via `pytest_plugins`), part 1,
  setup (research R2):
  - `pytest_configure`: real node = `$PLATSIM_REAL_NODE` if already set (nested pytest under the stand-in), else
    `shutil.which("node")` before changing `PATH`; set `PLATSIM_REAL_NODE`, `PLATSIM_WORKER_SCRIPT`
    (`REPO_ROOT/sim/worker.mjs` resolved), `PLATSIM_WORKER_LOG` (a fresh file under this session's basetemp), and
    prepend `tests/node_shim` to `os.environ["PATH"]`;
  - hookwrappers `pytest_runtest_setup`/`call`/`teardown`: set `PLATSIM_TEST_ID` = `item.nodeid`,
    `PLATSIM_TEST_MARKED` = `1`/`0` from `item.get_closest_marker("battle_sim")`, clear `PLATSIM_FIXTURE`;
  - hookwrapper `pytest_fixture_setup`: set `PLATSIM_FIXTURE` = `<fixturedef.baseid>::<fixturedef.argname>` (the
    fixture's defining location plus its name, so the two fixtures named `pool` in `test_champion_topup.py:49` and
    `test_ability_screen.py:23` stay distinct) around the setup, restore after;
  - `pytest_configure` also registers `battle_sim` itself (`config.addinivalue_line("markers", ...)`), so the plugin
    works without `pyproject.toml` (inner runs in T008)
- [X] T006 `tests/_battle_split.py` part 2, per-test check (research R3): at the end of each test's teardown read the
  log lines for `item.nodeid`; if any has `marked = 0`, fail the test with the contract's "Unmarked start" message
  (report as failed at teardown, so the run's exit code is non-zero)
- [X] T007 `tests/_battle_split.py` part 3, session check (research R4, R5): at `pytest_sessionfinish`, from the log
  and each collected item's `fixturenames` and outcome:
  - starter fixtures = the `<baseid>::<name>` values in any record; a test uses one when the fixture that pytest
    resolved for it (`item._fixtureinfo.name2fixturedefs[name][-1]`, matched on `baseid` and `argname`) is that
    fixture, never by name alone;
  - under-marked via a shared fixture: unmarked tests that ran and use a starter fixture → contract message;
  - started outside any test: records with an empty test id (e.g. at collection) → contract message "the battle
    worker was started outside any test (fixture <f>)";
  - over-marked: marked tests that passed and have neither their own record nor a starter fixture → contract message;
  - print a "battle split" summary in `pytest_terminal_summary` (counts; the route per marked test: own start, or
    fixture name) and, if `$PLATSIM_SPLIT_REPORT` is set, write it there as JSON; set the session exit status to
    failed when any of the three lists is non-empty

**Checkpoint**: run `uv run pytest -q tests/unit/test_constants.py` (no Node): passes, summary shows 0 starts.

## Phase 3: User Story 1 - Run every test except the battle simulations in minutes (Priority: P1) 🎯 MVP

**Goal**: one command runs every non-battle test; the split is enforced both ways in every run.

**Independent Test**: `uv run pytest -q -m "not battle_sim"` finishes in ≤ 30 min with no split failure; the guard test
passes; fast + battle = full collection.

### Tests for User Story 1

- [X] T008 [US1] Guard test `tests/unit/test_battle_split.py`. Each case writes throwaway test files into `tmp_path`
  and runs an inner `sys.executable -m pytest -p _battle_split -p no:cacheprovider -q
  --basetemp=<tmp_path>/inner --rootdir=<tmp_path> <files>` with `PYTHONPATH` = `tests/` and `cwd` = `REPO_ROOT`
  (the repo's `conftest.py` does not load for files outside `tests/`, so without `--basetemp` pytest would use its
  default under `/tmp`); cases (expected outcome in brackets):
  1. unmarked test running `subprocess.run(["node", "sim/worker.mjs"], input="")` [fails, message names it];
  2. the same test marked `battle_sim` [passes];
  3. unmarked test whose worker start happens in a `multiprocessing` `spawn` child [fails];
  4. marked test that starts no worker [session fails: over-marked];
  5. module-scoped fixture starting the worker, used by a marked test and then an unmarked one [session fails:
     the unmarked one named, via the fixture];
  6. unmarked test running a non-worker Node program (`node -e "1"`) [passes; not logged];
  7. two modules each defining a module fixture named `pool`; only one starts the worker and is used by a marked
     test; an unmarked test in the other module uses its own `pool` [passes: no false match by name];
  8. a worker started at import time of an inner test module (collection, outside any test) [session fails:
     started outside any test];
  9. positive control for the instrument: case 1 run with `-p no:_battle_split` and `PATH` without the stand-in
     [passes], proving the failure in case 1 comes from the detection.
  In the outer session also assert: `tests/integration/test_worker.py`'s test carries `battle_sim` (collected
  marker), and `platsim.sim.pool.WorkerPool`'s default command starts with the bare `"node"` (read the default
  without starting workers: inspect `pool.py`'s `WORKER_SCRIPT` and the `__init__` default, e.g. construct the list
  the same way the class does or check the source line; do not start a pool). This file must not be marked
  (it must start no worker in the outer session)
- [X] T009 [US1] Run `uv run pytest -q tests/unit/test_battle_split.py` and record the output in validation-log.md;
  every case behaves as bracketed

### Implementation for User Story 1

- [X] T010 [P] [US1] Mark whole battle files with module-level `pytestmark = pytest.mark.battle_sim` (research R7):
  `tests/integration/test_ability_screen.py`, `test_champion_topup.py`, `test_evaluate.py`,
  `test_optimize_small.py`, `test_worker.py`, `test_web_process_determinism.py`
- [X] T011 [US1] Mark per test in mixed files, after reading each test (research R7):
  `tests/integration/test_final_levels.py` (tests using fixture `runs` or a `WorkerPool`), `test_policy_strength.py`
  (the 2 `WorkerPool` tests), `test_pool.py` (tests that use a real `WorkerPool(n)`, not only `fake_cmd()`),
  `test_divergences.py` (the test at :130 that runs `sim/worker.mjs`). List each marked test with its route in
  validation-log.md (FR-009)
- [X] T012 [US1] Run the fast mode `uv run pytest -q -m "not battle_sim" --durations=25` (background), output to
  `runs/012-evidence/fast.log`; record the summary line, wall time (SC-001 ≤ 30 min), the battle-split summary, and
  `--collect-only` counts for `-m battle_sim` and `-m "not battle_sim"` (sum = full collection, SC-002). Any split
  failure: fix the mark (T010/T011), note it, rerun the affected file
- [ ] T013 [US1] Commit and push the test changes (`pyproject.toml`, `tests/conftest.py`, `tests/_battle_split.py`,
  `tests/node_shim/node`, `tests/unit/test_battle_split.py`, marked files)
- [X] T014 [P] [US1] README: next to the full-suite command, add the fast-mode and battle-set commands and the merge
  rule (full pytest suite + Node suite before every merge; fast mode never sufficient), per contracts/test-modes.md

## Phase 4: Polish & verification

- [ ] T015 Full suite in the background, no commits while it runs: `uv run pytest -q --durations=0 -rA` with
  `PLATSIM_SPLIT_REPORT=runs/012-evidence/split.json`, output `runs/012-evidence/full-pytest.log`, then
  `node --test sim/test/*.test.mjs` to `runs/012-evidence/full-node.log`; record in validation-log.md: summary lines
  vs 2026-10-26 (517 passed + the mid-run-commit test now passing, 4 xfailed, plus the new guard tests; Node 314),
  0 under-marked and 0 over-marked (FR-005, SC-003), the per-test times of the slowest tests in each set, and every
  difference from the R7 table
- [ ] T016 Confirm no behaviour change: `git diff --stat main -- src sim` is empty, and the T002 hashes are unchanged
  (FR-008)
- [ ] T017 Update `FUTURE-FEATURES.md` item 5 (built; waits for the user's test), `RUN-STATE.md` (012 section and
  start-here), mark tasks; commit docs and push
- [ ] T018 Hand over for the user's hands-on test (quickstart 4) with the measured fast-mode time and the battle-set
  list. Do not merge

## Dependencies & Execution Order

- T001 → T002 → T003 → T004 → T005 → T006 → T007 (same plugin file; sequential).
- T008 needs T004-T007; T009 after T008.
- T010 and T011 need T003; T010 [P] with T008. T012 needs T008-T011. T013 after T012. T014 [P] any time after T003.
- T015 after T013 (and T014 committed first: no commits during the run). T016 any time after T013. T017, T018 last.

## Parallel Example: User Story 1

```text
T008 (guard test file) and T010 (module-level marks) touch different files and can be written together.
T014 (README) can be written while T012 runs, but committed only before T015 starts.
```

## Implementation Strategy

MVP = Phases 1-3 (T001-T014): the fast mode works and is enforced. Phase 4 is the merge gate run (about 2.5 h,
local) plus docs. 18 tasks, one story.
