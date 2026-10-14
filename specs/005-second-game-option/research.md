# Research: Second-Game Option (005)

All findings were observed on 2026-10-13 on `main` at `dccb3a4` (004 merged). Paths are relative
to the repository root.

## R1. One switch for "is the group rule enforced?"

- **Decision**: add `groups_enforced(led) -> bool` in `src/platsim/legality/movesources.py`. It
  returns `not options_of(led).allow_unobtainable_pokemon`. Every place that applies the 004
  group rule asks it:
  1. `team_group_conflicts` returns `{}` when the rule is off. It is used by the optimizer's
     `resolve_species` and the web's `resolve_team`.
  2. The validator's group check (`validator.py`, the `for g, members in groups.items()` block)
     is skipped.
  3. `resources.realize` stops skipping options whose group holds a different choice.
- **Rationale**: one predicate, keyed on the ledger's options view. The options already travel
  in the ledger view: `run.py:268` uses `build_ledger().with_options(req.legality)`, and the
  validator uses `_ledger(ledger, options)`. Nothing new needs to be passed around.
- **Alternatives rejected**:
  - *Drop the `exclusive_group` of options in the option-on view.* That would remove the
    information the label needs (R2).
  - *A new option.* The spec says no (Assumptions).

## R2. Which member is "from a second game"

- **Decision**: `second_game_members(opts)` in `movesources.py`. It walks the team's chosen
  `SourceOption`s in team order and remembers the first `group_choice` per group. It returns the
  indices whose choice differs from that first one.
- **Use**: `report/sources.team_sources` appends `SECOND_GAME_NOTE = " (from a second Platinum
  game, allowed by rule)"` to those members' `opt.detail`. `team_sources` is the one source of
  "Obtained from" text for optimize (`run.py:661-663`), evaluate (`evaluate.py:385-387`) and
  `report --rerender` (`rerender.py:107`). The CSV, the spreadsheet, the JSON report and the web
  results view all read from it. One change covers every format (FR-004).
- **Rationale**: the label depends on the team, not on a species, so it can't live in
  `SourceOption.detail`. Team order is deterministic and matches the spec's Edge Cases.
- **Note**: with the option off, the validator refuses any team that would produce such indices,
  so the label can't appear on a default-option report.

## R3. `realize` with the groups lifted

- **Decision**: with the rule off, `realize` ignores the group when checking feasibility. It still
  records the first choice per group, so `second_game_members` and `realize` agree. The
  per-option quantity check is unchanged, so one starter gift still can't serve two members
  (FR-007).
- **Effect**: Torterra + Infernape may come out as two gifts (`gift:SPECIES_TURTWIG@…` and
  `gift:SPECIES_CHIMCHAR@…`, each quantity 1). The second is labelled. It may also come out as one
  gift plus one Day Care egg. The existing source preference (`option_sort_key`: egg last)
  decides.

## R4. Wording (FR-005, FR-006)

Current text, by `grep` over `src/platsim`, `tests` and `README.md`:

| Place | Now | New |
|---|---|---|
| `src/platsim/web/static/index.html:51` | "Allow Pokémon unobtainable in Platinum" | "Allow Pokémon unobtainable in one Platinum game" |
| `src/platsim/web/static/app.js:94` (summary label) | "Pokémon unobtainable in Platinum" | "Pokémon unobtainable in one Platinum game" |
| `src/platsim/cli.py:19` (help for validate, evaluate and optimize) | "allow pokemon that cannot be obtained in Platinum (other cartridges, events, none)" | "allow Pokémon unobtainable in one Platinum game (other cartridges, events, none, or a second starter / the other fossil)" |
| `README.md:56` | `--allow-unobtainable-pokemon` (003): … | same flag, new name and a sentence on the second-game rule |

- **Unchanged** (FR-006):
  - the key `allow_unobtainable_pokemon`;
  - the flag `--allow-unobtainable-pokemon`;
  - the checkbox id `allow-unobtainable-pokemon` (`test_web.py:253` asserts it);
  - the query name `unobtainable_pokemon`.
- **Not touched**: `OUTSIDE_DETAIL = "Unavailable in Platinum (allowed by rule)"` and the catalog
  reason "Unavailable in Platinum". These describe a species' source or reason, not the option.

## R5. Count verification (SC-002)

- **Decision**: the 004 test helper `_count_teams(led, groups=True)` applies the group rule
  itself.
  - Change its default to `groups=None`, meaning "ask the engine": `MS.groups_enforced(led)`.
  - `test_species_team_count` keeps its explicit off-view figures, 55,192,424,630 and, with
    groups off, C(188,6).
  - A new test checks the option-on view: the default (engine) gives 1,174,080,931,485 =
    C(310,6). Positive control: forcing `groups=True` on the same view gives 1,163,212,171,902.
- **Findings**:
  - The option-on view allows 310 species.
  - Both option-on figures were computed by the engine and match the closed form
    (2026-10-13; see spec Background).

## R6. Constitution v1.2.0 Principle III

- **Off by default**: yes, the existing option.
- **Validator enforces it**: the validator applies it per options view. With the option on, the
  validator still checks every other rule.
- **Label on each affected source**: `SECOND_GAME_NOTE` (R2).
- **Option recorded**: `provenance.legality_options` already records it (003 FR-012).
- **Not described as single-cartridge**: a labelled source says "second Platinum game".
