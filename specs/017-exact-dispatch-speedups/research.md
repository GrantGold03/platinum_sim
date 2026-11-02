# Research: Exact Dispatch, Damage-Input and Speed Speedups (round three)

Read on 2026-11-02 on `017-exact-dispatch-speedups` = `main` f6d845c + spec commits. Profile evidence:
`runs/016-evidence/scratchpad/prof3/REPORT3.md` (git-ignored copy of the session scratchpad; hooked digest equals
the plain digest `db6d20cf…`, so the measurement changed nothing). Counts below are per bench run of the fixed set
(40 gauntlets, 2,847 decisions, 127,219 trainer-AI calls) unless stated.

## R1. Effect-check runs become dispatch tables (`sim/ai/parse.mjs`, `sim/ai/interp.mjs`)

**Facts**. The interpreter executes 142,966,719 instructions per bench run; 128,283,632 (89.7%) are
`IfCurrentMoveEffectEqualTo` (TAI:1441-1451: `if (MOVE_DATA(AI_CONTEXT.move).effect == expected) AIScript_Iter(jump)`).
script.s has 364 of them in 13 maximal runs of consecutive instructions: lengths 178, 152, 5, 5, 5, 5, 4, 3, 2, 2,
1, 1 (`prof3/chains.mjs`). No jump target lands inside a run; one effect value is repeated inside a run (the first
entry wins, since the first match jumps). The handler reads `ctx.mem.move` (u16), `ctx.ai.moveData(move).effect`
(decomp move table, throws for an id with no row) and the instruction's `battle_effect` argument; it writes only
`ctx.next` on a match. `mem.move` does not change inside a run (only `AI_EVAL_STEP_INIT` in `evalMoves` sets it).

**Decision**. A post-pass `indexInstructions(prog)` at the end of `parseAiScript` finds every maximal run of two or
more consecutive `IfCurrentMoveEffectEqualTo` instructions, splits it at every possible entry point other than its
first instruction, and attaches to the first instruction of each resulting run `ins.dispatch = { table, after,
length }`: `table` is a `Map` from `int(battle_effect)` to the entry's `jump` target instruction index, filled in
run order and never overwritten (first match wins); `after` is the index of the instruction following the run;
`length` is for diagnostics. Entry points = every `jump` argument's `targetInstr` over the whole program, every
label's `instr`, and `ins.index + 1` for every `PushAndGoTo` (the return point `PopOrEnd` pops; `flow.mjs`). A run of
length 1 after splitting gets no table (nothing to gain).

In `runSection`, before looking up the handler: `if (ins.dispatch) { const t = ins.dispatch.table.get(ctx.ai.moveData(ctx.mem.move & 0xffff).effect); ctx.pc = t !== undefined ? t : ins.dispatch.after; continue; }`
(one loop iteration, one `INTERP_STATS.steps` and one `dispatches` increment). The lookup uses the same
`ai.moveData` call as the handler, so a missing row throws the same error at the same point.

**Why this is exact**. Stepping through a run from its first instruction evaluates, in order, `effect ===
int(expected_k)` and jumps at the first match, else falls through to the instruction after the run; nothing in
between has a side effect or changes `effect` (the handler only sets `ctx.next`; `mem.move` and the move table are
constant during a section). `table.get(effect)` with first-wins insertion returns exactly the first matching
entry's target, and `after` is the fall-through. Entering a run at instruction k evaluates only entries k..end,
which is exactly the table of the run that starts at k after the split; since every reachable entry point starts
a run, no entry evaluates a prefix it should skip. Today's script has no interior entry point (so the split is a
no-op and the structure test asserts 13 runs, 0 splits), but the split is implemented and tested on a synthetic
script so a future script change cannot break the equivalence silently.

