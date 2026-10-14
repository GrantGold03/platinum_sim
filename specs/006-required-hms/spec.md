# Feature Specification: Required HMs on the Team

**Feature Branch**: `006-required-hms`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Add options to require HMs on the team. In the web UI this is a new step 3 ('Required HMs'); the existing 'Optimize' step moves down to step 4. Each of the eight HMs (Cut, Fly, Surf, Strength, Defog, Rock Smash, Waterfall, Rock Climb) has its own toggle to make it a requirement; the default is none selected. A required HM must be carried in at least one team member's final four-move set used against Cynthia (user decision 2026-10-13: 'Must be in a moveset', not merely learnable), so the optimizer must fit it into a moveset and the validator must enforce it independently. If a required HM cannot be learned by any member of the chosen six (by a legal pre-Champion source under the active legality options), the run must be prevented before it starts, with a clear per-HM reason, similar to the existing 004 check that refuses two starter lines (web 422 with reasons; CLI optimize/evaluate/validate refuse)."

## Background

- **Why players want this.** Many real playthroughs keep HM users on the final team. Surf and
  Waterfall are mandatory to reach the League (see `hm_requirements.md`, observed 2026-10-13).
  Strength and Rock Climb are mandatory through the Distortion World.
  - Today the optimizer picks movesets for battle value only, so its best team may not be one a
    player would actually walk into the League with.
- **Today's refusal pattern (004).** A team that can't be built (two starter lines) is refused
  before a run, with a reason per Pokémon. The same pattern fits here: a required HM that none of
  the six can learn makes the request impossible.
- **HM learners under default options** (engine, `main` at `dccb3a4`, 2026-10-13):

  | HM | Allowed species (of 188) | Final forms (of 98) |
  |---|---|---|
  | Cut | 51 | 31 |
  | Fly | 18 | 10 |
  | Surf | 41 | 23 |
  | Strength | 91 | 56 |
  | Defog | 32 | 19 |
  | Rock Smash | 98 | 57 |
  | Waterfall | 30 | 16 |
  | Rock Climb | 37 | 22 |

  - Positive control: Garchomp learns Surf but not Fly.
  - The Fly count of 10 final forms matches the earlier Fly-team count.
  - Fly is the hardest to satisfy, so a random team often can't meet it, and US2's refusal matters.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Require HMs and get a team that carries them (Priority: P1)

A user picks six Pokémon. In step 3, "Required HMs", they turn on Surf and Waterfall, then
optimize in step 4. The result's movesets include Surf on at least one member and Waterfall on at
least one member, which may be the same member. The battle evaluation is run with those movesets.

**Why this priority**: this is the feature. Without it, results don't reflect teams that carry
their HMs.

**Independent Test**: optimize a team that can learn Surf and Waterfall, with both required. Check
that the reported movesets contain both moves, and that the validator accepts the result.

**Acceptance Scenarios**:

1. **Given** six Pokémon of which at least one can learn Surf, **When** Surf is required and the
   team is optimized, **Then** at least one member's final moveset contains Surf.
2. **Given** several HMs are required, **When** the team is optimized, **Then** every required HM
   appears in at least one member's moveset. One member may carry more than one required HM.
3. **Given** no HM is required (the default), **When** the team is optimized, **Then** the result
   is exactly as before this feature. Same seed and options give the same report.
4. **Given** a result with required HMs, **When** its report is read, **Then** the report records
   which HMs were required, and the validator confirms each is carried.

---

### User Story 2 - Impossible requirements are refused before a run (Priority: P1)

A user requires Fly, but none of the six chosen Pokémon can learn Fly. The run does not start.
The user sees which required HM no team member can learn.

**Why this priority**: an impossible requirement must fail clearly, never produce a misleading
result. Constitution III requires that "an input that cannot form a legal set MUST fail with a
clear error naming the reason".

**Independent Test**: require Fly for a team of six that can't learn it, on the web and on the
command line. The run is refused with a Fly reason. Remove the requirement and the run starts.

**Acceptance Scenarios**:

1. **Given** a required HM that none of the six can learn under the active legality options,
   **When** the user starts the run on the web, **Then** it is refused before a job is created.
   The message names the HM, e.g. "No team member can learn Fly".
2. **Given** the same request on the command line (`optimize`), **When** it is run, **Then** it
   exits with the same reason and no battles run.
3. **Given** several required HMs that nobody can learn, **When** the run is started, **Then**
   all of them are named in one refusal.
4. **Given** a team where one member can learn the HM only under an optional legality rule (e.g.
   a post-game tutor or item), **When** that rule is off, **Then** the HM counts as not learnable.
   When the rule is on, it counts as learnable.

---

### User Story 3 - Step 3 in the web page (Priority: P2)

The setup column reads: 1. Choose Pokémon, 2. Team, **3. Required HMs**, 4. Optimize. Step 3
lists the eight HMs as toggles, all off by default.

**Why this priority**: it is how users reach the feature on the web. The rules behind it are P1.

**Independent Test**: load the page. Check the step order and headings, and the eight toggles,
all off. Turn some on, start a run, and check that the job records them.

