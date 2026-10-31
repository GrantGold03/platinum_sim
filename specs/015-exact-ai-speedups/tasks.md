# Tasks: Exact AI-Prediction Speedups for expectimax2-v2

**Input**: Design documents from `specs/015-exact-ai-speedups/` (spec.md, plan.md, research.md, data-model.md,
contracts/adapter-api.md, contracts/bench-tool.md, quickstart.md).

**Tests**: Required by the spec (FR-001 to FR-006, FR-011, SC-001, SC-005) and Constitution V. The replay test
and fixture are recorded BEFORE either speedup (plan "Commit order"); each speedup's unit tests are written
first and shown to fail (or, for equivalence tests, shown to pass on both sides with a positive control).

**Organization**: by user story. US1 (memoised damage inputs) and US2 (resolved constants) are independent code
changes that share one proof (the replay test, Phase 2). US3 (measurement) depends on both landing.

## Conventions

- Temp files and scripts go in the session scratchpad; evidence (bench JSON, suite logs) in `runs/015-evidence/`
  (git-ignored). Never `/tmp`.
- Never `git commit -a`; stage paths by name. The user's own files (`.claude/scheduled_tasks.lock` deletion,
  `.claude/skills/speckit-assess-*`, `.specify/assessments/`, `.specify/extensions*`, `held_items.md`) stay out.
- `data/generated/` is shared: `uv run platsim extract` after every branch switch.
- Never commit, switch branches or run `extract` while a measurement or a suite is running. SC-002/SC-003
  measurements run with nothing else on the machine (check `pgrep -a node; pgrep -a pytest` first).
- Record every result (command, exit code, summary lines, Eastern times, commit hash) in
  `specs/015-exact-ai-speedups/validation-log.md` as it lands. Never pipe a command whose exit code matters.
- Node tests: `(cd sim && node --test test/*.test.mjs)` (314 today). Fast mode: `uv run pytest -q -m "not battle_sim"`.
  Full suite (merge gate, about 2 h 10 min): `uv run pytest -q`, background, nothing else running.
- Commit order is the exactness chain (plan): 1 instrumentation + fixture, 2 US1, 3 US2, 4 US3 + docs. Push
  every commit touching `sim/`, `src/` or `tests/`. Do not merge.
- `sim/` edits change `sim_code_hash`: checkpoints made before 015 will not resume (say so in RUN-STATE and the
  README note).
- Every `K()` / `C.get` site keeps its line-by-line decomp citation; US2 changes the lookup mechanics, never a
  cited value.

## Phase 1: Setup (baseline on `main` c751fb2, no code change)

**Purpose**: the numbers the branch is compared with, taken from `main` before any code lands.

