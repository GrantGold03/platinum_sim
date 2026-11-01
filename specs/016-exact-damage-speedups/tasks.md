# Tasks: Exact Damage-Path Speedups for expectimax2 (round two)

**Input**: Design documents from `specs/016-exact-damage-speedups/` (spec.md, plan.md, research.md, data-model.md,
contracts/damage-api.md, contracts/adapter-api.md, quickstart.md).

**Tests**: Required by the spec (FR-001 to FR-008, SC-001, SC-004, SC-005) and Constitution V. The proof harness
(replay test and fixture) exists from feature 015 and is used unchanged. Each story's new tests are written first
and shown to fail on the missing exports (or, for equivalence tests, shown to pass on both sides with a positive
control); every commit is gated on the replay test.

**Organization**: by user story. US1 (type-chart plan in the damage port), US2 (AI pre-variance memo and control
mode) and US3 (shared mappers) are separate code changes committed in that order so each gain is attributed; US4
(measurement and docs) depends on all three.

## Conventions

- Temp files and scripts go in the session scratchpad; evidence (bench JSON, suite logs) in `runs/016-evidence/`
  (git-ignored). Never `/tmp`.
- Never `git commit -a`; stage paths by name. The user's own files (`.claude/scheduled_tasks.lock` deletion,
  `.claude/skills/speckit-assess-*`, `.specify/assessments/`, `.specify/extensions*`, `held_items.md`) stay out.
- `data/generated/` needs no rebuild for this feature (no extractor change; identical on `main` and the branch).
- Never commit, switch branches or run a suite while a measurement is running. SC-002/SC-003 measurements run with
  nothing else on the machine (`pgrep -a -x node; pgrep -a pytest` first; never `pgrep -f` with the script name from
  a shell whose command line contains it).
- Record every result (command, exit code, summary lines, Eastern times, commit hash) in
  `specs/016-exact-damage-speedups/validation-log.md` as it lands. Never pipe a command whose exit code matters.
- Node tests: `(cd sim && node --test test/*.test.mjs)` (326 today, about 5 min; the replay test alone 35-45 s).
  Freeze run: `(cd sim && PLATSIM_AI_FREEZE=1 node --test test/replay.test.mjs test/ai_*.test.mjs)`. Fast mode:
  `uv run pytest -q -m "not battle_sim"` (528 passed, 4 xfailed today). Full suite (merge gate, about 1 h 20 min):
  `uv run pytest -q --durations=25`, background, nothing else running.
- Commit order is the exactness chain (plan): 1 US1, 2 US2, 3 US3, 4 US4 + docs. Push every commit touching
  `sim/`, `src/` or `tests/`. Do not merge.
- `sim/` edits change `sim_code_hash`: optimizer checkpoints made before 016 will not resume (say so in RUN-STATE
  and the README note).
- The replay fixture `sim/test/replay_prof_a.json` is never re-recorded in this feature (FR-002). A replay failure
  means a behaviour change: stop and fix the code, never the fixture.
- Every decomp citation in `sim/damage.mjs` and `sim/ai/*.mjs` stays with the line it documents; the plan and the
  memos change mechanics, never a cited value.

## Phase 1: Setup (baseline on `main` 19519ed, no code change)

**Purpose**: the numbers the branch is compared with, taken from `main` at comparison time under the same
conditions as the branch runs (quickstart step 0).

- [X] T001 Create `specs/016-exact-damage-speedups/validation-log.md` (header: times Eastern, evidence dir
  `runs/016-evidence/`; sections per task; record branch `016-exact-damage-speedups`, base `main` 19519ed,
  `git diff --stat main HEAD -- sim src tests` expected empty, exit 0); `mkdir -p runs/016-evidence`
- [X] T002 `git switch main`; alone on the machine: `node sim/bench.mjs --policy expectimax2-v2 --json > runs/016-evidence/main_v2.json`
  and `--policy expectimax2-v1 --json > runs/016-evidence/main_v1.json` (about 1 min each); `digest_full` MUST be
  `db6d20cf59008d32640358a6a143eb94d5102b46ebcc0d116f39c2856fd504d3` and `1273b69462bcce8c690e020e9c9699412e1a3f40809d4d7b1a77ecc23d3c3178`;
  record `gauntlets_per_s`, `ms_per_decision`, `ai_draws`, `wall_s` for both in the log (these are the "before" figures)
