# Validation log: 010 variable-power attacks without regression

Real output per checkpoint. Evidence: `runs/010-evidence/` (git-ignored). Research findings (cause of
the 007 regression, candidate diffs) are in `research.md` R1-R6.

## T004-T008 Code and tests (2026-10-19)

- `tests/unit/test_variable_power.py`: `17 passed` (Return 102; Low Kick 120/40; Gyro Ball ≤ 150; Hidden
  Power never offered incl. NPC-trade Haunter, positive control: learnable; Magnitude (Graveler), Wring Out
  (Tentacruel), Punishment (Infernape) not offered with learnability controls; Crush Grip, Hidden Power not
  attacks; the four offered moves are attacks; Gyro Ball in Bronzong's pool; pool additive: with variable
  power off the pool is exactly `POOL` fixed-power moves, a subset of the full pool).
- Candidates with every variable-power effect off are byte-identical to `main` for all 93 B1-B5 entries
  (research R6).
- `sim/test/greedy_v2.test.mjs` + `greedy.test.mjs`: `# pass 6, # fail 0`. greedy-v2 byte-identical to
  greedy-v1 over 30 gauntlets on a team without variable-power attacks; > 15/30 differ with Return and
  Grass Knot (positive control).
- Screen policy `greedy-v2` in `run.py`, `screen.py`, `abilities.py`; `STATE_VERSION` 3 → 4; pinned
  fingerprints updated; `test_abilities.py` stub worker offers greedy-v2.
- `uv run pytest -q tests/unit`: `474 passed, 4 xfailed in 109.09s`. `node --test sim/test/*.test.mjs`:
  `# tests 316, # pass 316, # fail 0` (314 + 2 greedy-v2 tests).

## T009 B2 smoke (quick, seed `010-smoke`, 2026-10-19)

