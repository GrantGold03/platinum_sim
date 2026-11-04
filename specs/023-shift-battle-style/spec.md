# Feature Specification: Shift Battle Style

**Feature Branch**: `023-shift-battle-style`

**Created**: 2026-11-04

**Status**: Draft

**Input**: User description: "Shift battle style: the simulator plays Platinum's Set style today (only the side whose Pokemon fainted sends a replacement), while the game's default is Shift: after the player KOs a foe in a single trainer battle, the game announces the trainer's next Pokemon and offers the player a free switch before it enters (FUTURE-FEATURES section 3, research recorded 2026-11-04 from decomp c248fb3f). Game rule, from the decomp (the sole reader of the option is the gate in src/battle/battle_controller_player.c:4144-4160; default Shift, src/game_options.c:31): the prompt fires when the battle is singles and not link or Frontier, the style is Shift, exactly one side is replacing (both fainting the same turn: no prompt, both replace, player first), and the player has a usable replacement (species, not an egg, HP above 0, not the active slot). The trainer AI chooses its replacement BEFORE the prompt, scored against the player's current active (BattleAI_SwitchedSlot then BattleAI_PostKOSwitchIn, battle_lib.c:7923-8095), and the prompt shows only the incoming Pokemon's name (subscript_replace_fainted.s:29-38). On yes the player's Pokemon enters first as a normal switch (stat stages reset, volatiles cleared, Natural Cure, Pursuit cannot trigger), then the foe; entry hazards in that order; entry abilities afterwards by category then speed order, not entry order (battle_lib.c:3649ff). It costs no turn: the next step is command selection. A player-only faint in a trainer battle is a forced replacement with no prompt. Elite Four and Champion battles are ordinary singles, so the prompt applies to every gauntlet battle. Set differs only in the absence of the prompt. Three stories. (1) The rule in the worker behind a battle-style option, Shift or Set, carried on the request (evaluate and optimize, CLI flag --battle-style), echoed in every result, recorded in provenance, in the job fingerprint only when non-default (the 006/018/022 rule), with a divergence-ledger entry (area mechanics, decomp_ref and showdown_ref) for the prompt itself and one for the entry-ability ordering difference, resolution stated. The vendored Showdown tree is never edited: the free switch is driven through the worker (the trainer's choice is already computed before makeChoices; Showdown's switchFlag and instaswitch carry a free switch for a healthy Pokemon). Under Set nothing changes: the v1/v2/v4 replay fixture digests (sim/test/replay_prof_a.json, digest_full and digest_logs), the determinism tests and every stored result stay byte-identical, so any new result field appears only under Shift. Unit tests pin the gate: no prompt when both faint, when only the player's faints, when the player has no replacement, when the foe's last Pokemon faints (battle over); a hand-walked battle shows the switch costs no turn, the player's Pokemon enters before the foe's, stat stages reset on the way out, and the announced species is the one that enters. (2) The player policies answer the prompt: greedy-v1 and expectimax2 (v1, v2, v4) decide stay or switch given the announced foe with their existing scoring (greedy's member score against the incoming foe; expectimax2 by cloning the root state, bringing the announced foe in, and comparing the value of staying against each bench switch), deterministic, same seed scheme, the decision and its reason in the battle log; the trainer AI is unchanged (its choice already matches the game's). A positive control shows a policy that must switch (a bench member with a guaranteed OHKO on the incoming foe and the active one walled) does switch, and one that must stay stays. (3) Acceptance, reference-first (Principle VI) with the numbers recorded (Principle V): 2,000 paired gauntlets Shift vs Set, expectimax2-v4, same seeds and opponents, 16 workers, on the reference fixture team, 014 b2-main, 014 b2-branch and bench-010 B3: clear rate under each style, McNemar exact, per-trainer pass rates, how often the prompt fired, how often the policy switched and the outcome of those battles, and the wall ratio; pairing control Shift vs Shift 0 discordant; then optimize B2 quick end to end under each style (same seed), levels and wall reported, not gated. Expected direction: Shift is never worse for the player on the game's terms; a team that is worse under Shift is a policy decision to examine, not a reason to drop the rule. After the table the user decides the default (Shift is the game's default; Set stays available). Measurements run alone on the machine with Eastern start and end times in the validation log. Deliverables: worker and policy changes with unit tests, the option end to end (CLI, request, result echo, provenance, fingerprint, state.json refusal for pre-feature checkpoints once the hash changes), two ledger entries, README (the rule, the flag, the default decision), FUTURE-FEATURES section 3 record, validation log, evidence under runs/023-evidence/ with small copies under the feature's evidence/. Out of scope: doubles, link and Frontier battles, wild battles and the "Use next Pokemon?" prompt, any change to the trainer AI or its replacement choice, any player-policy retune, editing the vendored Showdown tree, the lead feature, and any change to what qualifies."

