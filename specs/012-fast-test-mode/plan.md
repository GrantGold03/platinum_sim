# Implementation Plan: Fast test mode without the battle simulations

**Branch**: `012-fast-test-mode` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/012-fast-test-mode/spec.md`

## Summary

Mark every pytest test that starts the battle worker (`node sim/worker.mjs`) with `battle_sim`, and run the rest with
`uv run pytest -m "not battle_sim"`. Correctness of the split is enforced at run time, in every run, by a `node`
stand-in that `tests/conftest.py` puts first on `PATH`: it runs the real `node` unchanged but logs each start of the
battle worker with the current test and fixture. An unmarked test that started the worker (or uses a fixture that did)
fails; a marked test that never reaches the worker fails the session. Nothing in `src/` or `sim/` changes.

## Technical Context

**Language/Version**: Python 3.14 (uv); a POSIX `sh` stand-in script; Node ≥ 22.18 unchanged

**Primary Dependencies**: pytest (existing); no new packages

**Storage**: one log file per pytest session under the session's basetemp (`/dev/shm/platsim-pytest-<pid>`, removed
at exit by the existing `conftest.py` cleanup)

**Testing**: pytest; new `tests/unit/test_battle_split.py` (guard with positive controls); the full suite and the
Node suite as the merge gate

**Target Platform**: this Linux machine

**Project Type**: CLI + local web app (existing); this feature touches test infrastructure only

**Performance Goals**: fast mode ≤ 30 min (SC-001; estimate 10-12 min); the stand-in adds one `sh` start per `node`
start (a few ms; a few hundred `node` starts per full run)

**Constraints**: no change to `src/`, `sim/` (FR-008: `sim_code_hash` and `platsim_code_hash` unchanged); no commits
while a full run is going (011 lesson)

**Scale/Scope**: 522 tests today; expected battle set about 30-45 (research R7); edits in `tests/conftest.py`,
`pyproject.toml`, about 10 test files (marks only), one new test file, a stand-in script, README

## Constitution Check

Constitution v1.4.0.

| Principle | Check | Status |
|---|---|---|
| I. Decomp is ground truth | No data change | N/A |
| II. Showdown is the battle engine | No battle change; the real worker still runs in every test | N/A |
| III. In-game legality | No validator change | N/A |
| IV. Reproducible, honest evaluation | `src/` and `sim/` untouched, so results and code hashes are unchanged; full suite outcomes compared with the 2026-10-26 run (SC-005) | PASS (planned) |
| V. Verified claims, positive controls | Guard test: a deliberately unmarked worker start must be caught; a known battle test must carry the mark; a fake over-marked test must be reported. Both split directions checked on every run; the full run's record is pasted in the validation log | PASS (planned) |
| VI. Reference-first speed | The fast mode is a subset, not an approximation: the full suite (the reference) stays the merge gate (FR-007) | PASS |
| Development workflow | Spec Kit for the test changes; full suite + Node suite green before merge, output recorded | PASS (planned) |

Post-design re-check: unchanged, PASS.

## Project Structure

### Documentation (this feature)

```text
specs/012-fast-test-mode/
├── spec.md
├── plan.md              # this file
├── research.md          # R1-R8
├── data-model.md        # battle test, worker-start record, split report
├── quickstart.md        # how to run and check it
├── contracts/
│   └── test-modes.md    # commands, marker, failure messages
├── checklists/requirements.md
├── validation-log.md    # created during implementation
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml                         # register the battle_sim marker
tests/
├── conftest.py                        # PATH stand-in, per-test/fixture env vars, teardown check, session check
├── node_shim/node                     # the stand-in (sh): log worker starts, exec the real node
├── unit/test_battle_split.py          # guard test with positive controls
└── integration/                       # battle_sim marks (module-level or per test, research R7)
README.md                              # fast command next to the full-suite command; merge rule
FUTURE-FEATURES.md, RUN-STATE.md       # item 5 status
```

**Structure Decision**: existing single project; test infrastructure only.

## Complexity Tracking

None.
