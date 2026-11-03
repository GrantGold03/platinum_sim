# Tasks: expectimax2-v4, a Cheaper Battle Player, Reference-First

**Input**: Design documents from `specs/018-expectimax2-v4/` (spec.md, plan.md, research.md, data-model.md,
contracts/policy-api.md, contracts/python-and-cli.md, quickstart.md).

**Tests**: Required by the spec (FR-002 to FR-010, SC-001 to SC-007) and Constitution V. The proof harness (replay
fixture for v1/v2) exists from 015 and is used unchanged for v1/v2; v4 gets its own entry. Each story's new tests are
written first and shown to fail on the missing exports; every commit is gated on the replay test for v1/v2.

**Organization**: by user story, in the plan's commit order: US1 policy (commit 1), US3's code half (the Python
plumbing the B2 run needs, commit 2), US2 the ladder (commit 3), US1's final parameters and fixture entry (commit 4),
US3's runs and US4's gated switch with docs (commit 5). Phase labels name the story each task serves.

## Conventions

- Temp files and scripts go in the session scratchpad; evidence (pairs cache, optimizer outputs, bench JSON, suite
  logs) in `runs/018-evidence/` (git-ignored). Never `/tmp`.
- Never `git commit -a`; stage paths by name. The user's own files (`.claude/scheduled_tasks.lock` deletion,
  `.claude/skills/speckit-assess-*`, `.specify/assessments/`, `.specify/extensions*`, `held_items.md`) stay out.
- `data/generated/` needs no rebuild for this feature (no extractor change).
- Never commit, switch branches or run a suite while a measurement or a ladder run is going. Measurements and ladder
  runs run with nothing else on the machine (`pgrep -a -x node; pgrep -a pytest` first; never `pgrep -f` with the
  script name from a shell whose command line contains it). Long runs go in the background with their start time
  logged; the session must not start anything else until they finish.
- Record every result (command, exit code, summary lines, Eastern times, commit hash) in
  `specs/018-expectimax2-v4/validation-log.md` as it lands. Never pipe a command whose exit code matters.
- Node tests: `(cd sim && node --test test/*.test.mjs)` (347 today, about 2 min). Fast mode: `uv run pytest -q -m "not
  battle_sim"` (528 passed, 4 xfailed today). Full suite (merge gate, about 1 h): `uv run pytest -q --durations=25`,
  background, nothing else running.
- The replay fixture entries for v1 and v2 are never re-recorded (FR-002): a replay failure for them means a behaviour
  change; stop and fix the code. The v4 entry is recorded once, at commit 4, with the final `V4_OPTS`, and re-recorded
  only if `V4_OPTS` changes again in this feature (say so in the log).
- Policy names: `expectimax2-v4` only; never `expectimax2-v3` (archived 007 name). Candidate names carry their knobs
  (`expectimax2-v4?kRoot=..&kPly2=..&beam=..&floor=..`, data-model.md).
- "Not worse" = McNemar exact at alpha 0.05 with verdict not `B` (v2 better); "indistinguishable" passes. A candidate
  fails if any of the four teams gives `B`.
- `sim/` and `src/` edits change `sim_code_hash` / `platsim_code_hash`: optimizer checkpoints made before 018 will
  not resume (say so in RUN-STATE and the README note). `OptimizeRequest.player_policy` joins the checkpoint
  fingerprint.

## Phase 1: Setup

**Purpose**: the log, the evidence directory, and the presence of the four fixed teams.

- [X] T001 Create `specs/018-expectimax2-v4/validation-log.md` (header: times Eastern, evidence dir `runs/018-evidence/`,
  sections per task; record branch `018-expectimax2-v4`, base `main` 7a88ae6, `git diff --stat main HEAD -- sim src tests`
  expected empty apart from the Spec Kit 1.2.6 upgrade commit `875080a` (which touched no `sim/`, `src/` or `tests/`
  file), exit 0); `mkdir -p runs/018-evidence/pairs`