## Overview

Every gauntlet battle today is played in Platinum's **Set** style: when a Pokemon faints, only its own side sends a
replacement, and the other side learns what entered when it enters. The game's default is **Shift**: in a single
trainer battle, after the player knocks out a foe, the game names the trainer's next Pokemon and lets the player switch
for free before it comes in. Platinum's Elite Four and Champion battles are ordinary single trainer battles, so the
prompt applies to every battle the simulator plays. It is the largest game rule the simulator does not model, and the
effect on results is unmeasured (the expectation is that Set is pessimistic: a player who can answer "Garchomp is
coming" before it arrives loses less often).

This feature adds the rule as a battle-style option, **Shift** or **Set**, carried on every evaluate and optimize
request, lets the player policies answer the prompt with the scoring they already have, keeps the trainer's behaviour
exactly as it is (the game's trainer AI chooses its replacement before the prompt, against the player's current Pokemon,
which is what the port already does), and measures the difference on paired runs. Set remains available and nothing
played under Set changes by a byte. The owner chooses the default after the acceptance table, as in features 018, 021
and 022.

### The game rule (decomp c248fb3f, read 2026-11-04)

- The option is read in one place, the gate that replaces fainted Pokemon at the end of a turn
  (`src/battle/battle_controller_player.c:4144-4160`); the default for a new game is Shift (`src/game_options.c:31`).
- The prompt fires when all of these hold: the battle is singles and neither link nor Frontier; the style is Shift;
  exactly one side is replacing (when both faint in the same turn there is no prompt, both replace, the player first);
  the player has a usable replacement (a species, not an egg, HP above 0, not the active slot).
- The trainer's replacement is chosen **before** the prompt by the trainer AI, scored against the player's current
  active Pokemon (`BattleAI_SwitchedSlot`, then `BattleAI_PostKOSwitchIn`, `battle_lib.c:7923-8095`). The prompt shows
  the trainer and the incoming Pokemon's name only (`subscript_replace_fainted.s:29-38`).
- On yes: the player's Pokemon enters first as a normal switch (stat stages reset, volatile effects cleared, Natural
  Cure applies, Pursuit cannot trigger), then the trainer's; entry hazards apply in that order; entry abilities run
  afterwards by category and then speed order, not by entry order (`battle_lib.c:3649ff`). The switch costs no turn:
  the next step is command selection.
- A player-only faint in a trainer battle is a forced replacement with no prompt. Set differs from Shift only in the
  absence of the prompt.

## Clarifications

### Session 2026-11-04

- Q: Should the expectimax player's lookahead model the Shift rule inside its search (valuing a knockout higher because a free switch follows), or should only the prompt be answered while the search's model of future turns stays as it is today? → A: Answer the prompt only; the search's model of future turns stays Set.
- Q: Where should the offer and switch counts from Shift battles appear: in every evaluation report as an aggregate, or only in the acceptance script's table? → A: Per-battle records only (the battle log and per-run result); the acceptance script aggregates them; standard reports carry only the style name.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The rule in the battle, behind a style option (Priority: P1)

