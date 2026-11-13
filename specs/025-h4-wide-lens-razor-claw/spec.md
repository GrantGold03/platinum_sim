# Feature Specification: H4, Wide Lens and Razor Claw

**Feature Branch**: `025-h4-wide-lens-razor-claw`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "H4, the first held-item group after H3: the optimizer offers the two items the battle player already models and the game provides before the Champion, Wide Lens (hold effect ACCURACY_UP 10, unlimited copies: Game Corner and wild held items) and Razor Claw (hold effect CRITRATE_UP, 2 pre-Champion copies: a hidden item and an item ball), chosen by decomp hold effect never by name, as feature 014 did for Expert Belt and Wise Glasses. Scope Lens (the same effect, 0 copies), Zoom Lens (ACCURACY_UP_SLOWER, decomp param 20, not modelled: it needs the move-second condition in the player's hit chance), Shell Bell, Lum Berry, King's Rock and Razor Fang, Metronome, Quick Claw and Focus Band stay out: each needs a player-model addition or has no copy, and they are the next groups (FUTURE-FEATURES section 0). Rules carried from the dominance assessment (.specify/assessments/dominance-list/decision.md): this feature is the first to touch the candidate lists, so it also widens the R8 dominance rule in candidates.py with PP and a small decomp-backed effect cost class (charge turns, recharge, recoil, self stat drops, crash on miss, lock-in, delayed hit; two different secondaries incomparable), pinned by the three positive pairs (Earthquake over Dig, Waterfall over Dive, Rock Climb over Take Down) and the negative controls (Fire Blast against Flamethrower, Close Combat against Brick Break), with the dropped move named in the pruned map as R8 drops are. Three stories. (1) The items offered, additively: for every moveset whose strongest attack (by summed candidate value) has accuracy below 100, the ACCURACY_UP item with copies is appended to that moveset's item candidates; for every moveset with an attack, the CRITRATE_UP item with copies is appended; today's item candidates keep their order and come first (the baseline's first item unchanged); the single-use filter still applies; copy limits hold (a unit test shows a third Razor Claw is refused on a team when two members already hold one, as 014 tested Expert Belt); and, the 024 lesson, the optimizer's screen keeps its capped 81-team list exactly today's and screens the new item options beyond the cap as single-slot deviations of the baseline, generalising 024's extra-set mechanism to any appended option, so today's screened teams are a prefix of the branch's. The player's model, the damage model, the ledger and the validator are unchanged by the items; the dominance widening changes candidates.py only, and the B1 to B5 candidate lists are re-snapshotted with the differences listed per member (expected: only the dominated moves removed from pools and ranked lists, Lumineon's Dive leaving its B5 set). (2) The reports state the average-Pokemon assumptions: evaluate and optimize provenance gain a member_defaults block (nature Hardy, IVs 15, EVs 85, friendship 255, with one line on why: the average Pokemon, constitution v1.5.0) and the xlsx provenance sheet shows it; the reader-facing summary names the player policy as today; NPC-trade members keep the values the game fixes and the report says so for them. (3) Acceptance, the 024 protocol, alone on the machine with Eastern times, under today's defaults (v4, adaptive 0.98, Shift): the pre-feature side run on the branch before any code change (B2 quick with --seed 014-b2, the two identity evaluations, the candidate and item snapshot for the six B2 species and for B1 to B5 at their recorded levels), then the branch side: B2 quick, the screen-prefix check, the identity comparison with the volatile fields and the new member_defaults block removed, the equal-levels paired check on 2,000 gauntlets by expectimax2-v4 with the FR-009 rule of 024 (no supported loss at alpha 0.05, the branch winner's expected average final level at most one level above today's), and a table of which members took Wide Lens or Razor Claw; plus, for each of B1 to B5, the per-member diff of movesets, items and pools against the snapshot. Expected direction: the winner equal or better; where no member's strongest attack misses, the items are offered and not chosen, which is a valid outcome recorded as such. Deliverables: candidates.py (the two item rules, the dominance widening and its tests), the screen generalisation in run.py, the provenance block in evaluate.py and run.py with report tests, the acceptance script adapted from 024 under specs/025-*/scripts/, README (the H4 block, the items offered and why, the not-yet list with reasons, the dominance rule and its controls, the assumptions block), FUTURE-FEATURES sections 0 and 8, validation log, evidence under runs/025-evidence/ with small copies under the feature's evidence/. Merge gate: the Node suite and the full pytest suite. Out of scope: any change to the player's model (Zoom Lens, Shell Bell, Lum Berry, flinch, Metronome count across plies, Quick Claw's chance), the Choice items, items with zero pre-Champion copies, item dominance beyond the recorded Lum rule (which lands with the berry group), the archived 007 to 010 code, and any change to what qualifies."

