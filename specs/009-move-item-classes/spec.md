# Feature Specification: Move and Item Classification

**Feature Branch**: `009-move-item-classes`

**Created**: 2026-10-19

**Status**: Draft

**Input**: User description: "Move and item classification (slice 2 of re-slicing feature 007 onto main; user decision 2026-10-19). Every move is classified from the decomp's per-effect battle scripts into one category, with the reason for every move the optimizer will not offer. Held items are classified by whether the game's battle code references their hold effect. Groundwork: no optimizer, battle player or candidate behaviour changes; the two existing lists (excluded attack effects, experience hold effects) move into the new classification and must give the same results. A move marked as adopted is protected when a required HM must replace a move, with no effect while nothing is marked adopted. Brought over from 007 commit 9e1f065 and re-verified on main, not rewritten."

## Context

Second slice of landing feature 007 on `main` one piece at a time (`FUTURE-FEATURES.md` item 1). Slice 1 (feature 008, ledger item sources) is merged. This slice adds the classification that later slices build on: variable-power attacks (slice 3) need the "variable power" category, and the alternatives stage (slice 5) needs the status categories, the exclusion reasons and the held-item classes. On its own it changes no result.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every move has a category and, if never offered, a reason (Priority: P1)

A maintainer (or a later feature) asks what kind of move a move is. Every move in the game gets exactly one category derived from the game's battle scripts: attack, variable-power attack, inflict status, protection, recovery, Leech Seed, self-boost, screen, weather, hazards, foe stat drop, fixed damage, no effect in a single battle, sacrifice, reactive, and the rest. Moves in categories the optimizer will never offer carry the reason.

**Why this priority**: The status-move and variable-power work in later slices depends on this, and a wrong category there would silently change which moves are tried.

**Independent Test**: The classification tests pass: every effect of every move classifies; known moves land where expected (Screech is a foe drop, Seismic Toss is fixed damage, Magnitude is variable power and not fixed damage); every rule-table constant exists in the decomp.

**Acceptance Scenarios**:

1. **Given** the decomp's move data, **When** every move is classified, **Then** each gets exactly one category and none is left unclassified.
2. **Given** a foe-stat-drop move such as Screech, **When** it is classified, **Then** its category is "foe stat drop" with the reason (stat stages reset when the foe faints or switches).
3. **Given** the fixed-damage effects, **When** they are counted, **Then** there are exactly six, and Seismic Toss and Night Shade are among them.

---

### User Story 2 - Every held item is classified by what it does in battle (Priority: P1)

Every held item is classified by whether the game's battle code actually uses its hold effect. Items with no battle outcome (for example Amulet Coin) and experience/EV items (which raise the final level the tool minimises) are identified, with the code location that decides it.

**Why this priority**: The held-item work in later slices may only offer items that do something in battle.

**Independent Test**: The item classification tests pass: all 17 type-resist berries are found as battle-relevant (their subscript compares numbers, not names); the no-outcome items are referenced only in the functions that make them harmless; experience/EV items are derived from the experience and effort-value code.

**Acceptance Scenarios**:

1. **Given** the type-resist berries, **When** items are classified, **Then** all 17 are battle-relevant.
2. **Given** Amulet Coin, **When** items are classified, **Then** it has no battle outcome, with the function that reads it named.
3. **Given** experience and EV items (Exp. Share, Lucky Egg, Macho Brace, the power items), **When** items are classified, **Then** they are marked as experience/EV items and never held-item candidates.

---

### User Story 3 - Nothing the optimizer does changes (Priority: P1)

Two existing rules (attacks that only work under conditions the search cannot arrange, and experience items) now come from the new classification. Required-HM placement learns to protect "adopted" moves, which no current stage marks. The optimizer's candidates and results must not change.

**Why this priority**: A slice must not move results unless explained; that is what makes the re-slice worth doing.

**Independent Test**: Candidate movesets and held items for every benchmark member are identical before and after; a same-seed quick optimization is identical except for the code and data fingerprints; the required-HM tests pass, including a check that an adopted move survives HM placement and that unmarked teams place HMs exactly as before.

**Acceptance Scenarios**:

1. **Given** the same request and seed, **When** a quick optimization runs before and after, **Then** the results are identical apart from the code fingerprint.
2. **Given** a member with no adopted moves, **When** a required HM is placed, **Then** the same move gives way as before.
3. **Given** a member with an adopted status move, **When** a required HM is placed, **Then** another move gives way first; the adopted move is replaced only if nothing else can be.

### Edge Cases

- **A new effect the rules do not cover.** A test fails if any move's effect does not classify, so the table cannot fall behind the decomp silently.
- **An old list entry that no longer exists.** The previous experience-item list named an effect missing from the decomp; the derived list replaces it, and no type-boost choice may change because of it.
- **The player's modelled-move table.** The classification can read which effects the battle player models, but the current player has no such table; until the player slice adds one, nothing reads it.
- **Saved specs without the new adopted field.** Old saved runs and results load unchanged; the field is written only when non-empty.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every move effect MUST be classified into exactly one category, derived from the decomp's battle scripts wherever the scripts say it; the remaining rules MUST be decomp constants (never move names), each with its reason (Constitution I).
- **FR-002**: Moves in never-offered categories (foe stat drop, fixed damage, no effect in a single battle, sacrifice, reactive, and conditional attacks) MUST carry their reason.
- **FR-003**: Held items MUST be classified by whether battle code references their hold effect, by name or by number; no-outcome items and experience/EV items MUST be identified from the code locations that decide it.
- **FR-004**: The list of attacks excluded for conditions the search cannot arrange MUST be the same set as before.
- **FR-005**: Type-boost held-item candidates MUST be the same as before with the derived experience/EV list.
- **FR-006**: Required-HM placement MUST replace adopted moves last, and MUST place HMs exactly as before for members with no adopted moves.
- **FR-007**: Saved run state and result files without adopted moves MUST read and write exactly as before.
- **FR-008**: The work MUST reuse 007 commit `9e1f065` and re-verify it on `main`, not rewrite it; any adaptation is recorded.

### Key Entities

- **Move category**: one per move effect; offered or not; the reason when not offered.
- **Held-item class**: battle-relevant, no battle outcome, or experience/EV; with the code location that decides it.
- **Adopted move**: a move a later stage has chosen on evidence; protected from HM placement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of moves classify into exactly one category; the classification and item tests pass.
- **SC-002**: The 17 type-resist berries are 100% found as battle-relevant; exactly 6 fixed-damage effects are found.
- **SC-003**: Candidate movesets and held items for every member of the five benchmark teams are 100% identical before and after.
- **SC-004**: A same-seed quick optimization of a benchmark team gives the same result before and after, apart from the code fingerprint.
- **SC-005**: The full test suite passes, with every changed test count explained.

## Assumptions

- The 007 implementation was verified there (2026-10-14/15: move classification, item classification and adopted-move tests passed); this slice re-verifies it on `main`.
- Commit `9e1f065` is the first version of these files; later 007 changes to them (the modelled-move table use, item pairings, more categories offered) belong to later slices and are not brought over here.
- The adopted-move protection has no effect until the alternatives stage (slice 5) marks moves; it is included here because it is part of the same commit and is behaviour-neutral without marks.
