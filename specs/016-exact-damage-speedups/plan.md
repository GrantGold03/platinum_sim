# Implementation Plan: Exact Damage-Path Speedups for expectimax2 (round two)

**Branch**: `016-exact-damage-speedups` | **Date**: 2026-11-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/016-exact-damage-speedups/spec.md` (clarified 2026-11-01: the
equivalence test uses synthetic matchups plus a real-data layer; the base-damage control runs on one battle per
policy in the default suite and on the full fixed set as an opt-in, recorded run).

## Summary

Three exact changes on the damage path shared by the player policies and the trainer-AI port, plus the proofs
and the measurement around them:

1. **Type-chart plan** (research R1). `sim/damage.mjs` gains `typeChartPlan(input, opts)`, which walks the type
   chart once for one attacker, defender, move and field and returns the ordered multiplier steps, the status
   mask and the total multiplier, and `replayTypeChart(plan, damage)`, which applies the steps to one damage
   value with the game's per-step integer arithmetic. `applyTypeChart` keeps its signature and becomes
   plan-then-replay; the per-roll body stays exported as `applyTypeChartDirect`, the reference (Principle VI).
   `calcDamage` builds the plan once and replays it for the 16 rolls (32 chart walks and 36 `prepare()` calls per
   damage-table entry become 2 and 6).
2. **AI pre-variance memo** (R2). The adapter's per-decision cache (feature 015) gains two memoised methods:
   `typeChartPlan(att, def, move, opts, chartOpts)` and `preVariance(att, def, move, opts, fixedDamage)`, the
   trainer AI's damage before the sample's roll (TAI:3081-3103). `calcdamage.calcDamage` and
   `calcdamage.applyTypeChart` call them, so the K samples on one state share one base-damage computation per
   attacker, defender and move. Cleared by `beginDecision()`, frozen under `PLATSIM_AI_FREEZE=1`, and checked
   against a fresh computation under the new `PLATSIM_AI_CHECK=1` (control mode).
3. **Shared identifier mappers** (R3). The Showdown-id-to-decomp-number mappers are built once per
   `(dex, decomp tables)` pair at module level and shared by every adapter, with one `Map` per kind instead of
   template-string keys.

Proof (R4, R5): the feature-015 replay test against the unchanged fixture (digests, every choice, per-decision
draw counts for v1 and v2); a randomized equivalence test of `applyTypeChart` versus `applyTypeChartDirect` over
at least 10,000 synthetic and 1,000 real-data matchups with coverage counters and a positive control; the control
mode on one battle per policy in the default suite and on the full fixed set before the merge; the freeze run.

Measurement (R6): `node sim/bench.mjs` (v2, v1) and `platsim bench --workers 16` on `main` 19519ed and on the
branch under identical conditions.

## Technical Context

**Language/Version**: Node v22.22.1 (ESM, `node:test`, `worker_threads`); Python 3.14 via uv only for the
existing `platsim bench` and pytest gates

**Primary Dependencies**: none new. Touches `sim/damage.mjs`, `sim/ai/adapter.mjs`, `sim/ai/calcdamage.mjs`;
tests under `sim/test/`; docs (`sim/ai/INTERFACE.md`, README speed table, FUTURE-FEATURES, RUN-STATE)

**Storage**: none new. The feature-015 fixture `sim/test/replay_prof_a.json` is read, never re-recorded

**Testing**: `(cd sim && node --test test/*.test.mjs)` (326 today + new damage, adapter and control tests);
`uv run pytest -q -m "not battle_sim"` (528 passed, 4 xfailed today); full `uv run pytest -q` before merge
(556 passed, 4 xfailed today, 1 h 20 min); opt-in runs with `PLATSIM_AI_FREEZE=1` and `PLATSIM_AI_CHECK=1`

**Target Platform**: this Linux machine, offline, 16 cores

**Project Type**: simulator library + CLI (existing)

**Performance Goals**: SC-002 at least 1.2x single-process gauntlets/s on the fixed set (baseline 0.779 for v2
on `main` 19519ed, 18.3 ms/decision; profile estimate 1.25x to 1.35x, R6)

**Constraints**: byte-identical results for v1, v2 and the live `decomp-ai` (FR-001, FR-003); no change to
search parameters, policy names or the vendored Showdown tree; any `sim/` edit changes `sim_code_hash`
(optimizer checkpoints made before the change will not resume); `data/generated/` is unaffected (no extractor
change), so no rebuild on branch switch

**Scale/Scope**: about 90 lines in `sim/damage.mjs`, 80 in `sim/ai/adapter.mjs`, 15 in `sim/ai/calcdamage.mjs`;
about 300 lines of tests; 4 stories (two of them small), 24 to 28 tasks. Within the size rule; no split needed

## Constitution Check

Constitution v1.4.0.

| Principle | Check | Status |
|---|---|---|
| I. Decomp is ground truth | No game data changes. The type chart, move, item and species data are still read from the decomp; the plan replays the same table walk the port cites (battle_lib.c:2560-2679) with the same integer steps | PASS |
| II. Showdown is the battle engine | Vendored tree untouched. The adapter stays read-only over the live Battle; the new caches hold derived values only (freeze guard extended to them) | PASS |
| III. In-game legality | Not affected (no team output changes) | N/A |
| IV. Reproducible evaluation | Determinism test unchanged; the 015 replay test pins results per seed for both policies; benchmark requests name seeds, teams, policies and record `sim_code_hash` | PASS (planned) |
| V. Verified claims, positive controls | Equivalence test with coverage counters and an altered-plan control; control mode with a corrupted-memo test that must throw; freeze run; replay fixture unchanged; pool digest equals single-process digest | PASS (planned) |
| VI. Reference-first speed | Exact speedup, no approximation; v1 and v2 stay the references and are improved in place; the per-roll `applyTypeChartDirect` stays exported as the reference the plan is checked against; run times of `main` and the branch recorded | PASS (planned) |

Post-design re-check (after Phase 1): unchanged, PASS. Complexity Tracking: none (the control mode and the kept
reference function are Principle V/VI facilities, see below).

## Project Structure

### Documentation (this feature)

```text
specs/016-exact-damage-speedups/
├── spec.md
├── plan.md                     # this file
├── research.md                 # R1 type-chart plan; R2 AI memo + control mode; R3 shared mappers; R4 equivalence test; R5 proof chain; R6 measurement; R7 out of scope
├── data-model.md               # plan, pre-variance entry, decision cache (extended), shared mappers, counters
├── contracts/damage-api.md     # typeChartPlan, replayTypeChart, applyTypeChart, applyTypeChartDirect, calcDamage, DAMAGE_STATS
├── contracts/adapter-api.md    # typeChartPlan, preVariance, cacheStats fields, PLATSIM_AI_CHECK, shared mappers
├── quickstart.md
├── checklists/requirements.md
├── validation-log.md           # written during implementation
└── tasks.md                    # /speckit-tasks
```

### Source Code (repository root)

```text
sim/damage.mjs                 typeChartPlan(), replayTypeChart(), applyTypeChart() = plan+replay, applyTypeChartDirect() (reference), calcDamage() one plan per call, prepare() once per calcDamage; DAMAGE_STATS counters
sim/ai/adapter.mjs             shared mappers (module-level per dex+tables, per-kind Maps); ai.typeChartPlan(), ai.preVariance(); cacheStats {plans, planHits, preVariance, preVarianceHits, checks}; PLATSIM_AI_CHECK control mode
sim/ai/calcdamage.mjs          calcDamage(): ai.preVariance(); applyTypeChart(): replay of ai.typeChartPlan()
sim/test/damage_typechart.test.mjs   NEW: randomized equivalence (synthetic + real-data layers, coverage counters, positive control); calcDamage plan count
sim/test/ai_adapter.test.mjs   shared mappers == fresh mappers over every engine identifier; identity across adapters; preVariance memo lifecycle; freeze guard covers the new caches; CHECK mode corrupted-memo child test
sim/test/ai_cmds_damage.test.mjs     calcDamage via preVariance: counts independent of K; one-battle-per-policy CHECK run (child process)
sim/ai/INTERFACE.md            016 section next to the 015 one (methods, env vars)
README.md, FUTURE-FEATURES.md, RUN-STATE.md   speed table row, section 7 update, run state
```

**Structure Decision**: the plan and replay live in `sim/damage.mjs` because both users of the type chart (the
policy's damage table through `calcDamage`, the AI port through `calcdamage.mjs`) import from there; the memos
live in the adapter's existing decision cache because that is the object whose lifetime is one decision and
which `beginDecision()` already clears; the mappers move to module level because their inputs (engine dex,
decomp tables) are process-wide singletons.

## Commit order (the exactness chain)

1. **US1 type-chart plan**: `sim/damage.mjs` plan/replay, `applyTypeChartDirect` kept, `calcDamage` one plan;
   `damage_typechart.test.mjs`. Gate: equivalence test 0 mismatches with coverage met and the positive control
   firing; replay test green against the unchanged fixture; AI golden tests; freeze run.
2. **US2 pre-variance memo**: adapter `typeChartPlan` / `preVariance`, `calcdamage.mjs` call sites, `PLATSIM_AI_CHECK`
   control mode, counters; tests. Gate: replay; golden; freeze run; CHECK run on the full set (recorded);
   one-battle CHECK test in the suite.
3. **US3 shared mappers**: adapter module-level mappers; tests. Gate: replay; golden; mapper equivalence.
4. **US4 measurement, docs, validation log**: bench on `main` and branch (single and pool), README speed table,
   INTERFACE.md, FUTURE-FEATURES section 7, RUN-STATE.

Every commit runs the Node suite; fast mode after commit 4; the full suite after the user's hands-on testing.

## Complexity Tracking

None. `applyTypeChartDirect` is the kept reference (Principle VI, "the reference MUST stay available") and costs
nothing at run time. `PLATSIM_AI_CHECK` follows the `PLATSIM_AI_FREEZE` precedent: one environment variable read
at import; off, it costs one boolean test per memo hit.