## Overview

The optimizer chooses each member's held item from a short list: the best HP berry, a type boost for the strongest attack,
Leftovers when the team can hold it, and the damage boosters feature 014 added. Two items the game provides before the Champion
and the battle player already understands are never offered: Wide Lens, which raises accuracy by a tenth (the player's hit
chance already applies it), and Razor Claw, which raises the critical-hit stage (the player's crit chance already applies it).
A competent player with a Fire Blast or Stone Edge user would try a Wide Lens; the tool cannot.

This feature offers those two, by hold effect and within their copy counts, appended after the existing item candidates, and
lets each item re-value the member's moves: with the lens the accuracy penalty shrinks, so a Fire Blast set can beat a
Flamethrower set; with the claw, high-critical-ratio moves gain more. The move value also gains a critical-hit term for every
move, so today's rankings move where a high-crit move competes (the owner's decision: a competent player counts crits). Because it is the first feature to touch the candidate lists since the dominance assessment, it also carries
that assessment's two rulings: the R8 dominance rule gains the two axes it lacked, so Dig, Dive and Take Down stop occupying pool
slots beside Earthquake, Waterfall and Rock Climb; and the screen screens every appended option beyond its cap, the lesson of
feature 024. The reports gain the average-Pokemon assumptions the constitution (v1.5.0)
says every report states. Acceptance is the 024 protocol on both codes, with a merge blocked by a supported loss.

| Item | Hold effect (decomp) | Pre-Champion copies | Player model today |
|---|---|---|---|
| Wide Lens | `HOLD_EFFECT_ACCURACY_UP` 10 | unlimited (Game Corner; wild held items) | hit chance × 1.1 |
| Razor Claw | `HOLD_EFFECT_CRITRATE_UP` | 2 (a hidden item, an item ball) | crit stage +1 |
| Scope Lens | `HOLD_EFFECT_CRITRATE_UP` | 0 | crit stage +1 |
| Zoom Lens | `HOLD_EFFECT_ACCURACY_UP_SLOWER` 20 | unlimited | not modelled (move-second condition) |

## Clarifications

### Session 2026-11-13

- Q: Which movesets should get Wide Lens as an item candidate: only those whose strongest attack can miss, or any moveset with an attack that can miss? → A: Neither alone: choosing Wide Lens re-evaluates the member's moves. With the lens, the accuracy penalty on a move such as Fire Blast against Flamethrower shrinks, so the member's attacks are re-valued with the lens's accuracy boost and the sets that win under that valuation are offered as extra candidate sets paired with the lens; the lens is also offered on today's sets that contain an attack with accuracy below 100.
- Q: Should Razor Claw also re-evaluate the member's moves, favouring high-critical-ratio moves, or only be appended as an item to today's sets? → A: Re-evaluate, and also add the crit term to today's move value for every move at the base stage, so high-crit moves rank higher everywhere; today's lists change by that term, so this feature drops the pre-feature prefix guarantee and lists the differences instead.
- Q: In the dominance rule's effect cost class, should a move's self-inflicted stat drop (Close Combat, Superpower, Overheat, Draco Meteor, Psycho Boost) count as a cost? → A: Yes, count self stat drops as costs; and make sure the battle player's model knows that all stat changes are reset on a switch, so the cost is priced as lasting only until the user switches.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Wide Lens and Razor Claw offered, the lists kept honest (Priority: P1)