- [X] T003 Still on `main`, alone: `uv run platsim bench --workers 16 --json > runs/016-evidence/main_pool.json` (about 2 min);
  `digests_agree` MUST be true; record `pool_wall_s`, `pool_gauntlets_per_s`, `pool_digest_logs`; then
  `git switch 016-exact-damage-speedups`; record in the log

**Checkpoint**: v1 and v2 single-process figures and the 16-worker figure for `main` 19519ed are in the log.

---

## Phase 2: Foundational (the existing proof harness is the reference for this base)

**Purpose**: confirm, before any code lands, that the 015 replay fixture is the reference for `main` 19519ed on
this branch (positive control for every later replay gate).

- [X] T004 On the branch: `(cd sim && node --test test/replay.test.mjs)` exit 0 (3 tests; diagnostic about 35-45 s,
  6144 player decisions); record the diagnostic line in the log. If it fails here, nothing else may start: the
  fixture or the base is not what the plan assumes

**Checkpoint**: the replay gate is known-good on unchanged code.

---

## Phase 3: User Story 1 - Type effectiveness worked out once per matchup (Priority: P1) 🎯 MVP

**Goal**: `typeChartPlan` / `replayTypeChart` in `sim/damage.mjs`, `applyTypeChart` = plan + replay, the per-roll
body kept as `applyTypeChartDirect`, `calcDamage` with one `prepare()` and one plan per call, `DAMAGE_STATS`
(FR-004; research R1, R4; contract `damage-api.md`).

**Independent Test**: the randomized equivalence test reports 0 mismatches with every coverage counter >= 100
and its positive control firing; the replay test matches the unchanged fixture with only this change; the
Showdown cross-check in `damage.test.mjs` still passes.

### Tests for User Story 1 (write first; fail on the missing exports before T006)

