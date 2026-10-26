# Feature Specification: Held-Item Sources (held items, slice H1)

**Feature Branch**: `011-held-item-sources`

**Created**: 2026-10-26

**Status**: Draft

**Input**: User description: "Held items, slice H1: model the missing pre-Champion held-item sources in the availability ledger. The ledger today has no entry for three in-game sources found in held_items.md: the Route 221 house (daily rotating gift of Black Belt, Expert Belt, Focus Sash; gift needs a party Pokémon at the day's random level, so count 1 copy of each, the conservative reading), the Pastoria City southwest house (daily random berry, GetRandom 17 + ITEM_OCCA_BERRY, i.e. Occa through Chilan), and Amity Square (partner Pokémon pickup of Magost/Cornn/Rabuta/Nomel/Spelon/Pamtre/Watmel/Durin/Belue berries, plus the Gift Man). Every item, copy count, and gate comes from the decomp. The validator accepts these items exactly when the ledger does. `platsim explain item:<x>` shows the new source with its decomp file:line and a plain-language reason, with no internal labels (no feature numbers, task ids, or words like "dataflow"). Scope is the ledger, validator, and explain output only. The optimizer's held-item candidate rule (Sitrus Berry, one type-boost item, Leftovers) does not change, so a same-seed optimizer run must match main apart from provenance hashes. Prior art: the archived branch 008-ledger-item-sources (commit a8b529b) and specs/008-ledger-item-sources; reuse it where it fits, minus the jargon in explain output. Keep it small: at most about 3 stories and 30 tasks."

**Superseded in part (2026-10-26):** the "reuse it where it fits" part of the input is withdrawn; see Clarifications, Session 2026-10-26.

## Context

`main` was reset to the state before feature 007 on 2026-10-20 (user decision), because 007 grew too large to test piece by piece. The held-item work is now redone as a sequence of small features, each tested by the user before the next starts:

- **H1 (this feature).** The availability ledger learns three missing item sources. No optimizer or battle change.
- H2 and later (not specified yet). Offer more held items to the optimizer, one item group at a time, with the battle player learning each group as needed.

A version of this change was built once before, as feature 008 (branch `008-ledger-item-sources`). The user judged that work a mess, so this feature is built from scratch from the decomp and `main` (Clarifications, Session 2026-10-26). One lesson from 008's hands-on test stands: `platsim explain item:<x>` printed internal labels such as "(007 dataflow: ...)". This feature must not.

## Clarifications

### Carried over from 007 and 008 (user answers)

- Q: Are the missing item sources in scope? → A: Yes (2026-10-14).
- Q: How many copies does the Route 221 house give? → A: One of each: Black Belt, Expert Belt and Focus Sash. The gift needs a party Pokémon at that day's random level, so the ledger's usual "daily gift = unlimited" rule is not applied. This is the conservative reading (2026-10-14).
- Q: Should user-facing text carry internal labels? → A: No (user testing of 008, 2026-10-19; `FUTURE-FEATURES.md` item 4).

### Session 2026-10-26

- Q: Should this feature reuse 008's implementation and documentation (commit `a8b529b`, `specs/008-ledger-item-sources/`)? → A: No. "Don't rely too much on 008's documentation or implementation. It was a bit of a mess... When in doubt, create from scratch instead of referencing 008" (user). No archived code is applied; counts, item lists and wording are derived in this feature's own research from the decomp and `main`.
- Q: Should the ledger learn these sources by reading game scripts more completely in general, or by rules aimed at just these three places? → A: General (option A). Script reading is improved for all scripts; other sites may gain entries, but none may change a held item's availability without being reported.
- Q: May 008's archived results be used as a comparison once this version is built? → A: Only after the build, as a comparison (option B). Differences are listed and checked against the decomp; 008 is never the target and nothing is changed to match it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New item sources appear in the item catalog (Priority: P1)

A player looks up Focus Sash, Expert Belt, Black Belt, a Pastoria City berry or an Amity Square berry with `platsim explain`. Each now lists the in-game source, the game script it comes from (file and line), how many copies it gives, and whether it is available before the Champion, with the reason, all in plain language.

**Why this priority**: These sources give strong held items before the Champion that the tool currently treats as unavailable. Every later held-item feature can only offer what the ledger knows about.

**Independent Test**: Under default options, run `platsim explain` for Focus Sash, Expert Belt, Black Belt, Occa Berry and Belue Berry. Each shows the new source, its script reference, its copy count and its verdict with a reason. None of the text contains a feature number, task id or internal term.

**Acceptance Scenarios**:

1. **Given** default options, **When** Focus Sash, Expert Belt or Black Belt is explained, **Then** the Route 221 house is shown as a source, 1 copy, with the day's-random-level condition given as the reason for the count.
2. **Given** default options, **When** a Pastoria City berry (Occa through Chilan) is explained, **Then** the Pastoria City berry house is shown as a source, with its copy rule and the reason.
3. **Given** default options, **When** an Amity Square berry is explained, **Then** Amity Square is shown as a source (pickup while walking with a partner Pokémon, or the Gift Man), with the partner-Pokémon condition stated.
4. **Given** an item none of these sources gives (Liechi Berry, Choice Band), **When** it is explained, **Then** its availability is unchanged from `main`.
5. **Given** any explained item, **When** its source lines are read, **Then** they contain no feature number, task id, or internal implementation term (for example "dataflow", "GetRandom+AddVar", "save-var").

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