The owner runs `platsim optimize` and, where a member's moveset has an attack that can miss, Wide Lens is among that
moveset's item candidates; Razor Claw is among the candidates of every member with an attack, at most two members holding one;
both are appended after the existing item candidates. Each item also re-values the member's moves (the lens's accuracy boost,
the claw's crit stage) and offers the sets that win under it as extra sets paired with the item; the move value gains a
critical-hit term for every move, so high-crit moves rank higher everywhere. The dominance rule now drops a
two-turn, recharge, recoil, self-dropping, crash-on-miss, lock-in or delayed move when a same-type, same-category move is at
least as good on power, accuracy, priority and PP and strictly better on one, naming the winner in the pruned map. The screen's
capped list is built from the base options by today's rule; every appended option is screened beyond the cap.

**Why this priority**: it is the capability and its two guards; the other stories report and measure it.

**Independent Test**: unit tests on the six B2 species and the B1 to B5 members: the item lists are today's lists followed by
the new items under the stated conditions; a third Razor Claw is refused when two members hold one; the dominance controls
(three positive pairs, the negative pairs) decide as stated; every difference between the re-snapshotted candidate lists and
the pre-feature snapshot is attributed to a dominated move, the crit term or an appended item or set; the screen's capped list
on a B2 quick run follows today's rule from the base options with the appended options beyond the cap.

**Acceptance Scenarios**:

1. **Given** a moveset containing an attack with accuracy below 100 and a Wide Lens copy, **When** item candidates are
   built, **Then** Wide Lens is appended after today's candidates; **Given** every attack hits at 100 or never misses, **Then**
   it is not offered on that set; **Given** a member whose Fire Blast loses to Flamethrower on accuracy today, **When** the
   lens re-values the attacks, **Then** a set carrying Fire Blast is offered as an extra set paired with Wide Lens, and today's
   Flamethrower set is unchanged.
2. **Given** a moveset with an attack and a Razor Claw copy, **When** item candidates are built, **Then** Razor Claw is
   appended; **Given** two members already hold Razor Claw, **When** a third is realized, **Then** the repair step refuses it
   and falls back as 014's copy test does for Expert Belt.
3. **Given** a member who learns both Earthquake and Dig, **When** candidates are built, **Then** Dig is dropped with the reason
   "dominated by MOVE_EARTHQUAKE" and never reaches the pool; **Given** Fire Blast and Flamethrower, or Close Combat and
   Brick Break, **Then** neither is dropped.
4. **Given** the B2 quick request on today's code and on the branch, **When** both screens are built, **Then** the branch's
   capped list is built from its base options by today's rule, the appended options follow beyond the cap, and the acceptance
   reports how many of today's 81 screened teams reappear.
5. **Given** the pre-feature candidate snapshot of B1 to B5, **When** the branch's lists are compared, **Then** every difference
   is attributed to a dominated move removed, a ranking moved by the crit term, or an item or item-conditioned set appended,
   listed per member; any other difference fails the test.

---

### User Story 2 - The reports state the average-Pokemon assumptions (Priority: P2)

Every evaluate and optimize report records, in its provenance, the member defaults the constitution names: nature Hardy, IVs
15, EVs 85, friendship 255, with the one-line reason (the average Pokemon, constitution v1.5.0); the spreadsheet's provenance
sheet shows the block; NPC-trade members, whose values the game fixes, are named as exceptions in the same block.

**Why this priority**: the constitution says every report states the assumptions; it is small and independent of the items.

**Independent Test**: a report round-trips the block; the xlsx provenance sheet shows it; a report written before this feature
reads with the block absent, not defaulted.

**Acceptance Scenarios**:

1. **Given** an evaluate or optimize run, **When** result.json is written, **Then** `provenance.member_defaults` carries nature,
   IVs, EVs, friendship, the reason and the list of members whose values the game fixes instead.
2. **Given** a pre-feature result.json, **When** it is read, **Then** the block is absent and nothing is invented.

---

### User Story 3 - Not worse on B2, measured on both codes (Priority: P3)