- [X] T002 [P] Verify the four fixed teams exist and load: `tests/fixtures/policy_benchmark_team.json` (`.team`, 6 members,
  Lv 57), `tests/fixtures/reference_team.json` (`.builds`, Lv 60), `runs/014-evidence/b2-main/result.json` and
  `runs/014-evidence/b2-branch/result.json` (`.team.builds`, 6 members with `start_level` and `held_item`); record
  the member species, levels and items of all four in the log. If a 014 result is missing, regenerate ONE B2 team on
  today's code (`uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2
  --out runs/018-evidence/b2-regen`), run the ladder on three teams (both 014 sides would regenerate to the same team
  now that their code is on `main`), and record the change in the log and the spec's assumption

**Checkpoint**: log started; the four teams are known.

---

## Phase 2: Foundational (the replay gate on unchanged code)

- [X] T003 On the branch: `(cd sim && node --test test/replay.test.mjs)` exit 0 (3 tests, about 25-45 s); record the
  diagnostic line. If it fails here, nothing else may start

**Checkpoint**: the v1/v2 reference is known-good on this base.

---

## Phase 3: User Story 1 - A new, cheaper player that can be chosen by name (Priority: P1) 🎯 MVP

**Goal**: the four knobs as version options, `expectimax2-v4` with the provisional `V4_OPTS`, candidate names in the
gauntlet's lookup, `STATS.floored`; v1/v2 byte-identical (FR-001, FR-002, FR-003, FR-009 for the provisional set;
research R1, R2; contract `policy-api.md`).

**Independent Test**: the replay test matches the unchanged v1/v2 entries; v4 is deterministic per seed; a candidate
with `V4_OPTS`'s values gives the same digest as `expectimax2-v4`; invalid candidate names are request errors; the
floor counter is 0 for v2 and positive for v4 on a position.

### Tests for User Story 1 (write first; fail on the missing exports before T007)

- [X] T004 [P] [US1] Add to `sim/test/expectimax2.test.mjs` ("018 version options and v4"): import `V4_OPTS`,
  `EXPECTIMAX2_V4`, `expectimax2v4`, `STATS`; assert `V1_OPTS` and `V2_OPTS` deep-equal their recorded values (no knob
  keys), `V4_OPTS` deep-equals `{ koStop: true, wAlive: 0.25, wFR: 0.1, kRoot: 4, kPly2: 1, beam: 1, floor: 0.02 }` (the
  provisional set; this assertion is updated in T026 to the final set) and is frozen; `expectimax2v4.name ===
  'expectimax2-v4'`; on `spiritombPosition()`, `scoreActions(ctx, V4_OPTS, 'expectimax2-v4')` returns finite scores and
  `STATS.floored` grows by > 0, while `scoreActions(ctx, V2_OPTS, 'expectimax2-v2')` leaves `STATS.floored` unchanged;
  on the same position the v4 root prediction (`opp`) has at most `V4_OPTS.kRoot` distinct actions and the number of
  searched switches (scores not `-Infinity` among `switch` acts) is at most `V4_OPTS.beam`
- [X] T005 [P] [US1] Add to `sim/test/gauntlet.test.mjs` ("018 candidate policy names"): import `playerPolicyFor`,
  `RequestError`, `runGauntlet`; `playerPolicyFor('expectimax2-v2')` is the registered object; `playerPolicyFor(
  'expectimax2-v4?kRoot=4&kPly2=1&beam=1&floor=0.02')` returns an object whose `name` is the full string and the same
  object on a second call (cached); each of `'expectimax2-v4?'`, `'expectimax2-v4?bogus=1'`, `'expectimax2-v4?kRoot=0'`,
  `'expectimax2-v4?kRoot=33'`, `'expectimax2-v4?beam=6'`, `'expectimax2-v4?floor=0.6'`, `'expectimax2-v4?floor=-0.1'`,
  `'expectimax2-v4?kPly2=1&kPly2=2'`, `'expectimax2-v4?kPly2=x'` throws `RequestError` with `kind === 'invalid_policy'`;
  `playerPolicyFor('nope')` throws the existing unknown-policy error; a `runGauntlet` request with an invalid candidate
  name fails as a request error (the worker contract: `ok: false`) rather than crashing. Equality: two gauntlets (bench
  team, seeds `prof-a-bench-0/1`, Aaron only) with `player_policy: 'expectimax2-v4'` and with the candidate name
  spelling out `V4_OPTS`'s values give byte-identical `JSON.stringify` results apart from the `player_policy` field
  (compare after deleting it), proving the shared seeding; a candidate with a different knob (`kPly2=2`) differs
  (positive control)
- [X] T006 [P] [US1] In `sim/test/determinism.test.mjs` add `'expectimax2-v4'` to `POLICIES` (same seed → identical
  logs, other seed differs; the battle PRNG and the live AI RNG untouched, as the file checks for v1/v2)

### Implementation for User Story 1

- [X] T007 [US1] In `sim/policy/expectimax2.mjs`: `export const EXPECTIMAX2_V4 = 'expectimax2-v4'`; `export const V4_OPTS =
  Object.freeze({ ...V2_OPTS, kRoot: 4, kPly2: 1, beam: 1, floor: 0.02 })` (provisional; a comment says commit 4 sets the
  ladder's result); `STATS.floored = 0`; in `valuePly2` use `X.opts.kPly2 ?? PARAMS.K_PLY2`; in `scoreActions` use
  `X.opts.beam ?? PARAMS.SWITCH_BEAM` for the slice and `X.opts.kRoot ?? PARAMS.K_ROOT` for the root prediction; in
  `qValue`: `const floor = X.opts.floor ?? 0;` and per branch `const w = p * br.p; const ko = X.opts.koStop &&
  activeFainted(br.S); if (!ko && w < floor) { STATS.floored++; q += w * leafValue(X, br.S); continue; } q += w * (ko ?
  leafValue(X, br.S) : valuePly2(X, br.S));` (contracts/policy-api.md "floor"); `makeExpectimax2(name, opts)`: the seed
  name is `opts.seedName ?? name`, passed to `mirrorFor` and used for `seedBase` (so `X.seedBase` and the mirror key
  come from the seed name); `export const expectimax2v4 = makeExpectimax2(EXPECTIMAX2_V4, V4_OPTS)`; header: a VERSIONS
  entry for v4 (knobs, provisional, "measured in specs/018 validation log") and a short "BUDGET" paragraph defining the
  four knobs and the floor semantics (weight kept, leaf-valued, never dropped)
- [X] T008 [US1] In `sim/gauntlet.mjs`: `registerPlayerPolicy(expectimax2v4)` after v2 (import it); `export function
  playerPolicyFor(name)`: registered → return; `/^expectimax2-v4\?(.*)$/` → parse `key=value&…` (keys `kRoot`, `kPly2`
  integers 1..32, `beam` integer 1..5, `floor` decimal in [0, 0.5], each key at most once, no empty query, no other
  key), on success `makeExpectimax2(name, { ...V4_OPTS, ...parsed, seedName: EXPECTIMAX2_V4 })` cached in
  `PLAYER_POLICIES` under the full name, on failure `throw new RequestError('invalid_policy', \`invalid expectimax2-v4
  candidate ${name}: ${reason}\`)`; else the existing unknown-policy `RequestError`; `runGauntlet` uses
  `playerPolicyFor(req.player_policy ?? PLACEHOLDER)`; header comment: candidate names (research R2), the worker's hello
  still lists base names only
- [X] T009 [US1] Gate (quickstart step 1): `(cd sim && node --test test/expectimax2.test.mjs test/gauntlet.test.mjs
  test/determinism.test.mjs test/replay.test.mjs test/ai_golden.test.mjs)` exit 0 (replay still 2 policies, v1/v2
  digests unchanged); full Node suite exit 0 → `runs/018-evidence/node-suite-c1.log`; record
- [X] T010 [US1] Commit 1 by path (`sim/policy/expectimax2.mjs sim/gauntlet.mjs sim/test/expectimax2.test.mjs
  sim/test/gauntlet.test.mjs sim/test/determinism.test.mjs specs/018-expectimax2-v4/validation-log.md`), message
  `feat(018): expectimax2-v4 with per-version search budget and candidate names (v1/v2 byte-identical)`, push; record the hash

**Checkpoint**: v4 exists by name with provisional knobs; candidates resolve; v1/v2 proven unchanged.

---

## Phase 4: User Story 3 (code half) - The optimizer can be told which strong player to use (Priority: P2)

**Goal**: one Python default and `optimize --player-policy`, so the B2 run with v4 can happen before any default
changes (FR-007 prerequisite, FR-008 mechanism; research R4; contract `python-and-cli.md`). No default change here.

**Independent Test**: unit tests show every default equals `DEFAULT_PLAYER_POLICY` and that `optimize --player-policy
x` reaches the request; fast mode passes; an `optimize --player-policy expectimax2-v4 --budget quick` dry start fails
only if the name is unknown to the worker (it is known after commit 1).

### Tests for User Story 3, code half (write first; fail before T013)

- [X] T011 [P] [US3] Create `tests/unit/test_default_policy.py`: `platsim.evaluate.DEFAULT_PLAYER_POLICY == platsim.bench.DEFAULT_POLICY`; the argparse
  defaults of `evaluate --player-policy`, `bench --policy` and `optimize --player-policy` (parse `["evaluate", "x.json"]`,
  `["bench"]`, `["optimize"] + six species`) all equal the constant and the help text mentions it;
  `OptimizeRequest(species=...).player_policy == DEFAULT_PLAYER_POLICY`; `optimize ... --player-policy expectimax2-v4`
  parses into `OptimizeRequest.player_policy == 'expectimax2-v4'` (use the CLI's request-building function; if it is
  inline in `cli.py`, factor it into `platsim.cli.optimize_request(args)` in T013 and test that)
- [X] T012 [P] [US3] Add to `tests/unit/test_optimizer_resume.py`: a checkpoint written with `player_policy='expectimax2-v2'`
  is not resumed by a request with `player_policy='expectimax2-v4'` (fingerprint mismatch → fresh run or the documented
  error, whichever the resume code does for other fingerprint fields; assert that behaviour), and `state.json` records
  `player_policy`

### Implementation for User Story 3, code half

- [X] T013 [US3] `src/platsim/optimizer/api.py`: `player_policy: str = DEFAULT_PLAYER_POLICY` on `OptimizeRequest`
  (import from `platsim.evaluate`; part of the fingerprint and of `state.json`); `src/platsim/optimizer/run.py`: replace
  every `POLICY` use with `req.player_policy` (level search construction, setup check, confirmation `evaluate_team`
  calls, the result/provenance at line ~706, the "[confirm] winner … (<policy>, >= N runs)" log line); `src/platsim/
  optimizer/levels.py`: `LevelSearch(..., policy: str = DEFAULT_PLAYER_POLICY)` used in its requests and checks, `POLICY`
  kept as an alias of the default for `__all__` compatibility or removed with its references; `src/platsim/cli.py`:
  `evaluate --player-policy` and `bench --policy` default to `DEFAULT_PLAYER_POLICY` (help text f-string), `optimize`
  gains `--player-policy` (default the constant, help "strong player for level search, setup check and confirmation;
  the screening stages keep greedy-v1") passed into `OptimizeRequest`; `src/platsim/bench.py`: `DEFAULT_POLICY =
  DEFAULT_PLAYER_POLICY`; the web runner untouched (default)
- [X] T014 [US3] Gate: `uv run pytest -q tests/unit/test_default_policy.py tests/unit/test_optimizer_resume.py` exit 0; `uv run pytest -q -m "not battle_sim"` exit 0 → `runs/018-evidence/fast-c2.log`; smoke: `uv run
  platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 018-smoke --player-policy
  expectimax2-v4 --workers 4 --out runs/018-evidence/smoke-v4` started and stopped (Ctrl-C / timeout 60 s) after the
  first log lines show the policy name, or the full quick run if it is under 15 min; record
- [X] T015 [US3] Commit 2 by path (`src/platsim/optimizer/api.py src/platsim/optimizer/run.py src/platsim/optimizer/levels.py
  src/platsim/cli.py src/platsim/bench.py tests/unit/test_default_policy.py tests/unit/test_optimizer_resume.py
  specs/018-expectimax2-v4/validation-log.md`), message
  `feat(018): one default player constant; optimize --player-policy (default unchanged)`, push; record the hash

**Checkpoint**: the optimizer can run with any registered player; the default is still v2.

---

## Phase 5: User Story 2 - v4 is proven not worse than v2 before it is trusted (Priority: P1)

**Goal**: the paired-comparison script, the pairing control, the v2 sides, every single knob and the combinations
until one passes, all recorded (FR-004, FR-005; research R3; contract `python-and-cli.md`; clarification 1: full
protocol for every candidate).

**Independent Test**: the log's ladder table with one row per candidate x team (rates, discordant counts, p-values,
verdicts, speeds), the control row with 0 discordant pairs, and a named final candidate (or a recorded negative result).

### Script (write first; its own unit test covers the pure parts)

- [X] T016 [P] [US2] Create `specs/018-expectimax2-v4/scripts/paired_policies.py` per contracts/python-and-cli.md:
  argparse (`--a`, `--b`, `--teams` default `bench,ref,b2main,b2branch`, `--runs` default 2000, `--workers`, `--out`
  default `runs/018-evidence/pairs`, `--self`); team loaders (`bench`: fixture `.team`; `ref`: `.builds` via
  `load_and_validate` + `worker_team`; `b2main` / `b2branch`: `runs/014-evidence/b2-{main,branch}/result.json` `.team`
  written to `<out>/teams/<team>.json` (beside the pairs cache; never /tmp) then `load_and_validate` + `worker_team`); seeds `derive_seed(f"018-pairs|{team}", i, 0)`;
  requests as in `run_full_gauntlets` (`stop_on_loss: True`, `log: "none"`); one `WorkerPool(workers)`; result checks
  (`ok`, policies echoed, first-battle seeds equal across sides); cache files `<out>/<team>__<safe policy>__<runs>.json`
  with `cleared`, `battles_seed_0`, `wall_s`, `gauntlets_per_s`, `sim_code_hash`, `hello` (reuse only when
  `sim_code_hash` matches the pool's hello; otherwise recompute and print why); `mcnemar_exact(a, b)`, `wilson_ci`;
  per-team text block and a row appended to `<out>/summary.json`; `--self` plays `--a` twice (two independent pool
  passes) on the first team and exits 1 unless 0 discordant; exit 1 on any failed request. Pure helpers
  (`safe_name`, row building, cache validity) in functions a unit test can import
- [X] T017 [P] [US2] Add `tests/unit/test_scripts.py` cases (the file already tests the 014 scripts' pure parts, follow
  its pattern): `safe_name('expectimax2-v4?kRoot=4&kPly2=1&beam=1&floor=0.02')` is filesystem-safe and reversible
  enough to be unique; a cache entry with a different `sim_code_hash` is rejected; the summary row for a hand-built
  pair of outcome lists has the expected `a_only`, `b_only`, verdict (use `mcnemar_exact` directly as the oracle)

### Runs (background, alone; each logged with start and end times and the command)

- [X] T018 [US2] Pairing control: `uv run python specs/018-expectimax2-v4/scripts/paired_policies.py --a expectimax2-v2
  --b expectimax2-v2 --self --teams bench --runs 200 --workers 16` → exit 0, 0 discordant; record
  (`runs/018-evidence/pairs/control.txt`)
- [X] T019 [US2] Single knob 1 and the v2 sides: `--a 'expectimax2-v4?kRoot=8&kPly2=1&beam=2&floor=0' --b expectimax2-v2
  --runs 2000 --workers 16` on all four teams (about 40 min: v2 is computed and cached here); four rows in the log
- [X] T020 [US2] Single knobs 2 to 5, one command each (about 20 min each, v2 cached): `--a 'expectimax2-v4?kRoot=8&kPly2=2&beam=1&floor=0'`,
  `--a 'expectimax2-v4?kRoot=4&kPly2=2&beam=2&floor=0'`, `--a 'expectimax2-v4?kRoot=8&kPly2=2&beam=2&floor=0.02'`,
  `--a 'expectimax2-v4?kRoot=8&kPly2=2&beam=2&floor=0.05'`; four rows each; mark each knob pass / fail (fail = any team
  verdict `B`)
- [X] T021 [US2] Combinations, fastest first, until one passes on all four teams: first all passing knobs together
  (with the larger passing floor); then that set minus one knob each in descending sizing speed; then pairs; each a
  single `paired_policies.py` run on the four teams (about 20 min); record every row; name the final candidate and its
  knobs in the log, or the negative result if nothing passes (then T026 keeps `V4_OPTS` provisional and marks v4 "not
  validated", and T034 ships no default change)
- [X] T022 [US2] Ladder table in the validation log: candidate x team with a_rate, b_rate, a_only, b_only, p, verdict,
  a and b gauntlets/s, plus the control row; the chosen set stated in one line with its per-team verdicts (SC-002,
  SC-003)
- [X] T023 [US2] Commit 3 by path (`specs/018-expectimax2-v4/scripts/paired_policies.py tests/unit/test_scripts.py
  specs/018-expectimax2-v4/validation-log.md`), message `test(018): paired policy comparison script; ladder recorded`,
  push; record the hash

**Checkpoint**: v4's final knobs are decided by evidence (or the negative result is on record).

---

## Phase 6: User Story 1 (final) - final parameters, fixture entry, strength tests (Priority: P1)

**Goal**: `V4_OPTS` = the passing set; the v4 replay entry; the policy-strength tests cover v4; the speed measured
(FR-006, FR-009, FR-010, SC-004; research R6, R7).

**Independent Test**: the replay test checks three policies and passes; bench digests for v4 agree single vs pool; the
strength test's new pairs pass at the in-suite size.

- [X] T024 [US1] In `sim/policy/expectimax2.mjs`: set `V4_OPTS` to the final knobs from T021 (or keep provisional and
  add "NOT VALIDATED" to the VERSIONS entry if the ladder failed); update the header's VERSIONS entry with the ladder's
  numbers (per-team rates and verdicts for the chosen set); in `sim/test/expectimax2.test.mjs` update the `V4_OPTS`
  assertion of T004 to the final values
- [X] T025 [US1] Alone: `node sim/bench.mjs --policy expectimax2-v4 --record sim/test/replay_prof_a.json` (adds the v4
  entry; v1/v2 entries untouched: load the fixture before and after and assert `policies['expectimax2-v1']` and
  `policies['expectimax2-v2']` deep-equal their `main` versions (the file itself changes: the recorder rewrites the
  file-level `recorded` and `set` blocks, `sim/bench.mjs:209-211`, which is expected and noted in the log)); in
  `sim/test/replay.test.mjs` expect `['expectimax2-v1', 'expectimax2-v2', 'expectimax2-v4']`; `(cd sim && node
  --test test/replay.test.mjs)` exit 0 (now 3 x 40 gauntlets); record the v4 digests
- [X] T026 [US1] In `tests/integration/test_policy_strength.py`: `POLICIES` gains `'expectimax2-v4'`; `pairs` gains
  `('expectimax2-v4', 'greedy-v1')` (asserted verdict `A`, p < 0.05 like the v1/v2 pairs) and `('expectimax2-v4',
  'expectimax2-v2')` (asserted verdict is not `B`); keep `PLATSIM_STRENGTH_N`; the reversal-team test also runs v4 (not
  worse than greedy, verdict not `B`); run both with `PLATSIM_STRENGTH_N=400 PLATSIM_REVERSAL_N=200 uv run pytest -q
  tests/integration/test_policy_strength.py` as the in-suite smoke (about 6 min) and record; the full-size run happens
  in the merge-gate suite (T036)
- [X] T027 [US1] Alone (FR-006, SC-004): `node sim/bench.mjs --policy expectimax2-v2 --json > runs/018-evidence/bench_v2.json`,
  `--policy expectimax2-v4 --json > runs/018-evidence/bench_v4.json`, `uv run platsim bench --policy expectimax2-v4
  --workers 16 --json > runs/018-evidence/pool_v4.json`, `--policy expectimax2-v2 … pool_v2.json`: v4 > v2 single and pool,
  `digests_agree` true, v4 single digest equals the fixture entry's; table in the log with the ratio against the 1.5x
  target, ms/decision, AI calls/decision, interpreter steps
- [X] T028 [US1] Gate: full Node suite exit 0 → `runs/018-evidence/node-suite-c4.log`; commit 4 by path
  (`sim/policy/expectimax2.mjs sim/test/expectimax2.test.mjs sim/test/replay.test.mjs sim/test/replay_prof_a.json
  tests/integration/test_policy_strength.py specs/018-expectimax2-v4/validation-log.md`), message `feat(018): expectimax2-v4
  final search budget; replay fixture entry; strength tests cover v4`, push; record the hash

**Checkpoint**: v4 is final, pinned by its fixture entry, and measured.

---

## Phase 7: User Story 3 (runs) - The optimizer end to end with v4 (Priority: P2)

**Goal**: B2 optimized with v2 and v4, compared at equal levels, wall times reported (FR-007, SC-005; research R5).

**Independent Test**: two result directories with `result.json`, the equal-levels verdict and mean final levels, the
validator's pass on the v4 result, both wall times.

- [X] T029 [US3] Create `specs/018-expectimax2-v4/scripts/equal_levels.py` from `specs/014-damage-boost-items/scripts/equal_levels.py`:
  usage `equal_levels.py <v2_out_dir> <v4_out_dir> <runs> [--self]`, A = the v4 result team, B = the v2 result team, both
  at A's start levels, validated, played by `expectimax2-v2` (the reference player) on master `018-equal|B2`,
  `mcnemar_exact(A, B)`, mean final levels; `--self` plays B against itself (control)
- [X] T030 [US3] Background, alone: `uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget
  quick --seed 014-b2 --player-policy expectimax2-v2 --out runs/018-evidence/b2-v2 > runs/018-evidence/b2-v2.log 2>&1`
  (about 15 min; `/usr/bin/time -v` or start/end times for the wall); record exit and wall; consistency check: the
  result team equals `runs/014-evidence/b2-branch/result.json`'s team (015-017 were exact) apart from provenance;
  if it differs, say so and investigate before going on
- [X] T031 [US3] Background, alone: the same with `--player-policy expectimax2-v4 --out runs/018-evidence/b2-v4`;
  record exit and wall; write `result.json`'s `team` object to `runs/018-evidence/b2-v4/team.json` (the optimizer
  writes `team.txt`, `result.json`, `state.json`, `result.csv`, `result.xlsx` and no team JSON; the equal-levels
  script's `at_levels` helper does the same write per side) and `uv run platsim validate runs/018-evidence/b2-v4/team.json`
  exit 0; wall ratio in the log (SC-005)
- [X] T032 [US3] Background, alone: `uv run python specs/018-expectimax2-v4/scripts/equal_levels.py runs/018-evidence/b2-v2
  runs/018-evidence/b2-v4 200 --self` (control, 0 discordant) then `… 2000` (about 15 min): verdict not `B`, mean final
  level of A not higher; record (`runs/018-evidence/equal-levels.txt`)

**Checkpoint**: the end-to-end gate has a verdict.

---

## Phase 8: User Story 4 - v4 becomes the default player only after it passes (Priority: P2)

**Goal**: the gated switch and the docs (FR-008, FR-012, FR-013, SC-006, SC-007; research R6).

**Independent Test**: with the switch, `evaluate`, `optimize`, `bench` and the web report `expectimax2-v4` by default
and v2 on request; without it, the docs record the negative result.

- [X] T033 [US4] Decide the gate from the log: FR-005 (T021 passing set) AND FR-007 (T032 verdict not `B`, mean final
  level not higher) AND v4 faster than v2 (T027). Write the one-line verdict in the log
- [X] T034 [US4] If the gate passed: `src/platsim/evaluate.py` `DEFAULT_PLAYER_POLICY = "expectimax2-v4"`; `uv run platsim
  evaluate tests/fixtures/reference_team.json --runs 50 --out runs/018-evidence/eval-default` shows `player
  expectimax2-v4` in its summary and report; `uv run platsim bench --no-single --workers 16 --n 2` reports v4; `uv run
  platsim evaluate … --player-policy expectimax2-v2 --runs 50` shows v2 (by name); unit tests from T011 still pass (they
  compare against the constant). If the gate failed: no code change; record
- [X] T035 [P] [US4] Docs: `README.md` (the default-player sentence at line 23 and the command table rows for
  `evaluate`, `optimize --player-policy`, `bench`; the speed table gains the v2-vs-v4 row with the 1.5x target; the
  "Node suite" count; the `sim_code_hash` note; if not adopted, a paragraph with the negative result);
  `FUTURE-FEATURES.md` section 7 (018 done or not adopted with the ladder's numbers; 019+ = D, F, E, H);
  `RUN-STATE.md` START HERE (state, commits, numbers, what is left: user testing, full suite, merge)
- [X] T036 Gates (SC-007, FR-011): `git diff --stat main HEAD -- pokemon-showdown` empty, exit 0; full Node suite exit 0
  → `runs/018-evidence/node-suite.log`; `uv run pytest -q -m "not battle_sim"` exit 0 → `runs/018-evidence/fast.log`;
  record; commit 5 by path (`src/platsim/evaluate.py README.md FUTURE-FEATURES.md RUN-STATE.md
  specs/018-expectimax2-v4/scripts/equal_levels.py specs/018-expectimax2-v4/validation-log.md` plus any doc touched),
  message `feat(018): expectimax2-v4 is the default player (gate passed)` or `docs(018): v4 not adopted; results
  recorded`, push
- [ ] T037 Merge gate (after the user's hands-on testing and go, nothing else running, background): `uv run pytest -q
  --durations=25 > runs/018-evidence/full.log 2>&1` (about 1 h; the strength test now runs v4 at full size); record the
  summary line, exit code and Eastern start/end in the log and RUN-STATE. Do not merge; report to the user

---

## Dependencies & Execution Order

- **Phase 1 (T001-T002)**: first; T002 [P] with T001.
- **Phase 2 (T003)**: after T002; blocks everything after it.
- **US1 code (T004-T010)**: after T003. T004, T005, T006 [P] before T007-T008 (they fail on the missing exports);
  T007 before T008 (the gauntlet imports `V4_OPTS` / `expectimax2v4`); T009 after T008; T010 last.
- **US3 code (T011-T015)**: after T010 (the smoke run needs v4 registered). T011, T012 [P] before T013; T014 after T013;
  T015 last.
- **US2 (T016-T023)**: after T015 (the script runs candidates through the same pool and `derive_seed`; no code dependency
  on commit 2, but the commit order keeps the ladder's `sim_code_hash` fixed from here on). T016, T017 [P]; T018 after
  T016; T019 after T018; T020 after T019 (the v2 cache); T021 after T020; T022 after T021; T023 last.
  **Do not change `sim/` between T019 and T021**: the pairs cache is keyed by `sim_code_hash`.
- **US1 final (T024-T028)**: after T023. T024 before T025 (the fixture records the final knobs); T026 after T025 (policy
  list); T027 after T025; T028 last.
- **US3 runs (T029-T032)**: after T028 (v4 final). T029 before T032; T030 before T031 (sequential, alone); T032 after
  T031.
- **US4 (T033-T037)**: T033 after T032; T034 after T033; T035 [P] with T034 (different files) but after T033; T036 after
  T034-T035; T037 after T036 and the user's go.

### Parallel opportunities

- T001, T002; T004, T005, T006; T011, T012; T016, T017; T034, T035.
- Measurements and ladder runs (T018-T021, T025, T027, T030-T032, T037) are never parallel with anything: alone on the
  machine, in the background, one at a time.

## Parallel Example: User Story 1 tests

```bash
# Three independent test additions, then one run shows them fail before T007:
Task: "T004 version options, V4_OPTS, floor counter, root/beam bounds in sim/test/expectimax2.test.mjs"
Task: "T005 candidate names: resolve, cache, invalid, equality with the plain name in sim/test/gauntlet.test.mjs"
Task: "T006 determinism for expectimax2-v4 in sim/test/determinism.test.mjs"
(cd sim && node --test test/expectimax2.test.mjs test/gauntlet.test.mjs test/determinism.test.mjs)   # expected: failures (no V4_OPTS / playerPolicyFor yet)
```

## Implementation Strategy

- **MVP = Phases 1-3** (commit 1): v4 exists by name with provisional knobs, candidates resolve, v1/v2 proven
  unchanged. Stop and validate at T009.
- **Then the plumbing** (commit 2), **then the ladder** (commit 3, the long part: about 3 to 4 hours of pool time),
  **then the final parameters and fixture** (commit 4), **then the B2 runs and the gated switch** (commit 5).
- **Merge** only after the user's hands-on testing and the full suite (T037).

## Notes

- 37 tasks across 4 stories; 15 of them are runs, gates, measurements or commits. Above the ~30 guideline because the
  ladder is itself a sequence of recorded runs; the code is small (commits 1, 2 and 4). If the user prefers a smaller
  branch, US3's runs and US4 (T029-T036) can follow as their own feature once v4 is final.
- The ladder order is the plan's: singles, then all passing knobs together, then that set minus one knob (descending
  sizing speed), then pairs; stop at the first pass. Record every row even after a pass.
- A candidate name is never typed into the committed source except in tests; the shipped policy is `expectimax2-v4`.
- The B2 v2 re-run doubles as a consistency check of 015-017 (same team as the 014 branch result expected); a
  difference is a finding to investigate, not something to paper over.
