# Research: Variable-Power Moves Offered by the Optimizer

Sources read 2026-11-09 (read only): the decomp at c248fb3f (`src/battle/battle_script.c:6808-6828, 7123-7133`,
`include/data/battle/weight_to_power.h`, `res/battle/scripts/effects/effect_script_0121.s`), the vendored Showdown
(`data/moves.ts`, `data/mods/gen4`, `data/mods/gen5`), `sim/policy/{expectimax2,greedy}.mjs`, `sim/ai/calcdamage.mjs`,
`sim/damage.mjs`, `src/platsim/optimizer/{candidates,run,resources}.py`, `src/platsim/decomp/stats.py`, the fixtures, the
018 and 022 scripts, and the archived 010 record (as hypotheses only).

## R1. One shared helper for the four formulas (FR-001)

- **Finding**: the formulas exist twice in `sim/`: `expectimax2.variablePower` (`:470-493`) and the trainer-AI port's
  `calcDamage` switch (`sim/ai/calcdamage.mjs:245-293`); `WEIGHT_TO_POWER` and `speciesWeightHg` live in calcdamage
  (`:78-134`, parsed from the decomp header and `res/pokemon/<sp>/data.json` with the `speciesproc.c` rounding
  overrides). The two callers differ only at the edges (calcdamage throws on a missing or zero attacker speed and keeps
  u32 arithmetic; expectimax2 returns 0 on zero speed).
- **Decision**: new `sim/variable_power.mjs` with pure functions `weightTierPower(weightHg)` (the decomp loop: first
  limit `>= weight`, else 120), `returnPower(friendship)` (`trunc(f*10/25)`), `frustrationPower(friendship)`,
  `gyroBallPower(attackerSpeed, defenderSpeed)` (`min(150, 1 + floor(25*d/a))`, `a == 0` → 0), plus `WEIGHT_TO_POWER`
  and `speciesWeightHg` moved there and re-exported from calcdamage (its tests import them, `ai_cmds_damage.test.mjs:82`).
  `variablePower` and the AI switch call these; the AI switch keeps its throw on missing speeds (it wraps the pure
  function). Behaviour is unchanged by construction and proven by the replay fixtures and `ai_cmds_damage.test.mjs`.
- **Alternatives**: leaving the duplication and adding a third copy in greedy (rejected: three sources of truth).

## R2. The screening player (FR-002, FR-003)

- **Decision**: `greedy.expectedDamage` keeps `power <= 1 → 0` except for the four offered moves (by move constant:
  `MOVE_RETURN`, `MOVE_GRASS_KNOT`, `MOVE_LOW_KICK`, `MOVE_GYRO_BALL`), whose power comes from the helper and is passed
  through `fromShowdown(..., { power })` (`sim/damage.mjs:901`, `calcDamage` uses `move.power` when set, `:330`).
  Inputs: Return from `attacker.happiness` (Showdown defaults to 255, `pokemon.ts:342`; nothing in `team.mjs` sets it);
  weight from `speciesWeightHg(ENUMS.species[foe.species.num])` as expectimax2 does; Gyro Ball from the two Pokemon's
  `storedStats.spe` (the decomp stat at the level, set by `fixupSide`, `team.mjs:168`), **not** the game's battle speed
  values (greedy has no AI adapter and also scores benched members): an approximation of the screening heuristic,
  recorded in the header. Frustration stays 0 (friendship 255 → 1; not offered).
- **greedy-v1 keeps its name**: no fixture or test team carries any of the four moves (survey: bench, ref, reversal,
  t076_v8, legal, gauntlet.test teams; the League has only Lucian's Bronzong Gyro Ball, which greedy never scores since
  it models no incoming damage), so every recorded result is byte-identical; the replay and determinism tests are the
  proof (FR-003). If a fixture ever gains one of the moves, the change moves behind a new policy name.

## R3. Species weight on the Python side (FR-005)

- **Finding**: `data/generated/species.json` has no weight; nothing in `src/platsim` reads `weight_pounds`. Adding the
  weight to extract would change `decomp_data_hash`, a behaviour key the replay fixture pins.
