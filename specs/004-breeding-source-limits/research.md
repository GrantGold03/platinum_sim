# Research: Breeding and Fossils Respect One-Time Choices (004)

All facts below were observed on 2026-10-13 in this repository and in the vendored decomp
(`pokeplatinum/`). Paths are repo-relative.

## R1. How the starter choice reaches a team today

- **Decision**: keep the existing `exclusive_group` field and add a **choice key** next to it.
  The team rule becomes: within each group, all members must use the same choice key. The
  per-option quantity check also applies to grouped options. That check is skipped today.
- **Findings**:
  - `exclusive_group="starter"` is set only on the starter gift entries
    (`src/platsim/availability/sources.py:690`).
  - `_options` carries the group over to evolutions (`movesources.py:542`).
  - `_breed_options` sets `None` (`movesources.py:625-628`).
  - The validator rejects any two members in one group (`validator.py:370-374`) and skips the
    quantity check for grouped options (`:365`).
  - `resources.realize` skips a group once it is used (`resources.py:212, 231-232`).
  - That is why Torterra (gift) + Infernape currently passes: Infernape falls back to
    `breed:SPECIES_CHIMCHAR`, which has no group.
- **Rationale**: one field pair, (group, choice), expresses both the starter choice and the
  fossil parity. Same-line members share a choice, so they pass. Different lines differ, so they
  fail.
- **Alternatives rejected**:
  - *A hard-coded "one starter line" team check.* It would not cover fossils, and the validator
    and optimizer would drift apart.
  - *Removing breed options for starters.* That would wrongly forbid two Infernape, which the
    game allows by breeding the chosen starter.

## R2. Which choice a breed source inherits

- **Decision**: a breed option for egg species E inherits (group, choice) from its mothers, but
  only when every pre-Champion non-breed source of every qualifying mother of E carries the same
  group. The choice is then the mother line's choice: the starter species, or the fossil parity.
  If any mother has an ungrouped source, the breed option stays ungrouped.
- **Findings**: under default options, breed lines whose only parents are one-time sources are:
  - Turtwig, Chimchar and Piplup (starter group);
  - Eevee, Riolu and Togepi (gift or gift egg);
  - Cranidos and Shieldon (fossil);
  - Drifloon and Spiritomb (static).

  These come from `breed_mothers` plus the `source_options` probe on 2026-10-13. Only the
  starters and fossils are in a group.
- **Rationale**: breeding needs the mother. The mother exists only through the choice.

## R3. Can one-time parents be female? (spec FR-006)

- **Decision**: all ten affected parents can be female, so no breed source is removed. Add a
  data check: a one-time source with fixed personality or gender, or a genderless species, gets
  no breed source. A test fixture proves the check can fire (positive control).
- **Findings** (all random personality, so gender follows the species ratio):

  | Parent | Script | Command | Ratio |
  |---|---|---|---|
  | Starter | `res/field/scripts/scripts_route_201.s:280-286` | `GivePokemon VAR_0x8000, 5` → `Pokemon_InitWith(..., FALSE, ...)` (`src/unk_02054884.c:45`; random personality `src/pokemon.c:412`) | 12.5% F |
  | Eevee | `scripts_hearthome_city_northwest_house.s:38` | `GivePokemon` | 12.5% F |
  | Riolu egg | `scripts_iron_island_b2f_left_room.s:245` | `GiveEgg` → `Egg_CreateEgg` (`src/overlay005/daycare.c:675`, random) | 12.5% F |
  | Togepi egg | `scripts_eterna_city.s:1089` | `GiveEgg` | 12.5% F |
  | Cranidos / Shieldon | `scripts_mining_museum.s:228` | `GivePokemon VAR_REVIVED_POKEMON_SPECIES, 20` | 12.5% F |
  | Drifloon | `scripts_valley_windworks_outside.s:146` | `StartLegendaryBattle` → `CreateWildMon` (random) | 50% F |
  | Spiritomb | `scripts_route_209.s:78` | `StartWildBattle` | 50% F |

  Riolu and Togepi are Undiscovered and cannot breed. Their evolved forms are the mothers
  (Lucario; Togetic and Togekiss), and `breed_mothers` already handles that.
- **Rationale**: the decomp gives no fixed gender. Soft-resetting for gender is a normal player
  action and the spec assumes it.

## R4. Breeding partner (spec FR-005)

- **Decision**: extract the species-level part of `find_father` (`movesources.py:808-815`) into
  `compatible_father(mothers, led)`. `breed_mothers` then requires one of these:
  - a pre-Champion obtainable Pokémon that can be male, is not in the Undiscovered group and
    shares an egg group with a mother;
  - Ditto, if Ditto is obtainable.

  The egg-move path keeps its own move test on top of this.
- **Findings**: `BoxMon_GetPairDaycareCompatibilityScore` (`src/overlay005/daycare.c:817-875`)
  checks, in order:
  1. Undiscovered on either parent → incompatible.
  2. Two Dittos → incompatible.
  3. Ditto + any non-Undiscovered Pokémon → compatible.
  4. Same gender or a genderless parent → incompatible.
  5. Otherwise the parents need a shared egg group (`Egg_AreEggGroupsCompatible`, :802-815).

  Same species is not required. Ditto has no pre-Champion source (`led.species_sources` is
  empty).