Optimizer and battle results stay the same. The optimizer, the battle player and the held-item candidate rule are not changed by this feature.

**Why this priority**: The point of slicing is that each change can be judged alone. A slice that also moved optimizer results would defeat that.

**Independent Test**: The full test suite passes. The item counts change only by the items these sources add. The held-item candidates of the benchmark teams are identical to `main`'s, and a quick same-seed optimizer run gives the same result as on `main` apart from provenance hashes.

**Acceptance Scenarios**:

1. **Given** the same request and seed, **When** a quick optimization of a benchmark team is run on `main` and on this branch, **Then** the results are identical apart from provenance hashes.
2. **Given** the ledger on `main` and on this branch, **When** per-item availability is compared, **Then** every changed item is one these sources give.

### Edge Cases

- **Item already available elsewhere.** An item a new source gives that was already obtainable keeps its best copy count (an unlimited source is not reduced by a 1-copy source).
- **Conditions the player may not meet.** The Amity Square partner condition and the Route 221 level condition are recorded with the source, not silently assumed.
- **Post-Champion sources.** If any part of a source is only reachable after the Champion, it is reported as such and does not count under default options.
- **Other gift sites picked up by the same script reading.** Reading these scripts correctly may also record gifts at other sites. These are allowed only if they change no held item's availability; any that would is reported, not silently accepted.
- **Regenerated data.** Generated data is rebuilt from the decomp on each branch before any before/after comparison; a stale copy from another branch is never used.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The availability ledger MUST model the Route 221 house as a source of Black Belt, Expert Belt and Focus Sash, 1 copy each, with the reason (the day's-random-level condition) recorded. The rule MUST be detected from the game script's content, not from the map name.
- **FR-002**: The ledger MUST model the Pastoria City berry house as a source of every berry its script can give, with its copy rule and reason.
- **FR-003**: The ledger MUST model Amity Square as a source of the berries found while walking with a partner Pokémon and of the Gift Man's items, with the partner-Pokémon condition recorded.
- **FR-004**: Every new source MUST carry its decomp file and line and a before/after-Champion verdict with its reason (Constitution I). Items, copy counts and gates MUST come from the decomp, not be hand-typed.
- **FR-005**: The validator MUST accept a team that holds these items within their copy counts and reject one that exceeds them (Constitution III).
- **FR-006**: Held items not given by these sources MUST keep their current availability; Liechi Berry stays unobtainable and Choice Band stays unavailable under default options.
- **FR-007**: `platsim explain item:<x>` MUST show each new source in plain language. User-facing source text MUST NOT contain feature numbers, task ids, or internal implementation terms; decomp file:line references stay. A test MUST fail if such labels appear in the explain output for the new sources.
- **FR-008**: The optimizer, battle player and held-item candidate rule MUST NOT change in this feature.
- **FR-009**: The work MUST be built from the decomp and `main`'s code, not by applying or copying the archived 008 implementation (commit `a8b529b`). Its items, copy counts, gates and wording are derived in this feature's own research. 008's archived results MAY be compared only after the build; each difference is checked against the decomp and reported, never resolved by matching 008.
- **FR-010**: The three sources MUST be found by a general improvement in how the ledger reads game scripts, not by rules keyed to these maps or scripts. Every site that gains an entry from the improvement MUST be listed in the research with its items; any that changes a held item's availability beyond the three sources MUST be reported to the user before the feature is accepted.

### Key Entities

- **Item source**: where an item comes from in the game: its script reference, copy count, conditions and before/after-Champion verdict, with a plain-language reason.
- **Item availability**: per item, under the chosen options: how many copies are obtainable before the Champion, and why.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Under default options, all 3 Route 221 items, every Pastoria berry and every Amity Square item show the new source with a script reference and a verdict with its reason (100% coverage).
- **SC-002**: Under default options, every held item whose availability changed from `main` (66 unlimited, 37 finite, 55 unavailable; measured 2026-10-26) is one given by these sources, and each change matches the copy count this feature's research derives from the decomp.
- **SC-003**: The validator results match the ledger for 100% of the test teams (one Focus Sash holder passes; two fail on copies; Choice Band fails as unavailable).
- **SC-004**: 0 internal labels (feature numbers, task ids, implementation terms) in the explain output for every item these sources give.
- **SC-005**: The full test suite passes, with every changed test count explained.
- **SC-006**: The held-item candidates of benchmark teams B1-B5 are identical to `main`'s, and a quick same-seed optimization of one benchmark team is identical to `main`'s apart from provenance hashes.

## Assumptions

- Copy counts for the Pastoria berry house and Amity Square follow the ledger's existing rules on `main` for daily and repeatable gifts and for berries (replanting), unless research finds a reason not to.
- Whether each source is truly before the Champion is decided by the decomp scripts; no cartridge check is made.
- Fixing internal labels elsewhere in user-facing output (beyond the explain lines for these sources) is out of scope; that is `FUTURE-FEATURES.md` item 4.
- The new items are not offered to the optimizer: Focus Sash and Expert Belt are not in the current candidate rule, and the type-boost choice prefers Plates (unlimited) over Black Belt (1 copy). Offering them is slice H2.
