# Research: H4, King's Rock / Razor Fang

## R1. The game's rule and the engine checks

- Game: `CheckExtraFlinch` (`battle_controller_player.c:4630`): holder's hold effect `HOLD_EFFECT_SOMETIMES_FLINCH`, the move has
  `MOVE_FLAG_TRIGGERS_KINGS_ROCK`, the target took damage this hit and has HP, no `MOVE_STATUS_NO_EFFECTS`, `rand % 100 < param (10)`;
  then `subscript_flinch_mon.s` (moved this turn, substitute, Inner Focus, and Shield Dust for this indirect flinch). Called from the
  one-hit after-move step and from `MULTI_HIT_EXTRA_FLINCH` after each hit.
- Engine (Gen 4 mod): adds `{chance: 10, volatileStatus: 'flinch'}` to the move's secondaries for the 202 listed moves; secondaries
  run on every hit; Shield Dust and substitutes block secondaries; Inner Focus blocks the volatile; a flinch on a Pokemon that has
  moved has no effect.
- **Decision**: Node tests (030's pattern: seeds scanned for the rate, `|cant|...|flinch`, deduped log): (a) single-hit affected move,
  faster holder: flinch rate over 400 seeds within a 99% interval of 10%; (b) a multi-hit move (Bone Rush or Double Kick): more than
  one roll per use (the rate over uses of a 2-hit move near 19%); (c) Air Slash with the item: rate near 1 - 0.7 x 0.9 = 37%; (d)
  substitute, Inner Focus, Shield Dust, slower holder: never. Differences ledgered.

## R2. One option, two copies

- `_item_for_effect` picks one item (`kings_rock`, 1 copy). `realize` checks copies per item constant.
- **Decision**: an equivalence group `{kings_rock: (kings_rock, razor_fang)}` in `candidates`; candidates name `kings_rock`; in
  `realize`, when a member's item is in a group and its copy is not affordable, the next member of the group that is affordable is used
  and the realized member records it; the report shows the actual item. A third holder is refused. Team-gated copies (Gliscor uses
  the Razor Fang) come from `team_item_copies` unchanged.
- **Alternative rejected**: offering both keys (doubles the screen's item deviations for identical options; the dominance rule).

## R3. Where the item is appended

- **Decision**: in `extra_item_candidates`, after the resist berries, `kings_rock` when the set has at least one move with
  `MOVE_FLAG_TRIGGERS_KINGS_ROCK`; not for sets without one.

## R4. The multi-hit extra set

- 025's item-conditioned extras re-value moves under the item; the move values are damage only and do not change with a flinch item,
  so that path would only re-find existing sets.
- **Decision**: kind `flinch_item`: if the member's candidate moves include an affected multi-hit move, take its best base set (the
  variant's first-ranked base set), swap the member's highest-scoring affected multi-hit move (ties: the move key) in for the set's
  lowest-scoring move (ties: the lowest score, then the move key) (unless already in the set), and offer the
  result held with `kings_rock` if it is not already an offered set; at most one per member variant; 027's dead-move rule: no extra
  if the swapped-in move is dead in the League (its reason recorded in `dropped_extras`).

## R5. Acceptance

- 029's scripts, `NEW_ITEMS = {kings_rock, razor_fang}`; attribution allows `items_extra` to gain `kings_rock` at its end, and new
  extras of kind `flinch_item` (a defect otherwise); identity evaluations identical (no player change); equal levels per the 024 rule.

## R6. The multi-hit measurement (report only)

- Snapshot species that can learn an affected multi-hit move: Infernape and Weavile (Fury Swipes), Lucario (Bone Rush), Chatot (Fury
  Attack), Blissey and Clefable (Double Slap) (learnset read; legality confirmed by the candidates).
- **Amended at implementation (owner's decision 2026-11-24)**: with the same-type swap and 027's rule, the only snapshot member whose
  multi-hit move stays live is Torterra (Bullet Seed in place of Wood Hammer; B5); the measurement uses B5 quick and Torterra.
- **Original decision (superseded)**: run B3 quick on the branch (B3 includes Lucario); if Lucario is in the winner, measure the winner with Lucario on its
  `flinch_item` extra set holding the flinch item against the same set with its usual (first) item (both arms the same set; the
  team therefore differs from the B3 winner itself only in that member's set), 2,000 pairs under Shift, fresh
  seeds, `--self` control; else the snapshot's best multi-hit user in its team's winner. Report both rates and the verdict.