The owner runs `platsim evaluate` or `platsim optimize` with `--battle-style shift` and every battle offers the free
switch exactly where the game does: after the player knocks out a foe that is not the trainer's last, when the player's
own Pokemon did not faint in the same turn and the player has a replacement. The trainer's next Pokemon is announced by
name, the player's answer (stay, or switch to a named member) is applied before the foe enters, the switch costs no
turn, and the foe that enters is the one announced. With `--battle-style set` (the default until the owner's decision)
nothing changes: every stored result, fixture digest and determinism test is byte-identical to today. The style is
echoed in every result, recorded in provenance, enters the job fingerprint only when it differs from the default, and
two divergence-ledger entries record the prompt and the entry-ability ordering difference with their resolutions.

**Why this priority**: it is the game rule itself; the other two stories make the player use it and measure it.

**Independent Test**: a fast-mode battle with a scripted player that always switches on the prompt shows, in the
battle log, the announcement, the player's switch-in, the foe's entry, and the next turn beginning with command
selection; the same battle under Set shows no prompt and the identical log to today's.

**Acceptance Scenarios**:

1. **Given** Shift, a single battle, the foe's active faints by any cause and the trainer has another Pokemon, the
   player's active Pokemon is standing and the player has a bench member with HP, **When** the turn ends, **Then** the
   player is offered the free switch with the incoming Pokemon's name, before it enters.
2. **Given** Shift and the player accepts, **When** the switch is applied, **Then** the player's new Pokemon enters
   with reset stat stages and cleared volatile effects, the announced Pokemon enters in the same exchange, no move is
   used by either side before the next command selection, and the battle log records the announcement and the
   decision.
3. **Given** Shift, **When** both active Pokemon faint in the same turn, or only the player's faints, or the player has
   no usable replacement, or the fainted foe was the trainer's last, **Then** there is no prompt and the battle proceeds
   as under Set.
4. **Given** Set (or no style given), **When** the recorded replay fixtures for the v1, v2 and v4 players and the
   determinism tests run, **Then** every digest and every result is byte-identical to the pre-feature values.
5. **Given** a result written under Shift, **When** it is read, **Then** the style is named in the result, in the
   provenance and in the evaluation summary; **Given** an optimize request under Shift, **Then** its job fingerprint
   carries the style, and a request under the default fingerprints as before this feature.
6. **Given** a checkpoint written before this feature, **When** an optimize is resumed from it, **Then** the resume is
   refused as a code change (the same rule as 018).

---

### User Story 2 - The player answers the prompt (Priority: P2)

The player policies (`greedy-v1`, `expectimax2` v1, v2 and v4) decide stay or switch when the announcement comes,
using the scoring each already has for matchups: the greedy player scores each bench member against the incoming foe
as it scores a forced replacement; the expectimax player values the position with the announced foe on the field and
compares staying against each bench switch. The decision is deterministic under the same seed scheme and is recorded
with its reason in the battle log. The trainer's side is untouched: its replacement choice, made against the player's
current Pokemon, already matches the game's.

**Why this priority**: without an answer the rule does nothing; the policy's answer is the whole effect on results.

**Independent Test**: two constructed positions. In the first, the active Pokemon cannot damage the announced foe and
a bench member knocks it out in one hit; every policy switches to that member. In the second, the active Pokemon
knocks the announced foe out in one hit and outspeeds it; every policy stays. Both decisions and their reasons appear
in the log, and repeating each position gives the same answer.

**Acceptance Scenarios**:

1. **Given** the announcement of foe X, **When** a policy is asked, **Then** it returns stay or a bench member, using
   its existing matchup scoring with X as the foe, never an item, never a fainted or the active member.
2. **Given** the must-switch control position, **When** each policy answers, **Then** it switches to the member with
   the one-hit knockout; **Given** the must-stay control, **Then** it stays.
3. **Given** the same battle twice with the same seeds, **When** the prompt fires, **Then** the answers are identical
   and the random-draw counts match.
4. **Given** Set, **When** a policy plays, **Then** its choices and draw counts are byte-identical to today's (the
   prompt code path is never reached).

---

### User Story 3 - Measured difference and the default decision (Priority: P3)

The owner sees what Shift changes on paired runs with the same seeds and opponents: the clear rate under each style,
per-trainer pass rates, how often the prompt fired, how often the policy switched and how those battles ended, the
paired test's verdict, and the wall-time ratio, on four teams (the reference fixture team, the two optimizer-built 014
B2 teams, bench-010 B3). An optimizer run of the B2 quick job under each style shows the level and wall-time effect
end to end. With the table in hand the owner decides whether Shift becomes the default.

**Why this priority**: the rule is only worth having with its effect measured, and the default is the owner's call.

**Independent Test**: the acceptance script produces one table with the rows above for the four teams and the two
optimizer runs, the pairing control shows 0 discordant pairs, and the validation log carries the Eastern start and end
times.

**Acceptance Scenarios**:

1. **Given** 2,000 paired gauntlets per team, v4 player, 16 workers, **When** Shift and Set are compared, **Then** the
   table reports, per team, the clear rate under each style with its interval, the exact paired p-value and verdict,
   per-trainer pass rates, prompt count, switch count and the outcomes of prompted battles, and the wall ratio.
2. **Given** the same team under Shift twice, **When** paired, **Then** 0 discordant pairs.
3. **Given** the B2 quick optimize under each style with the same seed, **When** both finish, **Then** the winner, its
   levels, the confirmation's clear rate and the wall time are reported side by side (reported, not gated).
