# Feature Specification: Damage-Boosting Held Items (held items, slice H3)

**Feature Branch**: `014-damage-boost-items`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "H3 (held items, slice 3): offer the plain damage-boosting held items the battle player already models. Group: items whose only effect is a damage multiplier, chosen by hold effect from the decomp, not by name: HOLD_EFFECT_POWER_UP_SE (Expert Belt), HOLD_EFFECT_POWER_UP_SPEC (Wise Glasses), HOLD_EFFECT_POWER_UP_PHYS (Muscle Band). Pre-Champion copies today (ledger): Expert Belt 1, Wise Glasses 1, Muscle Band 0, so Muscle Band is never offered unless the ledger finds a copy. sim/damage.mjs already applies all three (:381-382, :639); the battle player needs no change. Rule: held_item_candidates also proposes, for each moveset, Expert Belt when it has a copy (it boosts every super-effective hit), and the physical/special booster matching the moveset's strongest attack's category when it has a copy. Existing candidates (HP berry, type-boost item, Leftovers) stay. The H2 single-use filter still applies. Each limited item goes to at most one team member (existing copy accounting in resources.py; add a test). Known divergences (accepted, data/divergences.json): damage-expert-belt-rounding and damage-final-modifier-chaining, Showdown 1 HP higher on some rolls. State them in the spec. Out of scope: Choice items (need choice-lock modeling in the player), Life Orb (0 copies), Metronome, Wide Lens, King's Rock / Razor Fang, Shell Bell, Lum Berry and resist berries (later groups). Acceptance: candidate sets for B1-B5 differ from main only by the added items; on one benchmark team (B2), a paired same-seed comparison at equal levels (010 rule) shows no statistically supported regression versus main; the optimizer's run-time change on B2 is measured and reported; explain shows the new items' sources; fast mode and the Node suite pass."

## Context

The held-item work is done in small slices, each tested by the user before the next. H1 (feature 011) added the Route 221 house and other item sources to the ledger. H2 (feature 013, merged 2026-10-29) made the optimizer never offer an item that is used up when it triggers, unless it is a berry.

Today the optimizer tries at most three held items per moveset: the best HP-restoring berry, one type-boost item for the moveset's strongest attack, and Leftovers when the team can get it. H3 adds the items whose only effect is to raise damage, which the battle player already accounts for when it scores moves:

| Item | Effect (decomp) | Pre-Champion copies (ledger, 2026-10-29) | Source |
|---|---|---|---|
| Expert Belt | `HOLD_EFFECT_POWER_UP_SE`, param 20: super-effective hits ×1.2 (`src/battle/battle_lib.c:2663-2665`) | 1 | Route 221 house, daily rotation, needs a party Pokémon at that day's random level (`scripts_route_221_house.s:39`) |
| Wise Glasses | `HOLD_EFFECT_POWER_UP_SPEC`, param 10: special move power ×1.1 | 1 | Celestic Town northwest house, one-time gift (`scripts_celestic_town_northwest_house.s:69`) |
| Muscle Band | `HOLD_EFFECT_POWER_UP_PHYS`, param 10: physical move power ×1.1 | 0 | Battle Frontier only (post-game) |

The battle player's damage model applies all three (`sim/damage.mjs:381-382` for the physical/special boosters, `:639` for Expert Belt; covered by `sim/test/damage.test.mjs` cases for each). Battles run in Showdown, which applies them too.

Unlike H2, this feature changes output: a team may now hold Expert Belt or Wise Glasses. So acceptance is a paired comparison against `main`, not "identical".

## Clarifications

### Session 2026-10-29

- Q: Which item group is H3? → A: The plain damage boosters (Expert Belt, Wise Glasses, Muscle Band), chosen by hold effect. Choice items, Life Orb, Metronome, Wide Lens, King's Rock / Razor Fang, Shell Bell, Lum Berry and resist berries are later groups (user, description above).
- Q: How many benchmark teams get the paired comparison? → A: One, B2. Same choice as H2 ("running on one team is sufficient"). Candidate sets are still compared on all of B1-B5.
- Q: Which optimizer budget do the B2 runs use? → A: Quick (user, `/speckit-plan`, 2026-10-29: "use the quick budget for the B2 runs").

