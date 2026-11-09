# Validation log: feature 024 variable-power moves

Branch `024-variable-power-moves` from `main` cf4a9ff, main checkout. Times US Eastern. Nothing is copied from the archived
007 to 010 branches (FR-011); their findings were read as hypotheses only.

## T001 Setup (11:59 AM EST)

`git diff --stat main -- src sim tests pyproject.toml` lines: 0 (the branch's code equals `main`, so the pre-feature side can
run here). Before-values (all three expected to change by the end):

```
sim_code_hash platsim_code_hash: sha256:c07be275722f26cf900d810cb52e577b15321cd1c8a7df2f26f196568d5af493 sha256:92793dc145501bae565639b5827c6b6c7a9c3113a48347d7e445ab0248b2370f
divergence_ledger_version: sha256:baeaf406c676c665
```

## T002 Pre-feature side (12:00:45 to 12:09:26 PM EST, alone, exit 0; code identical to `main`)

`acceptance.py --side main --workers 16` (evidence `runs/024-evidence/`, copies in `evidence/pre/`):

- B2 quick on today's code (`runs/024-evidence/b2-main`): species ['garchomp', 'infernape', 'staraptor', 'rotom', 'floatzel', 'weavile'], levels [51, 52, 52, 53, 52, 53], clear
  0.9300 [0.9042, 0.9492] (n 500, 2 confirm attempts), expected
  average final level 52.79, wall 365.9 s, variable-power members: none (as expected: today's
  code offers none). Code: `platsim_code_hash` sha256:92793dc14550..., `sim_code_hash` sha256:c07be275722f...,
  `repo_commit` c949d408109c7d61398689a8f59a88d180502df0. The same levels and clear rate as feature 023's `b2quick-shift` run of this job.
- Identity evaluations (`ident-main/ref`, `ident-main/b2main`; 200 runs, quick, seed 024-ident): written for the comparison
  after the code change (volatile fields removed: code hashes, repo commit, ledger version and entries).
- Candidate snapshot `evidence/b2-candidates-main.json`: the six B2 member variants (all `own`) at the job's reference level 48,
  each with the call arguments, 3 movesets, the setup set, the first 210 ranked combos and the pool.


## T003-T004 The shared helper (12:10 PM EST)

`sim/variable_power.mjs`: `WEIGHT_TO_POWER`, `speciesWeightHg` (moved from `sim/ai/calcdamage.mjs`, re-exported there),
`weightTierPower`, `returnPower`, `frustrationPower`, `gyroBallPower`, `OFFERED_VARIABLE`. The trainer-AI port's Return,
Frustration, Low Kick / Grass Knot and Gyro Ball cases and expectimax2's `variablePower` call the helper (the AI switch keeps its
throws on missing or zero speed; the u32 wrap of 25*d it guarded is unreachable for speed values).

```
node --test test/ai_cmds_damage.test.mjs test/ai_adapter.test.mjs test/expectimax2.test.mjs: exit 0, tests 40, pass 40
```

## T005-T008 greedy-v1 and the ledger (12:11 to 12:13 PM EST)

