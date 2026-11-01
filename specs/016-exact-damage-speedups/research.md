# Research: Exact Damage-Path Speedups (round two)

Read on 2026-11-01 on `016-exact-damage-speedups` = `main` 19519ed + spec commits. Profile evidence:
`runs/015-evidence/scratchpad/prof2/REPORT2.md` (git-ignored copy of the session scratchpad; hooked digest equals
the plain digest `db6d20cf…`, so the measurement changed nothing).

## R1. Type-chart plan and replay (`sim/damage.mjs`)

**Decision**: split `applyTypeChart` into `typeChartPlan(input, { ignoreTypeChecks, moveStatusMask })` and
`replayTypeChart(plan, damage)`. The plan holds, in order, the steps the game applies to the damage value and the
final status mask:

- `struggle: true` (early return, no steps, mask unchanged) for MOVE_STRUGGLE (battle_lib.c:2571-2573);
- `stab`: `x2` under Adaptability, else `*15/10` (:2590-2596), only when the attacker has the move's type and
  type checks are not ignored;
- zero or more `mul` steps with the chart multiplier (0, 5, 20 for immune / not very / super effective), one per
  matching chart row for each defender type, each applied as `battleDivide(damage * mul, 10)` **only if damage is
  nonzero** (ApplyTypeMultiplier, :7542-7581; the guard is kept per roll in the replay);
- after the walk: `div34` (Filter / Solid Rock on a super-effective hit, `battleDivide(damage*3, 4)`), `pct`
  (Expert Belt, `idiv(damage * (100 + param), 100)`), `x2` (Tinted Lens on a not-very-effective hit);
- `mask` (the final MOVE_STATUS bits), `totalMul`.

`replayTypeChart` applies the steps to one damage value with the same integer helpers in the same order and
returns `{ damage, moveStatusMask: plan.mask, totalMul: plan.totalMul }`. `applyTypeChart(input, damage, opts)`
keeps its signature and body-equivalence: `replayTypeChart(typeChartPlan(input, opts), damage)`. The current
per-roll body is kept verbatim as `applyTypeChartDirect` (exported): it is the reference the plan is tested
against (Principle VI) and the function the Showdown cross-check in `damage.test.mjs` validated.

**Why this is exact**: in the current body every branch condition reads the attacker, defender, move and field
(`prepare()` output, `attacker.types`, `defender.types`, volatiles, `defItem.holdEffect`, `attItem`, the
Wonder Guard / Filter / Expert Belt / Tinted Lens conditions on `st.mask` and `movePower`) and never the damage
value, with one exception: `applyTypeMultiplier` multiplies only `if (damage)`. The mask updates depend on the
running mask, which depends only on the steps taken so far. So for a fixed input the sequence of operations on
`damage` is fixed, and replaying that sequence per roll is the same computation. The incoming `moveStatusMask`
option seeds the running mask, so it is part of the plan's inputs (every caller today passes 0; the equivalence
test also tries nonzero seeds).

**`calcDamage`**: builds `prepare()` once and the plan once (normal and critical tables are separate
`calcDamage` calls with the same plan inputs; the plan does not depend on `critMul`), then replays for the 16
rolls: 32 chart walks + 36 `prepare()` per damage-table entry become 2 + 6. `calcBaseDamage`,
`applyScriptMultipliers`, `critMultiplier` and `critBlocked` keep their exported signatures; internally they
accept a precomputed `prepare()` result through private helpers.

**Counters**: `DAMAGE_STATS = { plans, replays, direct }` exported from `damage.mjs`, like the policy's `STATS`:
`plans` counts plan builds, `replays` the per-roll replays, `direct` the reference calls. The test for US1
scenario 4 reads them around one `calcDamage` call.

**Alternatives rejected**: a `(damage -> damage)` closure per plan (allocates per plan; the step array is
smaller and inspectable by the test); computing a single total multiplier (not exact: the game divides per step
with `battleDivide`, so `(d*15/10)*20/10` differs from `d*3` on odd values); a WeakMap memo keyed by the input
object inside `damage.mjs` (the policy mutates its inputs between calls, see 015 R1).

## R2. AI pre-variance memo and the control mode (`sim/ai/adapter.mjs`, `sim/ai/calcdamage.mjs`)

**Decision**: two memoised adapter methods in the decision cache that `beginDecision()` already clears:

- `ai.typeChartPlan(attackerPoke, defenderPoke, moveIdOrNum, { power, type, powerMul }, { ignoreTypeChecks })`
  returns `typeChartPlan(ai.damageInput(...), { ignoreTypeChecks, moveStatusMask: 0 })`, memoised per decision
  on `(attacker struct, defender struct, move num, power, type, ignoreTypeChecks)`.