- [X] T005 [US1] Create `sim/test/damage_typechart.test.mjs` per research R4: a seeded PRNG (mulberry32, seed
  constant, printed with `t.diagnostic`); `synthetic()` builds attacker/defender structs in the port's shape
  (`types` two of `ENUMS.types` excluding TYPE_MYSTERY, equal with p 1/4; `ability` from a weighted list incl.
  ABILITY_LEVITATE, WONDER_GUARD, FILTER, SOLID_ROCK, TINTED_LENS, ADAPTABILITY, SCRAPPY, MOLD_BREAKER, NORMALIZE,
  KLUTZ and 10 common others; `item` from ITEM_NONE, ITEM_EXPERT_BELT, ITEM_IRON_BALL, ITEM_LIFE_ORB, a berry, 5
  others; flags `foresight magnetRise ingrain roosting miracleEye abilitySuppressed embargo` each true with p 1/8;
  `stats`/`stages`/`level`/`hp` random in range), `field` `{ gravity p 1/8, weather random, defenderSide {} }`, `move`
  a random decomp move constant from `TYPE_CHART`-independent `moveData` list (collect constants from
  `pokeplatinum/res/moves/*/data.json` names once; MOVE_STRUGGLE with p 1/100), optional `power` / `type` overrides (p
  1/8 each), pre-variance damage 0..400 (0 with p 1/16), `ignoreTypeChecks` p 1/4, incoming `moveStatusMask` from
  {0, SUPER_EFFECTIVE, NOT_VERY_EFFECTIVE} (nonzero p 1/8); `realData()` builds structs from `decompTables()`
  species (`types` via `ENUMS.types`, ability from the species' own list), moves with `power > 0`, items from the
  item table, random stages. Test 1: for >= 10,000 synthetic and >= 1,000 real-data matchups and each of the 16
  rolls `applyVariance(pre, 85 + i)`, `applyTypeChart(input, d, opts)` deep-equals `applyTypeChartDirect(input, d,
  opts)` (`damage`, `moveStatusMask`, `totalMul`); coverage counters (immune, Levitate, Magnet Rise, Wonder Guard,
  Filter/Solid Rock applied, Expert Belt applied, Tinted Lens applied, STAB, Adaptability, Foresight/Scrappy break,
  Normalize, type override, ignoreTypeChecks, zero damage, Struggle, super effective, not very effective, grounding
  item vs Flying, Roost, Miracle Eye) each >= 100 in the synthetic layer, reported in a diagnostic. Test 2 (positive
  control): for 200 synthetic inputs whose plan has at least one `mul` step, replaying a copy of the plan with one
  `mul` step removed (and separately with a `stab15` step added or removed) differs from the direct result for at
  least one roll each. Test 3: for 300 synthetic inputs, `calcDamage(input)` and `calcDamage({ ...input, crit: true })`
  equal a 16-fold direct computation (`calcBaseDamage` + `applyScriptMultipliers` + `applyVariance` +
  `applyTypeChartDirect` per roll, immune handling as in `calcDamage`). Test 4: `DAMAGE_STATS` deltas around one
  `calcDamage` call: `plans` +1, `replays` +16, `direct` +0. Target runtime under 5 s

### Implementation for User Story 1

- [X] T006 [US1] In `sim/damage.mjs`: rename the current `applyTypeChart` body to `export function applyTypeChartDirect(...)`
  (verbatim, same citations, header comment "reference implementation, Constitution VI; the plan below is tested
  against it"); add `export function typeChartPlan({ attacker, defender, move, field = {} }, { ignoreTypeChecks =
  false, moveStatusMask = 0 } = {})` returning `{ struggle, steps, mask, totalMul }` with the step kinds of
  data-model.md (`stab15`, `x2`, `mul`, `div34`, `pct`), built by the same branch structure and citations as the direct
  body (the chart walk, Levitate / Magnet Rise, Foresight / Scrappy break, `basicTypeMulApplies`, Wonder Guard, Filter /
  Solid Rock, Expert Belt, Tinted Lens, the ignore-mode mask clears); add `export function replayTypeChart(plan, damage)`
  applying the steps in order with `idiv`, `s32`, `battleDivide` and the `if (damage)` guard on `mul`; make
  `applyTypeChart(input, damage, opts)` return `replayTypeChart(typeChartPlan(input, opts), damage)`; add
  `export const DAMAGE_STATS = { plans: 0, replays: 0, direct: 0 }` incremented in the three functions
- [X] T007 [US1] In `sim/damage.mjs` `calcDamage(input)`: call `prepare()` once and `typeChartPlan` once, then
  `replayTypeChart` per roll; add private helpers `calcBaseDamageP(prep, input, critMul)`, `applyScriptMultipliersP(prep,
  input, base, critMul)`, `critMultiplierP(prep, input)` holding the current bodies, with the exported `calcBaseDamage`,
  `applyScriptMultipliers`, `critMultiplier` as thin wrappers that call `prepare()` themselves (signatures and results
  unchanged); update the module header's function map (lines 1-20) with the new names
- [X] T008 [US1] Gate (quickstart step 1): `(cd sim && node --test test/damage_typechart.test.mjs test/damage.test.mjs
  test/replay.test.mjs test/ai_golden.test.mjs test/ai_gauntlet.test.mjs)` exit 0; freeze run exit 0; full Node suite
  exit 0 (326 + 4); alone on the machine `node sim/bench.mjs --policy expectimax2-v2 --json > runs/016-evidence/bench-c1-v2.json`
  → `digest_full` `db6d20cf…`, `ai_draws` equal to T002; record `gauntlets_per_s`, `ms_per_decision` under "US1
  attribution" with the coverage diagnostic and the equivalence test's runtime
- [X] T009 [US1] Commit 1 by path (`sim/damage.mjs sim/test/damage_typechart.test.mjs specs/016-exact-damage-speedups/validation-log.md`),
  message `perf(016): type-chart plan replayed per roll (exact; equivalence test vs the kept reference; replay digest unchanged)`,
  push; record the hash

**Checkpoint**: US1 alone is proven exact (equivalence test + replay) and its speedup is attributed.

---

## Phase 4: User Story 2 - The trainer AI's base damage computed once per matchup per decision (Priority: P1)

**Goal**: `ai.typeChartPlan()` and `ai.preVariance()` memoised in the 015 decision cache; `calcdamage.calcDamage`
and `calcdamage.applyTypeChart` use them; `PLATSIM_AI_CHECK=1` control mode; counters (FR-005, FR-006, FR-007;
research R2; contract `adapter-api.md`).

**Independent Test**: replay test passes with this change; `cacheStats.preVariance` builds per decision are
independent of K; the CHECK child on one Aaron battle per policy exits 0 with `checks > 0`; the corrupted-memo child
fails with `CHECK mismatch`; the frozen child throws on a write to a plan or an entry; the full-set CHECK run matches
both digests.

### Tests for User Story 2 (write first; fail on the missing methods before T013)

- [X] T010 [P] [US2] Add to `sim/test/ai_adapter.test.mjs` ("016 preVariance memo"): on the file's battle fixture and
  a sample of moves (a damaging move, power 0 with a type override, fixedDamage 40 as Dragon Rage's path):
  `ai.typeChartPlan(att, def, num, opts)` deep-equals `typeChartPlan(ai.damageInput(att, def, num, opts), {
  ignoreTypeChecks: false, moveStatusMask: 0 })` and `ai.preVariance(att, def, num, opts, 0)` deep-equals
  `replayTypeChart(plan, calcBaseDamage({ ...input, critMul: 1 }))` restricted to `{ damage, moveStatusMask }`, and with
  `fixedDamage 40` equals the replay of the ignore-mode plan on 40; a second identical call returns the same object
  (`===`), `cacheStats.preVariance` unchanged, `preVarianceHits` +1 (same for `plans` / `planHits`); `ai.beginDecision()`
  then a call → `preVariance` +1 (dropped); a different `fixedDamage` or `type` is a different entry; a non-singles
  battle throws. Extend the "015 freeze guard" child script: under `PLATSIM_AI_FREEZE=1`, `plan.steps.push({})` and
  `entry.damage = 1` throw `TypeError`; without it they do not (control)
- [X] T011 [P] [US2] Add to `sim/test/ai_adapter.test.mjs` ("016 CHECK mode", child processes via `spawnSync` as the
  freeze test does): (a) child with `PLATSIM_AI_CHECK: '1'` imports `../test/ai_fixtures.mjs` (`gd`), `runGauntlet` from
  `../gauntlet.mjs` and `CHECK_STATS` from `../ai/adapter.mjs`, runs `benchRequests({ n: 1, teams: ['bench'], trainers:
  ['aaron'], policy })` for `expectimax2-v2` and `expectimax2-v1`, prints `CHECK_STATS.checks` and `mismatches`; assert
  exit 0, `checks > 0`, `mismatches === 0` (about 5-10 s); (b) child with `PLATSIM_AI_CHECK: '1'` and no FREEZE builds
  an adapter on a small battle, calls `preVariance` once, sets the returned entry's `damage` to `damage + 1`, calls again
  with the same arguments; assert non-zero exit and stderr matching `/CHECK mismatch preVariance/` (positive control);
  (c) control: the same script with `PLATSIM_AI_CHECK: ''` exits 0 (no comparison)
- [X] T012 [P] [US2] Add to `sim/test/ai_cmds_damage.test.mjs` ("016 preVariance per decision"): with the file's AI
  env fixture, run `calcAllDamage` for K = 1, 2, 4 repeated calls (same `varyDamage` rolls pattern as the 015
  cacheStats test) without `beginDecision` between them: `cacheStats.preVariance` delta is the same for every K (one
  per attacker-defender-move), `preVarianceHits` grows with K, and the returned `damageVals` equal a by-hand computation
  for one move (`calcBaseDamage` + `applyTypeChartDirect` + immune check + `battleDivide(d * roll, 100)`); after
  `beginDecision()` the next call builds again

### Implementation for User Story 2

- [X] T013 [US2] In `sim/ai/adapter.mjs`: import `typeChartPlan`, `replayTypeChart`, `calcBaseDamage` from `../damage.mjs`;
  module-level `const CHECK = process.env.PLATSIM_AI_CHECK === '1'` and `export const CHECK_STATS = { checks: 0, mismatches: 0 }`;
  inside `createAdapter`: `plans = new Map()`, `pre = new Map()` (attacker struct → defender struct → key string), cleared
  by `beginDecision()`; `cacheStats` gains `plans, planHits, preVariance, preVarianceHits, checks`; `api.typeChartPlan(att,
  def, moveIdOrNum, opts, { ignoreTypeChecks = false } = {})` and `api.preVariance(att, def, moveIdOrNum, opts, fixedDamage)`
  per `contracts/adapter-api.md` (key `${num}|${power}|${type}|${ignore}|${fixed}`; frozen under FREEZE; under CHECK every
  hit recomputes, deep-compares via `JSON.stringify` of the compared fields, increments `checks` / `CHECK_STATS.checks`,
  and on a difference increments `mismatches` and throws `Error(\`adapter: CHECK mismatch ${kind} ${key}: memo=${a} fresh=${b}\`)`);
  update the header comment (016 paragraph) and `sim/ai/INTERFACE.md` ("Decision cache" section: the two methods, the
  counters, `PLATSIM_AI_CHECK` next to `PLATSIM_AI_FREEZE`)