`sim/policy/greedy.mjs`: `variablePowerFor(moveConst, attacker, foe)` (Return at the attacker's happiness, default 255; the weight
tier of the foe's species; Gyro Ball from `storedStats.spe` of both, the stat at level, an approximation recorded in the header);
`expectedDamage` passes the computed power through `fromShowdown(..., { power })`; every other power-1 move still scores 0.
`sim/test/variable_power.test.mjs` (9 tests): the decomp table, every tier and both sides of every limit, Snorlax 4600 / Pikachu 60 /
Flareon 250 (-> 40), Return 102, Gyro Ball values and the cap, zero speed; greedy's expected damage for the four moves on
Flint's and Bertha's leads equals a fixed-power move of the computed power and is > 0; Frustration and Magnitude still 0; a
Snorlax with return/tackle/rest/yawn picks Return. Slip corrected while writing the test: 25*436/100 is 109, so Gyro Ball at
(100, 436) is 110, not the 109 first written. Ledger: `mech-weight-tier-boundary` (accepted), `data/divergences.json` 76 entries,
version `sha256:feb2a48ef2e1dd08` (was `baeaf406c676c665`).

```
node --test test/variable_power.test.mjs: exit 0, pass 9, fail 0
uv run pytest -q tests/integration/test_divergences.py -m "not battle_sim": exit 0, 4 passed
```

## T009 Set guard and the Node suite (12:12:52 to 12:17:47 PM EST)

```
replay + determinism + gauntlet + bench + ai_cmds_damage: exit 0, tests 44, pass 44  (digests, choices, draw counts unchanged)
node --test test/*.test.mjs: exit 0, tests 381, pass 381
```

**Commit 2**: `feat(024): shared variable-power helper in sim/; greedy-v1 scores Return, Grass Knot, Low Kick, Gyro Ball; weight-tier ledger entry`.

## T010-T014 The optimizer offers the four moves (12:18 to 12:35 PM EST)

`src/platsim/decomp/weights.py` (the Python twin of the helper: `species_weight_hg`, `weight_tier_power`, `gyro_ball_power`,
`return_power`); `candidates.py`: `LeagueOpponent` with level/iv/nature, `variable_power` per opponent (Return 102; the opponent's
weight tier; Gyro Ball from the member's speed at the candidate level with IV 15 / EV 85 / Hardy against the opponent's at its
level with its iv / EV 0 / nature), `move_value(..., member_level=100)` (the level defaults to 100 so older callers and tests keep
working; every optimizer caller passes its level), `OFFERED_VARIABLE`, `NOT_OFFERED_VARIABLE` with reasons, the additive extras in
`member_candidates` (today's `pool`, `chosen`, setup and `ranked` prefix unchanged; extras ranked by the same key over the pool plus
the member's variable moves, diverse among themselves), `summary()` with `variable_offered` and `extras`; `held_item_candidates`
and `resources._slot_cost` take the level and accept the four moves as the best attack.

Two slips corrected by the prefix test against the pre-feature snapshot: (1) the rewrite multiplied the value's factors in a
different order and flipped a floating-point tie at position 174 of Rotom's ranked list; restored the exact pre-024 order, so
fixed-power values are bit-identical; (2) a first reading blamed a small pool, which was wrong (Rotom's pool is 10, 210 combos).

`tests/unit/test_variable_power.py` (5 tests): weight pins and Node parity for every League party species, tiers on both sides of
every limit, Gyro Ball, Return; `variable_power` per opponent (Grass Knot: Rhyperior 120, Flareon 40; a slow Bronzong's Gyro Ball
above a fast Weavile's); the not-offered list absent from every B2 list; **the additive prefix for all six B2 species** against
`evidence/b2-candidates-main.json`. Hand check `evidence/b2-candidates-branch.txt`: every B2 member learns Return, Infernape also
Grass Knot; 3 extras each.

```
uv run pytest -q tests/unit/test_variable_power.py: exit 0, 5 passed
fast mode, 12:20:57 to 12:31:06 PM EST: 2 failed, 587 passed, 32 deselected, 4 xfailed in 606.63s; the two failures were pins from
before the feature (test_optimizer_candidates: movesets <= K and every move an is_attack; test_required_hms: move_value with two
arguments); the pin updated for the additive list, the level given a default; rerun of the four touched files: exit 0
```

**Commit 3**: `feat(024): optimizer offers Return, Grass Knot, Low Kick, Gyro Ball in an additive candidate list ...`.

## T017 Acceptance, branch side (12:33:10 to 12:45:46 PM EST, alone, exit 0)

`acceptance.py --side branch --workers 16 --runs 2000` (evidence `runs/024-evidence/`, copies in `evidence/acceptance/`).

| | today's code (`b2-main`) | branch (`b2-branch`) |
|---|---|---|
| levels | [51, 52, 52, 53, 52, 53] | [51, 51, 52, 52, 52, 52] |
| confirmation clear rate [95% CI], n | 0.9300 [0.9042, 0.9492], 500 | 0.7920 [0.7543, 0.8253], 500 |
| expected average final level | 52.79 | 52.30 (diff -0.49) |
| members with a variable-power move | none | ['staraptor'] (Staraptor: return / close combat / fly / u-turn) |
| wall | 365.9 s | 315.5 s |
| equal levels ([51, 51, 52, 52, 52, 52], 2,000 pairs, v4) | B 0.8225 | A 0.7780; only A 241 / only B 330, p 0.000225, verdict **B** (today's better) |
| identity (reference team, 014 b2-main team) | identical after removing the code-version and ledger fields: ref True, b2main True | |
| FR-009 | | **FAIL** (supported loss; the level criterion itself passes) |

Teams: today's: garchomp earthquake+dragon claw+stone edge+aerial ace [sitrus_berry] / infernape fire blast+flamethrower+close combat+fire punch [wise_glasses] / staraptor pluck+close combat+giga impact+u turn [sky_plate] / rotom thunderbolt+shadow ball+thunder+ominous wind [expert_belt] / floatzel waterfall+ice beam+blizzard+ice fang [splash_plate] / weavile ice punch+avalanche+night slash+brick break [sitrus_berry]. Branch: garchomp earthquake+dragon claw+stone edge+aerial ace [sitrus_berry] / infernape fire blast+flamethrower+close combat+fire punch [sitrus_berry] / staraptor return+close combat+fly+u turn [silk_scarf] / rotom thunderbolt+shadow ball+thunder+ominous wind [sitrus_berry] / floatzel waterfall+surf+ice beam+brine [sitrus_berry] / weavile ice punch+avalanche+night slash+brick break [sitrus_berry].

Script slips fixed after the run, without new battles: the identity comparison had left `provenance.divergence_ledger_file_version`
in place (now removed with the other volatile fields; both pairs identical), and the variable-member detection compared constant
names against the report's move keys (Staraptor carries Return).

## T018 FR-009 verdict: FAIL, merge blocked; the cause as measured (12:50 PM EST)

The branch winner is worse at equal levels by a supported margin (4.5 points, p 2e-4). The displacement test is clean: today's
candidate sets are a prefix of the branch's for all six members (T013), so no set was displaced. The difference is upstream of the
sets: the **screen's sampling**. The screen builds its 81 candidate teams from the baseline, the single-slot deviations and a random
fill over the option list (`run.py` screen stage); appending up to three sets per member doubles the option list, so the random fill
and the 81 cap land on a different population: the two screens shared only 43 of 81 teams, and **today's winning team was never
screened on the branch** (nor the branch's winner on today's code). The branch's screen then preferred a Staraptor with Return (its
first move by score: 102 with STAB) over today's Pluck / Giga Impact set and a different Floatzel set and items, and the quick
level search and confirmation worked from that finalist. The loss is therefore attributable to the screen seeing a different, worse
subset under its cap, with the Return set as the one variable-power pick; whether the Return set itself is worse than today's
Staraptor set is not separated by this run (the 010 record found Return indistinguishable from what it replaced in single swaps).
The feature is not merged; the decision on the next step is the user's (options in the report: a screen that always includes today's
baseline team and deviations before the fill, or a larger cap when extras exist, or a single-swap measurement of the Return set).

## T022-T024 Screen superset (user's decision, 1:05 PM EST)

User decision on the T018 report: **screen superset**. `run.py`: `_member_options` returns today's sets only (the movesets before
the `extras` suffix), so the baseline, the single-slot deviations and the RNG fill are identical to today's; `_member_extra_options`
gives one option per extra set with its first held item, appended as single-slot deviations of the baseline beyond the 81 cap
(repaired, validated, deduplicated as the others); the screen stage records `extras_screened`. The spec gained FR-006b and a second
clarification entry; `acceptance.py --side branch` now checks that the branch's first 81 screened teams equal the pre-feature run's.

```
uv run pytest -q tests/unit/test_optimizer_resume.py tests/unit/test_required_hms.py tests/unit/test_legality_options.py tests/unit/test_optimizer_candidates.py: exit 0, 62 passed
```

## T023 Acceptance rerun with the screen superset (1:21:01 to 1:35:08 PM EST, alone, exit 0)

| | today's code (`b2-main`) | branch (`b2-branch`, rerun) |
|---|---|---|
| screened teams | 81 | 95 (14 variable-power extras beyond the cap); first 81 identical: **True** |
| winner | levels [51, 52, 52, 53, 52, 53], clear 0.9300, avg final 52.79 | **the same team, moves, items and levels**: levels [51, 52, 52, 53, 52, 53], clear 0.9300, avg final 52.79; variable-power members: none |
| wall | 365.9 s | 389.9 s (the 14 extra teams in the screen) |
| equal levels (2,000 pairs, v4) | 0.9275 | 0.9275; only A 0 / only B 0, p 1, indistinguishable |
| identity | ref True, b2main True | |
| FR-009 | | **PASS** (level diff +0.00) |

**Reading.** With the screen's capped population held to today's, the branch screens the 14 extra teams (18 extras minus repairs
and duplicates) and none beats today's finalist, so the optimizer's output on B2 quick is identical to today's: the four moves are
offered and not chosen on this team. The first acceptance's loss (T017, T018) was the screen's sampling, now removed by construction
(the prefix check). Every stated guarantee holds: today's candidate sets are a prefix (T013), today's screened teams are a prefix
(T023), unaffected teams evaluate identically, recorded results unchanged (T009). Whether a variable-power set ever wins is a
property of the team: on B2 quick, none did.

## T019 Docs (1:40 PM EST)

README (the 024 block with the outcome), FUTURE-FEATURES sections 1 and 6, RUN-STATE. **Commit 4**: `feat(024): acceptance rerun ...`.


## T020 Gates (1:36:13 to 3:05:23 PM EST, nothing else running)

Run on the final code (853eb88). Outputs in `runs/024-evidence/gates.txt` (copy `evidence/gates.txt`), `full.log` (slowest-25 table in
`evidence/full-durations.txt`).

```
git diff --stat main -- pokemon-showdown: 0 lines (the vendored engine untouched)
sim_code_hash after:     sha256:e968ff0f403539460e6c0260db6253ad971d1a3eb7c02feaa8c9fbe393e74b7d  (was c07be275...)
platsim_code_hash after: sha256:eb92dee26412cbc7226f65d030a30df0a914b267f9506a67fa78064246edde42  (was 92793dc1...)
divergence_ledger_version after: sha256:feb2a48ef2e1dd08  (was baeaf406c676c665)   -> pre-024 checkpoints are refused (FR-007)
node --test test/*.test.mjs: exit 0, tests 381, pass 381
full pytest (uv run pytest -q --durations=25), 1:38:48 to 3:05:23 PM EST: exit 0
621 passed, 4 xfailed, 1 warning in 5192.36s (1:26:32)
```

Slowest: `test_optimize_adaptive` 1,410 s, `test_optimize_small` 1,288 s, `test_policy_strength` 755 s. The suite grew from 616 to
625 (the 5 new variable-power tests and others). **All gates green on the final code; the feature is closed on its branch. Merge on the
user's go.**

## T021 Closing commit (3:10 PM EST)

`docs(024): gates recorded; feature closed on its branch`.
