# Feature Specification: Breeding and Fossils Respect One-Time Choices

**Feature Branch**: `004-breeding-source-limits`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Fix Day-Care breeding legality so bred Pokémon respect the one-time limits of the parent they come from. Today `breed_mothers`/`_breed_options` give every egg species an UNLIMITED breed source as long as some female-capable member of its line is obtainable pre-Champion; they ignore where that parent comes from. Consequence: all three starter lines are treated as simultaneously available via breeding, so validate/optimize/web UI accept a team with e.g. Torterra + Infernape, which the game cannot produce. [...] Same principle for any line whose only pre-Champion parent is a limited one-time source (gift/egg/static) [...] breeding needs a compatible partner (opposite-gender member of a shared egg group, or Ditto, which is not available pre-Champion) — verify and encode. Validator must report a clear violation and the species catalog / explain output must reflect it. [...] Add regression tests: Torterra+Infernape team is rejected; Infernape+Monferno is accepted; three Infernape are accepted."

## Background (observed 2026-10-13, default options)

These facts were measured with the current engine. They set the scope of the fix.

- **Starters are breedable without regard to which one was chosen.** Turtwig, Chimchar and
  Piplup each have two sources: the starter gift (one of three, a single choice) and a Day-Care
  egg with no limit. The egg source does not depend on which starter the player picked. As a
  result, any team that mixes starter lines is accepted. That includes Torterra + Infernape, or
  all three final starters together, and none of these can be produced in one game.
- **Size of the error.** The engine allows 56,574,476,596 species-only teams of six different
  species, which is every combination of the 188 allowed species. Allowing at most one starter
  line gives 55,379,676,751. That figure was checked against the closed form
  C(179,6) + 3·(C(182,6) − C(179,6)).
- **Ten egg lines have a parent that comes only from a one-time source.** Each of these lines
  can currently be bred without limit:
  - starters: Turtwig, Chimchar, Piplup (the starter choice);
  - Eevee (Hearthome gift);
  - Riolu (Iron Island egg);
  - Togepi (Eterna egg);
  - Cranidos and Shieldon (Mining Museum fossils);
  - Drifloon (Valley Windworks);
  - Spiritomb (Route 209).

  For lines other than the starters, breeding from one female is real game behaviour. The female
  is not used up, and her partner can be a male of a different species. These lines stay legal,
  but only when the conditions below hold.
- **Fossils depend on the Trainer ID (added 2026-10-13, user decision).** Before the National
  Dex, the Underground gives Armor Fossils (Shieldon) only to even Trainer IDs and Skull Fossils
  (Cranidos) only to odd ones (`src/underground/mining.c:647-648`, `Mining_GetWeightOfItem`). No
  other dig item is split this way before the National Dex. The engine has the problems below.
  - It allows both fossil lines on one team.
  - It caps each revival at one copy, although fossils can be dug again and again and each
    revival uses only one fossil (`scripts_mining_museum.s:103, 200`).
- **Ditto cannot be obtained before the Champion.** The engine has no pre-Champion source for it.
  Every egg therefore needs a male partner from an egg group the mother shares. Today the engine
  checks for such a male only when an egg move is involved. It does not check when a hatched egg
  is simply the way the species is obtained.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mixed-starter teams are rejected (Priority: P1)

A user validates, optimizes, or builds in the web UI a team that contains members from two or
more starter lines. The tool refuses it and says that only one starter can be chosen.

**Why this priority**: this is the confirmed defect. It lets the tool output teams that cannot
be built, which breaks the project's core promise of in-game legality.

**Independent Test**: validate a team containing Torterra and Infernape and confirm it is rejected
with a starter-choice reason. Validate teams drawn from a single starter line and confirm they
are accepted.

**Acceptance Scenarios**:

1. **Given** a team with Torterra and Infernape, **When** it is validated, **Then** it is rejected
   with a violation that names both members and says only one starter line can be chosen.
2. **Given** a team with Infernape and Monferno and four non-starter members, **When** it is validated,
   **Then** it is accepted. One member comes from the starter gift and the other is bred from it.
3. **Given** a team with three Infernape, **When** it is validated, **Then** it is accepted.
   Breeding the chosen starter gives further copies.
4. **Given** a team with one Empoleon and no other starter-line member, **When** it is validated,
   **Then** it is accepted, as it is today.
5. **Given** the optimizer is searching, **When** it builds candidate teams, **Then** it never
   proposes a team that mixes starter lines.
6. **Given** the web UI team builder already holds one starter-line Pokémon, **When** the user
   adds a member from a different starter line, **Then** the team is refused with the same
   reason before any run starts.

---

### User Story 2 - Breeding needs a real partner (Priority: P2)

