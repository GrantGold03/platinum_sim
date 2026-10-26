# Research: Fast test mode without the battle simulations

All findings from reading `main` at `e14f5e0` (2026-10-26). Searches named with what they cover and miss.

## R1. How the battle worker is started

- **Decision**: the single event to watch is the launch of a process whose command is `node` with the script
  `sim/worker.mjs`.
- **Findings** (search: `grep -rn -E 'worker\.mjs|"node"|WorkerPool\(|command='` over `src/platsim`, `tests`; misses
  dynamic string building, which the run-time detection in R2 covers):
  - Production path: `WorkerPool` (`src/platsim/sim/pool.py:194`) builds `["node", str(WORKER_SCRIPT)]` and starts
    each worker with `subprocess.Popen(..., env=self.pool.env)` (`pool.py:83-86`); `self.env` is a copy of
    `os.environ` taken when the pool is created (`pool.py:195`). The optimizer (`optimizer/run.py:283`), `evaluate`
    (`evaluate.py:282`) and the web job child (via the real runner) all go through `WorkerPool`.
  - Direct starts in tests: `test_worker.py:44` and `test_divergences.py:130` run `node sim/worker.mjs` with
    `subprocess.run` (the latter only sends `hello`).
  - Other Node programs that are **not** the battle worker: `sim/dump_dex.mjs` (divergence check,
    `divergence/compare.py:140`), `sim/seeds.mjs` (`test_seeds.py:25`), `sim/version.mjs` (`test_version.py:33`),
    inline `node -e` scripts (`test_legality_options.py:218`, `test_models.py:143`, `test_divergences.py:110`) and
    `test_pool.py`'s stand-in worker (`node -e FAKE`, `test_pool.py:95`). Not battle tests (spec Clarifications).
  - Every start uses the bare name `node`, so it is looked up on `PATH`. CPython looks the name up on the `PATH` of
    the `env` passed to `Popen` (here the pool's copy of `os.environ`).
- **Alternatives considered**: patching `WorkerPool` in-process (`monkeypatch`) misses the direct `subprocess.run`
  starts and anything in a spawned child process (`web/job_process.py:125`, `mp.get_context("spawn")`), which
  imports a fresh copy of the code; rejected.

## R2. Detection that also sees child processes, without changing `src/`

- **Decision**: a `node` stand-in script put first on `PATH` for the whole pytest session (in `tests/conftest.py`).
  - It always runs the real `node` (path found once at session start, before `PATH` changes) with the same
    arguments, so no test behaves differently and none can hang on it.
  - When one argument resolves to `sim/worker.mjs`, it first appends one line to a log file: the current test id,
    whether that test carries the battle mark, and the current fixture name (R4).
  - The current test id, its mark and the current fixture are passed in environment variables that `conftest.py`
    sets before each test's setup and each fixture's setup. Environment variables and `PATH` are inherited by
    `subprocess` children and by `spawn` children, so the web job child and the pool inside it are covered.
- **Checked 2026-10-26** (scratchpad script, Python 3.14 via uv): with a stand-in `node` first on `PATH`,
  `subprocess.run(["node", ...], env=dict(os.environ))` printed `SHIM x` and a `spawn` child's `node` call printed
  `SHIM y`; positive control, the same call with the stand-in removed from `PATH` printed `v22.22.1`.
- **The stand-in must `exec` the real `node`** (replace itself, same pid), not start it as a child:
  `test_web_shutdown.py:66` checks child processes with `pgrep -P`, and an extra process level would change what it
  sees.
- **Rationale**: no change to `src/` or `sim/` (FR-008); one mechanism for in-process, direct and child-process
  starts (FR-003); the real worker still runs, so results are unchanged (SC-005).
- **Known limit**: a launch of the worker by an absolute path to `node` would bypass `PATH`. None exists today (R1
  search). The guard test checks that `WorkerPool`'s default command starts with the bare `node`, so a change there
  fails loudly.
- **Alternatives considered**: an environment variable read by `sim/worker.mjs` itself (changes `sim/`, which
  changes `sim_code_hash` in every result; rejected); `sys.addaudithook` on `subprocess.Popen` (not inherited by
  `spawn` children unless installed there too, and misses nothing more than R2; more moving parts; rejected).

## R3. How a wrong start makes the test fail

- **Decision**: after each test (in `conftest.py`, at the end of the test's teardown), read the log lines for that
  test id. If any line says the worker started while the test had no battle mark, the test is reported as failed
  (an error at teardown, which fails the run) with the message "started the battle worker (sim/worker.mjs) but is
  not marked battle_sim; mark it or stop it from starting the worker". This applies in every run (Clarifications).
- **Rationale**: the test itself runs to completion (the stand-in did not block the real worker), so the report is
  about the mark, not a crash; the message names the test (pytest prints its id).
- **Alternatives considered**: the stand-in refusing to start the worker (exit 1): the pool's restart logic
  (`pool.py:120-123`) then turns it into a different error or a retry, and the message would not name the test;
  rejected.

## R4. Module-scoped fixtures that start the worker

- **Finding**: `test_champion_topup.py:48` (`pool`), `test_ability_screen.py:22` (`pool`) and
  `test_final_levels.py:315` (`runs`) are module-scoped fixtures that start workers once for several tests. In a
  full run only the first test that uses them starts the worker; the others reuse it.
- **Decision**: the log records the fixture being set up when the worker starts. A test is a battle test if it
  started the worker itself **or** it uses (directly or through other fixtures) a fixture that started it. That
  covers both directions:
  - under-marking: an unmarked test that uses such a fixture is caught in the full run too, even when another test
    set the fixture up (checked at the end of the session from the log and each test's fixture list);
  - over-marking: a marked test that reuses the fixture counts as having started the worker.
- **Alternatives considered**: running each marked test alone to see if it starts the worker (about 2.5 h more per
  check; rejected).

## R5. Over-marking check

- **Decision**: at the end of a session, every marked test that ran and passed must have started the worker or use
  a fixture that did (R4). Any that did not are listed and the session fails. Skipped, deselected, failed and
  expected-failure tests are not judged (they may stop before reaching the worker).
- **Rationale**: FR-005 both directions, checked on every run, not only once.

## R6. The mark and the command

- **Decision**: marker `battle_sim`, registered in `pyproject.toml` next to `browser`, with
  `--strict-markers` not added (unchanged behaviour). Whole files that only battle get a module-level
  `pytestmark`; mixed files mark per test. Fast mode: `uv run pytest -m "not battle_sim"`. Battle set alone:
  `uv run pytest -m battle_sim`.
- **Alternatives considered**: a separate test directory (moves files, breaks history and per-test split); a
  custom `--fast` option (more code than a marker expression).

## R7. Candidate split from reading the code (to be confirmed by the detection, not trusted)

| File | Expected | How it reaches the worker |
|---|---|---|
| `test_ability_screen.py` (5) | all battle | module fixture `pool` = `WorkerPool()` |
| `test_champion_topup.py` (6) | all battle | module fixture `pool`, plus `WorkerPool(3)`, `WorkerPool(5)` |
| `test_evaluate.py` (4) | all battle | `platsim.cli evaluate` subprocess → `WorkerPool` |
| `test_final_levels.py` (8) | mixed? | module fixture `runs` → `WorkerPool`; tests not using it stay fast |
| `test_optimize_small.py` (1) | battle | `platsim.cli optimize` subprocess |
| `test_policy_strength.py` (3) | mixed | `WorkerPool(workers)` in 2 tests; `test_reference_team_moves_are_own_level_up_moves` likely not |
| `test_pool.py` (10) | mixed | real `WorkerPool(n)` in some tests; `node -e FAKE` stand-in in others (not battle) |
| `test_worker.py` (1) | battle | `node sim/worker.mjs` directly |
| `test_divergences.py` (5) | 1 battle | `test_divergences.py:130` starts `sim/worker.mjs` for `hello` only; by the spec's rule it is a battle test (it starts the worker) although it is quick |
| `test_web_process_determinism.py` (1) | battle | `_fake_runners.evaluate_runner` runs `cli evaluate`, in-process and in a `spawn` child |
| every other file | fast | web tests use stub/sleepy/instant runners (all `create_app` calls pass `runner=`; search `grep -rn 'create_app(' tests` lines without `runner=`: none) |

Expected battle set: roughly 30-45 tests; fast set: the rest of 522 (+ this feature's tests). The detection decides;
this table is only the starting point, and every difference is recorded.

## R8. Timings

- **Decision**: one full run `uv run pytest -q --durations=0 -rA` (local, about 2.5 h, no paid resources) gives the
  per-test times and serves as the merge-gate run; one `uv run pytest -q -m "not battle_sim"` run measures the fast
  mode (SC-001, at most 30 min). No commits during either run (011 lesson: `repo_commit` is cached per process).
