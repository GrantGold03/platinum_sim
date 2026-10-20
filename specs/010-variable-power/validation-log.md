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
