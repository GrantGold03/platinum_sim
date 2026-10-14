# Feature Specification: Second-Game Option Lifts the One-Choice Rules

**Feature Branch**: `005-second-game-option`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Amend the 'unobtainable Pokémon' legality option (LegalityOptions.allow_unobtainable_pokemon) after feature 004. 1) Rename its user-facing label everywhere (web checkbox, web results summary, CLI flag help, README) to 'Allow Pokémon unobtainable in one Platinum game'. 2) When this option is checked, the 004 one-choice-per-group team rules are lifted: a team may contain members of more than one starter line and members of both fossil lines, as if a second Platinum game supplied them. The validator, optimizer and web job submission must all accept such teams when the option is on and keep rejecting them when it is off (default). Constitution III requires that each source allowed only by this rule be labelled in the report files [...]. Default behaviour (option off) must not change [...]. With the option on, starter/fossil mixing alone should add teams back (state the exact recount as a success criterion and verify it with the engine)."

## Background (observed 2026-10-13 on `main` at `dccb3a4`)

- **What the option does today.** It is off by default. It lets in Pokémon from other cartridges
  (dual-slot encounters), and gives a made-up level-1 source to a Pokémon with no source at all.
  Its labels are:
  - the web checkbox: "Allow Pokémon unobtainable in Platinum";
  - the web results summary: "Pokémon unobtainable in Platinum";
  - the command-line help: "allow pokemon that cannot be obtained in Platinum (other cartridges,
    events, none)".
- **What 004 added.** One choice per group: a team may use only one starter line (Turtwig,
  Chimchar or Piplup) and only one fossil line (Cranidos or Shieldon). This is enforced whatever
  the options are.
- **Engine counts of six-species teams** (species only, six different species):

  | | Allowed species | Teams |
  |---|---|---|
  | Option off (default) | 188 | 55,192,424,630 |
  | Option on, 004 groups enforced | 310 | 1,163,212,171,902 |
  | Option on, groups lifted | 310 | **1,174,080,931,485** = C(310, 6) |

  - Lifting the groups adds 10,868,759,583 teams.
  - The two option-on figures also match the closed form, computed with 297 = 310 − 13 species
    outside the starter and fossil lines.
  - With the groups lifted, every six-species combination of the 310 species can be built.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mixed starters and fossils with the option on (Priority: P1)

A user checks "Allow Pokémon unobtainable in one Platinum game". They then validate, optimize or
start a web run on a team with Torterra and Infernape, or with Rampardos and Bastiodon. The tool
accepts it. The report shows which member comes from a second Platinum game.

**Why this priority**: this is the requested behaviour. The option's meaning becomes "anything
one Platinum game can't give you", and a second starter or the other fossil is exactly that.

**Independent Test**: with the option on, validate Torterra + Infernape and Rampardos +
Bastiodon. Both are accepted, and the second member of each pair is labelled. With the option
off, both are still refused.

**Acceptance Scenarios**:

1. **Given** the option is on, **When** a team with Torterra and Infernape is validated, **Then**
   it is accepted. In the report, the later member's "Obtained from" text ends with
   "(from a second Platinum game, allowed by rule)".
2. **Given** the option is on, **When** a team with Rampardos and Bastiodon is validated,
   **Then** it is accepted, and the later fossil member is labelled the same way.
3. **Given** the option is on, **When** a team has all three final starters, **Then** it is
   accepted. The second and third starter-line members are labelled.
4. **Given** the option is on, **When** a team uses one starter line only (e.g. Infernape +
   Monferno), **Then** it is accepted and **no** member is labelled. One game is enough for
   that team.
5. **Given** the option is **off**, **When** any of the teams above with mixed lines is
   validated, optimized or submitted on the web, **Then** it is refused exactly as in 004.
6. **Given** the option is on, **When** the same mixed team is submitted on the web or given to
   the optimizer, **Then** the run starts. There is no refusal before the run.

---

### User Story 2 - The option says what it means (Priority: P2)

Everywhere the option is shown, it reads "Allow Pokémon unobtainable in one Platinum game".

**Why this priority**: the new wording explains the new behaviour. Today's wording,
"unobtainable in Platinum", would suggest that Platinum's own starters are excluded.

**Independent Test**: load the web page and read the checkbox. Run a job with the option on and
read the results summary. Read the command-line help and the README.

**Acceptance Scenarios**:

1. **Given** the setup page, **When** it is shown, **Then** the checkbox reads "Allow Pokémon
   unobtainable in one Platinum game".
2. **Given** a run with the option on, **When** its results summary lists the rules, **Then** it
   reads "Pokémon unobtainable in one Platinum game".
3. **Given** `--help` for `validate`, `evaluate` or `optimize`, **When** it is read, **Then**
   `--allow-unobtainable-pokemon` is described as allowing Pokémon unobtainable in one Platinum
   game. The description includes a second starter or the other fossil.
4. **Given** the README's legality section, **When** it is read, **Then** it describes the
   option with the new name and the second-game rule.