4. **Given** the table, **When** the owner decides, **Then** the chosen default is set in one commit on their go, with
   the decision recorded in the README, FUTURE-FEATURES section 3 and the validation log; until then Set is the default.

---

### Edge Cases

- Both active Pokemon faint in the same turn: no prompt, both replace, the player's enters first (the game's order).
- The player's active Pokemon faints and the foe's does not: forced replacement, no prompt.
- The player has only the active Pokemon left with HP: no prompt.
- The fainted foe was the trainer's last: the battle ends; no prompt.
- The announced Pokemon is the trainer's actual replacement: the simulator must never announce one Pokemon and send
  another (the trainer's choice is fixed before the announcement, as in the game).
- The player's switched-out Pokemon loses stat stages and volatile effects as on any switch; a Pokemon that cannot
  switch under the game's rules at that moment (trapped) is not a case here, since the prompt happens between turns
  with the trapping foe fainted.
- Pursuit on the free switch: cannot trigger in the game; the simulator must not apply it.
- Entry order and entry effects after the double entry (hazards, Intimidate on both sides): the game enters the
  player's Pokemon first and orders abilities by category then speed, the engine orders both by speed with seeded ties;
  the difference is recorded in the ledger as accepted.
- A result file without a style field (written before this feature) reads as Set.
- A request naming an unknown style is refused with a clear error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every evaluate and optimize request MUST carry a battle style, `shift` or `set`, settable with
  `--battle-style` on both commands; an unknown value MUST be refused. The default is `set` until the owner's decision
  (User Story 3), then whichever the owner chooses, set in its own commit.
- **FR-002**: Under Shift, after a turn in which the foe's active Pokemon fainted (by any cause: a hit, poison,
  recoil) and the player's did not, the simulator MUST offer the player a free switch if and only if the game's gate
  holds: a single trainer battle, the trainer has another Pokemon, and the player has a usable replacement (species, not
  an egg, HP above 0, not the active slot).
- **FR-003**: The offer MUST name the trainer's actual replacement, chosen by the trainer AI before the offer against the
  player's current active Pokemon, and that Pokemon MUST be the one that enters.
- **FR-004**: An accepted switch MUST be applied as a normal switch (stat stages reset, volatile effects cleared,
  Natural Cure applied, no Pursuit) with no move used by either side before the next command selection; the engine's
  turn counter advances once, as it does for a normal replacement. The order in which the two Pokemon enter and their
  entry effects run follows the engine (speed order with seeded ties) and is recorded as an accepted divergence from the
  game's player-first order (FR-010); it is not a requirement on the simulator.
- **FR-005**: Under Set, and whenever the gate does not hold, battles MUST proceed exactly as before this feature: the
  recorded replay fixtures for the v1, v2 and v4 players (digest_full and digest_logs), the determinism tests and every
  stored result MUST be byte-identical; any new result field MUST appear only under Shift.
- **FR-006**: The vendored battle engine MUST NOT be edited; the rule is driven from the simulator's side of the engine.
- **FR-007**: Each player policy (greedy-v1, expectimax2 v1, v2, v4) MUST answer the offer with stay or a bench member
  using its existing matchup scoring with the announced foe as the opponent, deterministically under the same seed
  scheme, never an item, never a fainted or the active member; the answer and its reason MUST be in the battle log.
- **FR-007a**: The policies' lookahead MUST NOT model the Shift rule inside the search: the search's model of future
  turns stays as it is today (a knockout is valued as under Set), and the Shift decision uses the existing position
  value with the announced foe on the field. Modelling the free switch inside the search is a separate feature with
  its own paired ladder.
- **FR-008**: The trainer AI's replacement choice and every other trainer behaviour MUST be unchanged.
- **FR-009**: The style MUST be echoed in the worker's run response under Shift (absent reads as Set, so Set results
  stay byte-identical per FR-005), named in every report, its evaluation summary and its provenance, enter the
  optimizer's job fingerprint only when it differs from the default, and be part of the code change that refuses
  pre-feature checkpoints on resume.
- **FR-009a**: Offer and switch counts MUST be recorded per battle (the battle log and the per-run result, present
  only under Shift) and MUST NOT be aggregated into the standard evaluation report, summary, xlsx or web view; the
  acceptance script aggregates them from the per-run records. Standard reports carry only the style name.
