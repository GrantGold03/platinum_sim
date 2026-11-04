# Implementation Plan: Adaptive Elite Four Sampling in evaluate

**Branch**: `021-adaptive-e4-sampling` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/021-adaptive-e4-sampling/spec.md`

## Summary

`platsim evaluate` gains `--sampling {full,adaptive}` (default `full`) and `--floor` (default 0.99). Under adaptive
sampling, full gauntlets run in request-seed order until every Elite Four member's Wilson 95% lower bound reaches
the floor; every full run that reaches Cynthia banks her starting state; the remaining runs are Cynthia-only
battles from banked states, drawn deterministically with a reserved battle index (98) the way the top-up draws with
99. The clear rate becomes the Elite Four pass rate times Cynthia's conditional rate over all her battles, with a
log-scale delta-method 95% interval, and today's threshold, half-width and borderline rules apply to that interval.
Extension runs are Cynthia-only while they can still close the half-width, full gauntlets once the Elite Four part
limits it. Reports carry the run mix and both intervals; loss causes include Cynthia-only losses; the full gauntlet
stays the reference and the default until the owner's go after the paired acceptance on six teams. `sim/` is not
touched.

## Technical Context

**Language/Version**: Python 3.12 (`uv`); Node 22 only through the existing worker (unchanged)

**Primary Dependencies**: `platsim.sim.pool.WorkerPool`, `platsim.sim.seeds.derive_seed`, `platsim.sim.champion`
(`_start_index` generalised, `champion_topup` given the Cynthia battles already on hand), `platsim.stats`
(`wilson_ci`, `wilson_half_width`, `runs_needed`, `Z95`), `platsim.report.losses` (replay already works from
`state_before`), `platsim.report.json_report` (new optional fields), `xlsx.py`, `csv_report.py`, `web/result_view.py`

**Storage**: result.json / xlsx / csv as today with new fields; acceptance evidence under `runs/021-evidence/` (local)
with small files copied to `specs/021-adaptive-e4-sampling/evidence/`

**Testing**: fast-mode unit tests for the new module's pure functions; a `battle_sim` integration test on the reference
team at a small count with floor 0.9 (so the switch happens inside the test); the existing evaluate tests unchanged;
the full pytest suite and the Node suite as the merge gate (behaviour change under `src/platsim`)

**Target Platform**: this Linux machine, 16-worker pool

**Project Type**: library + CLI change in one package module plus report writers; no `sim/` change

**Performance Goals**: on strong teams, wall time of a 2,000-run standard evaluation 1.5x or better than `full` (SC-002;
the spike projected 1.9 to 2.9x); on B3 about 1.0

**Constraints**: result.json a pure function of inputs (worker-count and batch independence, including the switch and
the draws); floor 1.0 byte-identical to `full`; `sim_code_hash` unchanged, replay fixtures untouched; no change to the
optimizer's calls (they keep `sampling="full"` by default)

**Scale/Scope**: one new module (~300 lines), edits to `evaluate.py`, `champion.py`, `seeds.py` (docstring), three
report writers, the web result view, the CLI; one unit-test module, one integration-test module; an acceptance script;
docs. Four commits.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I. Decomp is ground truth | Pass (not touched) | No game data or rule changes; exp, PP and items carry as today inside full runs, and banked states carry them into Cynthia-only battles. Divergence ledger untouched. |
| II. Showdown is the engine | Pass | No simulator change; the Cynthia-only request (`trainers: ["cynthia"]`, `start_state`) already exists for the top-up. |
| III. Legality of every output | Pass (not applicable) | No team is produced; `evaluate` still refuses illegal teams before simulating. |
| IV. Reproducible, honest evaluation | Pass | Run order fixed by request seeds; the switch point and the draws depend on run index and master only; results in excess of the switch are discarded so chunk size cannot change the result (R3); every rate keeps an interval; the composite interval is the delta method, decided by the owner after the spike. Provenance records the method, floor, run mix and seed scheme. |
| V. Verified claims, positive controls | Pass | Unit positive control (Elite Four pass below threshold yields not qualified); floor-1.0 control byte-identical to `full`; top-up control; acceptance negatives recorded. |
| VI. Reference-first speed | Pass | The full gauntlet stays available as `--sampling full`, remains the default until the owner's go, and is the reference in a paired acceptance on six teams including the Lucian-heavy one; wall times of both recorded. |
| Workflow and gates | Pass | Through Spec Kit; behaviour change under `src/platsim`, so the merge gate is the full pytest suite and the Node suite. |

**Post-design re-check (after Phase 1)**: unchanged. The one approximation (adaptive sampling itself) is built
reference-first by construction and never adopted without the paired comparison and the owner's go.

## Project Structure

### Documentation (this feature)

```text
specs/021-adaptive-e4-sampling/
├── plan.md, research.md (R1-R12), data-model.md, quickstart.md
├── contracts/
│   ├── cli-and-report.md     # the flag, the new result.json fields, xlsx/csv rows, web view, provenance
│   └── sampling-api.md       # the new module's functions and the evaluate_team / champion_topup signature changes
├── scripts/acceptance.py     # paired adaptive vs full on six teams, controls, the table
├── evidence/                 # small acceptance files
├── validation-log.md
└── tasks.md
```

### Source Code (repository root)

```text
src/platsim/sampling.py                 # NEW: switch rule, banked-state draw, Cynthia-only requests, run_adaptive, composite + delta interval, extension rule
src/platsim/evaluate.py                 # evaluate_team(..., sampling, floor); report fields; provenance; loss causes over both run kinds
src/platsim/sim/champion.py             # start_index(master, k, battle_index, n) generalised; champion_topup(..., extra_cynthia=(battles, wins))
src/platsim/sim/seeds.py                # docstring: battle index 98 reserved for Cynthia-only sampling runs
src/platsim/report/json_report.py       # EvaluationReport.sampling (default "full"), sampling_detail (default None); to/from dict
src/platsim/report/xlsx.py, csv_report.py, web/result_view.py   # the new rows / fields
src/platsim/cli.py                      # --sampling, --floor on evaluate
tests/unit/test_sampling.py             # pure functions, positive control
tests/integration/test_evaluate_adaptive.py   # battle_sim: small count, floor 0.9, determinism, fields, floor-1.0 equality
tests/unit/test_reports.py              # round trip with the new fields; old JSON reads as full
```

**Structure Decision**: the method is one new module with pure functions and one pool-driving function, so the
estimator and the switch rule are unit-testable without battles; `evaluate_team` composes it behind the `sampling`
argument and is otherwise unchanged for `full`.

## Complexity Tracking

No constitution violations. The discard rule in R3 wastes at most one chunk of full gauntlets at the switch; it is
the price of batch independence and is reported in the run mix.
