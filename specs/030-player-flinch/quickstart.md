# Quickstart: validate feature 030

1. `cd sim && node --test test/flinch.test.mjs`: engine-against-game cases and the model's cases pass.
2. `cd sim && node --test`: the full Node suite passes; the replay test passes with the knob off.
3. Player check (alone, about 45 min): 029's `paired_policies.py --battle-style shift --a expectimax2-v4 --b 'expectimax2-v4?flinch=0'`
   on `ref`, `bench`, `b2main`, 2,000 pairs each; `--self` 200 pairs; speed in both orders, 500 pairs each. Expected: no supported loss;
   at least 75% of the reference's speed.
4. Acceptance on both codes (029's script adapted): the candidate snapshot identical; the equal-level comparison passes.
