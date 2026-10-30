# Research: Exact AI-Prediction Speedups

Read on 2026-10-30 on `015-exact-ai-speedups` = `main` c751fb2 + spec commits. Profile evidence:
`runs/015-evidence/scratchpad/prof/REPORT.md` (git-ignored copy of the session scratchpad).

## R1. Where the damage-input memo lives

**Decision**: a new adapter method `damageInput(attackerPoke, defenderPoke, moveNum, { power, type, powerMul })`
in `sim/ai/adapter.mjs`, returning the same shape as `fromShowdown` (`{ attacker, defender, move, field, crit:
false }`) but with `attacker`, `defender` and `field` taken from a per-decision cache: battler structs keyed by
Showdown Pokemon object (`battlerFromShowdown(p)`, exported today), field structs keyed by defender side
(`abilitiesOnField` from the active, non-fainted Pokemon; weather; pseudo-weather; the defender side's screens;
Mud/Water Sport). `move` is built per call (power/type vary). Consumers: `calcdamage.portInput`
(`sim/ai/calcdamage.mjs:164`, used by `calcDamage` and `applyTypeChart`) and the post-KO switch scorer
(`sim/ai/switch.mjs:499`). `fromShowdown` itself is unchanged.

**Why not inside `fromShowdown`**: the policy's own damage table mutates the structs it gets back
(`sim/policy/expectimax2.mjs:493-510`: `fix()` overwrites `stages`, `hp`, `status`, `item`, `types`, and the
`field` members). A shared cache there would be corrupted by the first policy call. `greedy.mjs:51` also uses
`fromShowdown`; it stays as is (not on the hot path).

**Exactness**: `battlerFromShowdown` and the field block of `fromShowdown` read only battle state (`hp`,
`status`, `boosts`, `item`, volatiles, `getTypes()`, `getAbility()`, `getItem()`, `storedStats`, weather, side
conditions). Within one decision nothing writes the battle: the adapter is read-only by contract (header of
`adapter.mjs`), the interpreter and command handlers read through it, and the only live-battle write in the AI
path (`injectFullRestore`, `opponent.mjs:197`) happens after `pickCommand` returns and touches `moveSlots`,
which no cached struct contains. The damage port does not write its inputs: a grep for member assignments on
`attacker/defender/field/f/input/bt/base` over `sim/damage.mjs:290-700` finds none, while the same grep over the
policy's `fix()` block finds 12 (positive control for the grep). The structs are therefore pure functions of the
decision's state, and the K samples on one state read identical values whether rebuilt or cached.

**Guard**: with `PLATSIM_AI_FREEZE=1` (read once at import) every cached struct is deep-frozen; ESM strict mode
turns any write into a `TypeError`. The Node suite is run once with it set in the quickstart (replay + golden
tests). A unit test writes to a cached struct on purpose and expects the throw (positive control).

**Alternatives considered**: (a) cache per `(attacker, defender, move)` the finished pre-variance damage —
larger gain but a second-level change the user deferred (spec Clarifications); (b) copy-on-read structs
(return clones) — defeats the purpose, the allocation is most of the cost; (c) patching `fromShowdown` to
accept a cache argument — spreads the cache through `damage.mjs`, which is the port of the game's formula and
should stay a pure function.

## R2. Constants resolved once

Profile: `Constants.get` (`sim/ai/constants.mjs:187`) is 14.6% self time; 10.7 points of it from
`effectIn` (`calcdamage.mjs:137`), which runs `table.names.some((n) => K(ai, n) === effect)` for two tables on
every move of every damage evaluation. `get(name, stack = [])` allocates an array per call and does two Map
operations (`has` then `get`).

**Decision**:
1. `Constants.get`: `const v = this.values.get(name); if (v !== undefined) return v;` before the slow path; the
   `stack` array is created only on the slow path. Exact: `values` holds numbers only (set at the end of `get`),
   so `undefined` means "not memoised yet". Every one of the ~250 `K()`/`C.get` sites in `sim/ai` gets this for
   free.
2. `effectSet(ai, table)`: a `WeakMap<Constants, Set<number>>` on each parsed table (`NO_DAMAGE_CALC_EFFECTS`,
   `ALT_POWER_EFFECTS` in `calcdamage.mjs`; `MOVES_AFFECTED_BY_GRAVITY`, `MOVES_AFFECTED_BY_HEAL_BLOCK` in
   `choose.mjs:155-156`), filled once with `table.names.map((n) => C.get(n))`. `effectIn` becomes
   `effectSet(ai, table).has(effect)`. Exact: `some(K(n) === x)` is membership of `x` in the resolved values.
   Test: for every effect value in the move table (and `0`), `effectSet.has(v) === names.some(...)`.