A team member whose only source is a Day-Care egg is accepted only when the game could produce
that egg. A female of the line must be obtainable. A male partner must also be obtainable: either
a pre-Champion Pokémon that can be male, shares an egg group with the mother and is not in the
Undiscovered group, or Ditto.

**Why this priority**: in today's data this rule always holds where it matters, so the fix
changes no current answers. It closes a gap that would otherwise let a future data or option
change accept an impossible egg without anyone noticing.

**Independent Test**: list every species whose breed source exists and check that each one names
a qualifying mother and a qualifying partner. As a positive control, remove all compatible
partners for one line in a test setup and confirm its breed source disappears.

**Acceptance Scenarios**:

1. **Given** a line whose mother can be obtained but no compatible male or Ditto can be,
   **When** its sources are listed, **Then** there is no breed source for it.
2. **Given** a line with a compatible male partner, **When** its breed source is explained,
   **Then** the explanation names the mother's line and an example partner.

---

### User Story 3 - One-time parents are traced (Priority: P2)

A bred member whose parent line exists before the Champion only through a one-time source
(gift, gift egg, fossil, static encounter) is legal only if that one copy can be female. Its
explanation shows that the eggs come from that one parent.

**Why this priority**: this keeps the tool honest about where eggs come from without adding new
limits. Breeding from one female is legal in the game.

**Independent Test**: explain a bred Lucario and a bred Vaporeon. The explanation must name
Riley's egg or the Hearthome Eevee as the parent's source. Changing the test data so that the
one-time parent's gender is fixed to male must remove the breed source.

**Acceptance Scenarios**:

1. **Given** a one-time parent that the game data allows to be female, **When** the line's
   sources are listed, **Then** a breed source exists, and its explanation names the one-time
   source of the parent.
2. **Given** a one-time parent whose gender the game data fixes as male, or that is
   genderless, **When** the line's sources are listed, **Then** no breed source exists.
3. **Given** a team with Lucario from Riley's egg plus a bred Lucario, **When** it is validated,
   **Then** it is accepted. The parent is not used up by breeding.

---

### User Story 4 - Fossil lines follow the Trainer ID (Priority: P2)

A team may contain members of the Cranidos line or the Shieldon line, but not both. One
cartridge's Trainer ID makes only one fossil type diggable before the Champion. Several members
of the one fossil line are allowed, because fossils can be dug again and again.

**Why this priority**: it is the same kind of defect as User Story 1, at a smaller scale: two
species lines instead of three.

**Independent Test**: validate a team with Rampardos and Bastiodon and confirm it is rejected
with a Trainer ID reason. Validate a team with two Rampardos and confirm it is accepted.

**Acceptance Scenarios**:

1. **Given** a team with Rampardos and Bastiodon, **When** it is validated, **Then** it is
   rejected. The violation says the two fossils need different Trainer IDs (odd vs even).
2. **Given** a team with two Rampardos, **When** it is validated, **Then** it is accepted.
3. **Given** the fossil revival's explanation, **When** it is shown, **Then** it names the
   Trainer ID parity it needs (Skull Fossil: odd; Armor Fossil: even).
4. **Given** the option `allow_post_game_pokemon`, **When** it is on, **Then** this rule is
   unchanged. With the National Dex, Armor and Skull Fossils are still split by parity in the
   decomp.

---

### Edge Cases

- **All members bred, none taken directly from the starter gift**, for example two bred
  Infernape. The team is still restricted to one starter line, because breeding requires having
  chosen that starter.
- **Starter-line members at different stages** (Chimchar + Infernape): same line, so accepted.
- **Option `allow_unobtainable_pokemon` is on.** Pokémon brought from outside Platinum are not
  covered by the starter choice. The behaviour of that option is unchanged. Starters from other
  games remain reachable only through that option's own source.
- **Post-game options** (`allow_post_game_pokemon`): if the option admits another source for a
  starter line, that line is no longer limited by the starter choice.
- **Explain and catalog output for a starter species.** It shows the starter choice and the
  breed source as depending on it, not as two independent sources.
- **Team-level reasons.** A species is never shown as unavailable on its own only because
  another member of the team is from a different starter line. The conflict is reported at team
  level.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A Day-Care egg source MUST carry the limits of the parent line it is bred from.
  When every pre-Champion source of a parent line belongs to a choose-one group, eggs of that
  line MUST belong to the same group choice. There are two such groups: the starter choice and
  the fossil Trainer ID parity (FR-011).
- **FR-002**: The validator MUST reject a team whose members, in any mix of gift and bred
  sources, would need more than one choice from a choose-one group. The violation MUST name the
  members involved and the group (starter choice).
- **FR-003**: Several members from the chosen group line, whether gifted, bred or both, MUST be
  accepted. The gift gives one copy and breeding gives unlimited further copies.
- **FR-004**: The optimizer and the web UI team builder MUST apply the same rule as the
  validator. They MUST NOT propose or start a run on a team that FR-002 rejects. The validator
  remains the independent check.