- [X] T014 [US2] In `sim/ai/calcdamage.mjs`: `calcDamage(env, …)` lines 300-310 → `const att = ai.pokemon(attacker), def =
  ai.pokemon(defender)` (empty-battler error kept), `const r = ai.preVariance(att, def, move, { power: power & 0xffff,
  type: typeName(type), powerMul: 10 }, damage)`, then the immune check and variance step unchanged (TAI:3106-3109
  citations kept); `applyTypeChart(env, …)` → `replayTypeChart(env.ai.typeChartPlan(att, def, move, { power: 0, type:
  typeName(type), powerMul: 10 }), damage)` returning `{ damage, moveStatusMask }`; import `replayTypeChart` from
  `../damage.mjs`, drop `calcBaseDamage` / `dmgApplyTypeChart` / `portInput` if no longer referenced (grep first; keep
  what `damageCheckApplies` or others still use); update the file header's function map
- [X] T015 [US2] Gate (quickstart step 2): `(cd sim && node --test test/ai_adapter.test.mjs test/ai_cmds_damage.test.mjs
  test/replay.test.mjs test/ai_golden.test.mjs)` exit 0; freeze run exit 0; full Node suite exit 0; alone on the machine
  `PLATSIM_AI_CHECK=1 node sim/bench.mjs --policy expectimax2-v2 --json > runs/016-evidence/check_v2.json` and `-v1 …
  check_v1.json`: exit 0, digests `db6d20cf…` / `1273b694…` (about 2 min each; record wall, this is the recorded
  full-set control, SC-005); then `node sim/bench.mjs --policy expectimax2-v2 --json > runs/016-evidence/bench-c2-v2.json`
  (no CHECK) → digest and `ai_draws` unchanged; record `gauntlets_per_s`, `ms_per_decision` under "US2 attribution"
