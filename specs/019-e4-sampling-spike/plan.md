# Implementation Plan: Elite Four Sampling Spike

**Branch**: `019-e4-sampling-spike` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/019-e4-sampling-spike/spec.md`

## Summary

A measurement-only feature that decides whether adaptive Elite Four sampling (assessment `e4-scope`) is built. It
answers three questions with pass-or-kill numbers: (1) a composite estimator (Elite Four pass rate × Cynthia's
conditional rate, with a conservative interval) checked offline against the ten stored evaluations with at least
2,000 runs; (2) the adaptive rule replayed on two fresh 2,000-run recordings (reference fixture team, bench-010 B3)
over three floors and 200 run orders; (3) the Elite Four share of wall time inside a level-search-like setting on the
real pool, through an in-memory timing harness checked by digests. A projection against the 769 s and 350 s
baselines and the clarified go rule closes the feature with a go / no-go record for feature 021. Nothing under
`sim/` or `src/platsim` changes; the code hashes are proven identical.

## Technical Context

**Language/Version**: Python 3.12 (`uv`), Node 22 (the worker pool; the timing hook only)

**Primary Dependencies**: existing project modules only: `platsim.sim.pool.WorkerPool`, `platsim.sim.seeds.derive_seed`,
`platsim.stats` (Wilson interval, half-width, `runs_needed`), `platsim.budget.get_preset`, `platsim.bench` (the pool-side
`digest_logs`), `platsim.evaluate.run_full_gauntlets` (reused as is for the recordings); Node `node:module` `register`
hooks for the timing harness (the 016/017 profiling precedent)

**Storage**: files: `runs/019-evidence/` (recordings as JSON lines, replay and timing outputs as JSON, logs), the
validation log under the feature directory

**Testing**: pytest fast mode (`-m "not battle_sim"`) for the estimator's and replay's pure functions; the Node suite
unchanged; the harness-versus-plain digest check as the measurement's own control

**Target Platform**: this Linux machine, 16-worker pool, alone during measurements

**Project Type**: scripts under the feature directory plus unit tests; no library or CLI change

**Performance Goals**: not applicable to the feature itself; it measures. New battles are bounded: two 2,000-run
recordings (about 13 min each on the pool) and the timing runs (three teams × three batch sizes, about 8 min)

**Constraints**: `sim_code_hash` and `platsim_code_hash` identical before and after; replay fixtures untouched; same
seeds and opponents on both sides of every comparison; machine idle for measurements; Eastern times in the log

**Scale/Scope**: 10 stored results (8 distinct), 2 recordings × 2,000 runs, 3 floors × 200 orders, 3 teams × 3
batch sizes; about five scripts and one test module

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I. Decomp is ground truth | Pass (not touched) | No game data is read or produced; stored results and fresh gauntlets use the pinned data as today. |
| II. Showdown is the engine | Pass | No simulator change. The timing hook patches `sim/gauntlet.mjs` in memory only, adds timing side-output, and is proven not to change results by identical `digest_logs` against a plain run. |
| III. Legality of every output | Pass (not applicable) | No team is produced. The recorded teams are stored legal results (B3) and the legal reference fixture. |
| IV. Reproducible, honest evaluation | Pass | Recordings use `derive_seed("019-record-<team>", i, 0)` in index order with the default player and `decomp-ai`; the replay's 200 orders come from a fixed seed; every number is reported with its interval; the composite interval is conservative by construction (R1). |
| V. Verified claims, positive controls | Pass | The estimator has a positive control (a synthetic Elite Four pass rate below threshold must yield a differing verdict) and a not-estimable case; the timing harness is checked against a plain run by digest before any share is reported; every pass / kill is recorded with its numbers, negative results included. |
| VI. Reference-first speed | Pass | This feature is step 1 of Principle VI for feature 021: the full gauntlet is the reference, nothing cheaper is adopted here. The projection is labelled a projection, not a measurement of the method. |
| Workflow and gates | Pass | Through Spec Kit; no `sim/` or `src/` edit (FR-001, SC-007); merge gate clarified as fast-mode pytest + Node suite with the code-hash check logged. |

**Post-design re-check (after Phase 1)**: unchanged. The one design choice that could have become an approximation
(how the replay values the Cynthia-only phase, R3) is an offline accounting rule, labelled as such, and not a change
to any run.

## Project Structure

### Documentation (this feature)

```text
specs/019-e4-sampling-spike/
├── plan.md              # This file
├── research.md          # Phase 0: R1 interval, R2 verdict rule, R3 replay rule, R4 harness, R5 timing design, R6 projection, R7 layout, R8 dedup
├── data-model.md        # Phase 1: stored evaluation, composite estimate, recording, replay result, time-share, projection, go/no-go record
├── quickstart.md        # Phase 1: the commands, in order, with expected outputs
├── contracts/
│   └── scripts.md       # Phase 1: CLI and file formats of the five scripts
├── validation-log.md    # written during implementation (Eastern times, commands, hashes, outputs)
├── scripts/
│   ├── e4_estimator.py  # pure functions + CLI over stored result.json files (US1)
│   ├── record_runs.py   # 2,000-run recording per team through the pool (US2)
│   ├── e4_replay.py     # offline adaptive-rule replay over a recording (US2)
│   ├── time_share.py    # pool runs with the timing hook, digest check, share report (US3)
│   ├── hooks/register.mjs, hooks/hooks.mjs   # in-memory timing hook for the worker (US3)
│   └── projection.py    # wall-time projection from replay + time share (US3)
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
tests/unit/test_e4_estimator.py   # fast-mode tests of e4_estimator.py and e4_replay.py pure functions (loaded by path, 018 precedent)
runs/019-evidence/                # recordings, replay and timing outputs, logs (committed)
FUTURE-FEATURES.md                # section 8: go / no-go record for feature 021 (docs)
RUN-STATE.md, README.md           # START HERE and the feature's one-paragraph record (docs)
```

**Structure Decision**: scripts live under the feature directory (the 014 and 018 precedent), are imported by path in
the unit tests, and never under `src/platsim` or `sim/`, so the code hashes cannot change. The timing hook lives
beside the scripts and is loaded into the worker only through `NODE_OPTIONS` set on the pool's environment.

## Complexity Tracking

No constitution violations. No approximation is adopted. The replay's valuation of the Cynthia-only phase (R3) is an
offline accounting rule with a stated limitation, not an adopted shortcut.