- **FR-005**: A breed source MUST exist only if two conditions hold. First, a mother of the line
  that can be female is obtainable before the Champion. Second, a partner is obtainable before
  the Champion: a Pokémon that can be male, shares an egg group with that mother and is not in
  the Undiscovered group, or Ditto. This MUST hold whether or not egg moves are involved.
- **FR-006**: When a parent line's only pre-Champion source is a single one-time copy, the breed
  source MUST exist only if the decomp data allows that copy to be female.
- **FR-007**: Explanations (`explain`, web "obtained from" text, species catalog) MUST describe
  a breed source in terms of its parent's source. Examples: "Day Care egg from your starter
  Chimchar" and "Day Care egg from the Hearthome gift Eevee". For starters, the explanation MUST
  state that only the chosen starter's line can be bred.
- **FR-008**: The species catalog's per-species availability MUST NOT change for any species
  under default options. All 188 currently allowed species stay allowed, because each starter is
  individually obtainable. Only team-level checks change.
- **FR-009**: Every rule above MUST cite the decomp source behind it:
  - the starter choice script;
  - Day-Care compatibility (`Egg_AreEggGroupsCompatible`, daycare.c);
  - each one-time parent's gift or encounter data, including its gender.
- **FR-011**: The Cranidos and Shieldon fossil revivals MUST form a choose-one group decided
  by Trainer ID parity: Skull Fossil needs an odd ID and Armor Fossil an even one. A team MUST
  NOT contain members of both fossil lines. Rules FR-001 to FR-003 apply to this group exactly as
  to the starter choice.
- **FR-012**: A fossil revival MUST be limited only by the copies of its fossil item. When the
  fossil can be dug again and again before the Champion, the revival is unlimited.
- **FR-010**: Regression tests MUST cover:
  - Torterra + Infernape rejected;
  - Infernape + Monferno accepted;
  - three Infernape accepted;
  - two bred Infernape plus one Torterra rejected;
  - one-time-parent breeding accepted (bred Lucario, bred Vaporeon);
  - Rampardos + Bastiodon rejected, and two Rampardos accepted;
  - a positive control that removes the compatible partner, or fixes the parent's gender, and
    sees the breed source disappear.

### Key Entities

- **Source option**: one way to obtain a species, such as a wild slot, gift, static encounter or
  Day-Care egg. It has a quantity (one-time or unlimited) and may belong to a choose-one group.
  After this feature, an egg source also records which parent source it depends on.
- **Choose-one group**: a set of sources of which the player can take only one. The starter
  choice and the fossil Trainer ID parity are the two groups. Any source that depends on a group member inherits that
  member's group choice.
- **Parent line**: the line of the mother that lays the egg. Its own sources decide whether the
  egg can exist and which group choice it needs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 accepted teams mix starter lines or fossil lines. In particular, Torterra + Infernape and the
  three final starters together are rejected by validate, optimize and the web UI.
- **SC-002**: Recount species-only teams of six different species under default options, with
  the engine's own legality rules and no extra rule added. The result is exactly 55,192,424,630.
  Today it is 56,574,476,596. The target counts teams with at most one starter line and at most
  one fossil line. It is computed as Σ over i starter members and j fossil members of
  w_s(i)·w_f(j)·C(175, 6−i−j), where w_s(0)=1, w_s(i)=3·C(3,i), w_f(0)=1 and w_f(j)=2·C(2,j).
  A polynomial product gives the same figure. With the starter rule alone the count is
  55,379,676,751.
- **SC-003**: All 188 species allowed under default options today remain allowed, and no new
  species becomes allowed. The list in `allowed_pokemon.md` is unchanged.
- **SC-004**: Every regression test in FR-010 passes, and the existing test suite stays green.
- **SC-005**: Every breed source shown in explain output names the source of its parent. This
  covers 100% of the 86 egg species that have a breed source today, or fewer if FR-005 or
  FR-006 removes some.

## Assumptions

- Breeding does not use up the parent. One female from a one-time source plus a compatible male
  of any species yields unlimited eggs. The only change for those lines is tracing where the
  parent comes from (FR-006, FR-007).
- Gender limits come from decomp data only:
  - species gender ratio;
  - any fixed gender in a gift or encounter script.

  Soft-resetting for gender is treated as available for any one-time copy whose gender is random.
- After this feature there are two choose-one groups: the starter choice and the fossil
  Trainer ID parity. The rule is written for any choose-one group, so a future group needs no
  new code path.
- The Trainer ID cannot be chosen. It is treated as a free choice of the player, as with
  soft-resetting for gender. Real players can restart a new game until the parity they want
  comes up.
- No new user-facing option is added. This is a correctness fix to the default rules.
  Constitution Principle III requires it: outputs must be obtainable.