## Known divergences (accepted)

Both are recorded in `data/divergences.json` with resolution "accepted". This feature makes them matter for the first time, because a player team can now hold Expert Belt:

- `damage-expert-belt-rounding`: the game floors `damage × 120 / 100`; Showdown uses a 4096-based modifier with round-to-nearest. Showdown is 1 HP higher on some rolls.
- `damage-final-modifier-chaining`: against Filter / Solid Rock, the game floors the ×0.75 and the ×1.2 separately; Showdown chains them and rounds once. Showdown is 1 HP higher on some rolls.

Battle results with Expert Belt inherit these. The battle player's own model follows the game (`sim/damage.mjs`), so it can be 1 HP off Showdown on those rolls.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The optimizer can give a team Expert Belt or Wise Glasses (Priority: P1)

A player optimizes a team. For each member's moveset, the optimizer now also tries Expert Belt and, if the strongest attack is special, Wise Glasses (or, if physical, Muscle Band when it has a copy). It does this alongside the items it already tries. The final team holds whichever item scores best, and no item is given to more members than its copies allow.

**Why this priority**: These are strong held items obtainable before the Champion that the optimizer never considers today.

**Independent Test**: Produce held-item candidates for movesets with a special strongest attack, a physical strongest attack, and no attack. Check which boosters are proposed. Then build a team where two members both want Expert Belt and check that only one gets it.

**Acceptance Scenarios**:

1. **Given** a moveset whose strongest attack is special, **When** candidates are produced, **Then** they include Expert Belt and Wise Glasses, plus the existing berry / type-boost / Leftovers candidates.
2. **Given** a moveset whose strongest attack is physical, **When** candidates are produced, **Then** they include Expert Belt and not Wise Glasses. Muscle Band is not included, because it has no pre-Champion copy.
3. **Given** a moveset with no attacking move, **When** candidates are produced, **Then** no damage booster is proposed.
4. **Given** a ledger in which Muscle Band has a copy (test-only), **When** a physical moveset's candidates are produced, **Then** Muscle Band is included. This is the positive control for the copy check.
5. **Given** two members whose best build uses Expert Belt, **When** the team is realized, **Then** at most one holds it and the team passes the validator.
6. **Given** the H2 rule, **When** any candidate list is produced, **Then** it still contains no single-use non-berry item.

---

### User Story 2 - Teams do not get worse (Priority: P1)

A player gets a team that is at least as good as the one `main` produces for the same request.

**Why this priority**: More candidates can change the search and its result. A new option must not lead to a worse final team.