**Reference and test** (FR-004, SC-004). The reference is the step-by-step evaluation computed by the test from the
instruction list (not a second interpreter): for each run head and each effect value `e` in the decomp's
`move_battle_effects` list (277 values) plus `-1` and `100000`, walk the run and take the first `ins.a.battle_effect
=== e`'s `ins.jt.jump`, else `after`; compare with `table.get(e) ?? after`. Positive control: a copy of one table
with one entry retargeted (and one with an entry deleted) must produce at least one mismatch. Structure test on the
real script: 13 runs with the lengths above, the two long runs at the expected script lines, 0 splits, exactly one
repeated value, and no `dispatch` on any other instruction. Synthetic script (`parseAiScript({ scriptText })`, as
`ai_parse.test.mjs` does): a label in the middle of a run and a `GoTo` to it produce two runs whose tables agree
with stepping from each entry. Runtime: `INTERP_STATS` deltas around one golden decision show `dispatches > 0` and
`steps` well below the instruction count a stepped run would need; the bench reports fewer than 20 M steps.

**Alternatives rejected**: a synthetic opcode replacing the run head (changes `ins.name`, which `OPCODES.md`,
`ai_parse.test.mjs` and the full trace see); generalising to other compare-and-jump runs (`IfLoadedEqualTo` 4.3 M
steps, 3%: the value compared is `calcTemp`, which the handlers between loads can change, so runs would need a
side-effect analysis for a 0.3% gain; recorded in FUTURE-FEATURES); a jump-table opcode in the script (the script is
the decomp's, never edited).

## R2. Argument index, one loop, counters (`sim/ai/parse.mjs`, `interp.mjs`, `choose.mjs`)

**Facts**. `ctx.arg(ins, name)` is `ins.args.find((x) => x.name === name)` (interp.mjs:57); every handler calls it
at least once per execution (48 call sites across `cmds/*.mjs`), `ctx.target` the same for jumps. Without
TurboFan inlining `arg` is 1.6% of time plus 1.1% for its callback; inlined it is folded into the handlers' self
time. `choose.mjs` has a second copy of the loop (`runSectionTraced`) used only when a trace is requested (the
golden tests; the default trace records `AddToMoveScore` entries, `trace.full` every instruction).

**Decision**. The post-pass also sets, on every instruction, `ins.a` (a null-prototype object: argument name ->
`value` for `value`, `jump`, `table` and `distance` kinds, the same `value` the `args` entry holds) and `ins.jt`
(name -> `targetInstr` for `jump` kinds). `makeCtx` reads them: `arg: (ins, name) => { if (!(name in ins.a))
throw <today's message>; return ins.a[name]; }`, `target` likewise over `ins.jt` with today's message. `ins.args`
stays as it is (tests and OPCODES generation read it). `runSection(ctx, start, { maxSteps = 200000, onStep } = {})`
is the one loop; when `onStep` is given it is called after each handler (or dispatch step) with `(ins, before,
after)` exactly as `runSectionTraced` did; `evalMoves` passes it when tracing and `runSectionTraced` is deleted.
`INTERP_STATS = { steps: 0, dispatches: 0 }` is exported from `interp.mjs` and incremented in the loop.

**Why this is exact**. `ins.a[name]` is the same number `args.find` returned; a missing name throws the same
error. The loop body is unchanged apart from the dispatch branch and the counter; the hook is the tracing loop's
hook moved inside. The default trace (score additions with lines) is unchanged because `AddToMoveScore` is never
part of a run; the full trace shows one entry for a run (op `IfCurrentMoveEffectEqualTo`, the head's line, `jumped`
true iff a match) instead of one per check; no committed fixture uses the full trace (grep over `sim/test`), and a
new test records this shape.

**Counter cost**: measured on 2026-11-02 with a far heavier per-opcode map update on all 143 M steps: 0.966 vs
0.971 gauntlets/s (0.6%, within noise between parallel runs). A plain increment on < 20 M steps is below that.

## R3. Policy damage inputs from the root adapter's memo (`sim/policy/expectimax2.mjs`, `sim/ai/adapter.mjs`)

**Facts**. `damageTable` builds its inputs with `fromShowdown(X.battle, u.ref, t.ref, num, { power, type, powerMul:
10 })` on every table miss: 141,358 calls, 677,373 `battlerFromShowdown` builds (attacker, defender and the two
live actives for `abilitiesOnField`), each running Showdown's `Pokemon.getTypes()` ('Type' event, 4.6% of all time
alone), `getAbility()` and `getItem()`; 5.8% of time in total. `u.ref` / `t.ref` are the live Pokemon objects for
every state (shadow states keep the live refs). The policy then mutates the structs (`fix()`: `stages` replaced,
`hp`, `status`, `item` set, and for a fresh switch-in eleven flags and `types` replaced) and replaces the field's
`defenderSide`, `abilitiesOnField`, `attackerSideAbilities`, `defenderSideAbilities`. The live battle does not
change during `choose()`. 55% of the misses (78,059) come from `matchupScore` (fresh flag and zero stages make
distinct keys); at most 12 live Pokemon x 2,847 decisions = 34 k distinct conversions are needed.

