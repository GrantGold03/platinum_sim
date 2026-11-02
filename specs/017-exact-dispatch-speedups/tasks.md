# Tasks: Exact Dispatch, Damage-Input and Speed Speedups for expectimax2 (round three)

**Input**: Design documents from `specs/017-exact-dispatch-speedups/` (spec.md, plan.md, research.md, data-model.md,
contracts/interp-api.md, contracts/adapter-api.md, contracts/policy-and-bench.md, quickstart.md).

**Tests**: Required by the spec (FR-001 to FR-008, SC-001, SC-004 to SC-006) and Constitution V. The proof harness
(replay test and fixture) exists from feature 015 and is used unchanged. Each story's new tests are written first
and shown to fail on the missing exports (or, for equivalence tests, shown to pass on both sides with a positive
control); every commit is gated on the replay test.

**Organization**: by user story. A foundational instrumentation commit comes first (the interpreter step counter
in the benchmark tool, no behaviour change) so SC-004 has a committed before figure. US1 (interpreter effect
dispatch), US2 (policy damage inputs) and US3 (speed pair) are separate code changes committed in that order so
each gain is attributed; US4 (measurement and docs) depends on all three.

## Conventions

- Temp files and scripts go in the session scratchpad; evidence (bench JSON, suite logs) in `runs/017-evidence/`
  (git-ignored). Never `/tmp`.
- Never `git commit -a`; stage paths by name. The user's own files (`.claude/scheduled_tasks.lock` deletion,
  `.claude/skills/speckit-assess-*`, `.specify/assessments/`, `.specify/extensions*`, `held_items.md`) stay out.
- `data/generated/` needs no rebuild for this feature (no extractor change; identical on `main` and the branch).
- Never commit, switch branches or run a suite while a measurement is running. SC-002/SC-003/SC-004 measurements
  run with nothing else on the machine (`pgrep -a -x node; pgrep -a pytest` first; never `pgrep -f` with the script
  name from a shell whose command line contains it).
- Record every result (command, exit code, summary lines, Eastern times, commit hash) in
  `specs/017-exact-dispatch-speedups/validation-log.md` as it lands. Never pipe a command whose exit code matters.
- Node tests: `(cd sim && node --test test/*.test.mjs)` (334 today, about 2.5 min; the replay test alone 35-45 s).
  Freeze run: `(cd sim && PLATSIM_AI_FREEZE=1 node --test test/replay.test.mjs test/ai_*.test.mjs test/expectimax2.test.mjs)`.
  Fast mode: `uv run pytest -q -m "not battle_sim"` (528 passed, 4 xfailed today). Full suite (merge gate, about
  1 h 05 min): `uv run pytest -q --durations=25`, background, nothing else running.
- Commit order is the exactness chain (plan): 1 instrumentation, 2 US1, 3 US2, 4 US3, 5 US4 + docs. Push every
  commit touching `sim/`, `src/` or `tests/`. Do not merge.
- `sim/` edits change `sim_code_hash`: optimizer checkpoints made before 017 will not resume (say so in RUN-STATE
  and the README note).
- The replay fixture `sim/test/replay_prof_a.json` is never re-recorded in this feature (FR-002). A replay failure
  means a behaviour change: stop and fix the code, never the fixture. The trainer-AI golden fixtures in
  `sim/test/ai_golden.test.mjs` are likewise never edited (FR-003).
- Every decomp citation in `sim/ai/*.mjs`, `sim/ai/cmds/*.mjs` and `sim/policy/expectimax2.mjs` stays with the line
  it documents; the dispatch table, the copies and the memo change mechanics, never a cited value.
- The script `pokeplatinum/src/battle/trainer_ai/script.s` is the decomp's and is never edited; synthetic scripts
  for tests go through `parseAiScript({ scriptText })` only.

## Phase 1: Setup (baseline on `main` f6d845c, no code change)

**Purpose**: the numbers the branch is compared with, taken from `main` at comparison time under the same
conditions as the branch runs (quickstart step 0).

- [X] T001 Create `specs/017-exact-dispatch-speedups/validation-log.md` (header: times Eastern, evidence dir
  `runs/017-evidence/`; sections per task; record branch `017-exact-dispatch-speedups`, base `main` f6d845c,
  `git diff --stat main HEAD -- sim src tests` expected empty, exit 0); `mkdir -p runs/017-evidence`
- [X] T002 `git switch main`; alone on the machine: `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/main_v2.json`
  and `--policy expectimax2-v1 --json > runs/017-evidence/main_v1.json` (about 40 s each); `digest_full` MUST be
  `db6d20cf59008d32640358a6a143eb94d5102b46ebcc0d116f39c2856fd504d3` and `1273b69462bcce8c690e020e9c9699412e1a3f40809d4d7b1a77ecc23d3c3178`;
  record `gauntlets_per_s`, `ms_per_decision`, `ai_draws`, `wall_s` for both in the log (the "before" figures; the
  2026-11-02 health check saw 1.0187 / 12.36 for v2)