- `runs/010-evidence/smoke-b2`: `wall_s 1224` (`main`'s quick B2: 1273 s), exit 0, validator `[]`. Policies: screen stages `greedy-v2`, level search / setup check / confirm `expectimax2-v2`.
- Final team: Garchomp EQ/Dragon Claw/Rock Slide/Fire Blast; **Infernape Fire Blast/Close Combat/Stone Edge/Grass Knot** @ Flame Plate; Staraptor Brave Bird/Return/Aerial Ace/Close Combat; Rotom TB/Shadow Ball/Ominous Wind/Shock Wave; Floatzel Waterfall/Surf/Ice Beam/Return; Weavile Ice Punch/Avalanche/Night Slash/X-Scissor. Clear 0.824, avg 54.28 (quick budget: not comparable to standard).
- Screen: the R3 set (FB/Focus Blast/Stone Edge/GK) was the runner-up's Infernape; greedy-v2 ranked the Close Combat team first. One run, not proof; the acceptance decides.

## T011 Standard B1-B5 (2026-10-19 9:34 PM - 2026-10-20 5:39 AM EDT, code `a0e90a9`)

Same commands and seed (`bench-007`) as the T005 baseline (`runs/010-evidence/accept_chain.sh`); out `runs/bench-010/<B>`. All exit 0, all qualified, validator `[]` (B3 with Surf + Waterfall).

| Team | Wall (vs baseline, cap 2.0x) | Avg final level (vs baseline) | Confirm clear (vs baseline) | Variable-power moves in the final team |
|---|---|---|---|---|
| B1 | 93.6 vs 85.6 min (1.09x) | 56.92 vs 56.93 | 0.800 vs 0.787 | Infernape Grass Knot, Gyarados Return |
| B2 | 79.0 vs 94.1 min (0.84x) | **53.07** vs 53.88 | 0.773 vs 0.900 | Infernape Grass Knot, Floatzel Return |
| B3 | 74.1 vs 95.2 min (0.78x) | **58.13** vs 59.09 | 0.771 vs 0.888 | Infernape Grass Knot, Gyarados Return, Chatot Return |
| B4 | 128.2 vs 116.8 min (1.10x) | **58.95** vs 59.41 | 0.808 vs 0.822 | Roserade Grass Knot, Bronzong Return |
| B5 | 110.0 vs 100.2 min (1.10x) | **62.93** vs 64.18 | 0.778 vs 0.849 | Torterra Return, Clefable Return + Grass Knot |

SC-003 met (max 1.10x). Average final level equal or lower on all five.

## T012 Paired comparison as specified (each team at its own start levels)

`runs/010-evidence/accept_pair.py`, 2,000 paired, expectimax2-v2, seeds `010-accept|<B>|i`:
```
B1 new vs base: 0.8030 vs 0.7675, only 370/299, p 0.006759, verdict A
B2 new vs base: 0.7425 vs 0.8965, only 141/449, p 2.214e-38, verdict B
B3 new vs base: 0.7630 vs 0.8865, only 164/411, p 1.903e-25, verdict B
B4 new vs base: 0.7985 vs 0.8030, only 290/299, p 0.7417, verdict indistinguishable
B5 new vs base: 0.7985 vs 0.8455, only 222/316, p 5.845e-05, verdict B
```
**Confounded (found 2026-10-20):** each team plays at its own start levels, and the new teams are 0.5-1.25 levels lower, which the objective rewards and which lowers clear rate by design. The three "B" verdicts are the three largest level drops. By the rule as written (spec US2, carried over from 007 A1) B2, B3 and B5 are "worse"; by the objective they are better. Raised with the user before any conclusion (T013).

## T012 Equal-levels comparison (amended FR-005, user 2026-10-20)

Both final teams at the new team's start levels (all baseline teams legal there, validator `[]`); 2,000 paired, expectimax2-v2, seeds `010-equal|<B>|i` (`runs/010-evidence/accept_equal.py`):
```
B1 new vs base (equal levels): 0.8135 vs 0.7690, only 359/270, p 0.0004413, verdict A
B2 new vs base (equal levels): 0.7555 vs 0.8255, only 237/377, p 1.769e-08, verdict B
B3 new vs base (equal levels): 0.7760 vs 0.7100, only 448/316, p 2.028e-06, verdict A
B4 new vs base (equal levels): 0.8085 vs 0.8115, only 271/277, p 0.8309, verdict indistinguishable
B5 new vs base (equal levels): 0.7760 vs 0.7380, only 343/267, p 0.002365, verdict A
```
- B1, B3, B5 better; B4 equal; **B2 worse** (−7 points at equal levels), although its average final level is lower (53.07 vs 53.88). FR-005 not met for B2 → T013: stopped, raised with the user.
- B2 teams differ in every member: Floatzel base Waterfall/Ice Beam/Blizzard/Ice Fang vs new Waterfall/Brine/Ice Punch/Return (loses both special Ice moves); Weavile, Staraptor, Rotom sets differ; Garchomp Earth Plate → Sitrus, Staraptor Sky Plate → Sitrus. Infernape keeps Close Combat (both screen finalists). Cause not yet isolated.

## T013 B2 diagnosis (2026-10-20, user: "Diagnose B2 first")

New B2 team at its levels; one member at a time restored to its baseline build (moves + item), 2,000 paired, expectimax2-v2, seeds `010-b2diag|i` (`runs/010-evidence/b2diag.py`):
```
new cleared 1498/2000
restore garchomp vs new: 0.7640 vs 0.7490, only 286/256, p 0.2129, verdict indistinguishable
restore infernape vs new: 0.7580 vs 0.7490, only 246/228, p 0.4349, verdict indistinguishable
restore staraptor vs new: 0.7800 vs 0.7490, only 271/209, p 0.005311, verdict A
restore rotom vs new: 0.7510 vs 0.7490, only 135/131, p 0.8541, verdict indistinguishable
restore floatzel vs new: 0.7500 vs 0.7490, only 222/220, p 0.9621, verdict indistinguishable
restore weavile vs new: 0.7705 vs 0.7490, only 263/220, p 0.05588, verdict indistinguishable
base (all restored) vs new: 0.8260 vs 0.7490, only 403/249, p 1.753e-09, verdict A
```
- The loss is spread (Staraptor +3.1, Weavile +2.2, Garchomp +1.5, Infernape +0.9, Rotom +0.2, Floatzel 0; sum ≈ the +7.7 total). The members with variable-power moves (Infernape Grass Knot, Floatzel Return) cost ~1 point between them.
- **Mechanism:** the baseline's sets for Infernape, Staraptor, Floatzel and Weavile are **not among the B2 screen candidates** of the new run (they were in the baseline's). Each member keeps only `K_MOVESETS = 3` sets that differ pairwise in ≥ 2 moves; a variable-power set taking one place displaces a set `main` offered. Fix B made the pool additive, not the candidate list.
