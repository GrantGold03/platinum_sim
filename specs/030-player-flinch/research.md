# Research: The battle player models flinch

## R1. The game's rule (decomp, read 2026-11-23)

- `battle_script.c:8369` `BtlCmd_CheckEffectActivation`: effect chance = the move's `effectChance`, doubled for the attacker's Serene
  Grace; the roll `rand % 100 < chance`, and the target must have HP.
- `subscript_flinch_mon.s`: no flinch if the target **moved this turn** (`IfMovedThisTurn`), is behind a **substitute**, or has
  **Inner Focus** (ignorable: Mold Breaker gets through); Shield Dust is checked here only for the indirect (held item) flinch.
- `battle_controller_player.c:2528` `CHECK_STATUS_STATE_FLINCH`: when the flinched Pokemon tries to move, the flag is cleared and the
  move is lost; this check comes after sleep and freeze in the status-check order. `battle_lib.c:2234` clears flinch at turn end.
- `subscript_flinched.s:10`: Steadfast raises Speed one stage.
- **Decision**: the model applies the flinch only through `foeMovesLater` (the target's action this turn is a move still to come);
  this is exactly "has not moved this turn" for the model's turn structure, and it implements the owner's rule (no flinch chance when
  the flinch move's user moves second). A switch or item use by the target is not a move, so no flinch applies.

## R2. Which moves

- Flinch effects: `FLINCH_HIT`, `FLINCH_BURN_HIT`, `FLINCH_FREEZE_HIT`, `FLINCH_PARALYZE_HIT`, `FLINCH_DOUBLE_DAMAGE_FLY_OR_BOUNCE`,
  `FLINCH_MINIMIZE_DOUBLE_HIT`, `CHARGE_TURN_HIGH_CRIT_FLINCH` (hitting turn only), `ALWAYS_FLINCH_FIRST_TURN_ONLY` (Fake Out, 100).
  All are single-hit moves, so the multi-hit question of the spec does not arise. The Fang moves' second effect (burn, freeze,
  paralysis) stays unmodelled as today (the player ignores secondary status chances); only their flinch is added.
- **Decision**: a set of these effect names; chance from `rec.effect_chance` (Air Slash 30, Iron Head 30, Dark Pulse 20, the Fangs
  10, Zen Headbutt 20, Extrasensory 10, Dragon Rush 20, Fake Out 100).

## R3. Fake Out

- Game: fails unless its user has just come out (first turn out). Engine: `onTry` fails when `activeMoveActions > 1`.
- **Decision**: the model fails Fake Out when the user has been out for a full turn already (`activeTurns > 0`); the engine
  check confirms the two agree for a member that has just switched in, led, or been sent out after a faint. Today the model treats
  Fake Out as an ordinary hit every turn (a pre-existing gap fixed here because the flinch makes it matter).

## R4. Engine checks (Node tests against the vendored engine)

- A faster flinch move flinches a slower target (seeded so the roll succeeds; the target's move does not happen, `cant ... flinch`).
- A slower flinch move never flinches (the target already moved).
- Inner Focus blocks; a substitute blocks; Steadfast raises Speed; Fake Out fails on the second turn.
- Each difference from R1 goes to the ledger with its League impact (no League Pokemon has Inner Focus, Serene Grace or Substitute).

## R5. Speed measurement (SC-004)

- The paired script runs arm A then arm B in one worker pool; in 029 the first run of a pool was slower whatever the policy
  (identical play: 11.3 vs 14.9 gauntlets/s). **Decision**: speed comes from two 500-pair runs on the reference team with the arms in
  both orders; each arm's speed is the mean of its two positions. The 2,000-pair checks report clear rates only.

## R6. Which teams and controls

- Reference team (`ref`), benchmark team (`bench`), B2 winner (`b2main`) through the paired script's named teams; 2,000 pairs each,
  model (`expectimax2-v4`) against reference (`expectimax2-v4?flinch=0`).
- Pairing control: `--self` on the reference team, 200 pairs (0 discordant expected). Conditions control: the reference arm's clear
  rate on B2 within the optimizer's interval for that team (0.944 [0.920, 0.961]).
- A supported loss (two-sided McNemar, p < 0.05, more reference-only clears) on any team stops the feature (FR-008).

## R7. Acceptance on both codes

- 029's acceptance script with the identity rows expected to differ (each difference reported); the candidate snapshot must be
  identical (the optimizer is untouched); equal-level pairs with the 024 rule on the B2 winners.
