# Validation log: 012 fast test mode

Times in US Eastern. Evidence under `runs/012-evidence/` (git-ignored).

## T001 Setup (2026-10-27)

- `runs/012-evidence/` created; `git check-ignore runs/012-evidence` prints `runs/012-evidence`.
- Start commit: `c81e648127334601472f9207a4fd59415a148dea`.

## T002 Baseline (2026-10-27)

- `uv run pytest --collect-only -q`: `522 tests collected` (exit 0; `runs/012-evidence/collect-baseline.log`).
- Code hashes (`src/platsim/version.py`):
  - `platsim_code_hash` = `sha256:8738fac8b2746f76d2d3c82982d0ca62c2823a5b16cc30612f5608642432d7c6`
  - `sim_code_hash` = `sha256:4fbd74711f43176432816c78bacb816294d6a598c67342674ff0c492af08f566`

## T003-T007 Detection

- `battle_sim` registered in `pyproject.toml`; the plugin registers it too (inner runs).
- Stand-in `tests/node_shim/node` (sh, mode 755): logs `test, marked, fixture, pid` when an argument
  (`realpath -m`) is `sim/worker.mjs`, then `exec`s `$PLATSIM_REAL_NODE`; exit 127 if that is unset.
- Plugin `tests/_battle_split.py`, loaded from `tests/conftest.py` (`pytest_plugins`). Log file:
  `<basetemp>/battle-worker-starts.tsv` (basetemp created early via `config._tmp_path_factory.getbasetemp()`,
  which empties it once; later calls reuse it, so the log survives). Nested pytest resets
  `PLATSIM_TEST_ID/MARKED/FIXTURE` at configure, so starts during its collection count as outside any test.
- Checkpoint: `uv run pytest -q tests/unit/test_constants.py` -> `5 passed in 0.22s`, summary
  `0 battle worker starts; 0 marked tests reached it; under-marked 0, started outside a test 0, over-marked 0`.

## T008-T009 Guard test

- First run, before the marks (`runs/012-evidence/guard-1.log`): `1 failed, 11 passed in 6.80s`; the
  failure was the expected one, `test_known_battle_test_carries_the_mark` (test_worker.py not yet marked,
  `no tests collected (1 deselected)`). Cases 1-9 all behaved as bracketed in tasks.md.
- After T010/T011 (`runs/012-evidence/guard.log`): `12 passed in 6.78s`, exit 0.
  - case 1 unmarked start -> inner exit != 0, `ERROR`, message names `test_case1.py::test_starts_worker`;
  - case 2 marked -> passes, route `own start`; case 3 spawn child -> caught;
  - case 4 over-marked -> session fails with the over-marked message; case 5 shared module fixture -> the
    unmarked second user is named `uses fixture test_case5.py::pool`;
  - case 6 `node -e` and `node sim/seeds.mjs` -> `0 battle worker starts`; case 7 two fixtures named
    `pool` -> `under-marked 0`; case 8 start at import -> `started outside any test (fixture none)`;
  - case 9 positive control (no plugin, stand-in removed from PATH) -> the case-1 test passes;
  - outer checks: test_worker.py carries the mark; `WorkerPool.__init__` default is
    `['node', str(WORKER_SCRIPT)]` (read by `ast`, no pool started); stand-in first on PATH.

## T010-T011 Marks (FR-009: each marked test and its route)

Differences from the R7 table (read before marking, confirmed by the detection in T015):
- `test_ability_screen.py` is **not** all battle: only `test_real_screen_quick_preset` and
  `test_screen_is_deterministic` use the module `pool`; the other 3 call `choose_ability(None, ...)`.
  Marked per test.
- `test_evaluate.py` is **not** all battle: `test_illegal_fixture_exits_2` and
  `test_egg_move_team_exits_2_without_the_flag` exit 2 at validation, before any worker. Marked per test.
- `test_final_levels.py`: 5 marked (the 4 users of module fixture `runs`, plus `test_exp_items_variant`,
  which calls `run_gauntlets` -> `WorkerPool`).