- **Decision**: `src/platsim/decomp/weights.py`: `species_weight_hg(species_const)` reads
  `pokeplatinum/res/pokemon/<lower>/data.json` (`pokedex_data.weight_kilograms` or `weight_pounds` minus the
  `species_weight_rounding_override` entries of `tools/dataproc/src/speciesproc.c`, times 0.45359237, rounded to hg),
  the same algorithm as `speciesWeightHg`; cached. A unit test pins Snorlax 4600, Pikachu 60, Flareon 250 and compares
  Python with Node for every League party species by running `node -e` on the helper (the version test already runs
  node from pytest; not a battle worker, so the split guard is untouched). The weight tier itself is a pure Python
  function `weight_tier_power(weight_hg)` mirroring the decomp loop.

## R4. Per-opponent power and speeds in the optimizer (FR-005)

- **Finding**: `move_value(const_member, move_const)` (`candidates.py:367-375`) uses the data power, the member's base
  attacking stat and `league_opponents()` (`(species, types, weight)` per League Pokemon, `:175-185`), with no levels.
  `trainers.json` carries each opponent's `level`, `iv` (one value), `nature`; player defaults are IV 15, EV 85, Hardy
  (`legality/models.py:42-44`, `resources.py:293-305`); `decomp/stats.calc_stats(base, ivs, evs, level, nature)` exists
  (`decomp/stats.py:68-85`) and is unused by the optimizer today.
- **Decision**: `league_opponents()` gains `level`, `iv`, `nature` (a sibling named tuple; the old three-field use sites
  read the same positions). `move_value(const_member, move_const, member_level)` computes the power per opponent:
  fixed moves `m.power`; Return 102 (`FRIENDSHIP = 255`); Grass Knot and Low Kick `weight_tier_power(species_weight_hg(opp))`;
  Gyro Ball `gyro_ball_power(member_spe, opp_spe)` with `member_spe = calc_stats(base, IV 15, EV 85, member_level,
  Hardy)["spe"]` and `opp_spe = calc_stats(opp base, iv, EV 0, opp level, opp nature)["spe"]` (integer arithmetic as the
  decomp). `member_level` is the candidate level in `member_candidates` (`level`), the same in `held_item_candidates`,
  and the reference level in `resources._slot_cost` (checked at implementation; both callers already know a level or
  take one). Not offered and never scored: the list of FR-005, by move constant and by effect (`RANDOM_POWER_BASED_ON_IVS`,
  `POWER_BASED_ON_LOW_FRIENDSHIP`, the no-player effects, fixed damage and counters) with a reason table in the module.
- **Alternatives**: scoring Gyro Ball with the game's battle speeds (needs a battle; rejected) or at base stats (wrong
  by level scaling; rejected).

## R5. The additive candidate list (FR-006, FR-006a)

- **Finding**: `member_candidates` (`:467-506`): `attacks = prune(legal)` (is_attack: power > 1), `pool` = top POOL 10 by
  summed score, combos of 4 over the pool ranked by `(-coverage, -sum score, combo)`, `chosen` = up to K 3 sets each
  differing from the others by at least 2 moves, a setup variant, `ranked` = the 210 combos for `resources.repair`,
  items per set. The screen lists every `(variant, moveset, item)` option, builds single-slot deviations and random
  combos up to 81 (`run.py:396-414`); the baseline is `movesets[0]`.
- **Decision**: `is_attack` and `prune` unchanged (power > 1), so `pool`, `chosen`, the setup variant and the first 210
  `ranked` combos are exactly today's. Then `variable = [m for m in legal if m in OFFERED_VARIABLE]`; if non-empty:
  `extra_combos` = combinations of 4 over `sorted(pool ∪ variable)` containing at least one variable move, ranked by the
  same key with per-opponent values; `extras` = up to K of them in rank order, each differing from the other extras by at
  least 2 moves (clarification 1: diversity among extras only). `movesets = chosen + extras`; `ranked = today's 210 +
  extra_combos in rank order` (repair of an extra set can fall back to variable combos; the prefix is unchanged); `items`
  computed for every set (the "best attack" pick allows the four moves). `summary()` reports `variable_offered` and the
  extras count. A unit test compares the six B2 species' lists with a snapshot of today's lists taken on the pre-feature
  code (T001 artifact `evidence/b2-candidates-main.json`): prefix equality in order, extras present where a variable move
  is legal.
