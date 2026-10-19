# Feature Specification: Ledger Item Sources

**Feature Branch**: `008-ledger-item-sources`

**Created**: 2026-10-19

**Status**: Draft

**Input**: User description: "Ledger item sources (slice 1 of re-slicing feature 007 onto main; user decision 2026-10-19). The availability ledger gains three in-game item sources it does not model today: the Route 221 house (Black Belt, Expert Belt, Focus Sash; 1 copy each), the Pastoria City berry house, and Amity Square (berry pickup with the partner Pokémon, and the Gift Man). Each source carries its decomp script reference and a before/after-Champion verdict with its reason; the validator agrees with the ledger. Scope is the ledger and validator only. The implementation already exists on branch 007-status-moves-items as commit a8b529b and is to be brought over and re-verified on main, not rewritten."

## Context

This is the first of several small features that land the work of feature 007 on `main` one piece at a time (user decision 2026-10-19, after hands-on testing found a regression in 007 that could not be pinned to one change). Each slice is tested on its own against `main` before the next one starts. See `FUTURE-FEATURES.md`.

Numbering: this feature is `008` to match its branch. The 007 hand-off work that was previously called "008" (reference benchmark, prefilter, default switch) gets a later number.

## Clarifications

### Carried over from 007 (user answers, 2026-10-14)

- Q: Are the missing item sources in scope? → A: Yes.
- Q: How many copies does the Route 221 house give? → A: One of each: Black Belt, Expert Belt and Focus Sash. The gift needs a party Pokémon at that day's random level, so the ledger's usual "daily gift = unlimited" rule is not applied. This is the conservative reading.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New item sources appear in the item catalog (Priority: P1)

A player looks up Focus Sash, Expert Belt or Black Belt, a Pastoria City berry, or an Amity Square berry in the item catalog. Each now lists the in-game source, the game script it comes from, how many copies it gives, and whether it is available before the Champion, with the reason.

**Why this priority**: These sources give strong held items before the Champion that the tool currently treats as unavailable. Every later item feature can only use what the ledger knows about.

**Independent Test**: Under default options, look up each of the three Route 221 items, one Pastoria berry and one Amity Square berry. Each shows the new source, its script reference, its copy count and its verdict with a reason.

**Acceptance Scenarios**:

1. **Given** default options, **When** the ledger is built, **Then** the Route 221 house appears as the source of Black Belt, Expert Belt and Focus Sash, 1 copy each, with the level condition recorded as the reason for the count.
2. **Given** default options, **When** the ledger is built, **Then** the Pastoria City berry house appears as a source of its berries, with copies counted as unlimited and the reason recorded.
3. **Given** default options, **When** the ledger is built, **Then** Amity Square appears as a source of its berries (pickup while walking with a partner Pokémon, and the Gift Man), with the partner-Pokémon condition recorded.
4. **Given** an item none of these sources gives (Liechi Berry, Choice Band), **When** the ledger is built, **Then** its availability is unchanged.

---

### User Story 2 - The validator accepts teams that hold these items (Priority: P1)

A player validates a team that holds an item only these sources give. The validator agrees with the ledger: the item is legal, within its copy count.

**Why this priority**: A ledger the validator disagrees with would produce teams the tool calls illegal, or illegal teams it calls legal (Constitution III).

**Independent Test**: Validate a team where one member holds Focus Sash: no availability error. Validate a team where two members hold Focus Sash: a copy-count error. Validate a team holding Choice Band: still unavailable.

**Acceptance Scenarios**:

1. **Given** a team with one Focus Sash holder, **When** it is validated, **Then** it passes.
2. **Given** a team with two Focus Sash holders, **When** it is validated, **Then** it fails with a copy-count error.
3. **Given** a team holding Choice Band, **When** it is validated, **Then** it still fails as unavailable.

---

### User Story 3 - Nothing else changes (Priority: P2)

