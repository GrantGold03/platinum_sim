# Research: Variable-Power Attacks Without Regression

Observed 2026-10-19 on `010-variable-power` (from `main` at `27d51b0`). Evidence: `runs/010-evidence/`.

## R1. Adapting 007 commit `d3d53e7`

- It does not apply to `main` unchanged: hunks 4-5 (`member_candidates`) were written on top of 007's
  alternatives-stage code (a `policy` parameter, status-move lists). Applied with `git apply --reject`;
  the two rejected hunks re-done by hand (the IVs per variant and `level`/`ivs` passed to `move_value`).
- `is_attack` moves from "power > 1, not in the excluded list" to slice 2's classification. On every move
  the two rules agree except exactly 9 variable-power moves (Crush Grip, Grass Knot, Gyro Ball, Hidden
  Power, Low Kick, Magnitude, Punishment, Return, Wring Out): no fixed-power move changes status.
- Hidden Power excluded by its effect constant `BATTLE_EFFECT_RANDOM_POWER_BASED_ON_IVS`
  (`candidates.NOT_OFFERED_VARIABLE`, user 2026-10-19). Test: not offered to Snorlax or either Haunter
  variant (incl. the NPC trade with fixed IVs); positive control: Haunter legally learns it at Lv 60.
- `tests/unit/test_variable_power.py` adapted: 11 passed.

## R2. Candidate movesets with variable power (B1-B5, all variants, Lv 45/55/65)

- 67 of 93 entries change; 60 have a variable-power move in their top movesets.
- B2 Lv 55: every Infernape set gains Grass Knot, and one drops Close Combat
  (`fire_blast/focus_blast/stone_edge/grass_knot`); Floatzel, Staraptor and Weavile gain Return.
- Side effect: Garchomp's candidates change without any variable-power move in them (Fire Blast leaves).
  The pool is the top `POOL` attacks by score; variable-power moves now take pool slots and push other
  moves out of every combination.

## R3. Which change hurts, in battle (paired, same seeds)

Oct 8 B2 team at its Oct 8 levels (53,53,53,54,51,54), expectimax2-v2, 2,000 paired runs, seeds `010-swaps|i`
(`runs/010-evidence/swaps.py`, logs `swaps.log`, `swaps2.log`):

| Arm | Cleared | vs base |
|---|---|---|
| base | 1506 (0.7530) | — |
| Floatzel Ice Beam → Return | 1522 (0.7610) | 82/66, p 0.217, indistinguishable |
| Weavile X-Scissor → Return | 1503 (0.7515) | 4/7, p 0.549, indistinguishable |
| Infernape Flame Wheel → Grass Knot | 1530 (0.7650) | 117/93, p 0.112, indistinguishable |
| Infernape Close Combat → Grass Knot | 1318 (0.6590) | 137/325, p 1.1e-18, **worse** |
| Infernape = 007 set (FB/Focus Blast/Stone Edge/GK) | 1305 (0.6525) | 174/375, p 5.9e-18, **worse** |
| all three swaps | 1339 (0.6695) | 153/320, p 1.2e-14, **worse** |

**Return and Grass Knot are not harmful in themselves. Losing Close Combat costs about 10 points.**

## R4. How the 007 run chose the Close-Combat-less set

- The screen (greedy-v1, levels 56) kept finalists 50 and 68. They differ in **five members**; Infernape
  is FB/Focus Blast/Stone Edge/GK in 50 and FB/Close Combat/Stone Edge/GK in 68. Greedy ranked 50 first.
- greedy-v1 scores every variable-power attack as 0 (`sim/policy/greedy.mjs:23-28`), so in the screen
  Infernape plays both sets as 3-move sets, and the Return/Grass Knot/Hidden Power members are
  undervalued: the screen judges teams that are not the teams that will play.
- The runner-up check (expectimax, 2,000 paired, levels 55/54 after the +1 bump) found the two finalists
  indistinguishable (158/138, p 0.27): whole-team comparison at 92% clear, many differences; it cannot
  catch one member's moveset choice.
- On `main`, all three Infernape candidate sets keep Close Combat, so this failure could not happen there.

**Cause (FR-003):** adding variable-power moves lets candidate generation produce sets that drop a key
STAB attack (pool truncation and the diversity rule), and the greedy screen, blind to the new moves, picks
among them on the wrong information; no later stage compares a member's moveset on its own.

## R5. Which variable-power attacks the strong player can use

`main`'s expectimax2-v2 `variablePower` (`sim/policy/expectimax2.mjs:437-460`) handles
POWER_BASED_ON_FRIENDSHIP (Return), POWER_BASED_ON_LOW_FRIENDSHIP (Frustration), INCREASE_POWER_WITH_WEIGHT
(Grass Knot, Low Kick), RANDOM_POWER_BASED_ON_IVS (Hidden Power) and POWER_BASED_ON_LOW_SPEED (Gyro Ball);
anything else returns `undefined` and the damage table entry is `null`, i.e. the move does nothing in the
player's model. 007's v3 has the same cases (`007-status-moves-items:sim/policy/expectimax2.mjs:632-660`).
So Magnitude (PSYWAVE effect), Wring Out / Crush Grip (INCREASE_POWER_WITH_MORE_HP) and Punishment
(INCREASE_POWER_WITH_MORE_STAT_UP) were offered by 007 but never usable by its players: the same kind of
blind spot as the greedy screen. Decision (FR-004, FR-011): offer only Return, Grass Knot, Low Kick and
Gyro Ball; the other four wait for a player that models them (`FUTURE-FEATURES.md`).

## R6. After fix B (additive pool), 2026-10-19

- With every variable-power effect switched off, the new code's B1-B5 candidates (movesets and items, 93
  entries) are byte-identical to `main`'s (`cmp runs/009-evidence/candidates-branch.json
  runs/010-evidence/candidates-novp.json`): the adaptation and the pool change alter nothing except through
  the variable-power moves.
- With them on: 63 of 93 entries change (67 before fix B). Garchomp is back to `main`'s sets. No excluded
  or unmodelled move is offered.
- **Still present:** Infernape's third B2 set is FB/Focus Blast/Stone Edge/Grass Knot, the set R3 measured
  at −10 points. It comes from the diversity rule (sets differ pairwise in ≥ 2 moves), not from the pool.
  Fix B does not remove it; whether the screen picks it depends on fix A (greedy-v2 sees Grass Knot) and is
  checked by the B2 smoke run (T009) and the acceptance (T011-T012).