---

### Edge Cases

- **Order decides the label.** The first member of a group sets that game's choice. Each later
  member with a different choice is labelled. A team listed as Infernape, Torterra labels
  Torterra; listed as Torterra, Infernape it labels Infernape. Either way exactly one member is
  labelled.
- **Several lines.** All three starter lines plus both fossil lines on one team gives 3 labels:
  2 later starters and 1 later fossil.
- **One-copy sources are unchanged.** The legendaries and the Porygon gift keep their one-copy
  limits. Item copies (Shiny Stone, Dawn Stone, Razor Claw, Razor Fang) are also unchanged. This
  feature lifts only the starter and fossil groups. Two Giratina stay refused even with the
  option on.
- **Old reports are not rewritten.** Reports made before this change keep their text; the web
  page shows them as they are.
- **Other options don't matter.** Post-game, trade-evolution and egg-move options don't affect
  the group rule. Only this option lifts it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: With `allow_unobtainable_pokemon` on, the validator MUST NOT raise the one-choice
  violation for the starter group or the fossil Trainer ID group (004 FR-002, FR-011). With it
  off, behaviour MUST be exactly as in 004.
- **FR-002**: The optimizer MUST apply the same rule. With the option on, it MUST accept a team
  whose species need more than one choice in a group, and it MUST be able to build such a team
  from its sources. With the option off, it MUST refuse it as in 004.
- **FR-003**: Web job submission MUST apply the same rule. With the option on, such a team is
  accepted and a job is created. With it off, the 004 refusal (422) is unchanged.
- **FR-004**: In every report file (JSON report, CSV and spreadsheet "Obtained from") and in the
  web results view, the "Obtained from" text of each member whose group choice differs from an
  earlier member's MUST end with "(from a second Platinum game, allowed by rule)". No other
  member gets this text. This meets constitution v1.2.0 Principle III (each affected source is
  labelled with the rule).
- **FR-005**: The option's user-facing text MUST read:
  - web checkbox: "Allow Pokémon unobtainable in one Platinum game";
  - web results summary: "Pokémon unobtainable in one Platinum game";
  - command-line help: "allow Pokémon unobtainable in one Platinum game (other cartridges,
    events, none, or a second starter / the other fossil)";
  - README: the same name, plus a sentence describing the second-game rule.
- **FR-006**: The option's key (`allow_unobtainable_pokemon`), its command-line flag
  (`--allow-unobtainable-pokemon`), the web request key and the `/api/species` query name MUST
  NOT change. Saved jobs and old reports still read correctly.
- **FR-007**: Only the starter and fossil groups are lifted. Per-option quantities (one-time
  gifts, statics and the starter gift itself) and item copies MUST stay as they are. A team still
  can't use one starter gift twice; a second member of a line must be bred, or come from the
  other choice.
- **FR-008**: Regression tests MUST cover, each with the option on and off:
  - Torterra + Infernape;
  - Rampardos + Bastiodon;
  - all three final starters;
  - Infernape + Monferno (accepted either way, never labelled);
  - the label on exactly the later member, and its absence with one line;
  - two Giratina still refused with the option on.

### Key Entities

- **Legality option `allow_unobtainable_pokemon`**: an existing switch, off by default, recorded
  in each report's legality options. Its meaning widens to include a second Platinum game for the
  starter and fossil choices.
- **Second-game member**: a team member whose choice in a choose-one group differs from an
  earlier member's. It exists only with the option on, and its source text carries the rule
  label.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the option off, nothing changes:
  - 188 allowed species and 98 final forms (`allowed_pokemon.md`);
  - 55,192,424,630 species-only teams;
  - every 004 regression test passes unchanged.
- **SC-002**: With the option on, the engine's species-only team count (six different species)
  is exactly **1,174,080,931,485**, which is C(310, 6). It was 1,163,212,171,902 with the groups
  enforced, so starter and fossil mixing adds exactly **10,868,759,583** teams.
- **SC-003**: 100% of members needing a second game are labelled in every report format, and 0
  members that one game can supply are labelled.
- **SC-004**: All 6 user-facing places (checkbox, summary, 3 help texts, README) show the new
  wording, and the old wording "unobtainable in Platinum" no longer appears as the option's
  label.
- **SC-005**: The full test suite passes.

## Assumptions

- **"A second Platinum game" only gives a different starter or the other fossil.** It does not
  remove one-copy limits (a second Giratina, Porygon or legendary). The user asked only about
  starters and fossils. Lifting the other one-time limits would change many more teams and is out
  of scope.
- **The option stays one switch.** It is not split into a separate "second game" option. The
  user asked for this option to be renamed and widened.
- **The label is attached to members, not species.** A team's first member in each group is
  treated as coming from the main game, and later members with a different choice as coming from
  the second game.
- **The pages keep the "Pokémon" spelling with é,** as everywhere else on the web page and in
  the README. The user wrote "Pokemon".
- **Old reports and saved jobs are not rewritten** (003 and 004 practice).