The owner sees the 024 protocol's table: the B2 quick winner on today's code and on the branch (moves, items, levels,
confirmation clear rate, wall), which members took Wide Lens or Razor Claw, the screen-prefix check, the identity evaluations of
two unaffected teams, the equal-levels paired verdict, and the per-member diff of B1 to B5 candidate lists against the
pre-feature snapshot.

**Why this priority**: the reference-first check that gates the merge.

**Independent Test**: the acceptance script's table is complete; the identity rows are identical once the volatile fields and
the new provenance block are removed; the equal-levels row passes the 024 FR-009 rule or the cause is recorded and the merge
blocked.

**Acceptance Scenarios**:

1. **Given** the pre-feature side run on the branch before any code change, **When** the branch side runs after the code,
   **Then** the table compares both winners and names the members holding a new item.
2. **Given** the two winners at the branch winner's levels on 2,000 paired gauntlets by expectimax2-v4, **When** compared,
   **Then** no supported loss (alpha 0.05) and the branch winner's expected average final level at most one level above today's;
   otherwise the merge is blocked until the cause is found.
3. **Given** the reference team and the 014 b2-main team, **When** evaluated on both codes with the same request, **Then** the
   reports are identical after removing the code-version and ledger fields and the new `member_defaults` block.
4. **Given** no member's strongest attack can miss, **When** Wide Lens is offered and not chosen, **Then** the table records
   that outcome as valid.

---

### Edge Cases

- A member whose strongest attack never misses (accuracy 0 in the data, "never misses"): Wide Lens is not offered to that
  moveset.
- Razor Claw's two copies on a six-member team: at most two members hold one; the repair step resolves conflicts in candidate
  order as for Expert Belt.
- Scope Lens: the same hold effect with zero copies is never offered (the copy count decides, not the name).
- Zoom Lens: a different hold effect the player does not model; not offered, listed in the README with the reason.
- The dominance rule and the setup variant: a dominated move is dropped from the attack pool and the ranked combos; the
  setup variant's best three attacks are chosen from the pruned pool as today.
- A dominated move that is the member's only attack of its type: still dropped, since the dominating move of the same type
  is legal for that member by definition.
- Two moves with different secondary effects (Thunderbolt and Discharge): incomparable, both kept.
- The crit term and dominance: a high-critical-ratio move is a secondary effect in the dominance rule (positive class), so
  Slash is not dominated by a plain Normal move of equal power; the crit term only changes rankings.
- A member with Super Luck or Sniper: the ability's effect on crits is not counted in the move value in this feature; the
  battle player's model already handles it in battle.
- Self stat drops and switching: Close Combat's defence drops vanish when the member switches out; the battle player's model
  resets stat stages on its modelled switches, so a Close Combat user that switches after a KO (the Shift free switch) carries
  no penalty; the dominance cost class is a ranking heuristic and never changes battle play.
- An item appended to a moveset of an extra (024) set: the extra set keeps its first item in the screen, as today; the new
  items join its candidate list for the repair step.
- The screen with both kinds of appended options (024 extra sets and new items): all appended options are screened beyond the
  cap, in a fixed order (extra sets first, then item deviations), so the result is independent of worker count.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Items MUST be chosen by decomp hold effect, never by name, each only when a pre-Champion copy exists under the
  active legality options: the `ACCURACY_UP` item for every moveset containing an attack with accuracy below 100 and above 0
  (0 means never misses), and the `CRITRATE_UP` item for every moveset with an attack.
- **FR-001a**: Choosing an item MUST re-evaluate the member's moves under that item: for the `ACCURACY_UP` item, the member's
  attacks are re-valued with the item's accuracy boost applied to each move's accuracy (capped at 100), a pool and four-move
  sets are ranked under that valuation exactly as today's are, and up to K sets that differ from today's sets are appended as
  item-conditioned extra sets, each paired with the item, diverse among themselves (the 024 extras rule); today's sets and
  their item lists are unchanged by this. A set that wins only because the lens shrinks the accuracy penalty (Fire Blast over
  Flamethrower, Stone Edge over Rock Slide) is therefore offered with the lens and never without it. For the `CRITRATE_UP`
  item the same mechanism applies with the item's crit stage: up to K claw-conditioned extra sets, paired with the item.