**Acceptance Scenarios**:

1. **Given** the setup page, **When** it loads, **Then** the steps are numbered 1–4 in the order
   above. Step 3 has eight toggles in HM-number order: Cut, Fly, Surf, Strength, Defog, Rock
   Smash, Waterfall, Rock Climb. All are off.
2. **Given** some toggles are on, **When** a run is started, **Then** the job and its results
   show the required HMs.
3. **Given** the results view of a run, **When** required HMs were set, **Then** the summary
   lists them next to the legality options.

---

### Edge Cases

- **One member, several HMs.** Required HMs may share a member; a member's four slots can hold up
  to four HMs. The optimizer decides where each goes.
- **Every HM required.** All eight can be required as long as each is learnable by someone. A team
  might then spend 8 of its 24 move slots on HMs. The result reports its win rate honestly; there
  is no extra warning.
- **Duplicate species.** If two members are the same species, an HM it can learn counts as
  learnable by the team.
- **Learnable, but the clear rate can't be met.** If every required HM can be learned but no
  moveset that carries them meets the minimum clear rate, the run behaves as today when a target
  is missed. The requirement does not loosen the target.
- **`evaluate` and `validate` with a given team.** If a required HM is not in any member's given
  moveset, `validate` reports a violation naming the HM and `evaluate` refuses the team.
- **Old jobs and reports** have no required-HM field; it is read as none required.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to require any subset of the eight HMs: Cut, Fly, Surf,
  Strength, Defog, Rock Smash, Waterfall and Rock Climb. The default MUST be none.
- **FR-002**: A required HM MUST be satisfied only when at least one team member's final moveset
  (the four moves used in the battle evaluation) contains that HM move.
- **FR-003**: The optimizer MUST only return teams that satisfy every required HM (FR-002). Each
  HM move MUST come from a legal source for that member, as for any other move.
- **FR-004**: The validator MUST check FR-002 independently of the optimizer. It reports a
  violation naming each required HM that no member carries.
- **FR-005**: Before any battle runs, a request MUST be refused if a required HM can't be learned
  by any of the six members through a legal source under the active legality options. The refusal
  MUST name each such HM. This applies to the web (refused before a job is created, as for the
  004 starter refusal) and to the command line (`optimize` and `evaluate` exit without battles).
- **FR-006**: The web setup MUST show steps in the order 1. Choose Pokémon, 2. Team, 3. Required
  HMs, 4. Optimize. Step 3 has one toggle per HM in HM-number order, all off by default.
- **FR-007**: The command line MUST accept the same requirement on `optimize`, `evaluate` and
  `validate`, one value per HM. Its default is none.
- **FR-008**: Each report file (JSON report and spreadsheet) and the web results summary MUST
  record which HMs were required. Constitution IV: a result must state the constraints it was
  made under. A report without this field reads as none required.
- **FR-009**: With no HM required, outputs MUST be byte-identical to before this feature for the
  same inputs and seed. The job fingerprint MUST also be unchanged, so existing runs can still be
  resumed and compared.
- **FR-010**: Regression tests MUST cover:
  - a required HM present in the result;
  - several HMs on one member;
  - a learnable-nowhere refusal on the web and on the command line;
  - a legality-option-dependent learner (both sides of the option);
  - the validator violation;
  - the default path unchanged.

### Key Entities

- **Required HMs**: a set of 0–8 HM moves chosen by the user for a run. It is part of the run's
  inputs and recorded in its report. Like the legality options, it changes the result, so runs
  with different sets are different runs.
- **HM learner check**: for each required HM, whether any of the six members has a legal source
  for that move under the active legality options. A required HM that no member can learn makes
  the request impossible.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of results produced with required HMs carry every required HM in at least one
  member's moveset, as confirmed by the validator on every output.
- **SC-002**: 100% of requests with an unlearnable required HM are refused before any battle runs,
  and the refusal names every such HM.
- **SC-003**: With no HMs required, every existing regression test and default-option result is
  unchanged, and job fingerprints are identical.
- **SC-004**: A user can set required HMs and start a run in one pass through the four steps, with
  no hidden settings: all eight toggles are visible in step 3.
- **SC-005**: The full test suite passes.

## Assumptions

- **"Carried" means in the final four moves used against Cynthia** (user decision 2026-10-13).
  Learning an HM and deleting it later does not count.
- **All eight HMs are offered,** including Fly and Defog, which the story never requires
  (`hm_requirements.md`). Requiring them is the user's choice.
- **The requirement is about the team, not one member.** Which member carries each HM is the
  optimizer's choice; users can't pin an HM to a specific member.
- **HM learnability comes from the existing engine** (learnsets, HM item availability, legality
  options). No new game data is needed. All eight HM items exist before the Champion.
- **The requirement is a new input,** not a legality option. It narrows the result instead of
  widening it, so the constitution's Principle III rules for options that widen output don't
  apply. Principle III's "optional constraints MUST be explicit inputs" does apply, and FR-007
  and FR-008 meet it.
- **Work happens in the git worktree** `../platinum_sim-006` (branch `006-required-hms`), because
  the 005 full suite was running in the main checkout.