- `test_pool.py`: 5 marked, including the two hello-mismatch tests (a real `WorkerPool` starts real workers
  for `hello` before raising); the 5 `fake_cmd()` tests stay fast.

Marked (26). Expected route (the detection's own list is in T015):

| Test | Route |
|---|---|
| `test_ability_screen.py::test_real_screen_quick_preset`, `::test_screen_is_deterministic` | fixture `pool` |
| `test_champion_topup.py` (module mark, 6 tests) | fixture `pool` (and `strong` -> `pool`); `WorkerPool(3/5)` |
| `test_divergences.py::test_worker_hello_reports_ledger_version` | own start (`subprocess.run`) — confirmed: `1 battle worker starts ... own start`, `5 passed in 3.21s` |
| `test_evaluate.py::test_determinism_fast`, `::test_v7_reference_team_2000_runs` | own start (`cli evaluate` subprocess) |
| `test_final_levels.py::test_final_levels_match_worker`, `::test_final_exp_match_worker`, `::test_positive_control_trainer_factor`, `::test_positive_control_payout_ordering` | fixture `runs` |
| `test_final_levels.py::test_exp_items_variant` | own start |
| `test_optimize_small.py` (module mark, 1 test) | own start (`cli optimize` subprocess) |
| `test_policy_strength.py::test_expectimax2_beats_greedy_paired`, `::test_expectimax2_v2_not_worse_than_greedy_on_reversal_team` | own start |
| `test_pool.py::test_64_gauntlets_on_4_workers_match_single_worker`, `::test_killed_worker_is_restarted_and_its_request_completes`, `::test_hello_mismatch_raises`, `::test_hello_mismatch_decomp_raises`, `::test_real_pool_exposes_sim_code_hash` | own start |
| `test_web_process_determinism.py` (module mark, 1 test) | own start (in-process and `spawn` child) |
| `test_worker.py` (module mark, 1 test) | own start |

Collection: `-m battle_sim` -> `26/534 tests collected (508 deselected)`; `-m "not battle_sim"` ->
`508/534 tests collected (26 deselected)`. 26 + 508 = 534 = 522 + 12 guard tests (SC-002).

## T012 Fast mode

`uv run pytest -q -m "not battle_sim" --durations=25` (`runs/012-evidence/fast.log`), exit 0, wall 602 s:
`504 passed, 26 deselected, 4 xfailed, 1 warning in 599.72s (0:09:59)`. SC-001 (≤ 30 min): met.
- Battle split: `0 battle worker starts; 0 marked tests reached it; under-marked 0, started outside a test 0,
  over-marked 0`. (504 + 4 = 508 = the fast collection.)
- The warning is the pre-existing Starlette `httpx` deprecation (also in the T002 collection log).
- Slowest: `test_extract.py` 220 s, 88 s, 44 s; browser walkthrough setup 40 s; the two `test_evaluate.py`
  exit-2 tests ~40 s each (they spawn `platsim.cli evaluate`, which validates and exits 2 without a worker).

## T015 Full suite

## T016 No behaviour change

- First check, during the first T015 attempt (2026-10-27): `git diff --stat main -- src sim` empty;
  `sim_code_hash` unchanged, but `platsim_code_hash` = `sha256:c935b27e...` != T002. Cause:
  `platsim_code_files` (`src/platsim/version.py:71-78`) includes `pyproject.toml`, and T003 had added the
  marker line there. Effect: results and optimizer checkpoints would carry another hash (a checkpoint with
  another `platsim_code_hash` is refused, `test_optimizer_resume.py:84-86`). The plan missed this.
- Fix: the `pyproject.toml` line removed (`git diff main -- pyproject.toml` empty); the plugin's
  `addinivalue_line` registration (T005) keeps the marker: `pytest --markers` lists `battle_sim`; guard with
  `--strict-markers` `12 passed in 6.85s`; `-m battle_sim` still `26/534`. The first T015 run was stopped
  a few minutes in and restarted on this commit.
- After the fix: `platsim_code_hash` = `sha256:8738fac8...d7c6`, `sim_code_hash` = `sha256:4fbd7471...f566`,
  both identical to T002.