- [X] T003 Still on `main`, alone: `uv run platsim bench --workers 16 --json > runs/017-evidence/main_pool.json` (about 1 min);
  `digests_agree` MUST be true; record `pool_wall_s`, `pool_gauntlets_per_s`, `pool_digest_logs`; then
  `git switch 017-exact-dispatch-speedups`; record in the log

**Checkpoint**: v1 and v2 single-process figures and the 16-worker figure for `main` f6d845c are in the log.

---

## Phase 2: Foundational (replay gate known-good; interpreter step counter committed first)

**Purpose**: confirm the 015 replay fixture is the reference for this base (positive control for every later
replay gate), then land the instrumentation commit so the interpreter step count has a committed before figure
(clarification 2 of 2026-11-02; contract `policy-and-bench.md`). No behaviour change in this phase.

- [X] T004 On the branch: `(cd sim && node --test test/replay.test.mjs)` exit 0 (3 tests; diagnostic about 35-45 s,
  6144 player decisions); record the diagnostic line in the log. If it fails here, nothing else may start: the
  fixture or the base is not what the plan assumes
- [X] T005 In `sim/ai/interp.mjs`: `export const INTERP_STATS = { steps: 0, dispatches: 0 }` (header comment: one
  integer increment per loop iteration, diagnostics only, never reset by the module); in `runSection`, `INTERP_STATS.steps++`
  once per iteration (before the handler lookup). In `sim/ai/choose.mjs` `runSectionTraced`: the same increment
  (removed again in T012 when the loops merge). In `sim/bench.mjs`: import `INTERP_STATS`; in `runBench` snapshot it
  with `STATS` (`i0 = { ...INTERP_STATS }`) and add `interp_steps: INTERP_STATS.steps - i0.steps`,
  `interp_dispatches: INTERP_STATS.dispatches - i0.dispatches` to the report after `ai_draws`; print both in the human
  table in `main()`. In `src/platsim/bench.py` add the rows `("single: interpreter steps", out.get("interp_steps"))`
  and `("single: interpreter dispatches", out.get("interp_dispatches"))` after the AI-draws row
- [X] T006 [P] Extend `sim/test/bench.test.mjs` with one test "017 interpreter steps in the report": import `runBench`
  and `INTERP_STATS`; `const s0 = INTERP_STATS.steps; const r = runBench(gd, { policy: 'expectimax2-v2', n: 1, teams:
  ['bench'], trainers: ['aaron'] })` (one Aaron battle, a few seconds); assert `Number.isInteger(r.interp_steps)`,
  `r.interp_steps > 0`, `r.interp_steps === INTERP_STATS.steps - s0` (the report is the delta), and
  `r.interp_dispatches >= 0` (tightened to `> 0` in T009); positive control: `INTERP_STATS.steps` grew across the run
