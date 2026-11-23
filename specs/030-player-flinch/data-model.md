# Data Model: The battle player models flinch

- **Model Pokemon state** gains `flinched` (boolean, false by default; set only within a turn by a landing flinch move whose target
  moves later; cleared when the target's move is lost, and at end of turn). It is not part of the end-of-turn state signature
  because it is always false there.
- **Flinch chance** (per hit): `rec.effect_chance` (x2 for the attacker's Serene Grace, capped at 100); 0 when the target fainted, is
  behind a substitute, has Inner Focus (unless the attacker has Mold Breaker), or does not move later this turn.
- **Option** `X.opts.flinch` (on in `V4_OPTS` only; off for v1 and v2; `false` = today's play). Candidate syntax `expectimax2-v4?flinch=0|1`.
