# Data Model: Variable-Power Moves Offered by the Optimizer

## Variable-power helper (`sim/variable_power.mjs`, pure)

| Function | Input | Output | Source |
|---|---|---|---|
| weightTierPower(weightHg) | integer hectograms | 20 / 40 / 60 / 80 / 100 / 120 | `weight_to_power.h`; first limit >= weight (`battle_script.c:6815-6819`) |
| returnPower(friendship) | 0..255 | trunc(f*10/25) | `effect_script_0121.s` |
| frustrationPower(friendship) | 0..255 | trunc((255-f)*10/25) | `effect_script_0123.s` |
| gyroBallPower(attackerSpeed, defenderSpeed) | speed values | min(150, 1 + floor(25*d/a)); 0 when a == 0 | `battle_script.c:7123-7133` |
| WEIGHT_TO_POWER, speciesWeightHg(speciesConst) | | the parsed table; hg from `res/pokemon/<sp>/data.json` with `speciesproc.c` overrides | moved from `sim/ai/calcdamage.mjs`, re-exported there |

## Python mirror (`src/platsim/decomp/weights.py`, `optimizer/candidates.py`)

| Item | Notes |
|---|---|
| species_weight_hg(species_const) | same algorithm as speciesWeightHg; cached; pinned (Snorlax 4600, Pikachu 60, Flareon 250) and Node-parity-tested for League species |
| weight_tier_power(weight_hg) | the decomp loop |
| gyro_ball_power(atk_spe, def_spe) | min(150, 1 + 25*d // a); 0 when a == 0 |
| FRIENDSHIP = 255 | Return 102; the README states the assumption |
| LeagueOpponent | (species, types, weight, level, iv, nature); `league_opponents()` returns these; the first three positions as today |
| OFFERED_VARIABLE | {MOVE_RETURN, MOVE_GRASS_KNOT, MOVE_LOW_KICK, MOVE_GYRO_BALL} |
| NOT_OFFERED (reason table) | Hidden Power (IVs uniform 15 by assumption); Frustration (1 at friendship 255); Magnitude, Wring Out, Crush Grip, Punishment, Flail, Reversal, Fling, Trump Card, Natural Gift, Present, Spit Up (no player computes them); fixed-damage and counter moves (not attacks for this purpose) |
| move_value(const_member, move_const, member_level) | per opponent: power(m, member, opp) × acc × STAB × base attacking stat × effect weight × type multiplier × opponent weight; power is the data power for fixed moves, 102 for Return, the opponent's weight tier for Grass Knot / Low Kick, gyro_ball_power(member spe at member_level with IV 15 / EV 85 / Hardy, opponent spe at its level with its iv / EV 0 / nature) for Gyro Ball |

## Candidate list (`member_candidates`)

| Field | Before | After |
|---|---|---|
| pool, chosen (K sets), setup variant | today's | unchanged |
| extras | none | up to K sets from combinations over sorted(pool ∪ variable) containing >= 1 variable move, ranked by (-coverage, -sum score, combo), each differing from the other extras by >= 2 moves |
| movesets | chosen (+ setup) | chosen + extras (+ setup as today) |
| ranked | 210 pool combos | today's 210 first, then the extra combos in rank order |
| items | per set | per set, the "best attack" pick may be a variable move |
| summary() | as today | + `variable_offered` (the member's offered variable moves), `extras` (count) |

## Ledger entry

`mech-weight-tier-boundary`: area mechanics, resolution accepted; decomp_ref `pokeplatinum/src/battle/battle_script.c:6815`
(+ `include/data/battle/weight_to_power.h:1`); showdown_ref `pokemon-showdown/data/moves.ts:10449` (Low Kick; Grass Knot
`:7541`); impact: a weight exactly on a limit is one tier lower in the game (Flint's Flareon, 250 hg: 40 vs 60); the
player's model and the optimizer follow the decomp; test_id `sim/test/variable_power.test.mjs`.

## Acceptance table

| Row | Content |
|---|---|
| B2 quick, pre-feature (`runs/024-evidence/b2-main`) | species, moves, items, levels, confirmation clear rate and interval, n, wall, code hashes |
| B2 quick, branch (`b2-branch`) | the same, plus the members whose set carries a variable move |
| Equal levels (A = branch winner, B = pre-feature winner, at A's levels) | n, both rates, only-A / only-B, p, verdict, mean final levels, level difference, pass/fail by FR-009 |
| Identity (reference team, 014 b2-main team; `ident-main` vs `ident-branch`) | byte-identical result.json yes/no |