- **FR-010**: The divergence ledger MUST gain two entries in the mechanics area with decomp and engine references and a
  stated resolution: the Shift prompt itself, and the entry-ability ordering after a double entry.
- **FR-011**: Unit tests MUST pin the gate (no offer when both faint, when only the player's faints, when the player has
  no replacement, when the foe's last Pokemon faints) and a hand-walked battle (no move between the offer and the next
  command selection, both Pokemon entered, stat stages reset on the way out, the announced species enters), plus the two
  policy control positions (must switch, must stay) for every player policy.
- **FR-012**: Acceptance MUST run 2,000 paired gauntlets Shift against Set with the v4 player, the same seeds and
  opponents, 16 workers, on the reference fixture team, 014 b2-main, 014 b2-branch and bench-010 B3, and report per team:
  clear rate and interval under each style, the exact paired p-value and verdict, per-trainer pass rates, the number of
  offers, the number of switches and the outcomes of those battles, and the wall ratio; plus a pairing control (Shift
  against Shift, 0 discordant) and the B2 quick optimize under each style (winner, levels, confirmation clear rate, wall;
  reported, not gated). Measurements run alone on the machine with Eastern start and end times in the validation log.
- **FR-013**: The README MUST state the rule, the flag and the default decision; FUTURE-FEATURES section 3 MUST record
  the outcome; evidence lives under `runs/023-evidence/` with small copies under the feature's `evidence/`.

### Key Entities

- **Battle style**: `shift` or `set`; a request field, a result field, a provenance field, a fingerprint field when
  non-default.
- **Free-switch offer**: the moment between turns when the trainer's replacement is named and the player may switch;
  carries the announced species and the player's answer (stay or member) with its reason; appears in the battle log
  and, as counts per battle, in the per-run result under Shift only (never aggregated in the standard report).
- **Divergence entries**: `mech-shift-prompt` and `mech-shift-entry-order` (names indicative), area mechanics, with
  decomp and engine references and a resolution.
- **Acceptance table**: per team and style the clear rate with interval, paired p-value, per-trainer rates, offer and
  switch counts, prompted-battle outcomes, wall ratio; plus the control row and the two optimizer runs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Under Set, the three recorded replay fixtures (v1, v2, v4) and the determinism tests pass with
  pre-feature digests, and the stored web fixture result is unchanged: zero bytes differ.
- **SC-002**: Under Shift, the gate unit tests and the hand-walked battle pass: the offer appears in exactly the four
  conditions of the game and in none of the four exclusions; the switch costs zero turns.
- **SC-003**: Every player policy passes both control positions, and repeated runs give identical answers and draw
  counts.
- **SC-004**: The acceptance table is complete for the four teams and the optimizer pair, with 0 discordant pairs in the
  control, and the validation log carries start and end times.
- **SC-005**: The ledger validates with the two new entries, and the README names the rule, the flag and the default.
- **SC-006**: The owner has decided the default and the decision is recorded; the merge gate (Node suite and the full
  pytest suite) is green on the final code.

## Assumptions

- The direction of the effect is not gated: Shift is the game's rule, so a team that scores lower under Shift points at
  the policy's answer (to be examined in the log), not at the rule. The acceptance records the numbers either way.
- The entry-ability ordering difference (engine by entry order, game by category then speed) is expected to be accepted
  as a documented divergence; the planning stage may correct it instead if the correction is small and stays outside the
  vendored engine.
- The trainer's replacement choice is computed before the player's next decision today, against the player's current
  active Pokemon, which is the game's order; nothing in that choice changes.
- The reference-first rule of Principle VI applies to the policy's answer: it uses the existing scoring at the existing
  search depth, no cheaper shortcut; a faster approximation, if ever wanted, is a later feature with its own ladder.
- The default stays `set` during development so every test and fixture is unchanged; flipping the default is one commit
  on the owner's go after the table, as in 018, 021 and 022, and changes the code fingerprint (pre-feature checkpoints
  already stop resuming with this feature's code change).
- Results and checkpoints written before this feature read as Set.
- Acceptance pool time is about one hour: four teams at 2,000 paired gauntlets (Shift adds the policy's answer per
  prompt, so Shift runs are somewhat slower), the control, and two B2 quick optimizer runs of about six minutes each.
- Out of scope, as given: doubles, link and Frontier battles, wild battles and the "Use next Pokemon?" prompt, any change
  to the trainer AI or its replacement choice, any player-policy retune, edits to the vendored engine, the lead feature,
  and any change to what qualifies.