**FR-006 reading**: after this, the per-call work for a table check is one `Set.has`, independent of samples
and moves (the FR's count). Every other constant use is one memo hit per use, the same number of uses as today
but about three times cheaper. Hoisting those ~250 sites to pre-resolved fields (zero per-call lookups) is
mechanical but large and is deferred (R7). The replay test, not the count, is the exactness proof; the count
test covers the effect tables (`effectSet` resolution runs once per table per constants instance).

**Alternatives considered**: hoisting every `K()` into module-level constants — needs the `Constants` instance
at import time (it is created per decomp root, lazily); a per-adapter resolved object `ai.k` — would still be
~250 edits across the port's line-by-line C citations; deferred.

## R3. Decision boundaries (when the cache is dropped)

Adapters and their lifetimes, from the code:

| Adapter | Created | Lives | Boundary where `beginDecision()` is called |
|---|---|---|---|
| live `decomp-ai` (`st.ai`, `opponent.mjs:85`) | first `choose()` for the battle | whole battle | start of `decide()` (`opponent.mjs:207`), before `processLog` |
| policy mirror (`mirror.ai`, `expectimax2.mjs:301-314`, used as `X.rootView.ai`, `:1180`) | first decision of the battle per policy name | whole battle | `makeContext()` (`:1158`), right after `mirrorFor` |
| shadow views (`viewOf`, `:401-412`) | per state signature, per decision (`X.views`) | one decision | none needed (state immutable; the adapter is garbage with `X`) |

Both root-level adapters see the same live battle, which is static during the two `choose()` calls of a turn
(`gauntlet.mjs:135-137`: both choices are made before `makeChoices`). `processLog` reads the log only.

The replacement decision (`side.requestState === 'switch'`, `decide()` line 213) is a decision too and is
covered by the same call at the top of `decide()`.

## R4. The exactness proof chain and the fixture

**Fixture** (`sim/test/replay_prof_a.json`, schema in `contracts/bench-tool.md`): for `expectimax2-v2` and
`expectimax2-v1`, the 40 requests of the fixed set (`policy_benchmark_team.json` `.team` then
`reference_team.json` `.builds`, seeds `prof-a-<bench|ref>-<i>`, i < 20, all five trainers, `stop_on_loss:
false`, opponent `decomp-ai`), and per gauntlet: `cleared`, `final_levels`, battles `[trainer, end, turns,
log_hash]`, the p1 choice strings in order, the policy's AI draws (`STATS.aiDraws` delta) and the live AI's
draws per battle (`stateFor(battle).rng.draws` after the last opponent choice). Per policy: `digest_full` (the
harness digest: sha256 over `JSON.stringify(result)` of each gauntlet in order) and `digest_logs`
(cross-language digest, see R5).

**Chain**:
1. `main` c751fb2, independent harness: v2 `digest_full` = `db6d20cf59008d32640358a6a143eb94d5102b46ebcc0d116f39c2856fd504d3`
   (`runs/015-evidence/scratchpad/prof/plain_a.log`). v1's digest on `main` is recorded with the same harness
   before commit 1 (quickstart step 1; about 2 minutes).
2. Commit 1 (instrumentation only): `sim/bench.mjs --policy expectimax2-v2 --json` reports the same
   `digest_full`; v1 likewise. The fixture is recorded here with `--record`. The replay test passes trivially
   (same code), which proves the test harness itself (positive control: flip one choice in a copy of the fixture
   and the test fails).
3. Commits 2 and 3 (US1, US2): the replay test, the golden tests and the determinism test pass; the Node suite
   runs once more with `PLATSIM_AI_FREEZE=1`.

**Recording p1 choices and draws** without touching the policies: `runRecorded(gd, req)` in `sim/bench.mjs`
registers wrapped copies of the player and opponent policies (as `determinism.test.mjs` `instrument()` does),
records each p1 choice and, after each opponent choice, `stateFor(battle).rng.draws`; `STATS.aiDraws` is read
before and after. The wrappers do not change the choices (they call through), and the digest proves it.

**Test shape** (`replay.test.mjs`): like `determinism.test.mjs`, the file re-imports itself as a worker. W =
min(16, cpus) workers each run a slice of the 80 requests through `runRecorded` and return the per-gauntlet
records plus the result JSON string; the main thread orders them, computes both digests per policy and compares
with the fixture: digests equal, choices equal per gauntlet, draw counts equal. Expected wall: v2 about 104 s
CPU and v1 similar, so roughly 15 to 25 s on 16 threads.

## R5. The benchmark tool

**Decision**: two halves, one command each (contract in `contracts/bench-tool.md`).

- `sim/bench.mjs` (Node, in-process): builds the request set (`benchRequests({ block, n, teams, trainers })`),
  runs them with `runRecorded`, prints JSON: gauntlets, cleared, battles, turns, `wall_s`, `gauntlets_per_s`,
  `ms_per_decision`, `ai_calls_per_decision`, `ai_draws`, `digest_full`, `digest_logs`, `stats`
  (`STATS`), `sim_code_hash`. `--record FILE` writes the fixture. It is the only place the set is defined; the
  replay test imports `benchRequests` and `runRecorded` from it.
- `platsim bench` (Python): `--policy`, `--n`, `--block`, `--teams`, `--trainers`, `--workers` (default CPU
  count), `--no-single`, `--json`. Runs `node sim/bench.mjs --json` for the single-process figures, then builds
  the same requests (same seed pattern and fixtures; `op: "gauntlet"`) and times `WorkerPool(workers).map(...)`;
  reports wall, gauntlets/s, the pool's `sim_code_hash`, and `digest_logs` computed from the pool results.
  Positive control: the pool `digest_logs` must equal the single-process one, or the command exits 1.

**`digest_logs`** (reproducible in both languages, strings and integers only): sha256 over, per gauntlet in
request order, the line `seed|cleared(0/1)|final_levels joined by ','|battles joined by ';'` with each battle
`trainer:end:turns:log_hash`, newline-terminated. A different p1 decision changes the Showdown log and so the
battle's `log_hash` (both sides' moves are in the log), so this digest is as strict as the full-JSON digest
for "same decisions"; the full-JSON digest is kept because FR-001 names it.

