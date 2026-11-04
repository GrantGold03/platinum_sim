# Implementation Plan: Adaptive Sampling in the Optimizer's Confirmation Stage

**Branch**: `022-confirm-adaptive-sampling` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/022-confirm-adaptive-sampling/spec.md`

## Summary

`platsim optimize` gains `--sampling {full,adaptive}` (default `full` until the owner's go) and `--floor` (default
0.98) on `OptimizeRequest`, in the job fingerprint only when non-default. The confirmation stage calls the same
`evaluate_team` path as `evaluate`, now with `sampling` and `floor`; the 021 guard that refused adaptive sampling with
the borderline extension is replaced by a borderline extension inside `run_adaptive` (the 021 extension rule applied
while the composite interval straddles, up to the cap). The runner-up comparison stays paired by identical seeds:
full runs by run index, Cynthia-only runs by their ordinal (both teams derive the same seed for the same ordinal),
surplus runs excluded and counted. state.json's confirm attempts and provenance record the run mix and the sampling
per stage. The level search and the setup check are untouched; so is `sim/`.

## Technical Context

**Language/Version**: Python 3.12 (`uv`); Node 22 only through the unchanged worker

**Primary Dependencies**: `platsim.sampling` (021: `run_adaptive`, `AdaptiveRuns`, `composite_estimate`, `extension_kind`),
`platsim.evaluate.evaluate_team` (021 signature), `platsim.optimizer.run` (`_confirm`, `job_fingerprint`, provenance),
`platsim.optimizer.api.OptimizeRequest`, `platsim.stats.mcnemar_exact`, `platsim.cli`

**Storage**: state.json (confirm attempts gain the run mix), the winner's result.json (021 fields), acceptance evidence
under `runs/022-evidence/` (local) with small files under `specs/022-confirm-adaptive-sampling/evidence/`

**Testing**: fast-mode unit tests for the pairing function, the request fields and the fingerprint rule, and the
borderline extension in `run_adaptive` on a fake pool; a `battle_sim` test running a quick optimize on the reference
species with `--sampling adaptive --floor 0.9` at two worker counts; the existing optimize and resume tests; the full
pytest suite and the Node suite as the merge gate

**Target Platform**: this Linux machine, 16-worker pool

**Project Type**: library + CLI change in the optimizer and the sampling module; no `sim/` change

**Performance Goals**: the confirmation stage about 1.7x faster on b2-main-like winners at floor 0.98 (021 measured
1.70x on that team), about 1.0x on Lucian-heavy winners; the whole B2 quick run reported with its ratio

**Constraints**: result.json a pure function of the request (worker-count and resume independence); pre-feature
checkpoints refused (the code fingerprint in state.json already includes `platsim_code_hash`, research R1); the level
search and setup check unchanged; `sim_code_hash` unchanged

**Scale/Scope**: edits to `run.py` (confirm stage, fingerprint, provenance), `api.py`, `cli.py`, `sampling.py` (borderline
extension) and `evaluate.py` (lift the guard, pass the extension through); one new pure function for pairing; three
test modules; an acceptance script; docs. Four commits plus the optional flip.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I. Decomp is ground truth | Pass (not touched) | No game data or rule changes. |
| II. Showdown is the engine | Pass | No simulator change; the confirmation reuses 021's requests. |
| III. Legality of every output | Pass | The optimizer's outputs are produced and validated as today; the confirmation only changes how the winner's clear rate is estimated. |
| IV. Reproducible, honest evaluation | Pass | Same master seed per stage; full runs paired by index and Cynthia-only runs by ordinal, both by identical seeds; mixed or surplus runs excluded and counted; result.json independent of worker count and of resume; the composite interval is the 021 delta interval. |
| V. Verified claims, positive controls | Pass | Pairing unit tests with positive and negative controls; the pairing control on real runs (full-kind pairs reproduce the full method's counts exactly); the resume control; acceptance negatives recorded. |
| VI. Reference-first speed | Pass | `full` stays available and is the default until the owner's go; the acceptance pairs adaptive against full on the same seeds; wall times recorded. |
| Workflow and gates | Pass | Through Spec Kit; behaviour change under `src/platsim`, so the full pytest suite and the Node suite gate the merge. |

**Post-design re-check (after Phase 1)**: unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/022-confirm-adaptive-sampling/
├── plan.md, research.md (R1-R9), data-model.md, quickstart.md
├── contracts/
│   ├── optimize-cli-and-state.md   # the flags, the request fields, the fingerprint rule, confirm attempts, provenance
│   └── pairing-api.md              # paired_outcomes and the run_adaptive borderline extension
├── scripts/acceptance.py           # the four acceptance blocks
├── evidence/, validation-log.md, tasks.md
```

### Source Code (repository root)

```text
src/platsim/optimizer/api.py        # OptimizeRequest.sampling, .floor
src/platsim/optimizer/run.py        # _confirm: evaluate_team(sampling, floor); runner-up on the same method; pairing; attempts' run mix; fingerprint; provenance sampling_per_stage
src/platsim/optimizer/pairing.py    # NEW: paired_outcomes(a: TeamEvaluation-like, b) -> PairedOutcomes (pure)
src/platsim/sampling.py             # run_adaptive(..., borderline_threshold, borderline_max_runs): the borderline extension by the 021 rule
src/platsim/evaluate.py             # lift the 021 guard; pass extend_borderline through to run_adaptive; evaluate_team(adaptive_runs=...) precomputed reuse
src/platsim/cli.py                  # optimize --sampling, --floor; optimize_request
tests/unit/test_confirm_pairing.py  # pairing rule, controls; run_adaptive borderline extension on a fake pool
tests/unit/test_optimizer_resume.py # sampling/floor fingerprint rule
tests/integration/test_optimize_adaptive.py  # battle_sim: quick optimize on the reference species, adaptive, floor 0.9, two worker counts
```

**Structure Decision**: the pairing is one pure function in its own small module so the unit tests and the acceptance
control can share it; the borderline extension lives in `sampling.run_adaptive` beside the half-width extension it
mirrors; `_confirm` changes only where it calls `evaluate_team`, runs the runner-up and records attempts.

## Complexity Tracking

No constitution violations. The runner-up pairing excludes surplus runs rather than inventing pairs; the excluded
count is reported.