**Independent Test**: Optimize B2 on `main` and on this branch with the same seed and budget. Play both final teams at the same levels (the new team's start levels) in paired runs.

**Acceptance Scenarios**:

1. **Given** B1-B5, **When** held-item candidates are produced on this branch and on `main`, **Then** every difference is an added damage booster. Movesets and the existing items are unchanged.
2. **Given** B2's final teams from `main` and this branch, played at the new team's start levels with the same seeds, **When** compared, **Then** the new team does not clear significantly less (McNemar exact, alpha 0.05) and its expected average final level is not higher (the 010 equal-levels rule).
3. **Given** the same B2 runs, **When** timed, **Then** the optimizer's wall time on this branch versus `main` is reported.

---

### User Story 3 - The player can see where to get the item (Priority: P2)

A player whose team holds Expert Belt or Wise Glasses can see where to get it, in the report and with `platsim explain`.

**Why this priority**: An item the player cannot find is no use; the sources are already in the ledger, so this is a check that they reach the output.

**Independent Test**: Explain both items, and read the held-item source of a team holding one.

**Acceptance Scenarios**:

1. **Given** `platsim explain item:expert_belt` / `item:wise_glasses`, **When** run, **Then** each shows its pre-Champion source with the decomp reference and 1 copy (Expert Belt: the Route 221 house and its day's-random-level condition).
2. **Given** a final team that holds one of them, **When** the report files are written, **Then** the held-item source for that member names the same place.

---

### Edge Cases

- A moveset whose strongest attack is a status move or has no damage class gets no physical/special booster. Expert Belt is offered whenever the moveset has at least one attacking move.
- When Expert Belt's single copy is already assigned to an earlier member, a later member's Expert Belt option is refused by the copy accounting and that member falls back to another candidate.
- Route 221 house: Expert Belt, Black Belt and Focus Sash share one daily rotation. The ledger counts 1 copy of each (feature 011). This feature keeps that count; it does not model having to wait for the right day.
- An item that is both a damage booster and single-use would be removed by the H2 filter. None of the three is single-use (checked by the H2 reader).
- A ledger with 0 copies of an item (Muscle Band today) never yields that item. The feature uses whatever copy count the ledger gives under the active legality options; it adds no rule of its own.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The damage-booster group MUST be chosen by hold effect read from the decomp: `HOLD_EFFECT_POWER_UP_SE`, `HOLD_EFFECT_POWER_UP_PHYS`, `HOLD_EFFECT_POWER_UP_SPEC`. No hand-typed item names.
- **FR-002**: For every moveset with at least one attacking move, the held-item candidates MUST include each `HOLD_EFFECT_POWER_UP_SE` item that has a copy under the active legality options.
- **FR-003**: For every moveset with at least one attacking move, the candidates MUST include the `HOLD_EFFECT_POWER_UP_PHYS` item when the strongest attack (as the existing rule picks it) is physical, or the `HOLD_EFFECT_POWER_UP_SPEC` item when it is special, if that item has a copy.
- **FR-004**: The existing candidates (best HP berry, type-boost item, Leftovers when the team may hold it) and their order MUST stay unchanged. New items come after them.
- **FR-005**: The H2 rule MUST still hold: no single-use non-berry item is ever a candidate.
- **FR-006**: No team MUST hold more copies of an item than the ledger allows. A test MUST show that two members cannot both hold the single Expert Belt.
- **FR-007**: The battle player, the damage model, the ledger and the validator MUST NOT change.
- **FR-008**: The report files and `platsim explain` MUST show the source of a held Expert Belt or Wise Glasses with its decomp reference.
- **FR-009**: On B2, with the same seed and budget, the final team on this branch MUST NOT be worse than `main`'s by the 010 equal-levels rule: both teams played at the new team's start levels, 2,000 paired runs; it MUST NOT clear significantly less (McNemar exact, alpha 0.05) and its expected average final level MUST NOT be higher.
- **FR-010**: The optimizer's wall time on B2 MUST be measured on both sides and reported with the comparison.

### Key Entities

- **Damage-booster group**: the held items whose hold effect is one of the three above. Derived from the decomp item data.
- **Held-item candidate list**: per member and moveset, the items the optimizer tries. Gains up to two entries.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For B1-B5 (93 member/variant/level entries), every candidate-list difference from `main` is an added Expert Belt or Wise Glasses; 0 other differences.
- **SC-002**: The candidate tests pass: special → Expert Belt + Wise Glasses; physical → Expert Belt only; no attack → no booster; Muscle Band appears only when given a copy.
- **SC-003**: In every realized team in the tests and the B2 runs, each limited item is held by at most as many members as it has copies.
- **SC-004**: B2 equal-levels comparison: no statistically supported drop in clear rate (McNemar exact, alpha 0.05, 2,000 paired runs) and no higher expected average final level.
- **SC-005**: The B2 optimizer wall time on both sides is reported, with the ratio.
- **SC-006**: Fast mode and the Node suite pass.

## Assumptions

- The optimizer's objective is unchanged; this feature only adds held items for it to try.
- The B2 optimizations use the quick budget on both sides (user, Clarifications). The plan fixes the seeds.
- The equal-levels comparison script is written fresh from `main` and `platsim.stats` (McNemar exact). The archived 010 scripts are not reused.
- Run time is local compute only. The B2 optimizations take about 20 minutes each at the quick budget on `main`, and 2,000 paired runs per comparison side. The plan estimates the total.
- More candidates may make the optimizer slower. A slowdown is reported, not a failure, unless the user decides otherwise after seeing the numbers.
- The two Expert Belt divergences are accepted as recorded. This feature does not change them.