**Why not the Python pool for everything**: `STATS` (decisions, AI calls, draws) lives inside the Node
process; the worker protocol does not expose it, and extending the protocol is out of scope.

## R6. Measurement protocol and baseline

Baseline on `main` c751fb2 (single process, machine otherwise idle, 2026-10-30 5:13 PM EDT):

| Policy | Wall | gauntlets/s | ms/decision | AI calls/decision |
|---|---|---|---|---|
| expectimax2-v2 | 103.75 s / 40 | 0.386 | 34.2 | 44.7 |
| greedy-v1 | 5.93 s / 40 | 6.75 | n/a | n/a |

Category split (exclusive, two seed blocks within 0.2 points): AI prediction 72.2%, of which input conversion
36.0% inclusive (`fromShowdown` + `battlerFromShowdown` + live `getTypes` → Showdown `runEvent` 13.7%) and
`Constants.get` 14.6% self. Upper bound for US1 + US2: about 50% of time removed, i.e. about 2x; the cached
paths still cost something, so SC-002 asks for 1.5x.

**Protocol** (quickstart steps 4 and 6): on the branch after commit 2 and again after commit 3,
`node sim/bench.mjs --policy expectimax2-v2 --json` alone on the machine (the per-change attribution), then
`uv run platsim bench --policy expectimax2-v2 --workers 16` for the pool figure. The `main` 16-worker figure
comes from a ten-line scratchpad script on the `main` checkout that submits the same 40 requests to
`WorkerPool(16)` and times them (the tool does not exist on `main`). All numbers, with the commit hashes and
times, go in `validation-log.md`.

## R7. Out of scope here (recorded for FUTURE-FEATURES)

- Second-level memo: pre-variance damage per `(view, attacker, defender, move, power, type)`; `speedValuesNow`
  per view (2.4%); `party()` snapshots (1.9%).
- Caches that persist across decisions: `damageTable` (7.3% inclusive, 77% hit rate within a decision),
  `matchupScore` (3.9%).
- Hoisting the remaining `K()` sites to pre-resolved fields (R2).
- Hypotheses the profile killed: cloning / copy-on-write (0.7%), better prediction-cache keys (0.35% hit rate;
  coarse-key bound 11.6% of ply-2 calls), the end-state merge (collapses 0.5% of branches).
- Feature 016 (`expectimax2-v4`): K_PLY2 1, branch probability floor, switch beam 1; paired B1-B5 vs v2.