`X.rootView.ai` is `mirror.ai`, an adapter created by `createAIState(battle, …)` over the live battle; `makeContext`
calls `mirror.ai.beginDecision()` first. Its `damageInput(attackerPoke, defenderPoke, moveIdOrNum, opts)` (015)
returns `{ attacker, defender, move, field, crit: false }` identical to `fromShowdown` for the current state, with
`attacker` / `defender` the cached structs (one `battlerFromShowdown` per Pokemon per decision) and `field` a new
object whose shared parts come from the cached per-side field.

**Decision**. `damageTable` calls `const di = X.rootView.ai.damageInput(u.ref, t.ref, num, { power, type, powerMul:
10 })` and builds `base = { attacker: { ...di.attacker }, defender: { ...di.defender }, move: di.move, field: {
...di.field }, crit: false }`; `fix()` and the field overrides then run unchanged on the copies. `fix()` already
replaces `stages` and `types` with new objects, so the shared struct's nested objects are never written either.
The adapter's `battler(p)` and `fieldFor(side)` hits gain the CHECK comparison (recompute with
`battlerFromShowdown(p)` / a fresh field and `checkSame('battler' | 'field', …)`), counted in
`cacheStats.structChecks` and `CHECK_STATS.checks`.

**Why this is exact**. `damageInput` equals `fromShowdown` for the same live state (015 contract and test); the
copies hold the same field values a fresh build would; the live battle is constant within a decision (015
invariant, freeze-guarded), and `beginDecision()` at `makeContext` drops the structs before the next decision (FR-007,
User Story 2 scenario 5). The live opponent's own adapter is a different object (`stateFor(battle).ai`), so its
`decide()` calling its own `beginDecision()` does not touch the mirror's cache.

**Tests**: `expectimax2.test.mjs`: one `scoreActions` on a fixture battle; `X.rootView.ai.cacheStats` deltas:
`builds` <= number of Pokemon with hp > 0 on both sides, `fields` <= 2 (new counter `fieldBuilds`), `hits` >
`builds`; `fromShowdown` is not called by the policy (a spy via the `_internal` export or a `STATS.fromShowdown`
counter at 0). `ai_adapter.test.mjs`: with `PLATSIM_AI_CHECK=1`, a child that mutates a returned attacker struct
(`di.attacker.hp = 1`) and calls `damageInput` again must exit non-zero with `CHECK mismatch battler`; the clean
child (one Aaron battle per policy, already in the 016 test) now reports `structChecks > 0`. Freeze run: the
replay passes with `PLATSIM_AI_FREEZE=1`, proving `fix()` writes only to the copies.

