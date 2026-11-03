# Implementation Plan: Lead Spike

**Branch**: `020-lead-spike` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/020-lead-spike/spec.md`

## Summary

A measurement-only feature that decides whether the optimizer gets a lead check. On three optimizer-built teams (the
two feature-014 B2 teams and the 018 v2 B2 team, all Garchomp-first) it records 2,000 full gauntlets for each of the
six leads with identical seeds, builds the six-lead table per team, chooses the best lead on the first 1,000 pairs
and tests it against the first-listed lead on the second 1,000 by McNemar exact (split-sample, so the selection bias
of "best of six" never touches the test), reports the naive full-sample test and a pairing control beside it, checks
whether 200 or 400 pairs would have chosen the same lead, and records go or no-go for the confirmation-stage check.
Nothing under `sim/` or `src/platsim` changes.

## Technical Context

**Language/Version**: Python 3.12 (`uv`); Node 22 only through the existing worker pool

**Primary Dependencies**: existing modules only: `platsim.sim.pool.WorkerPool`, `platsim.sim.seeds.derive_seed`,
`platsim.evaluate.run_full_gauntlets` (unchanged), `platsim.stats` (`wilson_ci`, `mcnemar_exact`, `mcnemar_exact_p`);
the feature-019 helper scripts imported by path (`common.assert_idle`, `eastern_now`, `code_hashes`; the JSON-lines
recording layout of `record_runs.py`)

**Storage**: files: eighteen JSON-lines recordings under `runs/020-evidence/` (local, gitignored), analysis outputs as
JSON and text, the small result files copied to `specs/020-lead-spike/evidence/`, the validation log

**Testing**: pytest fast mode for the analysis's pure functions (rotation, selection, held-out and naive McNemar,
control, screening, level gain, seed-list pairing refusal) with a positive and a negative control; the Node suite
unchanged; the pairing control (0 discordant) as the measurement's own control

**Target Platform**: this Linux machine, 16-worker pool, alone during measurements

**Project Type**: scripts under the feature directory plus one unit-test module; no library or CLI change

**Performance Goals**: not applicable; the feature measures. New battles: 18 × 2,000 = 36,000 gauntlets, about 50
minutes at the 12 gauntlets per second 019 measured (stop-on-loss on)

**Constraints**: code hashes identical before and after; replay fixtures untouched; same seeds and opponents on both
sides of every comparison; machine idle for measurements; Eastern times in the log; no commit or suite while a
measurement runs

**Scale/Scope**: 3 teams × 6 leads × 2,000 runs; two scripts, one test module; three commits

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I. Decomp is ground truth | Pass (not touched) | No game data read or produced; the game rule (party reordering between rooms) is already decomp-cited in the assessment. |
| II. Showdown is the engine | Pass | No simulator change; rotation only reorders the request's team list, which the worker already accepts. |
| III. Legality of every output | Pass (not applicable) | No team is produced; the three teams are stored legal results. A rotated order is the same legal team. |
| IV. Reproducible, honest evaluation | Pass | One master seed per team, request seeds `derive_seed(master, i, 0)` identical across the six leads; the pairing control proves it; McNemar exact at alpha 0.05 on a held-out half so the test is not inflated by selection; every rate carries its Wilson interval. |
| V. Verified claims, positive controls | Pass | Unit tests: a lead with a 5-point advantage on independent synthetic runs must show a supported held-out gain, six identical leads must not; the pairing control on real runs; every negative result recorded. |
| VI. Reference-first speed | Pass | Nothing cheaper is adopted; the first-listed lead (today's behaviour) is the reference every lead is paired against. |
| Workflow and gates | Pass | Through Spec Kit; no `sim/` or `src/` edit; merge gate per the spec: fast-mode pytest + Node suite + hash check, full suite skipped with the reason logged. |

**Post-design re-check (after Phase 1)**: unchanged. The one subtle choice (selection on the first half, test on the
second) is a design for honesty, not an approximation.

## Project Structure

### Documentation (this feature)

```text
specs/020-lead-spike/
├── plan.md              # This file
├── research.md          # Phase 0: R1 rotation, R2 selection, R3 held-out test, R4 naive and control, R5 screening, R6 level gain, R7 reuse of 019, R8 layout and cost
├── data-model.md        # Phase 1: Team, LeadRecording, LeadRow, SplitSampleResult, ScreeningResult, Record
├── quickstart.md        # Phase 1: the commands in order with expected outputs
├── contracts/
│   └── scripts.md       # Phase 1: CLI and file formats of the two scripts
├── validation-log.md    # written during implementation
├── evidence/            # small result files copied from runs/020-evidence/
├── scripts/
│   ├── lead_runs.py     # six-lead recorder per team through the pool (US1)
│   └── lead_analysis.py # pure functions + CLI: tables, split-sample test, naive test, control, screening, level gains (US1-US3)
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
tests/unit/test_lead_spike.py     # fast-mode tests of lead_analysis.py pure functions (loaded by path, 018/019 precedent)
runs/020-evidence/                # eighteen recordings and analysis outputs (local, gitignored)
FUTURE-FEATURES.md                # section 8: the record under the lead bullet (docs)
RUN-STATE.md, README.md           # START HERE and the feature's one-paragraph record (docs)
```

**Structure Decision**: scripts under the feature directory, imported by path in the unit tests, never under
`src/platsim` or `sim/`. The recorder reuses the 019 helpers by inserting the 019 scripts directory on `sys.path`
(no copy, so a fix lands in one place), and writes the same JSON-lines layout with lead fields added to the header.

## Complexity Tracking

No constitution violations. No approximation adopted.
