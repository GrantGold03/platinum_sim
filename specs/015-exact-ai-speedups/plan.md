# Implementation Plan: Exact AI-Prediction Speedups for expectimax2-v2

**Branch**: `015-exact-ai-speedups` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/015-exact-ai-speedups/spec.md` (clarified 2026-10-30: the replay test
runs the full 40-gauntlet set in the default Node suite; the measurement harness ships with the simulator).

## Summary

Two exact changes inside the trainer-AI port, plus the proof and the measurement around them:

1. **Memoised damage inputs** (research R1, R3). The AI adapter gets `damageInput(attacker, defender, move, opts)`,
   which builds the damage-formula structs that `fromShowdown` builds today but caches the per-Pokemon battler
   struct and the per-side field struct for the current decision. `calcdamage.portInput` and the post-KO switch
   scorer call it instead of `fromShowdown`. The cache is dropped by `beginDecision()`, called at the two decision
   boundaries that reuse an adapter across turns: the live AI's `decide()` and the policy's `makeContext()` (the
   root view is the per-battle mirror's adapter). Shadow-view adapters are built per state and never change.
2. **Resolved constants** (R2). `Constants.get` gets a memo fast path (one Map read, no allocation), and the
   effect tables checked on every damage call (`effectIn`, plus the gravity / heal-block tables in `choose.mjs`)
   are resolved once per constants instance into Sets of values.

Proof (R4): a replay test runs the fixed 40-gauntlet set for `expectimax2-v1` and `-v2` in worker threads and
compares, per gauntlet, the result digest, every p1 choice, the policy's AI draw count and the live AI's draw
count with a fixture recorded before either change. The fixture's v2 digest must equal the digest the profiling
harness recorded on `main` (`db6d20cf…`), which ties the fixture to `main` independently of the new code. A
test-only freeze guard makes any write to a cached struct throw.

Measurement (R5, R6): `sim/bench.mjs` runs the fixed set in one process (gauntlets/s, ms/decision, digests) and
records the fixture; `platsim bench` wraps it and times the same requests through the 16-worker pool, checking
that the pool's digest equals the single-process digest.

## Technical Context

**Language/Version**: Node v22.22.1 (ESM, `node:test`, `worker_threads`); Python 3.14 via uv for `platsim bench`
and its test

**Primary Dependencies**: none new. Touches `sim/ai/{adapter,calcdamage,switch,choose,constants,opponent}.mjs`,
`sim/policy/expectimax2.mjs` (two lines: `beginDecision` call, `STATS.aiDraws`), new `sim/bench.mjs`,
new `src/platsim/bench.py`, `src/platsim/cli.py`

**Storage**: one committed fixture `sim/test/replay_prof_a.json` (about 80 gauntlet records, tens of KB)

**Testing**: `(cd sim && node --test test/*.test.mjs)` (314 today + new replay, adapter, calcdamage, constants,
bench tests); `uv run pytest -q -m "not battle_sim"`; new `tests/integration/test_bench.py` (`battle_sim`);
full `uv run pytest -q` before merge

**Target Platform**: this Linux machine, offline, 16 cores

**Project Type**: simulator library + CLI (existing)

**Performance Goals**: SC-002 at least 1.5x single-process gauntlets/s on the fixed set (baseline 0.386, 34.2
ms/decision, `main` c751fb2, measured alone 2026-10-30). Profile bound for the two items: about 2x (R6)

**Constraints**: byte-identical results for v1, v2 and the live `decomp-ai` (FR-001, FR-003); no change to search
parameters, policy names or the vendored Showdown tree; any `sim/` edit changes `sim_code_hash` (checkpoints
made before the change will not resume; `data/generated/` rebuilt after switching branches)

**Scale/Scope**: about 120 lines of product code in `sim/ai`, about 150 in `sim/bench.mjs`, about 120 in
`src/platsim/bench.py` + CLI, about 250 lines of tests, one fixture. 3 stories, 22 to 26 tasks

## Constitution Check

Constitution v1.4.0.

| Principle | Check | Status |
|---|---|---|
| I. Decomp is ground truth | No game data changes. Constants and effect tables are still read from the decomp; they are resolved once instead of per call, to the same values (equivalence test over every effect value) | PASS |
| II. Showdown is the battle engine | Vendored tree untouched. The adapter stays read-only over the live Battle (freeze guard proves no consumer writes through the cache) | PASS |
| III. In-game legality | Not affected (no team output changes) | N/A |
| IV. Reproducible evaluation | Determinism test unchanged and passing; replay test pins results per seed; benchmark requests name seeds, teams, policies and record `sim_code_hash` via the worker hello | PASS (planned) |
| V. Verified claims, positive controls | Digest chain: harness on `main` = fixture at the instrumentation commit = branch after each change. Freeze guard: a deliberate write in a test throws. Cache test: stale struct without `beginDecision`, fresh after. Pool digest equals single-process digest | PASS (planned) |
| VI. Reference-first speed | Exact speedup, no approximation: v2 stays the reference and is improved in place; run times of `main` and the branch recorded in the validation log (single process and 16 workers) | PASS (planned) |

Post-design re-check (after Phase 1): unchanged, PASS. Complexity Tracking: none.

## Project Structure

### Documentation (this feature)

```text
specs/015-exact-ai-speedups/
├── spec.md
├── plan.md                 # this file
├── research.md             # R1 memo placement; R2 constants; R3 decision boundaries; R4 proof chain; R5 bench tool; R6 measurement; R7 out of scope
├── data-model.md           # decision cache, resolved tables, replay fixture, bench report
├── contracts/adapter-api.md   # beginDecision, damageInput, cacheStats, freeze guard
├── contracts/bench-tool.md    # sim/bench.mjs and platsim bench: options, JSON output, digests, fixture schema
├── quickstart.md
├── checklists/requirements.md
├── validation-log.md       # written during implementation
└── tasks.md                # /speckit-tasks
```

### Source Code (repository root)

```text
sim/ai/adapter.mjs            beginDecision(), damageInput(), cacheStats; PLATSIM_AI_FREEZE deep-freeze guard
sim/ai/calcdamage.mjs         portInput -> ai.damageInput; effectIn over resolved Sets (export effectSet)
sim/ai/switch.mjs             post-KO scorer (:499) -> ai.damageInput
sim/ai/choose.mjs             checkInvalidMoves gravity / heal-block tables via effectSet
sim/ai/constants.mjs          Constants.get memo fast path
sim/ai/opponent.mjs           decide(): ai.beginDecision() first
sim/policy/expectimax2.mjs    makeContext(): mirror.ai.beginDecision(); STATS.aiDraws
sim/bench.mjs                 NEW: fixed set, runRecorded(), digests, CLI (--policy --n --block --teams --trainers --json --record)
sim/test/replay.test.mjs      NEW: worker-thread replay of the fixture for v1 and v2
sim/test/replay_prof_a.json   NEW: fixture (recorded at the instrumentation commit, before any speedup)
sim/test/ai_adapter.test.mjs  damageInput == fromShowdown; cache lifecycle; freeze guard; Constants equivalence
sim/test/ai_cmds_damage.test.mjs  effectSet == names.some over every effect value
sim/test/bench.test.mjs       NEW: request set, digest definitions (fast, 1 trainer)
src/platsim/bench.py          NEW: platsim bench (single via sim/bench.mjs, pool timing, digest control)
src/platsim/cli.py            bench subcommand
tests/integration/test_bench.py   NEW (battle_sim): 1 team x 1 gauntlet x 1 trainer, single == pool digest
specs/001-*/contracts/cli.md  bench row; README.md command table + speed table; sim/ai/INTERFACE.md adapter note;
FUTURE-FEATURES.md            follow-ons (second-level memo, cross-decision caches, constant hoisting, feature 016)
```

**Structure Decision**: the speedups live where the cost is, in the shared AI port, so the live opponent gets
them too and one set of golden tests covers both users. The benchmark tool is split by language: the Node half
owns the request set, the digests and the fixture (it runs in-process, where `STATS` lives); the Python half
owns the pool timing, because the optimizer's pool is Python.

## Commit order (the exactness chain)

1. Instrumentation + proof, no behaviour change: `sim/bench.mjs`, `STATS.aiDraws`, `replay.test.mjs`, fixture
   recorded at this commit. Gate: bench `digest_full` for v2 equals `db6d20cf…`; for v1 equals the digest
   recorded on `main` with the scratchpad harness (quickstart step 1).
2. Memoised damage inputs (US1). Gate: replay test, golden tests, freeze-guard run.
3. Resolved constants (US2). Gate: same.
4. `platsim bench`, measurements, docs, validation log (US3).

## Complexity Tracking

None. The freeze guard is an environment-variable switch read once at import (precedent: `PLATSIM_AI_DEBUG` in
`sim/ai/opponent.mjs`); off, it costs one boolean test per cached struct.