- **FR-001b**: The move value MUST gain a critical-hit term for every move: expected damage × (1 + crit chance), where the crit
  chance follows the game's stage table (stage 0: 1/16, stage 1: 1/8, stage 2: 1/4, stage 3: 1/3, 4 and above: 1/2; a critical
  hit doubles damage) and the stage is the move's high-critical-ratio effect (+1) plus the held item's crit stage when the
  valuation is item-conditioned (+1 for `CRITRATE_UP`); abilities that raise the stage are not counted in this feature. This
  changes today's rankings wherever a high-crit move competes, by design (clarification 2).
- **FR-002**: The new items MUST be appended after the existing item candidates for every moveset (the existing candidates in
  their existing order first, so a set's first item is the same kind of choice as today); the single-use filter MUST still
  apply; copy limits MUST hold through the existing repair step, with a unit test refusing a third Razor Claw.
- **FR-003**: The screen MUST build its capped candidate list from the base options (the non-extra sets with their item
  lists) by today's rule and MUST screen every appended option (the 024 extra sets, the item-conditioned extra sets and the new
  item options on base sets) beyond the cap as single-slot deviations of the baseline, in a fixed order. Because the crit term
  changes the base lists (FR-001b), the capped list is not expected to equal the pre-feature run's; the acceptance MUST report
  how many of the pre-feature run's 81 screened teams reappear and list the base-list differences per member.
- **FR-004**: The R8 dominance rule MUST gain PP and an effect cost class as axes: a move is dropped when another legal move of
  the same type and category is at least as good on power, accuracy, priority, PP and effect (a cost effect loses to plain or
  to a secondary; equal effects compare by chance; two different secondaries are incomparable) and strictly better on one; the
  cost class is a small table of decomp effects (charge turns, recharge, recoil, self stat drops including the two-stage
  special drops and the physical ones such as Close Combat, Superpower and Hammer Arm, crash on miss, lock-in, delayed hit)
  with each entry's reason; the dropped move MUST be named in the pruned map with the winner.
- **FR-004a**: The self-stat-drop cost is a candidate-ranking heuristic; in battle the player's model MUST price a self drop as
  lasting only until the user switches, because the game resets every stat stage on a switch. A Node test MUST assert that the
  battle player's model resets all stat stages of the switched-out member (the engine's reset is already asserted by feature
  023's hand-walk); no change to `sim/` code is expected, the test pins what is already there.
- **FR-005**: Unit tests MUST pin the dominance controls: Earthquake over Dig, Waterfall over Dive, Rock Climb over Take Down
  dropped; Fire Blast against Flamethrower, Close Combat against Brick Break, Thunderbolt against Discharge kept; and, for the
  self-drop cost, a constructed pair where a same-type plain move of equal power dominates a self-dropping one (dropped) and
  the real Close Combat against Brick Break (kept: Brick Break's power is lower).
- **FR-006**: The B1 to B5 candidate lists (movesets, pools, ranked combos, items) MUST be snapshotted on the pre-feature code
  and compared on the branch, with the per-member differences listed and attributed to one of three causes: a dominated move
  removed (FR-004), a ranking moved by the crit term (FR-001b), or an item or item-conditioned set appended (FR-001, FR-001a);
  a difference with none of these causes is a defect.
- **FR-007**: Every evaluate and optimize report MUST carry `provenance.member_defaults` (nature, IVs, EVs, friendship, the
  reason, the members whose values the game fixes) and the xlsx provenance sheet MUST show it; a pre-feature report reads with
  the block absent.
- **FR-008**: The player's model, the damage model, the ledger and the validator MUST be unchanged; `sim/` MUST be untouched
  (the sim code hash unchanged).
- **FR-009**: Acceptance MUST follow the 024 protocol, alone with Eastern times, under today's defaults: the pre-feature side on
  the branch before any code change (B2 quick, the two identity evaluations, the candidate and item snapshot for B2's six
  species and for B1 to B5 at their recorded levels), then the branch side (B2 quick, the screen-prefix check, the identity
  comparison with the volatile fields and `member_defaults` removed, the equal-levels check on 2,000 paired gauntlets by
  expectimax2-v4, the table of members holding a new item, the per-member diffs).
- **FR-010**: The feature MUST NOT merge if the equal-levels comparison shows a supported loss (alpha 0.05) or the branch
  winner's expected average final level more than one level above today's; the cause MUST be found first.
- **FR-011**: The README MUST state the H4 block (the items and why, the not-yet list with reasons, the dominance rule and its
  controls, the assumptions block); FUTURE-FEATURES sections 0 and 8 MUST be updated; evidence lives under `runs/025-evidence/`
  with small copies under the feature's `evidence/`.

### Key Entities

- **Item rule**: (hold effect, condition on the moveset, copy requirement) → appended candidate; two rules in this feature.
- **Item-conditioned extra set**: a four-move set ranked under the item's effect on move value (the lens's accuracy boost),
  appended after today's sets and paired with that item; counted in `extras` beside the 024 variable-power extras.