- `ai.preVariance(attackerPoke, defenderPoke, moveIdOrNum, { power, type, powerMul }, fixedDamage)` returns
  `{ damage, moveStatusMask }` = TrainerAI_CalcDamage before the variance step (TAI:3081-3103): with
  `fixedDamage === 0`, `calcBaseDamage(input, critMul 1)` then the chart with type checks on; otherwise the chart on
  `fixedDamage` with type checks ignored. Memoised per decision on the same key plus `fixedDamage`.

The memo is a `Map` keyed by attacker struct, then defender struct (both are the cached, identity-stable structs
from 015), then a string `${num}|${power}|${type}|${ignore}|${fixed}`. Entries are frozen under
`PLATSIM_AI_FREEZE=1`. `cacheStats` gains `plans`, `planHits`, `preVariance`, `preVarianceHits`, `checks`.

**Call sites**: `calcdamage.calcDamage` lines 300-310 (`portInput` + `calcBaseDamage` + `dmgApplyTypeChart`)
become one `ai.preVariance(...)` call; the immune check and the variance step (`battleDivide(damage * variance,
100)`, TAI:3106-3109) stay in `calcdamage.mjs`, per sample. `calcdamage.applyTypeChart(env, { move, type,
attacker, defender, damage })` becomes `replayTypeChart(ai.typeChartPlan(att, def, move, { power: 0, type, powerMul:
10 }, { ignoreTypeChecks: false }), damage)`; its callers (`hasSuperEffectiveMove`, `IfMoveEffectivenessEquals`,
`onlyIneffectiveMoves`, `hasAbsorbAbilityInParty`, the post-KO scorer at `switch.mjs:501`) are unchanged.

**Why this is exact**: everything that varies per sample happens before the shared part or after it. Before: the
switch in `calcdamage.calcDamage` (TAI:2885-3078) derives `power`, `type` and `damage` (fixed damage) from the
sample's inputs (`heldItem`, `ivs`, `ability`, `embargoTurns`, the two RNG draws for Psywave and Magnitude); all of
that is in the memo key. After: the sample's `variance` (the per-slot roll drawn in TrainerAI_Init) is applied by
the caller. The shared part (`calcBaseDamage` + chart) reads the cached input structs, which do not change within a
decision (015 invariant), and draws no random numbers, so the draw count per decision is unchanged.