- [X] T001 Create `specs/015-exact-ai-speedups/validation-log.md` (header: times Eastern, evidence dir; sections T001..; record branch `015-exact-ai-speedups`, base `main` c751fb2, `git diff --stat main HEAD -- src tests sim` expected empty, exit 0)
- [X] T002 `git switch main && uv run platsim extract` (exit 0); run `node runs/015-evidence/scratchpad/prof/run_gauntlets.mjs --policy expectimax2-v1` (about 2 min) and record v1's `digest` and wall in the log; **positive control**: rerun with `--policy expectimax2-v2` and confirm `db6d20cf59008d32640358a6a143eb94d5102b46ebcc0d116f39c2856fd504d3` (if the harness has no `--policy` flag, add it in the scratchpad copy only, never under the repo)
- [X] T003 Write a scratchpad script `<scratchpad>/bench_pool_main.py` that builds the 40 requests (`op: "gauntlet"`, teams `bench` = `tests/fixtures/policy_benchmark_team.json` `.team` then `ref` = `tests/fixtures/reference_team.json` `.builds`, seeds `prof-a-<team>-<i>`, i < 20, `player_policy: "expectimax2-v2"`, `opponent_policy: "decomp-ai"`, `stop_on_loss: False`), times `WorkerPool(16).map(reqs)` from `src/platsim/sim/pool.py`, prints wall, gauntlets/s, the hello `sim_code_hash`, and `digest_logs` per `contracts/bench-tool.md` (line `seed|cleared|final_levels,|battles;` with `trainer:end:turns:log_hash`); run it alone on the machine on `main`; record all four in the log (this is the `main` 16-worker baseline for SC-003 and the cross-language digest the branch's `platsim bench` must reproduce)
- [X] T004 `git switch 015-exact-ai-speedups && uv run platsim extract` (exit 0); record in the log

**Checkpoint**: v1 and v2 `main` digests, `main` pool wall/gauntlets/s and `main` `digest_logs` are in the log.

---

## Phase 2: Foundational (instrumentation, fixture, replay test; commit 1, no behaviour change)

**Purpose**: the proof harness both speedups are gated on. Nothing here may change a result: the gate is
`digest_full` equality with T002.

**⚠️ CRITICAL**: US1 and US2 cannot start until T010 is committed with a fixture whose v2 digest is `db6d20cf…`.

- [X] T005 Add `aiDraws: 0` to `STATS` in `sim/policy/expectimax2.mjs` (line 172) and, in `aiDecide` (line 937), add the sample's `rng.draws` to `STATS.aiDraws` on every return path (wrap the body: record `rng.draws` before returning; `AIRng.next()` increments `draws`, `sim/ai/choose.mjs:52-54`); also call `ms.ai.beginDecision?.()` in `makeContext` (line 1160, right after `mirrorFor`) so the hook exists before US1 adds the method (optional-call keeps commit 1 behaviour-free)
- [X] T006 Create `sim/bench.mjs` per `contracts/bench-tool.md`: `benchRequests({ block, n, teams, trainers })` (team loading from the two fixtures via `new URL('../tests/fixtures/…', import.meta.url)`), `runRecorded(gd, req)` (register `<policy>+rec` wrappers like `instrument()` in `sim/test/determinism.test.mjs:49-67`, record each p1 choice and the `STATS.aiDraws` delta across it (`policy_ai_draws[i]`), and for each opponent `choose` the `stateFor(battle).rng.draws` delta across it (`live_ai_draws[j]`, 0 baseline when the state does not exist yet); return `{ result, json, choices, policy_ai_draws, live_ai_draws }` with the two draw arrays per decision), `digestFull(jsons)` and `digestLogs(results, seeds)`, a `main()` behind `import.meta.url === pathToFileURL(process.argv[1]).href` that parses `--policy --n --block --teams --trainers --json --record FILE`, loads game data the way `sim/worker.mjs` does (`PLATSIM_GENERATED_DIR` / `PLATSIM_DIVERGENCES`), prints the table or JSON with every field in the contract (`sim_code_hash` from `sim/version.mjs`, `node`, `date`), exit 1 on unknown policy/team, and `--record` merging the policy key into the fixture file (schema in `data-model.md`, `recorded.commit` from `git rev-parse --short HEAD`)
- [X] T007 [P] Create `sim/test/bench.test.mjs` (fast, 1 trainer): `benchRequests` default set is 40 requests with seeds `prof-a-bench-0..19` then `prof-a-ref-0..19`, `stop_on_loss: false`, opponent `decomp-ai`; `digestLogs` of a hand-built result equals a sha256 computed inline from the contract's line format (positive control: changing one `log_hash` changes it); `runRecorded` with `greedy-v1` on `{ trainers: ['aaron'] }` returns `result` byte-equal to a plain `runGauntlet` run, `choices.length > 0`, `policy_ai_draws.length === choices.length` and every entry 0 for greedy, `live_ai_draws.length` equals the number of opponent choices and at least one entry is > 0 (positive control: the live AI drew)
- [X] T008 Gate (quickstart step 2): `node sim/bench.mjs --policy expectimax2-v2 --json > runs/015-evidence/bench-c1-v2.json` alone on the machine; `digest_full` MUST equal `db6d20cf…`; `node sim/bench.mjs --policy expectimax2-v1 --json > runs/015-evidence/bench-c1-v1.json`, `digest_full` MUST equal T002's v1 digest; record both plus `wall_s`, `gauntlets_per_s`, `ms_per_decision`, `ai_draws` in the log. A mismatch means the wrappers or the loader changed a result: stop and fix before anything else
- [X] T009 Record the fixture: `node sim/bench.mjs --policy expectimax2-v2 --record sim/test/replay_prof_a.json` then `--policy expectimax2-v1 --record sim/test/replay_prof_a.json`; check the file has both policy keys, 40 gauntlets each, `policies.expectimax2-v2.digest_full === db6d20cf…`, and `digest_logs` for v2 equals T003's pool `digest_logs` (cross-language positive control; if it differs, fix the line format in whichever side is wrong and re-record)
- [X] T010 Create `sim/test/replay.test.mjs` per `contracts/bench-tool.md`: the file re-imports itself as a worker (`determinism.test.mjs:76-78,106-112` pattern), W = `min(16, cpus().length)`, each worker runs a slice of the 80 (policy, request) pairs through `runRecorded` and posts `{ key, json, choices, policy_ai_draws, live_ai_draws, cleared, battles }`; main thread reassembles in request order, asserts per policy `digestFull === fixture.digest_full`, `digestLogs === fixture.digest_logs`, and per gauntlet `deepEqual` of `choices`, `policy_ai_draws` and `live_ai_draws` (per-decision arrays); `t.diagnostic` gauntlets, decisions, seconds; positive-control test: the comparison function applied to a copy of the fixture with one choice replaced reports a difference (and with one `live_ai_draws` entry changed). Run `(cd sim && node --test test/replay.test.mjs test/bench.test.mjs)`: pass; record wall (expected 15 to 30 s)
- [X] T011 Run `(cd sim && node --test test/*.test.mjs)` (expect 314 + new, exit 0); commit 1 by path: `sim/policy/expectimax2.mjs sim/bench.mjs sim/test/bench.test.mjs sim/test/replay.test.mjs sim/test/replay_prof_a.json specs/015-exact-ai-speedups/validation-log.md`, message `feat(015): bench tool, AI draw counter, replay fixture and test (no behaviour change)`, push; record the hash in the log

**Checkpoint**: the replay test passes on unchanged behaviour and its control fails on an altered fixture. US1
and US2 may start.

---

## Phase 3: User Story 1 - Damage-formula inputs built once per state (Priority: P1) 🎯 MVP

**Goal**: `ai.damageInput()` with a per-decision cache in the adapter; `portInput` and the post-KO switch scorer
use it; `beginDecision()` at the two decision boundaries (FR-004, FR-005; research R1, R3; contract
`adapter-api.md`).

**Independent Test**: replay test passes with only this change; `cacheStats.builds` per decision does not grow
with K; `PLATSIM_AI_FREEZE=1` suite run passes; stale-without-`beginDecision` control.

### Tests for User Story 1 (write first; expected to fail before T015-T017)

- [X] T012 [P] [US1] Add to `sim/test/ai_adapter.test.mjs`: (a) for a `newBattle` fixture (use the pattern already in that file) and every (attacker, defender) pair of active Pokemon and a sample of moves (a damaging move, a status move, a fixed-type override), `ai.damageInput(att, def, moveNum, opts)` deep-equals `fromShowdown(battle, att, def, moveNum, opts)` with `crit: false`; (b) two calls in one decision return the same `attacker` object (`===`), `cacheStats.builds` unchanged by the second call, `hits` +1; (c) mutate the battle between calls without `beginDecision()` (e.g. `p.boosts.atk = 2`, or `p.setStatus('brn')`) → the cached struct is stale (differs from a fresh `fromShowdown`; this is the control showing the cache really caches), then `ai.beginDecision()` → equal again and `cacheStats.decisions` +1; (d) a non-singles battle throws as `fromShowdown` does
- [X] T013 [P] [US1] Add to `sim/test/ai_adapter.test.mjs`: freeze guard: spawn `node` as a child (`spawnSync(process.execPath, ['--input-type=module', '-e', …], { env: { ...process.env, PLATSIM_AI_FREEZE: '1' } })`) that builds an adapter, calls `damageInput`, assigns `input.attacker.hp = 1`, and exits 0 only if a `TypeError` was thrown; assert exit 0 and that stderr/stdout names `TypeError`; control: the same script without the variable does NOT throw (exit code distinguishes)
- [X] T014 [P] [US1] Add to `sim/test/ai_cmds_damage.test.mjs` (FR-004 count): on a shadow-like battle fixture, run `calcAllDamage` (or `pickCommand` through the existing test helper) for K = 1, 2, 4 samples on the same adapter without `beginDecision` between samples and assert `cacheStats.builds` is the same for every K and at most the number of Pokemon on the field plus bench members the AI asked about (bound: 12), while the summed `calcDamage` calls grow with K (positive control that work happened)

### Implementation for User Story 1

- [X] T015 [US1] In `sim/ai/adapter.mjs`: import `battlerFromShowdown` and the field helpers from `../damage.mjs` (or re-implement the `field` block of `fromShowdown` lines 744+ exactly, citing the lines); add module-level `const FREEZE = process.env.PLATSIM_AI_FREEZE === '1'` and `deepFreeze`; inside `createAdapter` add `battlers = new Map()`, `fields = new Map()`, `cacheStats = { builds: 0, hits: 0, decisions: 0 }`; `beginDecision()` clears both maps and increments `decisions`; `damageInput(att, def, moveNum, { power, type, powerMul })` builds/looks up the two battler structs (`builds++` / `hits++`), the defender-side field struct (keyed by `def.side`), builds `attackerSideAbilities` / `defenderSideAbilities` and `move` per call, returns `{ attacker, defender, move, field, crit: false }`; throws on non-singles exactly as `fromShowdown`; expose `beginDecision`, `damageInput`, `cacheStats` on `api`; update the header comment (read-only contract: the returned structs are shared, callers must not write)
- [X] T016 [US1] `sim/ai/calcdamage.mjs:164-168` `portInput`: replace `fromShowdown(ai.battle, …)` with `ai.damageInput(att, def, move, { power: power & 0xffff, type: typeName(type), powerMul: 10 })`; `sim/ai/switch.mjs:499`: replace with `ai.damageInput(att, def, move, { power: 0, type: undefined, powerMul: 10 })`; drop now-unused `fromShowdown` imports if nothing else uses them in those files (grep first; keep the import if `greedy.mjs`-style uses remain)
- [X] T017 [US1] `sim/ai/opponent.mjs:207` `decide(st, side, opts)`: first statement `st.ai.beginDecision();` (before `processLog`); confirm `makeContext` already calls `ms.ai.beginDecision?.()` (T005) and make it unconditional (`ms.ai.beginDecision()`); update `sim/ai/INTERFACE.md` with `beginDecision` / `damageInput` / `cacheStats` and `PLATSIM_AI_FREEZE` next to the `PLATSIM_AI_DEBUG` note
- [X] T018 [US1] Gate (quickstart step 3): `(cd sim && node --test test/*.test.mjs)` exit 0 (replay, golden, determinism, adapter, calcdamage); `(cd sim && PLATSIM_AI_FREEZE=1 node --test test/replay.test.mjs test/ai_*.test.mjs)` exit 0; alone on the machine `node sim/bench.mjs --policy expectimax2-v2 --json > runs/015-evidence/bench-c2-v2.json` → `digest_full === db6d20cf…`, record `gauntlets_per_s`, `ms_per_decision`, `ai_draws` (must equal T008's) in the log under "US1 attribution"
- [X] T019 [US1] Commit 2 by path (`sim/ai/adapter.mjs sim/ai/calcdamage.mjs sim/ai/switch.mjs sim/ai/opponent.mjs sim/policy/expectimax2.mjs sim/ai/INTERFACE.md sim/test/ai_adapter.test.mjs sim/test/ai_cmds_damage.test.mjs specs/015-exact-ai-speedups/validation-log.md`), message `perf(015): memoise AI damage-formula inputs per decision (exact; replay digest unchanged)`, push; record the hash

**Checkpoint**: US1 alone is proven exact and its speedup is attributed.

---

## Phase 4: User Story 2 - Game constants resolved once (Priority: P1)

**Goal**: `Constants.get` memo fast path; effect tables resolved once into `Set`s (`effectSet`), used by
`effectIn` and the gravity / heal-block checks (FR-006 as read in research R2).

**Independent Test**: replay test passes with this change; `effectSet.has(v) === names.some(...)` for every
effect value; fresh and warmed `Constants` instances agree on every symbol; `effectSet` resolution runs once per
(table, constants) regardless of calls.

### Tests for User Story 2 (write first)

- [X] T020 [P] [US2] Add to `sim/test/ai_cmds_damage.test.mjs`: import `effectSet`, `NO_DAMAGE_CALC_EFFECTS`, `ALT_POWER_EFFECTS` from `../ai/calcdamage.mjs` and `MOVES_AFFECTED_BY_GRAVITY`, `MOVES_AFFECTED_BY_HEAL_BLOCK` from `../ai/choose.mjs`; for each table and for every distinct `effect` value in the move table plus `0` and `-1` (and for the move-list tables every move number 0..max), assert `effectSet(ai, table).has(v) === table.names.some((n) => ai.constants.get(n) === v)`; assert at least one `true` and one `false` per table (positive control); assert `effectSet(ai, table) === effectSet(ai, table)` (same Set object, resolved once) and that a second `Constants` instance gets its own Set with equal contents
- [X] T021 [P] [US2] Add to `sim/test/ai_adapter.test.mjs` (or a new `sim/test/ai_constants.test.mjs` if that file has no constants tests): build two `Constants` instances from the same root; on the first, call `get` on every defined name twice (warm), on the second once (cold); assert equal values for every name and equal `values.size`; assert unknown symbol and recursive definition still throw with the same message class on a warmed instance (error behaviour unchanged, contract)

### Implementation for User Story 2

- [X] T022 [US2] `sim/ai/constants.mjs:187` `Constants.get(name, stack)`: add the fast path `const v = this.values.get(name); if (v !== undefined) return v;` as the first statement and make `stack` default lazily (`stack ?? []`) only on the slow path; keep every other line, comment and citation as is
- [X] T023 [US2] `sim/ai/calcdamage.mjs:137`: replace `effectIn` with `effectSet(ai, table)` backed by a module-level `WeakMap<Constants, Set<number>>` stored on `table.resolved` (or a `WeakMap` keyed by table then constants), filled once with `new Set(table.names.map((n) => ai.constants.get(n)))`; `effectIn = (ai, table, effect) => effectSet(ai, table).has(effect)`; export `effectSet`; `sim/ai/choose.mjs:155-156`: replace the two `.names.some((n) => C(n) === moves[i])` with `effectSet(ai, MOVES_AFFECTED_BY_GRAVITY).has(moves[i])` / heal-block (import `effectSet`; check `ai`/constants are in scope there and adapt the key to `ai.constants` if the function only has `C`)
- [X] T024 [US2] Gate (quickstart step 4): `(cd sim && node --test test/*.test.mjs)` exit 0; `(cd sim && PLATSIM_AI_FREEZE=1 node --test test/replay.test.mjs test/ai_*.test.mjs)` exit 0; alone on the machine `node sim/bench.mjs --policy expectimax2-v2 --json > runs/015-evidence/bench-c3-v2.json` → `digest_full === db6d20cf…`, `ai_draws` equals T008; record `gauntlets_per_s` and `ms_per_decision`; SC-002 check: `gauntlets_per_s ≥ 0.579` (1.5 × 0.386), otherwise record the smaller gain plainly; also run `--policy expectimax2-v1 --json` once (digest must equal T002's v1 digest)
- [X] T025 [US2] Commit 3 by path (`sim/ai/constants.mjs sim/ai/calcdamage.mjs sim/ai/choose.mjs sim/test/ai_cmds_damage.test.mjs sim/test/ai_adapter.test.mjs` or `sim/test/ai_constants.test.mjs`, `specs/015-exact-ai-speedups/validation-log.md`), message `perf(015): resolve AI effect tables and constants once (exact; replay digest unchanged)`, push; record the hash

**Checkpoint**: both speedups landed, each gated by the replay test, each attributed.

---

## Phase 5: User Story 3 - The speedup is measured and recorded (Priority: P2)

**Goal**: `platsim bench` (pool half of the tool, FR-009, FR-011, SC-003) with its battle_sim test; the
before/after table in the validation log.

**Independent Test**: `uv run platsim bench --policy expectimax2-v2 --workers 16` exits 0 with the pool digest
equal to the single-process digest; `tests/integration/test_bench.py` passes; the log has both sides and ratios.

### Tests for User Story 3 (write first)

- [ ] T026 [P] [US3] Create `tests/integration/test_bench.py` (`@pytest.mark.battle_sim`, pattern of `tests/integration/test_pool.py`): (a) `platsim.bench.bench_requests(block='a', n=1, teams=['bench'], trainers=['aaron'], policy='greedy-v1')` yields one request with seed `prof-a-bench-0`; (b) `digest_logs(results, seeds)` of a hand-built result equals the sha256 computed inline from the contract line (same vector as `sim/test/bench.test.mjs` T007 so both languages are checked against one constant); (c) run `main(['bench','--policy','greedy-v1','--n','1','--teams','bench','--trainers','aaron','--workers','2','--json'])` via `platsim.cli.main` with `capsys`, parse the JSON, assert `digest_logs == pool_digest_logs`, `pool_workers == 2`, `gauntlets == 1`, exit 0; (d) control: with `--no-single` the single-process fields are absent and no comparison is claimed
- [ ] T027 [P] [US3] Add a fast unit test `tests/unit/test_bench_cli.py` (no worker start, not marked): `build_parser().parse_args(['bench', '--policy', 'x', '--no-single'])` has the defaults from the contract (`n 20`, `block a`, `teams ['bench','ref']`, `workers None`→CPU count); an unknown option exits 2

### Implementation for User Story 3

- [ ] T028 [US3] Create `src/platsim/bench.py`: `bench_requests(...)` mirroring `benchRequests` (same fixtures, seed pattern, `op: "gauntlet"`, `stop_on_loss: False`); `digest_logs(results, seeds)` per the contract line; `run_single_node(args)` → `subprocess.run([node, 'sim/bench.mjs', '--json', ...], check=False, capture_output=True)` (use `shutil.which('node')`, repo root from `platsim.version.REPO_ROOT`), parse JSON, propagate exit 1; `run_pool(requests, workers)` → `WorkerPool(workers)` from `platsim.sim.pool`, `time.perf_counter()` around `.map`, hello `sim_code_hash`; `run(args)` merges, prints the table (or JSON), compares digests when both halves ran, returns 0 / 1
- [ ] T029 [US3] `src/platsim/cli.py`: add `_add_bench(sub)` after `_add_report` with the options in `contracts/bench-tool.md` (`--policy` default `expectimax2-v2`, `--n` 20, `--block` a, `--teams` comma list default `bench,ref`, `--trainers` comma list, `--workers` int default `os.cpu_count()`, `--no-single`, `--json`), `set_defaults(func=bench.run)`; append to `_SUBCOMMANDS`; module docstring mention
- [ ] T030 [US3] Gate (quickstart step 5): `uv run pytest -q tests/unit/test_bench_cli.py tests/integration/test_bench.py -s` exit 0; alone on the machine `uv run platsim bench --policy expectimax2-v2 --workers 16 --json > runs/015-evidence/bench-c4-pool.json` exit 0 (pool digest equals single digest; `digest_logs` equals T003's `main` value since results are identical); record in the log the before/after table: single-process gauntlets/s and ms/decision (`main` T002/T008 vs branch T024) with ratio; 16-worker wall and gauntlets/s (`main` T003 vs branch) with ratio; SC-002 verdict in one line
- [ ] T031 [US3] Commit 4a by path (`src/platsim/bench.py src/platsim/cli.py tests/unit/test_bench_cli.py tests/integration/test_bench.py specs/015-exact-ai-speedups/validation-log.md`), message `feat(015): platsim bench (pool timing with single-process digest control)`, push; record the hash

**Checkpoint**: every number FR-009 asks for is in the log, produced by the committed tool.

---

## Phase 6: Polish, docs, gates

- [ ] T032 [P] Docs: `specs/001-champion-team-optimizer/contracts/cli.md` bench row (text in `contracts/bench-tool.md`); `README.md` command table (around line 145) bench row, speed table (lines 404-407) new row/footnote with the branch's 16-worker figure and the single-process before/after, plus a one-line note that `sim_code_hash` changed in 015 so earlier checkpoints will not resume; `FUTURE-FEATURES.md` new section "6. expectimax2 speedups after 015" listing research R7 (second-level memo, cross-decision caches, constant hoisting, killed hypotheses, feature 016 `expectimax2-v4`)
- [ ] T033 [P] `RUN-STATE.md` START HERE: 015 state (commits, numbers, what is left: user testing, full suite, merge), the trap list (sim_code_hash, extract after switching, no commit during runs)
- [ ] T034 Gates (SC-004): `(cd sim && node --test test/*.test.mjs)` exit 0 → `runs/015-evidence/node-suite.log`; `uv run pytest -q -m "not battle_sim"` exit 0 → `runs/015-evidence/fast.log`; record summary lines and times in the log; commit 4b by path (`README.md FUTURE-FEATURES.md RUN-STATE.md specs/001-champion-team-optimizer/contracts/cli.md specs/015-exact-ai-speedups/validation-log.md`), message `docs(015): bench command, speed table, follow-ons, run state`, push
- [ ] T035 Merge gate (after the user's go, nothing else running, background): `uv run pytest -q > runs/015-evidence/full.log 2>&1` (about 2 h 10 min; give the start time); record the summary line, exit code and Eastern start/end in the log and RUN-STATE. Do not merge; report to the user

---

## Dependencies & Execution Order

- **Phase 1 (T001-T004)**: first; T002 and T003 both run on `main` and must run alone (sequential: T002 then T003); T004 last.
- **Phase 2 (T005-T011)**: after T004. T005 → T006 (bench reads `STATS.aiDraws`); T007 [P] with T006's tail; T008 after T006; T009 after T008 passes; T010 after T009; T011 last. T008's digest gate blocks everything after it.
- **US1 (T012-T019)** and **US2 (T020-T025)**: both after T011. They touch different files except `sim/ai/calcdamage.mjs` (US1 `portInput` lines 164-168; US2 `effectIn` line 137 and the export) and `sim/test/ai_cmds_damage.test.mjs` / `ai_adapter.test.mjs` (different test blocks). The plan's commit order is US1 then US2 so each gain is attributed; do them sequentially in that order. Tests T012-T014 before T015-T017; T020-T021 before T022-T023.
- **US3 (T026-T031)**: after T025 (the pool figure must be of the finished code). T026, T027 [P]; T028 → T029 → T030 → T031.
- **Phase 6**: T032, T033 [P] after T030 (they quote its numbers); T034 after T032-T033; T035 after T034 and the user's go.

### Parallel opportunities

- T007 (bench test) alongside the end of T006.
- T012, T013, T014 together (three test blocks, two files, independent assertions).
- T020, T021 together.
- T026, T027 together; T032, T033 together.
- Measurements (T003, T008, T018, T024, T030) are never parallel with anything: alone on the machine.

## Parallel Example: User Story 1 tests

```bash
# Three independent test additions, then one suite run shows them fail before T015:
Task: "T012 damageInput deep-equals fromShowdown; cache hit/stale/beginDecision in sim/test/ai_adapter.test.mjs"
Task: "T013 freeze-guard child process test in sim/test/ai_adapter.test.mjs"
Task: "T014 builds-per-decision independent of K in sim/test/ai_cmds_damage.test.mjs"
(cd sim && node --test test/ai_adapter.test.mjs test/ai_cmds_damage.test.mjs)   # expected: new tests fail (no damageInput yet)
```

## Implementation Strategy

- **MVP = Phase 1 + Phase 2 + US1** (commits 1 and 2): the proof harness plus the larger speedup (36% bound),
  attributed on its own. Stop and validate at T018.
- **Then US2** (commit 3): the second speedup, same gate. SC-002 is judged at T024.
- **Then US3 and docs** (commits 4a, 4b): the tool's pool half and the recorded before/after.
- **Merge** only after the user's hands-on testing and the full suite (T035), per the project rules.

## Notes

- 35 tasks across 3 stories; 11 of them are gates, measurements or commits rather than code. Within the plan's
  stated bound (22 to 26 code-ish tasks + records); still one branch, no split proposed.
- The four measurement runs (T003, T008, T018, T024, T030) are about 2 min each single-process plus about 1 min
  each on the pool; the full suite (T035) is the only long run.
- Draw counts are recorded per decision (user decision 2026-10-31, analyze I2): `policy_ai_draws[i]` per player
  choice, `live_ai_draws[j]` per opponent choice; FR-003 and SC-005 are checked as written.
- FR-006 scope (user decision 2026-10-31, spec Clarifications): the effect-table checks resolve no names per
  call and every other constant use is one memo read; hoisting the ~250 `K()` sites is a future plan. T032's
  FUTURE-FEATURES section lists it (research R7).