- **Effect cost class**: a table of decomp effect constants that count as a cost in dominance, each with its reason.
- **Dominance drop**: (dropped move, winner, axis) recorded in the pruned map.
- **Appended option**: a (variant, moveset, item) choice screened beyond the cap; two kinds: 024 extra sets, new item deviations.
- **member_defaults**: nature, IVs, EVs, friendship, reason, fixed-value members; a provenance block.
- **Acceptance table**: both B2 winners, the new-item members, the screen prefix, the identity rows, the equal-levels row, the
  per-member snapshot diffs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the B1 to B5 members, Wide Lens appears in the item candidates of every moveset containing an attack that
  can miss and of none whose attacks all hit; the lens-conditioned extra sets appear where the lens changes the ranking and
  carry the lens; Razor Claw in every moveset with an attack; claw-conditioned extra sets where the claw changes the ranking;
  every list difference from the pre-feature snapshot attributed to one of the three causes of FR-006.
- **SC-002**: The dominance controls pass; on the benchmark, the 17 dominated moves the assessment's probe found are dropped
  and no other move is.
- **SC-003**: The branch's screen on B2 quick is built by today's rule from the base options with every appended option
  beyond the cap; the overlap with the pre-feature run's 81 teams is reported.
- **SC-004**: The identity evaluations are identical after removing the volatile fields and `member_defaults`; the equal-levels
  row passes FR-010; the sim code hash is unchanged.
- **SC-005**: Every report carries `member_defaults`; the xlsx shows it; a pre-feature report reads without it.
- **SC-006**: The Node suite and the full pytest suite are green on the final code.

## Assumptions

- Wide Lens is offered on any of today's sets with a missing attack, and generates item-conditioned extra sets by re-valuing
  the member's attacks with its accuracy boost (clarification 1); the extra sets share the 024 extras mechanism (appended after
  today's sets, screened beyond the cap, counted in `extras`).
- All appended options share one mechanism with 024's extra sets; the screen's appended teams are ordered variable-power
  extra sets first, then item-conditioned extra sets, then item deviations on base sets, by slot then item order.
- The crit term uses the game's stage table and a 2x critical hit; the stage counts the move's high-critical-ratio effect and,
  in item-conditioned valuation, the held item; abilities are not counted (a later refinement if a benchmark member has one).
- The effect cost class is the assessment probe's set, reviewed at clarify; contested effects (Close Combat's and Superpower's
  self-drops, Overheat's and Draco Meteor's) are "incomparable" unless the owner rules otherwise.
- The equal-levels pass rule is 024's FR-009 as clarified there (one level of quick-search noise allowed with no supported loss).
- Checkpoint refusal comes from `platsim_code_hash` changing; `sim_code_hash` and the ledger version do not change.
- Acceptance pool time about 35 min: two B2 quick runs, four identity evaluations, the equal-levels run; plus the gates.
- Out of scope, as given: the player's model (Zoom Lens, Shell Bell, Lum Berry, flinch, Metronome across plies, Quick Claw),
  the Choice items, zero-copy items, item dominance beyond the recorded Lum rule, the archived branches, what qualifies.