Existing results stay the same. The optimizer, battle player and held-item candidates are not changed by this feature.

**Why this priority**: The point of the re-slice is that each change can be judged alone. A slice that also moved optimizer results would defeat that.

**Independent Test**: The full test suite passes. The item counts change only by the items these sources add. A short optimizer run on a benchmark team whose candidates do not include these items gives the same result as on `main`.

**Acceptance Scenarios**:

1. **Given** the same request and seed, **When** a quick optimization of a benchmark team is run before and after this feature, **Then** the result is identical, unless a team's held-item candidates include one of the newly available items (in which case the difference is recorded and explained).
2. **Given** the ledger before and after, **When** the per-item availability is compared, **Then** every changed item is one these sources give.

### Edge Cases

- **Item already available elsewhere.** An item a new source gives that was already obtainable keeps its best copy count (an unlimited source is not reduced by a 1-copy source).
- **Conditions the player may not meet.** The Amity Square partner condition and the Route 221 level condition are recorded with the source, not silently assumed.
- **Post-Champion sources.** If any part of a source is only reachable after the Champion, it is reported as such and does not count under default options.
- **Regenerated data.** The generated data is rebuilt from the decomp; a stale copy from another branch must not be used for the before/after comparison.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The availability ledger MUST model the Route 221 house as a source of Black Belt, Expert Belt and Focus Sash, 1 copy each, with the reason (the day's random level condition) recorded.
- **FR-002**: The ledger MUST model the Pastoria City berry house as a source of the berries it gives, with its copy rule and reason.
- **FR-003**: The ledger MUST model Amity Square as a source of the berries found while walking with a partner Pokémon and of the Gift Man's items, with the partner-Pokémon condition recorded.
- **FR-004**: Every new source MUST carry a reference to the game script it comes from and a before/after-Champion verdict with its reason (Constitution I).
- **FR-005**: The validator MUST accept a team that holds these items within their copy counts and reject one that exceeds them (Constitution III).
- **FR-006**: Items not given by these sources MUST keep their current availability; Liechi Berry stays at 0 copies and Choice Band stays unavailable under default options.
- **FR-007**: The optimizer, battle player and held-item candidate rules MUST NOT change in this feature.
- **FR-008**: The work MUST reuse the existing 007 implementation (branch `007-status-moves-items`, commit `a8b529b`) and re-verify it on `main`, not rewrite it. Any adaptation needed to apply it to `main` is recorded.

### Key Entities

- **Item source**: where an item comes from in the game; its script reference, copy count, conditions and before/after-Champion verdict.
- **Item availability**: per item, under the chosen options: how many copies are obtainable before the Champion, and why.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Under default options, all 3 Route 221 items, every Pastoria berry and every Amity Square item show the new source with a script reference and a verdict with its reason (100% coverage).
- **SC-002**: Under default options, the held-item counts are 74 unlimited, 40 finite and 44 unavailable (the values measured in 007), and every item whose availability changed from `main` is one given by these sources.
- **SC-003**: The validator results match the ledger for 100% of the test teams (one Focus Sash holder passes; two fail on copies; Choice Band fails as unavailable).
- **SC-004**: The full test suite passes, with every changed test count explained.
- **SC-005**: A quick optimization of at least one benchmark team with the same seed gives a byte-identical result before and after this feature, or each difference is traced to a newly available item.

## Assumptions

- The 007 implementation of these sources is correct as verified there (63 ledger tests passed, 2026-10-15); this feature re-verifies it on `main`, it does not re-derive it.
- "Unlimited" for the Pastoria berry house and Amity Square follows the ledger's existing rules for repeatable, flagless gifts, as in 007.
- Whether each source is truly before the Champion is decided by the decomp scripts, as in 007; no cartridge check is made.
- Constitution v1.4.0 (Principle VI, reference-first) exists only on the 007 branch. This feature has no approximations, so it does not depend on it; bringing the amendment to `main` is a separate docs change.