- **Known side effect, stated**: appending options changes the screen's random-combo fill (`len(opts)` in the RNG) and
  can crowd deviations under the 81 cap, so a job's screened set differs even where today's sets are untouched; the
  acceptance measures the end result, not the screen's sampling.

## R6. Fingerprint and checkpoints (FR-007)

- **Decision**: no `STATE_VERSION` bump. `platsim_code_hash` and `sim_code_hash` both change (candidates.py, greedy,
  the new helper), so `_State` refuses every pre-024 checkpoint (`run.py:116-144`, `version.BEHAVIOUR_KEYS`), the
  018/022/023 precedent; a bump would change every default out dir and break two tests that pin `state_version: 3`.

## R7. The ledger entry (FR-004)

- `mech-weight-tier-boundary`, area mechanics, resolution accepted: the game breaks at the first limit `>= weight`
  (`battle_script.c:6815-6819`, `weight_to_power.h:1-8`), Showdown's Low Kick and Grass Knot use `weight >= limit`
  thresholds (`data/moves.ts:10449-10458`, `:7541`), so a weight exactly on a limit differs by one tier; impact: among
  League Pokemon only Flint's Flareon (55.1 lb → 250 hg): game 40, engine 60; the player's model and the optimizer
  follow the decomp. `test_id`: `sim/test/variable_power.test.mjs` (the boundary case).

## R8. Acceptance protocol and the pre-feature side (FR-008, FR-009)

- **Finding**: this branch differs from `main` cf4a9ff only under `specs/024-*`; `git diff --stat main -- src sim
  tests pyproject.toml` is empty. Precedent (013, 014, 015, 017): the baseline was run on `main`'s code before the
  branch code, in the main checkout, and `runs/` survives switches (gitignored). No worktree (memory).
- **Decision**: **T001 runs the pre-feature side now**, before any code commit, alone: (a) B2 quick into
  `runs/024-evidence/b2-main` (`optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2
  --workers 16`), (c) the two byte-identity evaluations into `runs/024-evidence/ident-main/{ref,b2main}` (`evaluate ...
  --runs 200 --budget quick --seed 024-ident --workers 16`; the 014 b2-main team written from
  `runs/014-evidence/b2-main/result.json` as 022 did), and the candidate snapshot `evidence/b2-candidates-main.json`;
  the result files' `platsim_code_hash`/`sim_code_hash`/`repo_commit` prove the code. After the code: `b2-branch`,
  `ident-branch`, then `cmp`.
- **Equal levels**: `scripts/equal_levels.py` adapted from 018's: team B = `b2-main` winner, team A = `b2-branch`
  winner, both at A's levels, validated, 2,000 full gauntlets each with `run_full_gauntlets` (master `024-equal|B2`,
  player `expectimax2-v4`, today's default style), `mcnemar_exact(A, B)`, mean final levels; the pass rule of FR-009
  (no supported loss at alpha 0.05, A's expected average final level at most one above B's).
- **Members carrying a variable move**: from each winner's `team.builds[*].moves`.
- **Cost**: B2 quick about 7 min per side; identity evaluations about 2 min per side; equal levels about 5 min; total
  under 30 min of pool time plus the two gate suites.

## R9. The archived record as hypotheses (FR-011)

- 010's single-swap finding (Return and Grass Knot indistinguishable from the moves they replaced; losing Close Combat
  cost about 10 points) and its displacement diagnosis motivate R5's additive list. Nothing is copied: the helper, the
  Python weight reader, the candidate logic and the acceptance script are written from the decomp and `main`.