- [X] T016 [US2] Commit 2 by path (`sim/ai/adapter.mjs sim/ai/calcdamage.mjs sim/ai/INTERFACE.md sim/test/ai_adapter.test.mjs
  sim/test/ai_cmds_damage.test.mjs specs/016-exact-damage-speedups/validation-log.md`), message `perf(016): memoise the
  trainer AI's pre-variance damage per decision (exact; CHECK mode; replay digest unchanged)`, push; record the hash

**Checkpoint**: US1 and US2 landed, each gated by the replay test and the freeze run; the full-set CHECK run recorded.

---

## Phase 5: User Story 3 - The identifier translation built once and shared (Priority: P2)

**Goal**: module-level mapper sets per `(dex, decomp tables)` with one `Map` per kind; `createAdapter` uses them
(FR-008; research R3; contract `adapter-api.md`).

**Independent Test**: shared equals fresh over every engine identifier the decomp knows; unknown ids throw the same
messages; two adapters share one set; replay test passes.

### Tests for User Story 3 (write first; fail on the missing `makeMappers` export / `ai.mappers` before T018)

- [X] T017 [US3] Add to `sim/test/ai_adapter.test.mjs` ("016 shared mappers"): import `makeMappers`, `decompTables` from
  `../ai/adapter.mjs`; build `fresh = makeMappers(battle.dex, decompTables())` (unshared) and two adapters `a`, `b` on the
  same battle; assert `a.mappers === b.mappers` and `a.mappers !== fresh`; for every `battle.dex.moves.all()` entry with
  `num > 0` and `T.moves[num]`, `a.mappers.move(x.id) === fresh.move(x.id)`; same for abilities (`C.nameOf('abilities',
  num)` known) and items (`T.items[num]` with matching name, as the existing num-equivalence test at line 57 selects
  them); every type name in `ENUMS.types` (as Showdown names, plus `'???'`) and the species of both parties; unknown
  ids (`'notamove'`, `'notanability'`, `'notanitem'`, type `'Fairy'`) throw with the same messages on shared and fresh;
  the shared set's `Map`s are non-empty after the loop (positive control that lookups went through the shared set)