**Control mode**: `PLATSIM_AI_CHECK=1` read at import time in `adapter.mjs`. On every memo hit the adapter
recomputes the value from scratch and compares it (plan: steps, mask, totalMul; pre-variance: damage and mask);
a difference throws an `Error` naming the key and both values. `checks` counts the comparisons (positive control
that the mode ran). Default suite: a child-process test runs one Aaron battle per policy (`expectimax2-v2`,
`expectimax2-v1`) with `PLATSIM_AI_CHECK=1` and asserts exit 0 and `checks > 0` printed by the child; a second
child corrupts one memo entry on purpose and must exit non-zero with the control's message. Full set: `PLATSIM_AI_CHECK=1
node sim/bench.mjs --policy expectimax2-v2` and `-v1`, recorded in the validation log (digests must still match).

**Alternatives rejected**: memoising inside `calcdamage.mjs` (the memo must die with the decision, and the
adapter owns that boundary); keying by Showdown Pokemon objects instead of the cached structs (equivalent, but
the structs are what the computation reads, so a stale struct would be caught by the 015 freeze/lifecycle tests).

## R3. Shared identifier mappers (`sim/ai/adapter.mjs`)

**Decision**: `makeMappers(dex, T)` becomes a module-level lookup `mappersFor(dex, T)` in a `WeakMap` keyed by
`dex` whose value is `{ T, move: Map, ability: Map, item: Map, species: Map, type: Map, api }`; a different `T`
(another decomp root) for the same dex replaces the entry. `api` keeps the five functions with identical results
and error messages, each doing one `Map.get` on its own `Map` (miss: resolve, validate, `set`). The per-adapter
`cache`/`memo` with template-string keys disappears. `createAdapter` calls `mappersFor(dex, T)`.

**Why this is exact**: each mapper is a pure function of `(dex entry, decomp tables)`: `move(id)` returns
`dex.moves.get(id).num` after checking `T.moves[num]` exists; `ability`, `item`, `species`, `type` likewise. Neither
the dex nor the tables change during a process (the dex is Showdown's static data for the format; `T` is the
`decompTables` singleton). Sharing therefore returns the same numbers the cold cache would compute.

**Test**: for every `dex.moves.all()`, `dex.abilities.all()`, `dex.items.all()` entry that the decomp knows (the
existing `num` equivalence test at `ai_adapter.test.mjs:57` is the model), every type name and the species of a
sample battle, the shared mapper equals a freshly built one (exported `makeMappers(dex, T)` for the test,
unshared); unknown ids throw the same messages; two adapters on the same battle share one mapper object.

## R4. Randomized equivalence test (clarification 1)

**Decision**: `sim/test/damage_typechart.test.mjs`, seeded PRNG (mulberry32, fixed seed printed in the
diagnostic), two layers:

- **Synthetic** (>= 10,000 matchups): attacker and defender structs in the port's input shape with every field
  drawn independently: two types from `ENUMS.types` (equal with probability 1/4), ability from a weighted list that
  includes Levitate, Wonder Guard, Filter, Solid Rock, Tinted Lens, Adaptability, Scrappy, Mold Breaker, Normalize,
  Klutz and common others, item from {none, Expert Belt, Iron Ball, a berry, Life Orb, others}, the volatile flags
  (`foresight`, `magnetRise`, `ingrain`, `roosting`, `miracleEye`, `abilitySuppressed`, `embargo`) as independent
  booleans with probability 1/8, field `{ gravity }` and weather at random; move: a random decomp move constant
  with real `moveData` (power 0 moves included) plus optional `power` / `type` overrides, Struggle at 1%; a
  pre-variance damage in 0..400 (0 with probability 1/16); `ignoreTypeChecks` with probability 1/4; incoming
  `moveStatusMask` in {0, SUPER_EFFECTIVE, NOT_VERY_EFFECTIVE} (nonzero 1/8). For each matchup and each of the 16
  rolls (`applyVariance(pre, 85 + i)`), compare `applyTypeChart` (plan + replay) with `applyTypeChartDirect`:
  damage, moveStatusMask, totalMul. Also compare `calcDamage` (one plan) against a 16-fold direct computation for
  a subset, normal and critical.
- **Real data** (>= 1,000 matchups): species types from `decompTables().species`, moves from `decompTables().moves`
  with power > 0, items from `decompTables().items` (constants via `ENUMS`), random stages, abilities from the
  species' own list, flags off; same comparison.
- **Coverage counters**, asserted >= 100 each in the synthetic layer: immune (mask INEFFECTIVE), Levitate,
  Magnet Rise, Wonder Guard, Filter / Solid Rock applied, Expert Belt applied, Tinted Lens applied, STAB, Adaptability,
  Foresight or Scrappy break, Normalize, type override, ignoreTypeChecks, zero damage, Struggle, super effective,
  not very effective, grounding item vs Flying immunity, Roost, Miracle Eye.
- **Positive control**: a copy of a plan with one `mul` step removed, or `stab` flipped, replayed against the
  direct result for the same input, must differ for at least one roll over the generated set.

Runtime target: under 5 s (one plan + 16 replays + 16 direct calls per matchup, about 11,000 matchups).

## R5. Proof chain

Unchanged from 015 and reused: the replay fixture (`sim/test/replay_prof_a.json`, recorded at b2a69d4, v2 digest
= `main`'s `db6d20cf…`, v1 `1273b694…`) with every choice and the per-decision draw counts; the 015 validation log
and the 2026-11-01 re-profile show `main` 19519ed still reproduces both digests, so the fixture is the reference for
this branch too. Each commit: replay test, AI golden and fixture tests, freeze run. Commit 2 adds the CHECK runs.
Pool digest equals the single-process digest in `platsim bench` (digests_agree true).

## R6. Measurement

Before: `main` 19519ed at comparison time, nothing else running: `node sim/bench.mjs --policy expectimax2-v2`
(and `-v1`), `uv run platsim bench --workers 16`. After: same on the branch at commit 4. Reference figures from the
015 log for the same set: v2 0.7793 gauntlets/s, 16.57 ms/decision (bench, alone); pool 12.423 s, 3.2199 gauntlets/s.
The re-profile (hooked, three processes in parallel) saw 18.2 ms/decision; the comparison uses the bench tool alone,
as 015 did. Estimate from shares: type chart + prepare 17.7% of time, of which the plan removes most (about 14
points); the AI base-damage memo removes most of the remaining AI damage-calc self time shared across samples
(about 5 points); the mappers about 3.5 points: 20 to 25 points, 1.25x to 1.35x. SC-002 bar: 1.2x (>= 0.935
gauntlets/s for v2).

## R7. Out of scope (FUTURE-FEATURES section 7)

The replacement heuristic's memo (`matchupScore`, `damageOutcomes`, 7.6% + 2.1%), the interpreter's argument
lookup (`ctx.arg` linear search), hoisting the remaining `K()` sites (4.9%), cross-decision caches, and the
`expectimax2-v4` approximations (feature 017). `switch.mjs:500`'s own `calcBaseDamage` per party member stays as
is (1.5% category; it already benefits from the shared plan).