**Alternatives rejected**: a policy-side `WeakMap<Pokemon, struct>` in `X` (a second cache with its own lifetime,
not covered by CHECK or FREEZE); deep-cloning the whole input (allocates more than today's `fromShowdown` saves);
teaching `calcDamage` to take per-state overrides (changes the damage port's interface for one caller).

## R4. One speed pair per view (`sim/ai/cmds/battler.mjs`, `sim/ai/adapter.mjs`, `sim/policy/expectimax2.mjs`)

**Facts**. `compareBattlerSpeed(ctx, b1, b2)` (BL:1188-1454) = two early returns on a fainted battler
(`curHP(b1) === 0 && curHP(b2)` -> 1, the converse -> 0), `noCloudNine` via `countAliveAbility` x 2,
`battlerSpeed(ctx, b, noCloudNine)` for each battler (reads stats, stages, ability, items, status, field,
`ai.speedRand(b)` for Quick Claw; draws nothing), writes `mem.monSpeedValues[b1|b2]`, then the comparison with
`coin()` draws on ties. Callers: `speedValuesNow(ai)` once per AI sample with `rand: () => 0` (127,219 calls, 4.6%
of time); `speedInfo(X, S)` once per `resolveTurn` with `rand: () => 0` (246,632 calls, 194,240 view hits, each
paying a `signature(S)` string, 4.0%); `IfSpeedCompareEqualTo` with the sample's RNG (1.0%). Views per run:
54,779. `battlerSpeed(b)` does not depend on the other battler or on the argument order; `monSpeedValues[b]` is
the same value whichever order the pair is compared in.

**Decision (adapter)**. `ai.speedPair(build)`: the decision cache gets one slot `speedPair` (undefined after
`beginDecision()`); `speedPair(build)` returns the slot if set, else `slot = build()` (frozen under FREEZE), counting
`cacheStats.speedPairs` / `speedPairHits`. Under CHECK a hit recomputes `build()` and `checkSame('speedPair', …)`.

**Decision (battler.mjs)**. Today's body is kept verbatim as `compareBattlerSpeedDirect` (exported, reference).
`compareBattlerSpeed` = the two early returns as today (before any memo), then `const pair = ai.speedPair(() => {
const ncn = …; return { b: [battlerSpeed(ctx, 0, ncn), battlerSpeed(ctx, 1, ncn)] }; })` (singles: battlers 0 and
1; a battler id >= 2 falls back to the direct body), then `b1 = pair.b[battler1]`, `b2 = pair.b[battler2]`, the
`monSpeedValues` writes and the comparison with `coin()` exactly as today. The pair holds `{ speed, ability,
quickClaw, laggingTail }` per battler, what the comparison reads.

**Decision (policy)**. `resolveTurn(X, S, pa, oa, speedOf = () => speedInfo(X, S))` uses `speedOf()` where it calls
`speedInfo(X, S)` today. `valuePly2` creates one lazy thunk per call after `replaceFainted` (`let sp; const speedOf
= () => (sp ??= speedInfo(X, S))`) and passes it to every `resolveTurn` in its loops; `qValue` does the same for the
root; the forced-switch path goes through `valuePly2`. `variablePower`'s mid-turn call stays `speedInfo(X, S)` on
the partially resolved state (keyed by that state's signature, as today). `STATS.speedInfo` counts `speedInfo`
calls.

**Why this is exact**. The early returns run before the memo, so a fainted active gives today's result on every
path without building a pair. Both `battlerSpeed` results are pure functions of the adapter's state (constant
within a decision for the root and live adapters, immutable for a shadow view) and `ai.speedRand(b)` (fixed per
decision), and draw nothing; the comparison and its `coin()` draws run per call in the same order as today, after
the same values. `speedValuesNow`'s `monSpeedValues` and `speedInfo`'s `speeds` are the same two numbers in both
orders. The policy thunk evaluates `speedInfo(X, S)` on the same `S` object the loop would have passed, and `S` is
not mutated between the loop's `resolveTurn` calls (`resolveTurn` clones `S` before any write; `predictOpponent`
is read-only), so one evaluation equals many.

**Tests** (FR-008, SC-006): `ai_cmds_battler.test.mjs` harvests >= 1,000 views by running a few decisions of
`expectimax2-v2` on fixture battles through `_internal.viewOf` (the views of each `X` after `scoreActions`, plus the
root view) and, per view and per caller shape (`(0, 1)` with `rand: () => 0`, `(1, 0)` with `rand: () => 0`, `(1,
0)` with a seeded stub RNG), compares `compareBattlerSpeedDirect` and `compareBattlerSpeed` on fresh contexts:
result, `mem.monSpeedValues`, RNG draw count; asserts `speedPairs` grows by exactly 1 per view over all calls;
includes views with a fainted active (post-KO states) and states with stages, paralysis, Choice Scarf, Quick Claw
(speedRand supplied), Trick Room and weather if present in the harvested set, with a coverage count printed; a
positive control mutates a pair's `speed` and expects a different result. `ai_adapter.test.mjs`: lifecycle and
freeze. `expectimax2.test.mjs`: `STATS.speedInfo` delta over one `scoreActions` <= `X.nodes` + number of root
actions + mid-turn Gyro Ball calls (0 on the fixture).

**Alternatives rejected**: caching `speedInfo` on the state object by identity (stale after `replaceFainted` and
the mid-turn `variablePower` use; R4 in the spec's edge cases); sharing the whole comparison result including the
coin (changes draw order); keying the pair per `(b1, b2)` order (two builds per view instead of one).

## R5. Proof chain

Unchanged from 015 and 016 and reused: the replay fixture (`sim/test/replay_prof_a.json`, v2 digest = `main`'s
`db6d20cf…`, v1 `1273b694…`) with every choice and the per-decision draw counts for the player's predictions and the
live opponent; the 2026-11-02 health check shows `main` f6d845c still reproduces the v2 digest (bench) and the Node
suite is 334/334, so the fixture is the reference for this branch. Each commit: replay test, AI golden, fixture and
gauntlet tests, freeze run. Commit 3 adds the CHECK runs (now covering battler and field structs). Pool digest
equals the single-process digest in `platsim bench` (`digests_agree` true).

## R6. Measurement

Before: `main` f6d845c at comparison time, nothing else running: `node sim/bench.mjs --policy expectimax2-v2` (and
`-v1`), `uv run platsim bench --workers 16`. Same-session reference from the 2026-11-02 health check: v2 1.0187
gauntlets/s, 12.36 ms/decision alone (bench); the 016 log's pool figure 10.03 s, 3.99 gauntlets/s. The interpreter
step count before comes from commit 1 on the branch (instrumentation only, identical behaviour) since `main` has no
counter; the profile's harness figure (143 M) is the cross-check. After: same on the branch at commit 5, and the
single-process v2 figure after commits 2, 3 and 4 for attribution. Estimate from shares: interpreter 10.7% of time,
of which the dispatch removes most of the 90% of steps (about 6 to 9 points); policy damage inputs 5.8% (about 5
points); speed 7.2% + 2.4% of which the shared pair and the hoist remove about 4 to 5 points: 15 to 19 points,
about 1.2x. SC-002 bar: 1.15x (>= 1.17 gauntlets/s for v2 against 1.019).

## R7. Out of scope (FUTURE-FEATURES section 7)

Hoisting the ~320 `K()` / `C.get` sites (6.3%), the `damageOutcomes` memo (66% repeats of 2.8%), skipping the merge
signature for single-branch turns (21% of `resolveTurn` calls, 0.5%), generalised compare-and-jump runs
(`IfLoadedEqualTo`, 3% of steps), cross-decision caches, and the `expectimax2-v4` approximations (feature 018 after
this one takes 017). Killed: a per-decision `matchupScore` memo (0 repeated keys in 12,269 calls).