### Implementation for User Story 3

- [X] T018 [US3] In `sim/ai/adapter.mjs`: replace `makeMappers(dex, T)`'s per-call `cache` / `memo` with five `Map`s
  (`move`, `ability`, `item`, `species`, `type`) looked up by their natural key (`id`, `id`, `id`, `sp.id`, `name`), same
  validation and error messages; export `makeMappers`; add module-level `const MAPPERS = new WeakMap()` and
  `function mappersFor(dex, T)` returning the cached set for `dex` when its `T` matches, else building and storing a new
  one; `createAdapter` uses `mappersFor(dex, T)` and exposes `api.mappers` (the shared set's function object, read-only);
  update the header comment
- [X] T019 [US3] Gate (quickstart step 3): `(cd sim && node --test test/ai_adapter.test.mjs test/replay.test.mjs
  test/ai_golden.test.mjs)` exit 0; full Node suite exit 0; alone `node sim/bench.mjs --policy expectimax2-v2 --json >
  runs/016-evidence/bench-c3-v2.json` → digest and `ai_draws` unchanged; record `gauntlets_per_s`, `ms_per_decision`
  under "US3 attribution"
- [X] T020 [US3] Commit 3 by path (`sim/ai/adapter.mjs sim/test/ai_adapter.test.mjs specs/016-exact-damage-speedups/validation-log.md`),
  message `perf(016): share the Showdown-to-decomp id mappers across adapters (exact; replay digest unchanged)`, push;
  record the hash

**Checkpoint**: all three speedups landed and attributed.

---

## Phase 6: User Story 4 - The speedup is measured and recorded (Priority: P2)

**Goal**: the before/after table (FR-011, SC-002, SC-003) from the committed bench tool, and the docs.

**Independent Test**: `runs/016-evidence/branch_*.json` exist with digests equal to `main`'s and `digests_agree` true;
the validation log has both sides and the ratios.

- [X] T021 [US4] Alone on the machine, on the branch at commit 3: `node sim/bench.mjs --policy expectimax2-v2 --json >
  runs/016-evidence/branch_v2.json`, `--policy expectimax2-v1 --json > runs/016-evidence/branch_v1.json`, `uv run platsim
  bench --workers 16 --json > runs/016-evidence/branch_pool.json` (`digests_agree` true, `pool_digest_logs` equal to
  T003's); write the table in the log: v2 and v1 single-process `gauntlets_per_s` and `ms_per_decision` (`main` T002 vs
  branch) with ratios, 16-worker `pool_wall_s` and `pool_gauntlets_per_s` (T003 vs branch) with ratio, the per-commit
  attribution column (T008, T015, T019); SC-002 verdict in one line (`gauntlets_per_s` ≥ 0.935 for v2, otherwise the
  smaller gain stated plainly)
- [X] T022 [P] [US4] Docs: `README.md` speed table: add the 016 row (single-process and 16-worker before/after from
  T021) and extend the `sim_code_hash` note (016 changed it again); `README.md` or the sim docs where
  `PLATSIM_AI_FREEZE` is described: add `PLATSIM_AI_CHECK=1` in one line; `FUTURE-FEATURES.md` section 7: mark the
  three items done with the measured gain, keep the remaining items (replacement-heuristic memo, interpreter argument
  index, `K()` hoisting, cross-decision caches, `expectimax2-v4` as feature 017)
- [X] T023 [P] [US4] `RUN-STATE.md` START HERE: 016 state (commits, numbers, what is left: user testing, full suite,
  merge), the trap list (`sim_code_hash`, no commit during runs, fixture never re-recorded, `pgrep -f` trap)
- [X] T024 Gates (SC-006): `git diff --stat main HEAD -- pokemon-showdown` empty, exit 0 (FR-010); `(cd sim && node
  --test test/*.test.mjs)` exit 0 → `runs/016-evidence/node-suite.log`; `uv run pytest -q -m "not battle_sim"` exit 0 →
  `runs/016-evidence/fast.log`; record summary lines and Eastern times in the log; commit 4 by path (`README.md
  FUTURE-FEATURES.md RUN-STATE.md specs/016-exact-damage-speedups/validation-log.md` plus any doc touched in T022),
  message `docs(016): speed table, CHECK mode note, follow-ons, run state; gates recorded`, push
- [ ] T025 Merge gate (after the user's hands-on testing and go, nothing else running, background): `uv run pytest -q
  --durations=25 > runs/016-evidence/full.log 2>&1` (about 1 h 20 min; give the start time); record the summary line,
  exit code and Eastern start/end in the log and RUN-STATE. Do not merge; report to the user

---

## Dependencies & Execution Order

- **Phase 1 (T001-T003)**: first; T002 and T003 run on `main`, alone, sequentially; switch back at the end of T003.
- **Phase 2 (T004)**: after T003, on the branch. Blocks everything after it.
- **US1 (T005-T009)**: after T004. T005 before T006-T007 (the test fails on missing exports, then passes); T008 after
  T007; T009 last.
- **US2 (T010-T016)**: after T009 (its tests import `typeChartPlan` / `replayTypeChart` from US1). T010, T011, T012 [P]
  (three test blocks in two files) before T013-T014; T013 before T014 (calcdamage calls the new methods); T015 after
  T014; T016 last.
- **US3 (T017-T020)**: after T016 (same file `sim/ai/adapter.mjs` and `ai_adapter.test.mjs`; sequential by the commit
  order). T017 before T018; T019; T020.
- **US4 (T021-T025)**: T021 after T020; T022, T023 [P] after T021 (they quote its numbers); T024 after T022-T023;
  T025 after T024 and the user's go.

### Parallel opportunities

- T010, T011, T012 together (US2 tests: two files, independent blocks).
- T022, T023 together (docs).
- Measurements (T002, T003, T008, T015, T019, T021) are never parallel with anything: alone on the machine.

## Parallel Example: User Story 2 tests

```bash
# Three independent test additions, then one run shows them fail before T013:
Task: "T010 preVariance / typeChartPlan memo lifecycle + freeze extension in sim/test/ai_adapter.test.mjs"
Task: "T011 CHECK-mode child processes (clean run, corrupted memo, control) in sim/test/ai_adapter.test.mjs"
Task: "T012 preVariance builds independent of K in sim/test/ai_cmds_damage.test.mjs"
(cd sim && node --test test/ai_adapter.test.mjs test/ai_cmds_damage.test.mjs)   # expected: new tests fail (no preVariance yet)
```

## Implementation Strategy

- **MVP = Phase 1 + Phase 2 + US1** (commit 1): the largest item, proven by the equivalence test and the replay
  test, attributed on its own. Stop and validate at T008.
- **Then US2** (commit 2) with the recorded full-set CHECK run, **then US3** (commit 3), each on the same gate.
- **Then US4** (commit 4): the before/after table and docs. SC-002 is judged at T021.
- **Merge** only after the user's hands-on testing and the full suite (T025), per the project rules.

## Notes

- 25 tasks across 4 stories; 10 of them are gates, measurements or commits rather than code. Within the plan's
  bound (24 to 28); one branch, no split proposed.
- `CHECK_STATS` (module-level aggregate of `checks` / `mismatches`) is added to `contracts/adapter-api.md` so the
  child-process test can read the counters without reaching into per-adapter `cacheStats`.
- The six measurement runs are about 1 to 2 min each single-process and 2 min on the pool; the two CHECK runs about
  2 min each; the full suite (T025) is the only long run.
- If the equivalence test's coverage for a rare condition (e.g. Wonder Guard with a super-effective hit that is
  `BASIC_EFFECTIVENESS`) cannot reach 100 at 10,000 matchups, raise the synthetic count or weight that ability, never
  lower the bar; record the final counts.
