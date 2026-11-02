# Implementation Plan: Exact Dispatch, Damage-Input and Speed Speedups for expectimax2 (round three)

**Branch**: `017-exact-dispatch-speedups` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/017-exact-dispatch-speedups/spec.md` (clarified 2026-11-02: the
in-script speed comparison shares the per-state speed values and keeps its tie-break draw per sample; the
benchmark tool reports the interpreter step count).

## Summary

Three exact changes, each on a different layer of the player's search, plus the instrumentation, the proofs and
the measurement around them:

1. **Interpreter effect dispatch** (research R1, R2). A parse-time post-pass in `sim/ai/parse.mjs` gives every
   instruction its arguments by name (`ins.a`, `ins.jt`) and attaches to the first instruction of every maximal
   run of two or more consecutive `IfCurrentMoveEffectEqualTo` instructions a dispatch table
   (`ins.dispatch = { table: Map<effect, targetInstr>, after, length }`, first entry wins). Runs are split at every
   possible entry point (jump targets, labels, return points after `PushAndGoTo`), so entering a run anywhere
   gives the same destination. The single interpreter loop in `sim/ai/interp.mjs` (`runSection`, now with an
   optional per-step hook that replaces the duplicate tracing loop in `choose.mjs`) answers a run in one step:
   `table.get(moveData(mem.move).effect) ?? after`. `ctx.arg` / `ctx.target` read `ins.a` / `ins.jt` with the same
   errors as today. `INTERP_STATS = { steps, dispatches }` counts loop iterations; `node sim/bench.mjs` reports
   them (`interp_steps`, `interp_dispatches`).
2. **Policy damage inputs from the root adapter's memo** (R3). `damageTable` in `sim/policy/expectimax2.mjs`
   replaces `fromShowdown(X.battle, u.ref, t.ref, …)` with `X.rootView.ai.damageInput(u.ref, t.ref, …)` (the 015
   per-decision memo of the per-battle mirror adapter, which wraps the live battle and is cleared by
   `beginDecision()` in `makeContext`) and shallow-copies the attacker, defender and field structs before `fix()`
   mutates them. `PLATSIM_AI_CHECK=1` now also recomputes every battler-struct and field-struct hit and compares.
3. **One speed pair per view** (R4). The deterministic part of `compareBattlerSpeed` (the two `battlerSpeed`
   results and the Cloud Nine check, after the fainted-battler early returns) is memoised per adapter per
   decision (`ai.speedPair`, cleared by `beginDecision()`, frozen under `PLATSIM_AI_FREEZE=1`); the comparison
   and its tie-break draws stay per call. The current body is kept as `compareBattlerSpeedDirect` (reference).
   In the policy, `speedInfo(X, S)` is computed at most once per state by the callers of `resolveTurn`
   (`valuePly2`, `qValue`, the forced-switch path) through a lazy thunk, instead of once per
   (action, opponent action) pair.

Proof (R5): the feature-015 replay test against the unchanged fixture (digests, every choice, per-decision draw
counts for v1, v2 and the live opponent) after every commit; the exhaustive dispatch equivalence test (every run
x every effect value plus one undefined value, positive control, split-at-entry test on a synthetic script); the
CHECK runs (one battle per policy in the suite, the full set before the merge) now covering the shared structs;
the freeze run; the speed-pair equivalence test over at least 1,000 real views (three callers, draw counts).

Measurement (R6): `node sim/bench.mjs` (v2, v1; the interpreter step count before and after) and
`uv run platsim bench --workers 16` on `main` and on the branch under identical conditions, plus the single-process
v2 figure after each story commit.

## Technical Context

**Language/Version**: Node v22.22.1 (ESM, `node:test`, `worker_threads`); Python 3.14 via uv only for the
existing `platsim bench` and pytest gates

**Primary Dependencies**: none new. Touches `sim/ai/parse.mjs`, `sim/ai/interp.mjs`, `sim/ai/choose.mjs`,
`sim/ai/cmds/battler.mjs`, `sim/ai/adapter.mjs`, `sim/policy/expectimax2.mjs`, `sim/bench.mjs`; tests under
`sim/test/`; docs (`sim/ai/INTERFACE.md`, `sim/ai/OPCODES.md` note, README speed table, FUTURE-FEATURES,
RUN-STATE)

**Storage**: none new. The feature-015 fixture `sim/test/replay_prof_a.json` is read, never re-recorded

**Testing**: `(cd sim && node --test test/*.test.mjs)` (334 today + new interpreter, adapter, battler and policy
tests); `uv run pytest -q -m "not battle_sim"` (528 passed, 4 xfailed today); full `uv run pytest -q` before
merge (556 passed, 4 xfailed today, 1 h 05 min); opt-in runs with `PLATSIM_AI_FREEZE=1` and `PLATSIM_AI_CHECK=1`

**Target Platform**: this Linux machine, offline, 16 cores

**Project Type**: simulator library + CLI (existing)

**Performance Goals**: SC-002 at least 1.15x single-process gauntlets/s on the fixed set (baseline 1.019 for v2
on `main` f6d845c on 2026-11-02, 12.4 ms/decision, re-measured in the same session as the after figure; profile
estimate about 1.2x, R6); SC-004 fewer than 20 million interpreter steps per bench run (143 million today)

**Constraints**: byte-identical results for v1, v2 and the live `decomp-ai` (FR-001, FR-003); no change to
search parameters, policy names or the vendored Showdown tree; any `sim/` edit changes `sim_code_hash`
(optimizer checkpoints made before the change will not resume); `data/generated/` is unaffected (no extractor
change), so no rebuild on branch switch; the trainer-AI golden fixtures (score additions with script lines,
choices, draw counts) must pass unchanged

**Scale/Scope**: about 70 lines in `sim/ai/parse.mjs`, 40 in `interp.mjs`, 20 removed from `choose.mjs`, 50 in
`cmds/battler.mjs`, 40 in `adapter.mjs`, 30 in `policy/expectimax2.mjs`, 10 in `bench.mjs`; about 350 lines of
tests; 4 stories, 5 commits, about 30 tasks. At the size rule's edge (3 code stories); no split, since each story
is one commit with its own gate and attribution and the stories do not touch the same functions

## Constitution Check

Constitution v1.4.0.

| Principle | Check | Status |
|---|---|---|
| I. Decomp is ground truth | No game data changes. The dispatch table is built from the parsed script's own effect values and jump targets; the effect compared is `MOVE_DATA(move).effect` from the decomp move table, as the handler reads today (TAI:1441-1451). Speed values come from the same `battlerSpeed` port (BL:1225-1304) | PASS |
| II. Showdown is the battle engine | Vendored tree untouched (`git diff --stat main HEAD -- pokemon-showdown` empty is a gate). The adapter stays read-only over the live Battle; the policy's copies of the shared structs are its own objects | PASS |
| III. In-game legality | Not affected (no team output changes) | N/A |
| IV. Reproducible evaluation | Determinism test unchanged; the 015 replay test pins results per seed for both policies and the live opponent's draw counts; benchmark requests name seeds, teams, policies and record `sim_code_hash` | PASS (planned) |
| V. Verified claims, positive controls | Dispatch equivalence over every run x every effect value with an altered-entry control; a synthetic script with a label inside a run proves the split; CHECK mode with a corrupted-struct child test that must fail; freeze run; speed-pair equivalence over real views with a positive control; replay fixture unchanged; pool digest equals single-process digest; the interpreter step count is reported by the tool before and after | PASS (planned) |
| VI. Reference-first speed | Exact speedup, no approximation; v1 and v2 stay the references and are improved in place; `compareBattlerSpeedDirect` stays exported as the reference the memoised version is checked against; the step-by-step evaluation of a run is the reference the dispatch table is checked against (computed by the test from the instructions, not kept as product code); run times of `main` and the branch recorded | PASS (planned) |

Post-design re-check (after Phase 1): unchanged, PASS. Complexity Tracking: none (see below).

## Project Structure

### Documentation (this feature)

```text
specs/017-exact-dispatch-speedups/
├── spec.md
├── plan.md                     # this file
├── research.md                 # R1 dispatch tables; R2 argument index + single loop + counters; R3 policy damage inputs; R4 speed pair; R5 proof chain; R6 measurement; R7 out of scope
├── data-model.md               # instruction fields, dispatch table, INTERP_STATS, decision cache (extended), speed pair, policy counters
├── contracts/interp-api.md     # parse post-pass fields, runSection(onStep), ctx.arg/target, INTERP_STATS, dispatch semantics
├── contracts/adapter-api.md    # ai.speedPair, cacheStats fields, CHECK on battler/field structs, damageInput use by the policy
├── contracts/policy-and-bench.md   # damageTable inputs, speedInfo once per state, STATS.speedInfo, bench interp_steps / interp_dispatches
├── quickstart.md
├── checklists/requirements.md
├── validation-log.md           # written during implementation
└── tasks.md                    # /speckit-tasks
```

### Source Code (repository root)

```text
sim/ai/parse.mjs               post-pass indexInstructions(prog): ins.a (value args by name), ins.jt (jump targets by name), ins.dispatch on run heads (split at entry points); exported for tests: effectRuns(prog)
sim/ai/interp.mjs              runSection(ctx, start, { maxSteps, onStep }): one loop, dispatch step, INTERP_STATS; makeCtx: arg/target over ins.a / ins.jt (same errors)
sim/ai/choose.mjs              runSectionTraced removed; evalMoves passes onStep for traces (default trace unchanged; full trace: one entry per dispatch)
sim/ai/cmds/battler.mjs        compareBattlerSpeedDirect (today's body, reference); compareBattlerSpeed = early returns, then ai.speedPair() memo, then the comparison with coin flips
sim/ai/adapter.mjs             ai.speedPair(computeFn) memo slot in the decision cache (cleared by beginDecision, frozen under FREEZE); CHECK on battler/field hits; cacheStats { speedPairs, speedPairHits, structChecks }
sim/policy/expectimax2.mjs     damageTable: X.rootView.ai.damageInput + shallow copies; resolveTurn(X, S, pa, oa, speedOf); valuePly2 / qValue / forced-switch path: one lazy speedInfo per state; STATS.speedInfo
sim/bench.mjs                  interp_steps, interp_dispatches from INTERP_STATS deltas (JSON and table)
src/platsim/bench.py           prints the two new single-process rows (pass-through)
sim/test/ai_interp.test.mjs    NEW: runs found (13; 178, 152, …; 0 splits on the real script); synthetic script with a label inside a run splits; exhaustive equivalence (every run x 277 effect values + 1 undefined) with positive control; ctx.arg/target errors unchanged; INTERP_STATS deltas for one golden decision
sim/test/ai_golden.test.mjs    unchanged (score-addition traces); one added test: full trace shows one entry per dispatch
sim/test/ai_cmds_battler.test.mjs   speed pair: memo == direct over >= 1,000 real views x three callers (result, monSpeedValues, draw counts); builds per view == 1; fainted-active cases; positive control
sim/test/ai_adapter.test.mjs   speedPair lifecycle (beginDecision clears, freeze); CHECK compares battler/field hits; corrupted-struct child fails with CHECK mismatch battler
sim/test/expectimax2.test.mjs  damageTable builds <= alive mons per decision, fields <= 2, fromShowdown not called; STATS.speedInfo per decision <= X.nodes + root actions
sim/ai/INTERFACE.md            017 section (interp fields, speedPair, CHECK extension); the 015 sentence about the policy using fromShowdown updated
sim/ai/OPCODES.md              one note under the table: IfCurrentMoveEffectEqualTo runs are dispatched as a table
README.md, FUTURE-FEATURES.md, RUN-STATE.md   speed table row, section 7 update (017 done, 018 = approximations), run state
```

**Structure Decision**: the dispatch table is a property of the parsed program, so it is built where the program
is built (`parse.mjs` post-pass, run inside `parseAiScript`) and consumed by the one interpreter loop; the policy
reuses the adapter's existing decision cache for its damage inputs because that cache already has the right
lifetime and the control mode and freeze guard already cover it; the speed pair lives in the same cache for the
same reason, with the per-call comparison left in `cmds/battler.mjs` next to its reference.

## Commit order (the exactness chain)

1. **Instrumentation**: `INTERP_STATS` in `interp.mjs` (one increment per step), `interp_steps` /
   `interp_dispatches` in `bench.mjs` and `platsim bench`. No behaviour change. Gate: replay test green;
   `node sim/bench.mjs --policy expectimax2-v2` records the before figure for SC-004 (expected about 143 million)
   and the before throughput on the branch (same session as the `main` figure).
2. **US1 dispatch + argument index + single loop**: `parse.mjs` post-pass, `interp.mjs`, `choose.mjs`;
   `ai_interp.test.mjs`, the golden full-trace test. Gate: dispatch equivalence 0 mismatches with the positive
   control firing; real-script structure test (13 runs, 0 splits); replay green against the unchanged fixture;
   golden and gauntlet AI tests; freeze run; bench: steps < 20 M, v2 gauntlets/s recorded (attribution).
3. **US2 policy damage inputs**: `adapter.mjs` CHECK on battler/field hits + counters; `policy/expectimax2.mjs`
   `damageTable`; tests. Gate: replay; golden; freeze run (the copies absorb `fix()`); CHECK child tests (clean
   and corrupted struct); CHECK run on the full set for v2 and v1 (recorded); builds-per-decision test; bench
   attribution.
4. **US3 speed pair + speedInfo once per state**: `cmds/battler.mjs`, `adapter.mjs`, `policy/expectimax2.mjs`;
   tests. Gate: speed-pair equivalence over >= 1,000 real views (three callers, draw counts), builds per view == 1;
   replay; golden; freeze run; bench attribution.
5. **US4 measurement, docs, validation log**: bench on `main` and branch (single and pool), README speed table,
   INTERFACE.md, OPCODES.md note, FUTURE-FEATURES section 7 (017 done; approximations renumbered 018), RUN-STATE.

Every commit runs the Node suite; fast mode after commit 5; the full suite after the user's hands-on testing.

## Complexity Tracking

None. `compareBattlerSpeedDirect` is the kept reference (Principle VI) and costs nothing at run time. The
dispatch table's reference is the instruction list itself (the test steps through it); no second interpreter is
kept. `INTERP_STATS` follows the policy's `STATS` precedent: one integer increment per step, measured at under 1%
of run time with a far heavier per-opcode counter in the 2026-11-02 profile. The `onStep` hook in `runSection`
replaces a duplicated loop (less code, not more); when absent it costs one undefined test per step.
