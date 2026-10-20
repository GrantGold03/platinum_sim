# Implementation Plan: Variable-Power Attacks Without Regression

**Branch**: `010-variable-power` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/010-variable-power/spec.md`

## Summary

Offer Return, Grass Knot, Low Kick and Gyro Ball at their decomp power (adapted 007 `d3d53e7`), and remove
the two causes of 007's B2 regression (research R3-R4): the move pool becomes additive (variable-power
attacks join `main`'s pool, never displace it), and the greedy screen gets a successor, `greedy-v2`, that
values these moves at their real power. Hidden Power (user), Magnitude, Wring Out, Crush Grip and Punishment
(no player models them, R5) are not offered. Accept only if no B1-B5 team is worse than its baseline.

## Technical Context

**Language/Version**: Python 3.14 (uv); Node ≥ 22.18 for the battle worker

**Primary Dependencies**: none new; `sim/damage.mjs` `fromShowdown(..., {power})`, `sim/ai/calcdamage.mjs` `speciesWeightHg`/`WEIGHT_TO_POWER`

**Storage**: state version bump (screen policy and candidates change, so old checkpoints must not resume)

**Testing**: pytest (`test_variable_power.py`, candidates, screen), node (`greedy` tests, golden v1/v2), then the full suite and the B1-B5 acceptance

**Target Platform**: this Linux machine, 16 threads

**Project Type**: CLI + local web app (existing)

**Performance Goals**: standard run ≤ 2.0x baseline per team (baseline B1-B5: 85.6 / 94.1 / 95.2 / 116.8 / 100.2 min)

**Constraints**: greedy-v1 byte-identical (pinned golden); decomp is ground truth for powers

**Scale/Scope**: `candidates.py`, `greedy.mjs`, `gauntlet.mjs` registration, `run.py`/`screen.py`/`abilities.py` screen policy, tests; acceptance ~10-12 h local compute

## Constitution Check (v1.4.0)

| Principle | Check | Status |
|---|---|---|
| I. Decomp is ground truth | Powers from decomp formulas (friendship 255, `weight_to_power.h`, Gyro Ball speed ratio); exclusions by effect constant | PASS |
| II. Showdown is the battle engine | greedy-v2 changes the screen player's choices only; Showdown resolves battles | PASS |
| III. In-game legality | Validator on every final team; required HMs unchanged | PASS (acceptance) |
| IV. Reproducible, honest evaluation | Paired McNemar vs baseline on B1-B5; same-seed determinism | PASS (planned) |
| V. Verified claims, positive controls | greedy-v2 equals greedy-v1 on a team without variable-power moves (byte-identical logs) and differs on a Return team | PASS (planned) |
| VI. Reference-first | greedy-v2 is a screen heuristic like greedy-v1; its effect is measured by the B1-B5 acceptance against the baseline; the strong player stays the judge | PASS |

## Approach

1. **Candidates** (`candidates.py`): the adapted `d3d53e7` (done, R1); `NOT_OFFERED_VARIABLE` gains the
   three unmodelled effects (PSYWAVE = Magnitude, INCREASE_POWER_WITH_MORE_HP, INCREASE_POWER_WITH_MORE_STAT_UP);
   pool = `main`'s top-`POOL` fixed-power attacks **plus** every offered variable-power attack (additive);
   `RANKED` keeps all combos of the larger pool.
2. **Screen player** (`sim/policy/greedy.mjs`): `greedy-v2` = greedy-v1 plus power for Return (friendship),
   Grass Knot / Low Kick (foe weight), Gyro Ball (speed ratio), passed to `fromShowdown(..., {power})` as
   expectimax2 does. greedy-v1 untouched. Register in `gauntlet.mjs`.
3. **Optimizer**: `SCREEN_POLICY = "greedy-v2"` for calibrate, ability screen and screen (`run.py`, `screen.py`,
   `abilities.py`); `STATE_VERSION` 3 → 4.
4. **Checks**: unit/node tests; greedy-v2 vs v1 identical on the policy benchmark team (no variable-power
   moves) and different on a Return team; candidates: every `main` pool move still in the pool.
5. **Acceptance**: standard B1-B5 (seed `bench-007`, as the baseline), wall time vs baseline; each final team
   vs its baseline final team, 2,000 paired runs with expectimax2-v2 at their own start levels; plus the
   average-final-level rule (spec US2).
6. Full suite, docs, commit, user test, merge.

## Project Structure

```text
src/platsim/optimizer/candidates.py   # variable power, exclusions, additive pool
src/platsim/optimizer/run.py, screen.py, abilities.py   # SCREEN_POLICY greedy-v2; STATE_VERSION 4
sim/policy/greedy.mjs, sim/gauntlet.mjs                 # greedy-v2
tests/unit/test_variable_power.py (+ pool test), sim/test/greedy_v2.test.mjs
```

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| A second greedy policy | greedy-v1 is pinned by the golden test and recorded in past runs' provenance | Editing v1 would change every past result's meaning and break the golden pin |