- [X] T007 Gate and commit 1 (quickstart step 1): `(cd sim && node --test test/bench.test.mjs test/replay.test.mjs test/ai_golden.test.mjs)`
  exit 0; `uv run pytest -q tests/unit/test_bench_cli.py` exit 0 (the two new rows parse; `tests/integration/test_bench.py` is
  marked `battle_sim` and runs in T033's full suite); alone on the machine `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/c1_v2.json`
  → `digest_full` `db6d20cf…`, `ai_draws` equal to T002, `interp_steps` about 143 M (record the exact value: the SC-004
  before figure), `interp_dispatches` 0, `gauntlets_per_s` within noise of T002; commit by path
  (`sim/ai/interp.mjs sim/ai/choose.mjs sim/bench.mjs src/platsim/bench.py sim/test/bench.test.mjs specs/017-exact-dispatch-speedups/validation-log.md`),
  message `perf(017): interpreter step counter reported by the bench tool (instrumentation; replay digest unchanged)`, push; record the hash

**Checkpoint**: the replay gate is known-good on unchanged code and the before step count is committed.

---

## Phase 3: User Story 1 - The trainer AI answers a list of effect checks in one step (Priority: P1) 🎯 MVP

**Goal**: parse-time dispatch tables on every run of consecutive `IfCurrentMoveEffectEqualTo` instructions (split
at entry points), `ins.a` / `ins.jt` argument index, one interpreter loop with an `onStep` hook, `INTERP_STATS.dispatches`
(FR-003, FR-004, FR-005; research R1, R2; contract `interp-api.md`).

**Independent Test**: the exhaustive dispatch equivalence test reports 0 mismatches over every run x every
effect value plus undefined values with its positive controls firing; the synthetic split test passes; the replay
test matches the unchanged fixture with only this change; the golden traces are unchanged; `interp_steps` drops
below 20 M.

### Tests for User Story 1 (write first; fail on the missing `effectRuns` export / `ins.dispatch` before T010)

- [ ] T008 [US1] Create `sim/test/ai_interp.test.mjs`: import `aiProgram` from `../ai/choose.mjs`, `effectRuns`,
  `parseAiScript` from `../ai/parse.mjs`, `makeCtx`, `runSection`, `INTERP_STATS` from `../ai/interp.mjs`, `readList`
  from `../ai/constants.mjs`. Test 1 (structure, real script): `effectRuns(prog)` after splitting has 13 runs with
  lengths `[178, 152, 5, 5, 5, 5, 4, 3, 2, 2, 1, 1]` sorted descending, `split === false` for all, exactly 11 heads
  carry `ins.dispatch` (runs of length >= 2), `dispatch.length` equals the run length, `dispatch.after === end + 1`,
  no other instruction has `dispatch`, exactly one run contains a repeated `battle_effect` value and its table maps
  that value to the FIRST entry's target; every instruction has `ins.a` with one key per `args[]` entry and equal
  values, and `ins.jt` with one key per `jump` argument equal to its `targetInstr`. Test 2 (exhaustive equivalence,
  FR-004): `effects = readList('move_battle_effects').map((e) => e.value)` (277 values) plus `[-1, 100000]`; for each
  head with `dispatch` and each value `e`: reference = walk `k` from `head.index` to `after - 1`, first `k` with
  `prog.instructions[k].a.battle_effect === e` gives `prog.instructions[k].jt.jump`, none gives `after`; assert
  `dispatch.table.get(e) ?? after` equals it; count comparisons (>= 11 x 279) in a diagnostic. Test 3 (positive
  controls): a copy of the longest run's table with one entry retargeted to `after` and a copy with one entry deleted
  each produce at least one mismatch against the reference walk. Test 4 (split, scenario 4): `parseAiScript({ scriptText })`
  with a minimal script (a `FlagTable` of one `LabelDistance` as `ai_parse.test.mjs`'s synthetic scripts do; a run of
  four `IfCurrentMoveEffectEqualTo` with distinct effects whose third instruction carries a label `Mid`, a `GoTo Mid`
  elsewhere, then `PopOrEnd` and the jump-target labels): `effectRuns` yields two runs (`[2, 2]`, the second with
  `split === true`), both heads have tables, and for every effect value the table of each run agrees with the walk from
  its own head. Test 5 (arguments, FR-005): `ctx = makeCtx({ prog, ai: {}, mem: {}, rand: () => 0 })`; for the first
  `AddToMoveScore`, `ctx.arg(ins, 'i') === ins.args[0].value`; `ctx.arg(ins, 'nope')` throws
  `/AddToMoveScore \(script\.s:\d+\) has no argument nope/`; `ctx.target(firstGoTo)` equals its `targetInstr`;
  `ctx.target(addToMoveScore)` throws `/has no jump target jump/`. Test 6 (runtime): run one golden decision
  (`leagueBattle` + `decide` from `ai_fixtures.mjs` / `opponent.mjs`, as `ai_golden.test.mjs` does) between two
  `INTERP_STATS` snapshots: `dispatches` delta > 0 and `steps` delta < 2,000 (a stepped evaluation of the two long runs
  alone would exceed it; record the actual number in a diagnostic)
- [ ] T009 [P] [US1] Add to `sim/test/ai_golden.test.mjs` one test "017 full trace: one entry per dispatched run":
  run fixture A1 with `decide(x.st, x.p2, { trace: 'full' })`; among the entries with `op === 'IfCurrentMoveEffectEqualTo'`
  the count is below 100 (a stepped run would produce hundreds) and every such entry's `line` is the line of a run
  head (from `effectRuns`); the default-trace entries (`compact(r.detail.trace)`) still equal the fixture's `trace`.
  Tighten `sim/test/bench.test.mjs` from T006: `interp_dispatches > 0`

### Implementation for User Story 1

- [ ] T010 [US1] In `sim/ai/parse.mjs`: add `export function indexInstructions(prog)` run at the end of `parseAiScript`
  (before `return`): (a) for every instruction set `ins.a = Object.create(null)` with `a[arg.name] = arg.value` for
  every `args[]` entry and `ins.jt = Object.create(null)` with `jt[arg.name] = arg.targetInstr` for `kind === 'jump'`;
  (b) entry points = `Set` of every `jump` argument's `targetInstr`, every label's `instr` (defined ones), and
  `ins.index + 1` for every `PushAndGoTo`; (c) maximal runs of consecutive `name === 'IfCurrentMoveEffectEqualTo'`,
  split so that every entry point inside a run starts a new run; (d) for each run of length >= 2 set on its head
  `dispatch = { table: new Map(), after: end + 1, length }`, filling `table` in order with `(a.battle_effect | 0) ->
  jt.jump` only when the key is absent (first wins). Add `export function effectRuns(prog)` returning
  `[{ start, end, head, split }]` (recomputed from the instructions, `split` true when the run's start is an interior
  entry point of the maximal run). Header comment: cite TAI:1441-1451 for the handler the table replaces and the
  exactness argument (research R1). `args[]`, `image`, `labels` untouched
- [ ] T011 [US1] In `sim/ai/interp.mjs`: `runSection(ctx, start, { maxSteps = 200000, onStep } = {})`: per iteration
  `INTERP_STATS.steps++`; `if (ins.dispatch) { const d = ins.dispatch; const t = d.table.get(ctx.ai.moveData(ctx.mem.move & 0xffff).effect);
  ctx.next = t !== undefined ? t : d.after; INTERP_STATS.dispatches++; }` else the handler path as today (`ctx.next =
  ins.index + 1; fn(ctx, ins)`); when `onStep` is given, capture `before = ctx.mem.moveScore[ctx.mem.moveSlot]` before the
  step and call `onStep(ins, before, ctx.mem.moveScore[ctx.mem.moveSlot])` after it; then `ctx.pc = ctx.next`. The
  `maxSteps` error message unchanged. `makeCtx`: `arg: (ins, name) => { if (!(name in ins.a)) throw new Error(\`${ins.name} (script.s:${ins.line}) has no argument ${name}\`); return ins.a[name]; }`,
  `target: (ins, name = 'jump') => { const t = ins.jt[name]; if (t === undefined) throw new Error(\`${ins.name} (script.s:${ins.line}) has no jump target ${name}\`); return t; }`.
  Header comment: the dispatch step, the hook, `INTERP_STATS`
- [ ] T012 [US1] In `sim/ai/choose.mjs`: delete `runSectionTraced`; in `evalMoves`, when `trace` is set call
  `runSection(ctx, sectionStart, { onStep: (ins, before, after) => { …the same two trace shapes as today… } })`, else
  `runSection(ctx, sectionStart)`; the full-trace entry for a dispatch step is the head instruction's `{ flagBit,
  slot, line, op: ins.name, jumped: ctx.next !== ins.index + 1 }` (no special case needed: `ctx.next` is the table's
  answer). Update the `trainerAIMain` doc comment (full trace: one entry per executed step, a dispatched run counts
  once). In `sim/ai/OPCODES.md` add one note under the table: runs of `IfCurrentMoveEffectEqualTo` are answered by a
  parse-time table (feature 017), instruction counts unchanged
- [ ] T013 [US1] Gate (quickstart step 2): `(cd sim && node --test test/ai_interp.test.mjs test/ai_golden.test.mjs
  test/ai_choose.test.mjs test/ai_parse.test.mjs test/ai_gauntlet.test.mjs test/bench.test.mjs test/replay.test.mjs)`
  exit 0; freeze run exit 0; full Node suite exit 0 (334 + new); alone on the machine `node sim/bench.mjs --policy
  expectimax2-v2 --json > runs/017-evidence/c2_v2.json` → `digest_full` `db6d20cf…`, `ai_draws` equal to T002,
  `interp_steps` < 20,000,000 (record the exact value; SC-004), `interp_dispatches` > 0; record `gauntlets_per_s`,
  `ms_per_decision` under "US1 attribution" with the equivalence diagnostic (comparisons, 0 mismatches)
- [ ] T014 [US1] Commit 2 by path (`sim/ai/parse.mjs sim/ai/interp.mjs sim/ai/choose.mjs sim/ai/OPCODES.md
  sim/test/ai_interp.test.mjs sim/test/ai_golden.test.mjs sim/test/bench.test.mjs specs/017-exact-dispatch-speedups/validation-log.md`),
  message `perf(017): dispatch tables for effect-check runs, argument index, one interpreter loop (exact; exhaustive equivalence; replay digest unchanged)`,
  push; record the hash

**Checkpoint**: US1 alone is proven exact (exhaustive equivalence + replay + golden) and its speedup is attributed.

---

## Phase 4: User Story 2 - The player converts each live Pokemon once per decision (Priority: P1)

**Goal**: `damageTable` builds its inputs from the root adapter's 015 memo and copies before `fix()`; the control
mode compares battler and field struct hits; counters (FR-006, FR-007; research R3; contracts `adapter-api.md`,
`policy-and-bench.md`).

**Independent Test**: replay test passes with this change; builds per decision are at most one per live Pokemon
plus one field per side; the CHECK child on one Aaron battle per policy exits 0 with `structChecks > 0`; the
corrupted-struct child fails with `CHECK mismatch battler`; the freeze run passes (the copies absorb `fix()`); the
full-set CHECK run matches both digests.

### Tests for User Story 2 (write first; fail on the missing counters / the policy still calling `fromShowdown` before T017)

- [ ] T015 [P] [US2] Add to `sim/test/expectimax2.test.mjs` ("017 damage inputs from the root adapter's memo"): build
  the file's existing League battle fixture at a mid-battle position (reuse the helper the file already has for
  `scoreActions`), call `scoreActions(ctx, V2_OPTS, 'expectimax2-v2')` once and read `X.rootView.ai.cacheStats` before
  and after: `builds` delta <= number of Pokemon with `hp > 0` on both sides, `fieldBuilds` delta <= 2, `hits` delta >
  `builds` delta, `decisions` delta === 1; a second `scoreActions` on the same battle (new context) rebuilds (`builds`
  delta > 0 again: the memo did not leak across decisions, scenario 5). `fromShowdown` is no longer imported by the
  policy: read `sim/policy/expectimax2.mjs` with `readFileSync` and assert the import line from `'../damage.mjs'` does
  not name `fromShowdown` (regex on that one `import { … } from '../damage.mjs'` statement, so comments elsewhere in the
  file cannot trip it); and the memo served every table entry: `hits` delta >= `X.dmg.size` (each table miss asks for an
  attacker and a defender struct, both cache hits after the first use)
- [ ] T016 [P] [US2] Add to `sim/test/ai_adapter.test.mjs` ("017 CHECK covers battler and field structs", child
  processes via `spawnSync` as the 016 CHECK test does): (a) extend the existing clean child (one Aaron battle per
  policy) to print the aggregate `structChecks` summed over adapters (or add `CHECK_STATS.structChecks` and print it)
  and assert > 0; (b) new child with `PLATSIM_AI_CHECK: '1'` and no FREEZE: build an adapter on a small battle, `const di
  = ai.damageInput(att, def, num, opts)`, set `di.attacker.hp = di.attacker.hp + 1`, call `damageInput` again with the
  same arguments; assert non-zero exit and stderr `/CHECK mismatch battler/`; (c) the same for the field: `di.field`
  is a per-call object, so corrupt through the cached side struct: call once, then mutate `ai.battle.p1.sideConditions`
  by adding a fake `luckychant` entry, call again; assert `/CHECK mismatch field/`; (d) control: both corruptions with
  `PLATSIM_AI_CHECK: ''` exit 0

### Implementation for User Story 2

- [ ] T017 [US2] In `sim/ai/adapter.mjs`: `cacheStats` gains `fieldBuilds, structChecks, speedPairs, speedPairHits`
  (the last two filled in US3; declared now so the shape is stable); in `battler(p)` on a hit under `CHECK`:
  `checkSame('battler', \`${p.species.id}#${p.side.id}${p.position}\`, b, battlerFromShowdown(p))` and
  `cacheStats.structChecks++`; in `fieldFor(defenderPoke)` on a hit under `CHECK`: rebuild the field object into a local
  and `checkSame('field', defenderPoke.side.id, f, fresh)`, `structChecks++`; count `fieldBuilds++` on a build;
  `CHECK_STATS.checks` already incremented inside `checkSame`. Header comment: 017 paragraph (the policy's damage
  table now reads `damageInput` and copies; CHECK covers the structs). `sim/ai/INTERFACE.md`: in the 015 "Decision
  cache" bullet replace "(the policy's own damage table, which mutates its inputs, uses `fromShowdown`)" with "(the
  policy's own damage table copies the structs before its per-state adjustments, feature 017)"; add the counters
- [ ] T018 [US2] In `sim/policy/expectimax2.mjs` `damageTable`: replace `const base = fromShowdown(X.battle, u.ref, t.ref,
  num, { power, type, powerMul: 10 });` with `const di = X.rootView.ai.damageInput(u.ref, t.ref, num, { power, type,
  powerMul: 10 }); const base = { attacker: { ...di.attacker }, defender: { ...di.defender }, move: di.move, field: {
  ...di.field }, crit: false };` (comment: the structs are shared and read-only, 015 contract; `fix()` writes to the
  copies; `stages` and `types` are replaced, never mutated); remove `fromShowdown` from the import; the header's
  "Decision context" comment gains one line. No other change in the function
- [ ] T019 [US2] Gate (quickstart step 3): `(cd sim && node --test test/expectimax2.test.mjs test/ai_adapter.test.mjs
  test/replay.test.mjs test/ai_golden.test.mjs)` exit 0; freeze run exit 0; full Node suite exit 0; alone on the
  machine `PLATSIM_AI_CHECK=1 node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/check_v2.json` and
  `-v1 … check_v1.json`: exit 0, `check_stats.mismatches` 0, digests `db6d20cf…` / `1273b694…` (about 2 min each;
  record wall and `checks`: the recorded full-set control, SC-005); then `node sim/bench.mjs --policy expectimax2-v2
  --json > runs/017-evidence/c3_v2.json` (no CHECK) → digest and `ai_draws` unchanged; record `gauntlets_per_s`,
  `ms_per_decision` under "US2 attribution"
- [ ] T020 [US2] Commit 3 by path (`sim/ai/adapter.mjs sim/ai/INTERFACE.md sim/policy/expectimax2.mjs
  sim/test/expectimax2.test.mjs sim/test/ai_adapter.test.mjs specs/017-exact-dispatch-speedups/validation-log.md`),
  message `perf(017): the policy's damage inputs come from the root adapter's per-decision memo (exact; CHECK covers the structs; replay digest unchanged)`,
  push; record the hash

**Checkpoint**: US1 and US2 landed, each gated by the replay test and the freeze run; the full-set CHECK run recorded.

---

## Phase 5: User Story 3 - Who moves first is worked out once per hypothetical state (Priority: P2)

**Goal**: `ai.speedPair` memo in the decision cache; `compareBattlerSpeed` = early returns + memoised pair +
per-call comparison, today's body kept as `compareBattlerSpeedDirect`; `speedInfo` once per state in the policy via
a lazy thunk; `STATS.speedInfo` (FR-008; research R4; contracts `adapter-api.md`, `policy-and-bench.md`).

**Independent Test**: memo equals direct over >= 1,000 real views x three caller shapes (result, `monSpeedValues`,
draw counts) with one pair build per view and a positive control; the replay test passes; `STATS.speedInfo` per
decision is at most the ply-2 node count plus the root actions.

### Tests for User Story 3 (write first; fail on the missing `compareBattlerSpeedDirect` / `ai.speedPair` before T024)

- [ ] T021 [US3] Create the block "017 speed pair" in `sim/test/ai_cmds_battler.test.mjs`: harvest views by running
  `expectimax2-v2` decisions on 3 to 5 fixture battles from `ai_fixtures.mjs` (`leagueBattle` for different trainers,
  play a few turns with `battle.makeChoices` using the policy's `choose` for p1 and `decide` for p2, and after each
  player decision collect `[X.rootView, ...X.views.values()]` from `scoreActions`'s returned `X`) until >= 1,000 distinct
  views, including views where an active has `hp === 0` (for each harvested `X`, also push two fainted-active views:
  `const S = _internal.cloneState(X.root); S.sides[i].mons[S.sides[i].active].hp = 0; _internal.viewOf(X, S)` for `i`
  in 0 and 1), and report a coverage diagnostic
  (count of views with stages != 0, paralysis, Choice Scarf / Quick Claw items, Trick Room, weather, a fainted active).
  For each view and each caller shape `[(0, 1, () => 0), (1, 0, () => 0), (1, 0, seeded stub rng)]`: build two fresh
  contexts `{ ai: view.ai, mem: { monSpeedValues: [0, 0, 0, 0] }, rand }` with independently seeded but identical stub
  RNGs (`stubRng` with the same sequence), call `compareBattlerSpeedDirect` on one and `compareBattlerSpeed` on the
  other; assert equal result, deep-equal `mem.monSpeedValues`, equal draw counts; `view.ai.cacheStats.speedPairs`
  delta over all nine calls on the view is exactly 1 (0 for fainted-active views) and `speedPairHits` >= 8. Positive
  control: on one view with both alive, `const pair = view.ai.speedPair(() => { throw new Error('must hit'); })` (the
  stored pair), `const bad = { b: [{ ...pair.b[0], speed: pair.b[0].speed + 1 }, pair.b[1]] }`; assert
  `compareWith(ctx, 0, 1, bad.b[0], bad.b[1])` differs from `compareBattlerSpeedDirect(ctx, 0, 1)` in result or in
  `mem.monSpeedValues` for at least one such view over the set (ties may hide the result difference on a single view,
  the `monSpeedValues` write never does). Runtime target under 20 s
- [ ] T022 [P] [US3] Add to `sim/test/ai_adapter.test.mjs` ("017 speedPair memo"): `ai.speedPair(build)` calls `build`
  once and returns its value, a second call returns the same object without calling `build` (`speedPairs` +1,
  `speedPairHits` +1); `beginDecision()` then a call builds again; the freeze child: under `PLATSIM_AI_FREEZE=1`
  `pair.b[0].speed = 1` throws `TypeError`, without it does not; the CHECK child: with `PLATSIM_AI_CHECK: '1'`, `speedPair`
  whose `build` returns a different object on the second call exits non-zero with `/CHECK mismatch speedPair/`
- [ ] T023 [P] [US3] Add to `sim/test/expectimax2.test.mjs` ("017 speedInfo once per state"): around one
  `scoreActions` on the fixture position, `STATS.speedInfo` delta <= `X.nodes` + `acts.length` + 1 (root) and > 0;
  and `X.rootView.ai.cacheStats.speedPairs` delta <= 1

### Implementation for User Story 3

- [ ] T024 [US3] In `sim/ai/adapter.mjs`: decision-cache slot `let speedPair;` cleared in `beginDecision()`;
  `api.speedPair(build)`: hit → `speedPairHits++`, under CHECK `checkSame('speedPair', 'pair', speedPair, build())`,
  return it; miss → `speedPair = build()`, `if (FREEZE) deepFreeze(speedPair)`, `speedPairs++`, return. Header and
  `sim/ai/INTERFACE.md` 017 section (method, counters, CHECK)
- [ ] T025 [US3] In `sim/ai/cmds/battler.mjs`: rename today's `compareBattlerSpeed` body to `export function
  compareBattlerSpeedDirect(ctx, battler1, battler2)` (verbatim, citations kept; comment "reference, Constitution VI");
  new `export function compareBattlerSpeed(ctx, battler1, battler2)`: the two early returns verbatim (BL:1204-1210);
  if `(battler1 | battler2) > 1` return `compareBattlerSpeedDirect(ctx, battler1, battler2)` (doubles slots); else
  `const pair = ai.speedPair(() => { const ncn = countAliveAbility(ctx, K(ctx, 'ABILITY_CLOUD_NINE')) === 0 &&
  countAliveAbility(ctx, K(ctx, 'ABILITY_AIR_LOCK')) === 0; return { b: [battlerSpeed(ctx, 0, ncn), battlerSpeed(ctx, 1,
  ncn)] }; })`, `b1 = pair.b[battler1]`, `b2 = pair.b[battler2]`, then the `monSpeedValues` writes and the comparison
  block verbatim (move it into a shared helper `compareWith(ctx, battler1, battler2, b1, b2)`, exported for tests only
  and documented as such in its comment, used by both functions so the comparison text exists once; the direct function
  keeps computing its own `b1`, `b2`). Doc comment:
  why the pair is order-independent and draw-free (research R4)
- [ ] T026 [US3] In `sim/policy/expectimax2.mjs`: `STATS.speedInfo = 0` and `STATS.speedInfo++` at the top of `speedInfo`;
  `resolveTurn(X, S, pa, oa, speedOf = () => speedInfo(X, S))` using `speedOf().pFirst` where it read `speedInfo(X, S).pFirst`;
  in `valuePly2` after `replaceFainted` and the terminal check: `let sp; const speedOf = () => (sp ??= speedInfo(X, S));`
  passed to its `resolveTurn` calls; in `qValue` the same thunk per call passed to its `resolveTurn` calls;
  `variablePower` unchanged. Header "Decision context" comment: one line on the thunk and why `S` is constant across
  the loop (research R4)
- [ ] T027 [US3] Gate (quickstart step 4): `(cd sim && node --test test/ai_cmds_battler.test.mjs test/ai_adapter.test.mjs
  test/expectimax2.test.mjs test/replay.test.mjs test/ai_golden.test.mjs)` exit 0; freeze run exit 0; full Node suite
  exit 0; alone `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/c4_v2.json` → digest and
  `ai_draws` unchanged; record `gauntlets_per_s`, `ms_per_decision` under "US3 attribution" with the speed-pair
  coverage diagnostic
- [ ] T028 [US3] Commit 4 by path (`sim/ai/adapter.mjs sim/ai/cmds/battler.mjs sim/ai/INTERFACE.md sim/policy/expectimax2.mjs
  sim/test/ai_cmds_battler.test.mjs sim/test/ai_adapter.test.mjs sim/test/expectimax2.test.mjs specs/017-exact-dispatch-speedups/validation-log.md`),
  message `perf(017): one speed pair per view, speedInfo once per state (exact; equivalence vs the kept reference; replay digest unchanged)`,
  push; record the hash

**Checkpoint**: all three speedups landed and attributed.

---

## Phase 6: User Story 4 - The speedup is measured and recorded (Priority: P2)

**Goal**: the before/after table (FR-011, SC-002, SC-003, SC-004) from the committed bench tool, and the docs.

**Independent Test**: `runs/017-evidence/branch_*.json` exist with digests equal to `main`'s and `digests_agree`
true; the validation log has both sides, the step counts and the ratios.

- [ ] T029 [US4] Alone on the machine, on the branch at commit 4: `node sim/bench.mjs --policy expectimax2-v2 --json >
  runs/017-evidence/branch_v2.json`, `--policy expectimax2-v1 --json > runs/017-evidence/branch_v1.json`, `uv run platsim
  bench --workers 16 --json > runs/017-evidence/branch_pool.json` (`digests_agree` true, `pool_digest_logs` equal to
  T003's); write the table in the log: v2 and v1 single-process `gauntlets_per_s` and `ms_per_decision` (`main` T002 vs
  branch) with ratios, `interp_steps` (T007 vs branch) with ratio, 16-worker `pool_wall_s` and `pool_gauntlets_per_s`
  (T003 vs branch) with ratio, the per-commit attribution column (T013, T019, T027); SC-002 verdict in one line
  (`gauntlets_per_s` >= 1.15 x T002's for v2, otherwise the smaller gain stated plainly); SC-004 verdict (< 20 M)
- [ ] T030 [P] [US4] Docs: `README.md` speed table: add the 017 row (single-process and 16-worker before/after from
  T029, the interpreter step count) and extend the `sim_code_hash` note (017 changed it again); the bench command
  table gains the two new rows; `FUTURE-FEATURES.md` section 7: mark A, B, C done with the measured gain, keep D
  (`Constants.get` hoisting), E (`damageOutcomes` memo), F (merge signature), the generalised compare-and-jump idea
  (`IfLoadedEqualTo`, R1) and the killed `matchupScore` memo; renumber the `expectimax2-v4` approximations to 018
- [ ] T031 [P] [US4] `RUN-STATE.md` START HERE: 017 state (commits, numbers, what is left: user testing, full suite,
  merge), the trap list (`sim_code_hash`, no commit during runs, fixture and golden fixtures never re-recorded,
  `pgrep -f` trap)
- [ ] T032 Gates (SC-007, FR-010): `git diff --stat main HEAD -- pokemon-showdown` empty, exit 0; `(cd sim && node
  --test test/*.test.mjs)` exit 0 → `runs/017-evidence/node-suite.log`; `uv run pytest -q -m "not battle_sim"` exit 0 →
  `runs/017-evidence/fast.log`; record summary lines and Eastern times in the log; commit 5 by path (`README.md
  FUTURE-FEATURES.md RUN-STATE.md specs/017-exact-dispatch-speedups/validation-log.md` plus any doc touched in T030),
  message `docs(017): speed table, follow-ons, run state; gates recorded`, push
- [ ] T033 Merge gate (after the user's hands-on testing and go, nothing else running, background): `uv run pytest -q
  --durations=25 > runs/017-evidence/full.log 2>&1` (about 1 h 05 min; give the start time); record the summary line,
  exit code and Eastern start/end in the log and RUN-STATE. Do not merge; report to the user

---

## Dependencies & Execution Order

- **Phase 1 (T001-T003)**: first; T002 and T003 run on `main`, alone, sequentially; switch back at the end of T003.
- **Phase 2 (T004-T007)**: after T003, on the branch. T004 blocks everything after it. T005 and T006 [P] (different
  files) after T004; T007 after both. Blocks every story (the step counter is the SC-004 instrument).
- **US1 (T008-T014)**: after T007. T008 and T009 [P] before T010-T012 (the tests fail on the missing exports, then
  pass); T010 before T011 (the loop reads `ins.dispatch` / `ins.a`); T011 before T012 (`evalMoves` uses the hook);
  T013 after T012; T014 last.
- **US2 (T015-T020)**: after T014 (commit order; `ai_adapter.test.mjs` and `expectimax2.test.mjs` are touched again in
  US3). T015, T016 [P] before T017-T018; T017 before T018 (the policy relies on the CHECK-covered memo); T019 after T018;
  T020 last.
- **US3 (T021-T028)**: after T020 (same files `adapter.mjs`, `ai_adapter.test.mjs`, `expectimax2.test.mjs`). T021,
  T022, T023 [P] before T024-T026; T024 before T025 (battler.mjs calls `ai.speedPair`); T026 independent of T024-T025
  in code but committed together; T027 after T026; T028 last.
- **US4 (T029-T033)**: T029 after T028; T030, T031 [P] after T029 (they quote its numbers); T032 after T030-T031;
  T033 after T032 and the user's go.

### Parallel opportunities

- T005, T006 together (instrumentation code and its test).
- T008, T009 together (US1 tests: two files).
- T015, T016 together (US2 tests: two files).
- T021, T022, T023 together (US3 tests: three files).
- T030, T031 together (docs).
- Measurements (T002, T003, T007, T013, T019, T027, T029) are never parallel with anything: alone on the machine.

## Parallel Example: User Story 3 tests

```bash
# Three independent test additions, then one run shows them fail before T024:
Task: "T021 speed pair memo == direct over >= 1,000 real views in sim/test/ai_cmds_battler.test.mjs"
Task: "T022 speedPair lifecycle, freeze and CHECK children in sim/test/ai_adapter.test.mjs"
Task: "T023 STATS.speedInfo once per state in sim/test/expectimax2.test.mjs"
(cd sim && node --test test/ai_cmds_battler.test.mjs test/ai_adapter.test.mjs test/expectimax2.test.mjs)   # expected: new tests fail (no speedPair yet)
```

## Implementation Strategy

- **MVP = Phase 1 + Phase 2 + US1** (commits 1 and 2): the largest item, proven by the exhaustive equivalence test,
  the replay test and the unchanged golden traces, attributed on its own with the step count before and after.
  Stop and validate at T013.
- **Then US2** (commit 3) with the recorded full-set CHECK run, **then US3** (commit 4), each on the same gate.
- **Then US4** (commit 5): the before/after table and docs. SC-002 and SC-004 are judged at T029.
- **Merge** only after the user's hands-on testing and the full suite (T033), per the project rules.

## Notes

- 33 tasks across 4 stories plus the instrumentation phase; 12 of them are gates, measurements or commits rather
  than code. Slightly above the ~30 guideline the plan estimated; the extra tasks are the instrumentation commit
  (two tasks) and the split of US3's tests into three files. If the user prefers, US3 (T021-T028) can be deferred to
  its own feature without touching US1 or US2: it shares files with US2 but no functions.
- The structure test's expected run lengths (13 runs; 178, 152, …) are facts of the pinned decomp script measured on
  2026-11-02 (`runs/016-evidence/scratchpad/prof3/chains.mjs`); a decomp bump would change them and the test says so
  in its message.
- The policy test in T015 proves the switch two ways: the import statement no longer names `fromShowdown`, and the
  root adapter's hit count covers every table entry.
- The eight measurement runs are about 40 s each single-process and 1 min on the pool; the two CHECK runs about
  2 min each; the full suite (T033) is the only long run.
