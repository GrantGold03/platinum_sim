# Contract: the variable-power helper and greedy-v1's scoring

## `sim/variable_power.mjs`

```js
export const WEIGHT_TO_POWER;                 // [[100,20],[250,40],[500,60],[1000,80],[2000,100],[0xFFFF,0xFFFF]]
export function speciesWeightHg(speciesConst); // cached; data.json + speciesproc.c overrides (moved from calcdamage)
export function weightTierPower(weightHg);     // first limit >= weight, else 120
export function returnPower(friendship);       // Math.trunc(f * 10 / 25)
export function frustrationPower(friendship);  // Math.trunc((255 - f) * 10 / 25)
export function gyroBallPower(a, d);           // a === 0 ? 0 : Math.min(150, 1 + Math.floor(25 * d / a))
```

`sim/ai/calcdamage.mjs` re-exports `WEIGHT_TO_POWER` and `speciesWeightHg`; its AI switch calls the helper and keeps its
throw on missing speeds and zero attacker speed (u32 arithmetic preserved). `sim/policy/expectimax2.mjs` `variablePower`
calls the helper for the four effects. Both callers' outputs are unchanged (replay fixtures, `ai_cmds_damage` tests).

## greedy-v1 (`sim/policy/greedy.mjs`)

`expectedDamage(gd, battle, attacker, foe, sdId)`: for `MOVE_RETURN`, `MOVE_GRASS_KNOT`, `MOVE_LOW_KICK`, `MOVE_GYRO_BALL`
(matched by the decomp move constant of `sdId`), `power` is `returnPower(attacker.happiness ?? 255)`,
`weightTierPower(speciesWeightHg(ENUMS.species[foe.species.num]))`, or `gyroBallPower(attacker.storedStats.spe,
foe.storedStats.spe)`, and the damage is `calcDamage(fromShowdown(battle, attacker, foe, sdId, { power }))`; all other
moves with data power <= 1 still return 0. `moveScores`, `memberScore` and `shiftChoice` inherit it. The policy keeps the
name `greedy-v1` because no fixture team carries the four moves (FR-003).
