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