- **Expected impact**: no current breed source is removed, because every egg group with a
  female-capable pre-Champion species also has a male. This is to be confirmed by the test that
  lists all 86 breed sources. Positive control: a test that removes the partners sees the
  breed source disappear.

## R5. Fossils and Trainer ID parity (spec FR-011, FR-012)

- **Decision**: fossil revival entries get `exclusive_group="trainer_id_parity"`, with choice
  `odd` (Skull Fossil, Cranidos) or `even` (Armor Fossil, Shieldon). The parity is derived from
  the extracted mining weights: a fossil diggable pre-National-Dex for only one parity takes that
  parity. A revival's quantity comes from the copies of its fossil item, and the revival uses up
  one fossil (`consumes`). When the fossil is unlimited, so is the revival.
- **Findings**:
  - Weights are in `src/underground/mining.c:647-648`, selected in `Mining_GetWeightOfItem`
    (:1831-1850):
    - Armor Fossil: odd 0, even 25 (with National Dex: 0 / 12).
    - Skull Fossil: odd 25, even 0 (with National Dex: 12 / 0).
  - Each of the 85 rows of the mining table was checked. Armor and Skull are the only items with
    exactly one zero weight before the National Dex; the other fossils and Oval Stone are 0/0,
    which is post-game only.
  - `availability.json` already has `underground ITEM_SKULL_FOSSIL ... mining (odd TID)`, which is
    pre_champion with an unlimited quantity.
  - The revival entry is `gift ... quantity 1` (`sources.py:693-694`).
  - The revival script removes one fossil (`scripts_mining_museum.s:103, 200`). No lifetime flag
    exists (only `FLAG_MAP_LOCAL_0x01`).
- **Rationale**: it is the same mechanism as the starters. It also corrects the quantity: two
  Rampardos are legal.
- **Alternative rejected**: a user option to pick the Trainer ID parity. The spec adds no
  options, and the group already lets the team pick either parity.

## R6. Where team-level refusal happens

- **Decision**: one shared function, `team_group_conflicts(consts, led)`, in
  `legality/movesources.py`. It reports, per group, whether the team's species can be given one
  consistent choice. The validator does not use it: it works from declared sources (R7).
  `candidates.resolve_species` (optimizer, after the per-name loop) and
  `SpeciesCatalog.resolve_team` (web, after line 171) call it and raise `InvalidRequest` with
  per-species reasons.
- **Findings**: today neither caller does any team-level check. The web returns 422
  `{"detail", "reasons"}` (`web/app.py:450-463`). The optimizer takes the user's six species
  (`optimizer/run.py:269`).
- **Rationale**: users get a refusal before a run starts. The validator stays independent,
  because it checks the declared sources itself (Constitution III).

## R7. Validator

- **Decision**: in `validate`, replace "more than one member in the group" with "more than one
  distinct choice in the group". Stop skipping the quantity check for grouped options, so two
  members that both declare the starter gift still fail. Violation code: `SOURCE_EXHAUSTED`.
  The message names the members, the group and the choices: "only one starter can be chosen:
  Torterra (Turtwig), Infernape (Chimchar)" and "Skull and Armor Fossils need different Trainer
  IDs (odd vs even): Rampardos, Bastiodon".
- **Findings**: the source is declared per member (`Build.source`) and matched by id
  (`validator.py:419-424`). With grouped breed options, a member declaring
  `breed:SPECIES_CHIMCHAR` is placed in the starter group with choice Chimchar.
  `test_starter_choice_is_exclusive` (two gift Chimchar) must still fail, through the quantity
  check.

## R8. Optimizer resource assignment

- **Decision**: in `resources.realize`, change `groups: set` into `dict[group → choice]`. Skip an
  option only when its group is held with a *different* choice. Apply the quantity check to all
  options. Assignment is greedy in slot order. With mixed lines already refused up front (R6),
  greedy assignment cannot dead-end on a group. `member_floor` (single member) is unaffected.

## R9. Count verification (SC-002)

- **Decision**: add a test that recounts species-only teams of six distinct species from the
  engine. It enumerates feasible subsets of the "special" species (one-time or grouped), times
  C(free, 6−k), using the same method as the 2026-10-13 scratch script. It asserts
  55,192,424,630.
- **Findings**: special species under the new rules:
  - the 9 starter-line species and the 4 fossil-line species, which are now grouped;
  - Porygon, Rotom, Uxie, Mesprit, Azelf and Giratina (one copy each);
  - Roserade and Togekiss (Shiny Stone ×2), Gallade and Froslass (Dawn Stone ×2), Weavile (Razor
    Claw ×2) and Gliscor (Razor Fang ×1).

  For distinct species only the groups bind. Two independent closed forms give 55,192,424,630.
  The run takes about 35 s of ledger build, plus well under a second of counting.
