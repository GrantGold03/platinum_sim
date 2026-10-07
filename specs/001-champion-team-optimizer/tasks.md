---

description: "Task list for the Champion Team Optimizer"
---

# Tasks: Champion Team Optimizer

**Input**: Design documents from `specs/001-champion-team-optimizer/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required. The constitution (Development Workflow & Quality Gates) mandates extraction,
legality, divergence and determinism tests, and Principle V requires positive controls.

**Organization**: The tasks are grouped by user story. User Story 1 (optimize) and User Story 2
(evaluate) both need the battle engine, so the engine is in Phase 2 (Foundational).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2 or US3 (from spec.md)
- Paths are relative to the repository root.
- Short names used below:
  - `PP` = `pokeplatinum/`
  - `PS` = `pokemon-showdown/`
  - `FD` = `specs/001-champion-team-optimizer/`

## Rules that apply to every task

- **Game facts**: every game fact in code or tests MUST be read from `PP` and cite `path:line` in a
  `src` field or test comment. Never type a game value from memory. If a test needs a known value,
  open the decomp file, copy the value, and cite it.
- **Pinned commits**: `PP` @ `c248fb3f8cc9934ded800e489567c5c0eeee92eb`,
  `PS` @ `c046106cbe075931b1ff8d8b800ff5be47a85f96`. Do not edit any file under `PP/` or `PS/`
  (Showdown build outputs `node_modules/` and `dist/` are the only exception).
- **Done means verified**: a task is done only when its test or check has been run and the output
  is recorded in `FD/validation-log.md` (Constitution V).
- **Temporary files**: temporary scripts go in the session scratchpad, never `/tmp` or the repo.
- **RUN-STATE**: keep `RUN-STATE.md` at the repo root updated as tasks land (goal, method, done,
  next, traps).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton, toolchains, pins.

- [X] T001 Create `pyproject.toml` with:
  - package `platsim` under `src/`, `requires-python = ">=3.14"`;
  - dependencies `fastapi`, `uvicorn`, `openpyxl`;
  - dev dependency `pytest`, plus `httpx` (needed by FastAPI's TestClient);
  - console script `platsim = "platsim.cli:main"`.
  
  Then run `uv sync` and record its output. If any package fails to install on Python 3.14,
  stop and report it; do not downgrade Python silently.
- [X] T002 [P] Create the directory skeleton from plan.md:
  - `src/platsim/{decomp,availability,legality,divergence,sim,optimizer,report,web,web/static}/__init__.py`
    (no `__init__.py` in `web/static`);
  - `sim/{ai,ai/cmds,policy,spikes,test}/`;
  - `tests/{unit,integration,fixtures}/`;
  - `data/`.
- [X] T003 [P] Create `sim/package.json` (`"type": "module"`, `"private": true`,
  `"scripts": {"test": "node --test test/"}`, no dependencies). Create `sim/showdown.mjs`, which
  re-exports `Battle`, `Dex`, `Teams`, `PRNG` from `../pokemon-showdown/dist/sim/index.js` via
  `createRequire`. This is the only file that imports Showdown.
- [X] T004 Build Showdown: `cd pokemon-showdown && npm ci && node build`. This needs network once.
  - Verify `pokemon-showdown/dist/sim/index.js` exists.
  - Verify `node -e "require('./pokemon-showdown/dist/sim').Dex.mod('gen4').species.get('garchomp').baseStats"`
    prints stats.
  - Record both outputs in `FD/validation-log.md`.
- [X] T005 [P] Create `src/platsim/pins.py`:
  - constants `DECOMP_COMMIT`, `SHOWDOWN_COMMIT`, `ROM_REV1_SHA1 = "0862ec35b24de5c7e2dcb88c9eea0873110d755c"`;
  - `check_pins()`, which runs `git -C <repo> rev-parse HEAD` and `git status --porcelain` (ignoring
    `node_modules/`, `dist/` and `config/config.js` in `PS`) and raises with a clear message on a
    mismatch.
  
  Test in `tests/unit/test_pins.py`: positive control (passes on the real repos) and negative
  control (a monkeypatched wrong commit raises).
- [X] T006 [P] Add `/data/generated/` to `.gitignore` (`/runs/`, `.venv/` and `node_modules/` are
  already there). Add `tests/conftest.py` with `DECOMP_ROOT` and `SHOWDOWN_ROOT` fixtures pointing
  at the vendored dirs.
- [X] T007 [P] Create `RUN-STATE.md` at the repo root with sections Goal, Method, Done, Next, Traps,
  seeded from plan.md's "Phases after this plan".

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Game data, availability, legality, the battle engine with game layer, statistics and
report writers. Both US1 and US2 depend on all of this.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### 2a. Spikes (do first; results can change the plan)

- [X] T008 [P] Throughput spike in `sim/spikes/throughput.mjs`:
  - In one Node process, run 500 battles in format `gen4customgame` with seed
    `sodium,<run index as 32 hex>`.
  - p2 is Cynthia's team, typed from `PP/res/trainers/data/champion_cynthia.json`.
  - p1 is a fixed 6-member level-60 team.
  - Both sides choose `default`.
  - Print battles/s and mean turns.
  
  Then run 16 copies in parallel and report aggregate battles/s. Write the numbers into
  `FD/research.md` under a new "R8 – Measured" subsection.
- [X] T009 [P] Mid-battle level-up spike in `sim/spikes/levelup.mjs`. After turn 1, set a p1
  Pokémon's `level` and `set.level`, recompute stored stats and `maxhp` using Showdown's stat
  routine, and raise `hp` by the max-HP increase.
  - Verify a later damage roll uses the new stats. Use the same seed with and without the change
    and compare.
  - Record works / doesn't work and the exact code in `FD/research.md` R5. If it doesn't work, mark
    the ledger plan as "levels applied between battles".
- [X] T010 [P] Full Restore spike in `sim/spikes/fullrestore.mjs`.
  - Before the first `Dex.get`, add a move `trainerfullrestore` to `Dex.mod('gen4').data.Moves`:
    priority high enough to act before all moves, no PP use shown, heals to full HP, cures status
    and confusion, target self, never misses.
  - Have p2 choose it on a turn when p2 is poisoned and below 25% HP.
  - Verify the HP, the status and that it acted first.
  - Record the result in `FD/research.md` R5.

**Checkpoint A**: If T008 shows < 5 battles/s per process, or T009/T010 fail, update plan.md and
research.md (R5/R7/R8) before continuing.

### 2b. Decomp readers (Python)

- [X] T011 [P] `src/platsim/decomp/constants.py`:
  - `load_enum(name)` parses `PP/generated/<name>.txt`: value = 0-based line index, or the explicit
    value after `=` when present. Skip blank lines and handle trailing `MAX_*`/`NUM_*` sentinels.
  - Returns `{name: int}` plus a `src` ref per name.
  
  Tests in `tests/unit/test_constants.py`: `SPECIES_NONE == 0`, `SPECIES_EGG == 494`,
  `SPECIES_BAD_EGG == 495`, `ABILITY_NONE == 0`, `TYPE_MYSTERY == 9` (values per research.md R1;
  re-confirm against the files).
- [X] T012 [P] `src/platsim/decomp/species.py`, which reads every `PP/res/pokemon/<name>/data.json`
  and the forms listed as `data` in `PP/res/pokemon/form_registry.json`:
  - Map the folder name to `SPECIES_*` with the rule in `PP/res/pokemon/meson.build`.
  - Reorder `base_stats` to hp/atk/def/spa/spd/spe.
  - Set `abilities[1] = None` when it is `ABILITY_NONE`.
  - Parse evolutions by array shape exactly as `PP/tools/dataproc/src/speciesproc.c:552-630`.
  - Display name from `pokedex_data.en.name`.
  
  Tests in `tests/unit/test_species.py` (SC-005: at least 20 species): full records (base stats,
  types, abilities, exp rate, level-up learnset, TM list, tutor list, evolutions), with values
  copied from each `data.json` and cited, for 20 species chosen to cover:
  - all six of Cynthia's species and Garchomp's line (Gible, Gabite);
  - Bulbasaur;
  - a mono-type species whose type is repeated;
  - a species with two abilities and one with `ABILITY_NONE` in slot 2;
  - a trade evolution (Kadabra → Alakazam `EVO_TRADE`);
  - an item-trade evolution (Onix → Steelix `EVO_TRADE_WITH_HELD_ITEM`);
  - a `LEVEL_KNOW_MOVE` evolution (Piloswine → Mamoswine);
  - a `LEVEL_SPECIES_IN_PARTY` evolution (Mantyke → Mantine);
  - a form with its own stats (Rotom-Wash);
  - Eevee (7 evolutions);
  - Shedinja (Ninjask/Shedinja methods).
  
  Also test the total species count.
- [X] T013 [P] `src/platsim/decomp/moves.py`: read `PP/res/moves/<name>/data.json`, with the
  accuracy and power normalisation from `PP/tools/dataproc/src/moveproc.c:136-147`.
  - Test Quick Attack priority 1, Swift accuracy 0 (never misses), and Earthquake fields, copied
    from source.
- [X] T014 [P] `src/platsim/decomp/items.py`: read `PP/res/items/data/*.json` (skip `ITEM_UNUSED_*`
  per `itemproc.c:162`) and the TM/HM → move map from `teachesMove`.
  - Test TM01 = Focus Punch, TM26 = Earthquake, TM92 = Trick Room, HM08 = Rock Climb; Leftovers
    hold effect `HOLD_EFFECT_HP_RESTORE_GRADUAL`; Lucky Egg `HOLD_EFFECT_EXP_UP`.
- [X] T015 [P] `src/platsim/decomp/tutors.py`: read `PP/res/pokemon/move_tutors.json` (38 entries,
  array order = bit index) and add the two script tutors:
  - Draco Meteor: `scripts_route_210_grandma_wilma_house.s`, Dragon type + max friendship.
  - Starter ultimates: `scripts_route_228_north_house.s`, with the 12 species parsed from
    `Route228NorthHouse_CheckFinalStageStarter`.
  
  Test 38 entries, Dive at ROUTE_212 costing 2/4/2/0, and Superpower at SURVIVAL_AREA.
- [X] T016 [P] `src/platsim/decomp/exp.py`: parse `PP/res/pokemon/.shared/exp_tables.csv` (column
  order = `generated/exp_rates.txt`) and add `level_from_exp(rate, exp)` mirroring
  `PP/src/pokemon.c:2366` and `exp_at(rate, level)`.
  - Test that level-100 values match the CSV, and the boundary cases exp = table[n] − 1 → n−1 and
    exp = table[n] → n.
- [X] T017 [P] `src/platsim/decomp/trainers.py`: read the five first-run files listed in
  `FD/research.md` R3. Port `TrainerData_BuildParty` (`PP/src/trainer_data.c:176-316`):
  - LCRNG `state*1103515245+24691`, return `>>16` (`PP/src/math_util.c:80`);
  - seed `ivScale+level+species+trainerID`;
  - iterate `trainerType` times;
  - `(rnd<<8)+genderMod` (120 female class / 136 male, from
    `PP/include/data/trainer_class_genders.h`);
  - IV = `ivScale*31//255`;
  - nature = personality % 25;
  - ability slot from `personality & 1`.
  
  Tests in `tests/unit/test_trainers.py`: the parties match research.md R3 (species, level, moves,
  held item, bag items, AI flags); all IVs are 30; every ability is slot 1. Personalities and
  natures are a cross-check against R3's values, which came from a separate re-implementation. If
  they disagree, re-derive both by hand from the C code and record which was wrong.
- [ ] T018 `src/platsim/decomp/scripts.py`, a field-script parser for `PP/res/field/scripts/*.s`:
  - tokenize labels, `ScriptEntry` lines (index = order) and commands with args;
  - build a control-flow graph over `GoTo`/`Call`/`GoToIf*`/`CallIf*`/`End`;
  - resolve `CallCommonScript`/`Common_*` to `scripts_common.s`;
  - `script_id → (file, entry)` per `PP/include/script_manager.h:89-119` (local 1–1999; 2000 common;
    7000 visible items; 8000 hidden items; etc.);
  - every node keeps `file:line`.
  
  Tests: `VisibleItems_OreburghGateB1F_TM01` gives TM01 ×1; Route 201 starter `GivePokemon` at
  level 5.
- [X] T019 `src/platsim/extract.py` and the `platsim extract [--check]` subcommand in
  `src/platsim/cli.py`:
  - run every reader (T011–T018, plus T024 once it exists);
  - write `data/generated/{species,moves,items,tutors,trainers,exp,availability}.json` and
    `manifest.json` (decomp commit, sha256 per output);
  - `--check` regenerates in memory and exits 1 on any difference;
  - call `check_pins()` first.
- [X] T020 `tests/integration/test_extract.py`: run extract twice and assert identical bytes; run
  `--check` and assert exit 0; corrupt one output byte and assert `--check` exits 1 (positive
  control).

### 2c. Availability ledger (FR-003–FR-006, research R2)

- [ ] T021 `src/platsim/availability/mapgraph.py`:
  - nodes = `MAP_HEADER_*` from `PP/generated/map_headers.txt`;
  - script and encounter links from `PP/include/data/map_headers.h`;
  - edges from:
    - `warp_events` in `PP/res/field/events/events_*.json`;
    - script warps (`Warp`, `TakeShipFrom*`) via T018;
    - adjacency of non-`MAP_HEADER_EVERYWHERE` cells in `PP/res/field/matrices/map_matrix_000.json`;
    - hidden locations (`EnableHiddenLocation`).
  - Each edge records the script node that triggers it, if any. Reachability starts from
    `MAP_HEADER_TWINLEAF_TOWN`.
- [ ] T022 `src/platsim/availability/gates.py`: for a script node, collect the gate conditions on
  every path that reaches it: `FLAG_GAME_COMPLETED` checks, `CheckGameCompleted`,
  `GetNationalDexEnabled` comparisons, and badge checks (`CheckBadgeAcquired`).
  - Classify a node post-game if all paths to it require a post-game gate.
  - A map edge is cut when its trigger is post-game.
  - Each gate keeps `file:line`.
- [ ] T023 `src/platsim/availability/sources.py`, which emits `AvailabilityEntry` records (shape in
  `FD/data-model.md`) for:
  - **Wild encounters**: grass, surf, old/good/super rod, swarm, radar, day/night, dual-slot,
    Trophy Garden, Great Marsh (before/after lists), honey trees and Feebas, each tagged with its
    slot-type gate per `PP/src/overlay006/wild_encounters.c` (research R2 rule 3).
  - **Gifts, eggs and fixed encounters**: `GivePokemon`, `GiveEgg`, `StartWildBattle`,
    `StartLegendaryBattle`, `StartGiratinaOriginBattle`, roamers via `ActivateRoamingPokemon`, and
    fossils via `PP/src/scrcmd_fossil.c`.
  - **NPC trades**: `PP/res/npc_trades/*.json`, linked to the `InitNPCTrade` call site, with a
    `FixedMon`.
  - **Item balls**: only script IDs referenced by some events JSON.
  - **Hidden items**: from `PP/include/data/field/hidden_items.h`; quantity unlimited when the flag
    is daily-cleared per `PP/src/script_manager.c` `FieldSystem_ClearDailyHiddenItemFlags`.
  - **NPC item gifts**: `Common_GiveItemQuantity` with `VAR_0x8004`/`VAR_0x8005`, and `AddItem`.
  - **Shops**: `PP/include/data/mart_items.h` with badge tier per `PP/src/scrcmd_shop.c:21-74`,
    plus specialties linked to their `PokeMartSpecialties*` call sites; all unlimited.
  - **Game Corner**: `PP/src/scrcmd_game_corner_prize.c:22-41`; unlimited.
  - **Underground**: `PP/src/underground/mining.c`; pre-National Dex weights only.
  - **Tutors**: from T015.
- [ ] T024 `src/platsim/availability/ledger.py`:
  - set `phase` from gates and reachability, never by hand;
  - queries:
    - `species_sources(species)`: includes evolution from an obtainable pre-evolution, and
      excludes `EVO_TRADE`/`EVO_TRADE_WITH_HELD_ITEM` per FR-005;
    - `tm_copies(tm)` (int or unlimited);
    - `item_copies(item)`;
    - `tutor_available(location)`;
  - add `availability.json` to extract (T019).
- [ ] T025 `tests/integration/test_availability_controls.py`.
  - **Must be post-game**: Fight Area and Survival Area maps; Survival Area tutor; Route 228 tutor;
    Foppa Magikarp trade (Route 226); Super Rod; all swarm and Poké Radar slots; Regice, Registeel,
    Regirock, Regigigas, Heatran.
  - **Must be pre-Champion**: Route 212 and Snowpoint tutors; TM76 from the Oreburgh gym; Kazza
    Abra, Charap Chatot and Gaspar Haunter trades; Riolu egg; Togepi egg; Eevee; Porygon; Rotom;
    Spiritomb; Giratina; Uxie; Azelf; all eight gym maps, Victory Road and every Pokémon League
    room reachable; Veilstone 3F TMs unlimited.
  
  Every assertion cites the script line that justifies it.
- [ ] T026 Resolve research R2's UNVERIFIED items:
  - which maps use `encounters_unknown_533–557`;
  - honey tree map headers;
  - whether Victory Road or the League is badge-gated;
  - whether the Snowpoint tutor has a gate;
  - whether any PP-restoring item (Ether, Max Ether, Elixir, Max Elixir, Leppa Berry as a
    repeatable source) can be bought, or respawns, before the Champion (`PP/include/data/mart_items.h`,
    specialty marts, Game Corner, daily hidden items). Write the answer to
    `data/generated/availability.json` as `pp_restore_between_battles: true|false` with refs.
  
  Record the findings with `file:line` in `FD/research.md` R2 and add a control to T025 for each.

### 2d. Legality validator (Constitution III, independent of the optimizer)

- [X] T027 [P] `src/platsim/legality/models.py`: dataclasses `Build`, `MoveChoice`, `TeamCandidate`,
  `Violation(code, message, src)` exactly as in `FD/data-model.md`, with JSON round-trip and
  Showdown export/import of the team.
- [ ] T028 `src/platsim/legality/movesources.py`: `sources(species, move, level, ledger)` returns
  every legal `MoveChoice` source:
  - level-up at or below level;
  - pre-evolution level-up, where the pre-evolution's level must be below its evolution level;
  - move relearner (only if its map is pre-Champion per the ledger);
  - TM/HM;
  - pre-Champion tutor (honour Draco Meteor and starter requirements);
  - egg move, where a pre-Champion-obtainable father in a shared egg group must be able to learn
    the move by a non-egg method; record the father.
  
  The `detail` strings follow `FD/contracts/spreadsheet.md`.
- [ ] T029 `src/platsim/legality/validator.py`: `validate(team) -> list[Violation]`. It checks:
  - species availability (FR-003, FR-005);
  - source choice (FR-008b);
  - move legality at `start_level` (FR-007);
  - ability rules (FR-008c, fixed by trade);
  - IV 15 / EV 85 / neutral nature, or `FixedMon` values (FR-008);
  - held-item availability and copies (FR-006);
  - TM copies across the team (FR-004);
  - final level gap ≤ 10, when final levels are present.
  
  It MUST NOT import `platsim.optimizer`; enforce this with a test that inspects `sys.modules`
  after import.
- [ ] T030 [P] Fixtures and tests:
  - fixtures in `tests/fixtures/`: `legal_team.json`, `illegal_postgame_tutor.json`,
    `illegal_trade_evo.json` (Gengar), `illegal_tm_copies.json` (two members using a single-copy
    TM), `illegal_stats.json` (IV 31), `illegal_ability.json`, `illegal_level_gap.json`;
  - tests in `tests/unit/test_validator.py`: each illegal fixture yields exactly the expected
    violation codes, and the legal one yields none.
- [ ] T031 `platsim validate TEAM` in `src/platsim/cli.py` per `FD/contracts/cli.md` (exit 2 with
  violations).

### 2e. Battle engine and game layer (Node)

- [X] T032 `sim/worker.mjs`:
  - NDJSON loop on stdin/stdout per `FD/contracts/worker-protocol.md`;
  - `hello` op;
  - at startup, load `data/generated/*.json` and `data/divergences.json` and apply every
    `corrected` data patch to `Dex.mod('gen4').data` before any `Dex.*.get()`. If
    `data/divergences.json` does not exist yet (it is created by T053), apply no patches and
    report `divergence_ledger_version: "none"` in `hello`;
  - register the `trainerfullrestore` pseudo-move from T010.
- [X] T033 [P] Seed derivation, the same in `sim/seeds.mjs` and `src/platsim/sim/seeds.py`:
  `sodium,` + first 32 hex of `sha256(f"{master}|{run}|{battle}")`.
  - Test both languages produce identical seeds for 100 inputs; the Python test calls the Node
    function via a subprocess.
- [X] T034 [P] `sim/team.mjs`: Build JSON → Showdown `PokemonSet` (level, ivs, evs, nature,
  ability, item, moves). Opponent party: IV 30 all, EV 0, nature and ability from
  `trainers.json`. For **both** sides, after the Battle is constructed, reset every move slot to
  base PP (`maxpp = pp = move.pp`, `ppUps = 0`), because Showdown applies 3 PP Ups
  (`pokemon-showdown/sim/pokemon.ts:361`) and the spec says no PP Ups (FR-008, research R5). Test
  that Cynthia's Spiritomb Dark Pulse has 15 PP and so does the same move on a player build.
  - Test that a converted Garchomp at a known level gets the stats computed by the decomp formula
    (`PP/src/pokemon.c:564`) via a Python reference function in `src/platsim/decomp/stats.py`.
    Create that function with its own unit test.
- [X] T035 `sim/gauntlet.mjs`, the `gauntlet` op:
  - run trainers in order;
  - between battles restore HP, status and fainted members; carry PP over unless
    `pp_restore_between_battles` from T026 is true, in which case restore PP too (FR-012); keep
    levels and exp;
  - accept an optional `start_state` (levels, exp, PP, items) and return `state_before` for each
    battle when `log` is `summary` or `full` (`FD/contracts/worker-protocol.md`, op 4);
  - turn limit or draw counts as a loss;
  - `stop_on_loss`;
  - returns the result object from the worker contract.
- [X] T036 `sim/exp.mjs`: participation mask exactly per `PP/src/battle/battle_lib.c:1456-1479` and
  `PP/src/battle/battle_script.c:455-626`. Exp per `BtlCmd_CalcExpGain` (`battle_script.c:2186`) and
  `BattleScript_GetExpTask` (`:9685`):
  - u16 truncation;
  - Exp. Share split;
  - Lucky Egg ×1.5;
  - trainer ×1.5;
  - traded ×1.5 (×1.7 for a different language);
  - minimum 1.
  
  Level-ups are applied mid-battle if T009 succeeded, otherwise between battles; new moves are
  declined and evolution is declined.
  
  Tests in `sim/test/exp.test.mjs`: at least 8 hand-computed cases (show the arithmetic in
  comments), including multi-level gain, an Exp. Share holder that did not participate, and a
  traded Lucky Egg holder.
- [X] T037 `sim/damage.mjs`: port `BattleSystem_CalcMoveDamage` (`PP/src/battle/battle_lib.c:6601-7080`)
  plus the crit multiplier, the variance (`:7081`) and the type chart (`:2399`, `:2560`), returning
  all 16 rolls.
  - Tests in `sim/test/damage.test.mjs`: ≥ 50 combinations (physical/special, STAB, ×4/×0.25/×0
    effectiveness, crit, burn, Choice Band, weather, abilities that modify damage). Compare against
    Showdown's damage for the same inputs (via `battle.actions.getDamage` with a fixed roll).
  - Each mismatch either is a bug in the port (fix it) or becomes a divergence entry with the
    decomp line.
- [X] T038 `sim/ai/parse.mjs`:
  - parse `PP/asm/macros/aicmd.inc` macro definitions (opcode and argument kinds) and
    `PP/src/battle/trainer_ai/script.s` into `{labels, instructions[{op, args, line}]}`;
  - resolve `gTrainerAITable` flag offsets;
  - fail loudly on any unknown macro.
  
  Test that it parses the full file, that the section labels exist at the lines given in research
  R6, and that the opcode count is 109 per `PP/include/data/scripts/aicmd.h`.
- [X] T039 `sim/ai/adapter.mjs`: read-only battle-state queries the commands need (HP, status,
  stat stages, types, ability, item, last move used, side conditions, weather, party, move data,
  turn count, whether a move was used before) over Showdown `Battle`/`Side`/`Pokemon` objects.
  Each query documents the decomp field it mirrors (`battleCtx->…`).
- [X] T040 [P] `sim/ai/cmds/flow.mjs`: control-flow, compare, jump, call, return and score-adjust
  commands, each implemented with a comment citing the `trainer_ai.c` handler line.
- [X] T041 [P] `sim/ai/cmds/battler.mjs`: HP, status, stat-stage, type, ability, item and volatile
  query commands, with citations.
- [X] T042 [P] `sim/ai/cmds/moves.mjs`: move-effect, power, type, priority, last-used and
  move-in-set queries, with citations.
- [X] T043 [P] `sim/ai/cmds/damage.mjs`: `FlagMoveDamageScore`, `IfCurrentMoveKills`, highest-damage
  comparisons, using `sim/damage.mjs` with the AI's per-move roll from `TrainerAI_Init`.
- [X] T044 [P] `sim/ai/cmds/misc.mjs`: random-chance, turn-count, weather, side-condition, party and
  remaining commands. Any opcode still unimplemented MUST throw `ai_unimplemented` with its name
  and the script line that reached it.
- [ ] T045 `sim/ai/choose.mjs`: `TrainerAI_Init` (scores 100, invalid → 0, per-move roll),
  `TrainerAI_EvalMoves`, and `TrainerAI_MainSingles` (flag order, max score, random tie break via
  the run PRNG).
- [ ] T046 `sim/ai/switch.mjs`: `TrainerAI_ShouldSwitch` (`trainer_ai.c:3894`) and
  `BattleAI_PostKOSwitchIn` (`battle_lib.c:7923-8090`), including the documented u8 overflow bug
  (`PP/docs/bugs_and_glitches.md`).
- [ ] T047 `sim/ai/items.mjs`: `TrainerAI_ShouldUseItem` (`trainer_ai.c:4056`), which uses
  Full Restore only when `0 < hp < maxhp/4`, plus the slot rule and the no-break
  double-consumption behaviour. On "use", p2 chooses `trainerfullrestore` and the count is
  decremented. Then `TrainerAI_PickCommand` order: switch → item → fight.
- [ ] T048 AI tests:
  - `sim/test/ai_cmds.test.mjs`: at least one test per implemented opcode.
  - `sim/test/ai_golden.test.mjs`: at least 15 hand-built positions across all five trainers. Each
    fixture comment walks through the script lines that produce the expected choice. Include Full
    Restore use at 24% HP, no use at 26%, a post-KO switch-in choice, and Lucian's
    SETUP_FIRST_TURN.
  - Also run 200 full gauntlets with `greedy-v1` and assert no `ai_unimplemented` is reached. If
    one is reached, implement that opcode.
- [ ] T049 [P] `sim/policy/greedy.mjs`: pick the highest expected-damage move via `sim/damage.mjs`;
  switch only when forced, to the member with the best expected damage.
- [ ] T050 `sim/policy/expectimax2.mjs` per research R7:
  - enumerate actions;
  - predict the opponent with the AI (`sim/ai/choose.mjs`, `switch.mjs`, `items.mjs`) on a
    hypothetical state;
  - weight outcomes by the 16 rolls × accuracy × crit chance;
  - turn order per the decomp speed rules;
  - 2 plies;
  - leaf evaluation documented in a header comment.
  
  The policy is named `expectimax2-v1`.
- [ ] T051 `sim/test/determinism.test.mjs`: the same gauntlet request run twice gives byte-identical
  output, for both policies; a different seed changes the output (positive control). Also assert
  over 200 gauntlets that every p1 choice is a `move` or `switch`, never an item (FR-011).
- [ ] T052 `src/platsim/sim/pool.py`:
  - start W workers (default `os.cpu_count()`);
  - `hello` check that provenance matches pins;
  - submit requests and gather by id;
  - restart a crashed worker and re-run its request;
  - propagate `ai_unimplemented` as an error that stops the job.
  
  Test in `tests/integration/test_pool.py`.
- [ ] T053 Divergence ledger:
  - `sim/dump_dex.mjs` dumps Showdown gen4 species, moves and items as JSON;
  - `src/platsim/divergence/compare.py` diffs that dump against `data/generated/` and writes
    `data/divergences.json` (fields per data-model `DivergenceEntry`);
  - add the mechanics entries from research R5 and R6 (AI, Full Restore, exp, level-up timing,
    RNG differs from the cartridge), each with a decomp ref;
  - add the `platsim divergences` command, which exits 1 if any entry lacks a resolution;
  - test in `tests/integration/test_divergences.py`, with a positive control that injects a fake
    stat difference and expects an entry.
- [X] T054 [P] `src/platsim/stats.py`:
  - Wilson 95% CI;
  - runs needed for a given half-width;
  - paired comparison of two candidates on shared seeds (McNemar exact test on discordant pairs);
  - mean and CI of final average level.
  
  Tests against textbook values in `tests/unit/test_stats.py`.
- [X] T055 [P] Report writers:
  - `src/platsim/report/json_report.py`: the EvaluationReport from data-model;
  - `src/platsim/report/xlsx.py`: the sheets Team, Evaluation, Resources, Provenance and
    Divergences, exactly per `FD/contracts/spreadsheet.md`;
  - `src/platsim/report/csv_report.py`: the Team sheet.
  
  Test in `tests/unit/test_reports.py`: open the xlsx with openpyxl and check the sheet names,
  headers and that every move has a source.
- [ ] T056 Policy strength benchmark, `tests/integration/test_policy_strength.py`: on
  `tests/fixtures/reference_team.json`, run 2,000 paired gauntlets for `greedy-v1` and
  `expectimax2-v1`. `expectimax2-v1` must have a higher clear rate with a significant paired test.
  Record rates, CIs and run time in `FD/research.md` R7. If it fails, improve the leaf evaluation;
  do not relabel the policy as strong.

- [ ] T057 `src/platsim/sim/champion.py`, the Cynthia top-up (FR-017, SC-003, research R8
  "Champion share"):
  - from the full gauntlet results of a candidate, collect the `state_before` of every Cynthia
    battle;
  - run Cynthia-only gauntlets (`trainers: ["cynthia"]`, `start_state` drawn with replacement
    from those states, seeds derived with battle index 99 so they never collide with full runs)
    until Cynthia's Wilson half-width meets the budget preset's target **and** her battle count
    exceeds every Elite Four member's;
  - return her win rate as P(win | reached Cynthia) with its CI, separately from the gauntlet
    clear rate.
  
  If no full run reached Cynthia, report that and run no top-up; never invent a start state.
  Test in `tests/integration/test_champion_topup.py` that the counts meet the rule, that the
  result is deterministic for a fixed seed, and that the zero-reach case is handled.

**Checkpoint B**: data extracted, ledger controls pass, validator passes, worker deterministic, AI
reaches no unimplemented opcode, policy benchmark recorded. Update `RUN-STATE.md`.

---

## Phase 3: User Story 1 - Find the lowest-level team that beats the League (Priority: P1) 🎯 MVP

**Goal**: Six species in, the optimized legal team out (CLI and web page), with the xlsx sheet.

**Independent Test**: `platsim optimize <six species> --seed fixed` gives either a qualifying team
(clear ≥ 75%, CI half-width ≤ 2 points, final gap ≤ 10, passes `platsim validate`) or a "no
qualifying team" report. Running it again gives identical output. The web flow V9 in
`FD/quickstart.md` works.

### Tests for User Story 1

- [ ] T058 [P] [US1] `tests/integration/test_optimize_small.py`: optimize with `--budget quick` on a
  fixed six-species set and seed. Assert:
  - the output passes `validator.validate`;
  - the report has every provenance field;
  - the `quick` budget is labelled in the output;
  - two runs give identical JSON.
- [ ] T059 [P] [US1] `tests/integration/test_web.py` (FastAPI TestClient):
  - species search returns Garchomp for `gar`, and the post-game-only species are flagged;
  - POST with 5 species gives 422;
  - a valid POST gives 201;
  - polling reaches `done` with a stubbed fast optimizer;
  - result endpoints return 409 before done and files after.

### Implementation for User Story 1

- [ ] T060 [P] [US1] `src/platsim/optimizer/abilities.py`, FR-008c. An ability has a battle effect
  iff its `ABILITY_*` constant is referenced anywhere under `PP/src/battle/` (grep at extract
  time; store the refs).
  - Screening runs 200 paired gauntlets per ability; it keeps slot 1 when there is no significant
    difference and records `ability_reason`.
  - Test with a positive control: an ability known to be referenced in battle code yields
    has-effect with refs.
- [ ] T061 [P] [US1] `src/platsim/optimizer/candidates.py`: for each member, enumerate:
  - sources (wild / gift / NPC trade, FR-008b);
  - legal moves at a level via `legality/movesources.py`;
  - prune moves per research R8 (strictly dominated: same type, category and accuracy class,
    lower power, no secondary effect);
  - held items from the ledger.
- [ ] T062 [US1] `src/platsim/optimizer/resources.py`: assign single-copy TMs and limited items
  across the team (a member may only take a copy if one is left). Candidates that violate this are
  never generated.
- [ ] T063 [US1] `src/platsim/optimizer/screen.py`: successive halving over candidate teams at a
  fixed level vector, with paired seeds. Rounds of 100 → 200 → 400 runs, keeping the top third.
- [ ] T064 [US1] `src/platsim/optimizer/levels.py`:
  - bisection on a uniform start-level offset to the lowest level that meets the threshold;
  - then per-member descent while the final gap stays ≤ 10 and the threshold holds;
  - the objective is the simulated expected final average level (FR-016);
  - borderline handling per research R8.
- [ ] T065 [US1] `src/platsim/optimizer/run.py`: orchestrate prune → ability screen → screen →
  level search → confirm (run counts per the budget preset in `FD/research.md` R8; paired runs on
  the winner and runner-up, FR-019) → Cynthia top-up via T057 for the winner.
  - Checkpoint to `runs/<job-id>/state.json` after each stage and resume from it.
  - Run `validator.validate` on the final team; a violation is a hard error.
  - Emit a "no qualifying team" report with the best rate and levels when nothing qualifies.
- [ ] T066 [US1] `platsim optimize` in `src/platsim/cli.py` per `FD/contracts/cli.md`: species
  name/key resolution with closest-match errors, `--min-clear`, `--seed`, `--workers`, `--budget`.
  Writes JSON, xlsx, csv and `team.txt` (Showdown export, via T027) into `runs/<job-id>/`, as the
  constitution's Interface rule requires. T058 asserts `team.txt` exists and re-imports to the
  same team.
- [ ] T067 [US1] `src/platsim/web/app.py` per `FD/contracts/http-api.md`:
  - bind to 127.0.0.1;
  - `/api/species` reads the ledger;
  - a single-job FIFO queue runs `optimizer.run` in a background thread with progress callbacks;
  - job state is persisted in `runs/<id>/job.json`;
  - `platsim serve` subcommand.
- [ ] T068 [P] [US1] `src/platsim/web/static/index.html`, `style.css`, `app.js` (plain JS, no
  framework):
  - search-as-you-type list, with a toggle to show excluded species and their reasons;
  - six slots with remove;
  - options for min clear and seed;
  - Optimize button;
  - progress panel polling every 2 s;
  - result table with the spreadsheet columns, plus download links.
  
  Must work at phone width.

**Checkpoint**: US1 is complete when T058 and T059 pass and quickstart V8 and V9 have been run
with their output recorded.

---

## Phase 4: User Story 2 - Battle-test a user-specified team (Priority: P2)

**Goal**: Evaluate a fixed team: legality first, then per-battle and gauntlet clear rates.

**Independent Test**: `platsim evaluate tests/fixtures/reference_team.json --runs 2000 --seed fixed`
twice gives identical reports, with per-trainer rates and CIs, expected final levels and loss
causes. An illegal team exits 2 with its violations.

- [ ] T069 [P] [US2] `src/platsim/report/losses.py`: from gauntlet results (`log: summary`),
  tally which opponent Pokémon were on the field when the player's last member fainted, per
  trainer. Test with synthetic results.
- [ ] T070 [US2] `platsim evaluate TEAM` in `src/platsim/cli.py`:
  - accepts JSON or Showdown export;
  - validate first (exit 2 on violations);
  - run N paired gauntlets through `pool.py`;
  - stats via `stats.py`;
  - Cynthia top-up via T057;
  - write the reports via T055 with loss causes, plus `team.txt` (Showdown export, via T027).
- [ ] T071 [US2] `tests/integration/test_evaluate.py` (quickstart V7): determinism across two runs;
  CI half-width ≤ 2 points at 2,000 runs; an illegal fixture exits 2.

- [ ] T072 [US2] `tests/integration/test_final_levels.py` (SC-006):
  - add `exp_gain(...)` to `src/platsim/decomp/exp.py`: an independent Python implementation of
    the decomp exp formula (same `file:line` refs as T036);
  - run 200 seeded gauntlets of `tests/fixtures/reference_team.json` with `log: "full"`, recompute
    each run's final levels in Python from the battle log (who was active when each opponent
    fainted, held items, traded flag), and assert they equal the worker's final levels exactly;
  - assert the mean final average level matches the Python value within 1 level;
  - include one fully hand-worked run in `tests/fixtures/reference_team_handcalc.md`, showing the
    arithmetic for every exp award.

**Checkpoint**: US2 works on its own with any legal fixed team.

---

## Phase 5: User Story 3 - Trace every rule and number back to the game (Priority: P3)

**Goal**: `platsim explain` answers "why" with game-source references.

**Independent Test**: quickstart V3 and V4 outputs match the expected values, each line with a
`file:line` ref. Divergence entries are queryable.

- [ ] T073 [US3] `platsim explain SUBJECT` in `src/platsim/cli.py`:
  - subjects `tmNN`, `hmNN`, `species:<key>`, `item:<key>`, `move:<key>`, `trainer:<key>`,
    `divergence:<id>`;
  - prints availability entries (phase, quantity, gates) or trainer details, each with `src` refs.
- [ ] T074 [US3] `tests/integration/test_explain.py`:
  - Cynthia's party output (V3);
  - Abra pre-Champion trade and Magikarp Foppa post-game (V4);
  - a Game Corner TM shows "unlimited";
  - an unknown subject exits 2 with suggestions.

**Checkpoint**: All three stories work independently.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T075 [P] `README.md`: what the tool does, setup (quickstart prerequisites), CLI and web usage,
  how to read the spreadsheet, and the provenance and divergence concepts.
- [ ] T076 Run every scenario V1–V9 in `FD/quickstart.md` and record the commands and real outputs
  in `FD/validation-log.md`. Record the quickstart benchmarks (runs/s per policy, full optimize
  wall time) in `FD/research.md` R8.
- [ ] T077 Constitution compliance review against `.specify/memory/constitution.md` Principles I–V.
  Record findings in `FD/validation-log.md`, and fix or justify each in plan.md Complexity
  Tracking.
- [ ] T078 Final `RUN-STATE.md` update: done, open risks (AI fidelity without an emulator), next
  steps.

---

## Dependencies & Execution Order

- **Setup (T001–T007)**: T001 first; T002, T003, T005, T006 and T007 in parallel after it; T004
  after T003.
- **Foundational (T008–T057)** blocks every story. Inside it:
  - Spikes T008–T010 run first and in parallel. Checkpoint A may change later tasks.
  - Readers T011–T017 run in parallel; T018 is independent of them. Then T019 → T020.
  - Availability: T021 and T022 need T018; T023 needs T018 and T021; T024 needs T022 and T023;
    then T025 and T026.
  - Legality: T027 is independent; T028 needs T012–T015 and T024; T029 needs T027 and T028; then
    T030 and T031.
  - Engine: T032 needs T004, T019 and T010. T033 and T034 run in parallel. T035 needs T032 and
    T034. T036 needs T009 and T035. T037 is independent after T003. T038 → T039 → T040–T044
    (parallel) → T045 → T046 → T047 → T048. T049 needs T037. T050 needs T045–T047 and T049. Then
    T051, then T052.
  - T053 needs T019 and T032. T054 and T055 are independent. T056 needs T050 and T052.
    T057 needs T035, T052 and T054.
- **US1 (T058–T068)** needs Phase 2. T060 and T061 run in parallel → T062 → T063 → T064 → T065
  → T066 → T067. T068 can be built in parallel with T060–T066.
- **US2 (T069–T072)** needs Phase 2 only, so it can be done before or alongside US1.
- **US3 (T073–T074)** needs T024 and T053 only.
- **Polish (T075–T078)** comes after the desired stories.

### User story completion order

Phase 2 → US2 (smallest end-to-end slice of the engine) → US1 (MVP value) → US3. US2 is listed
after US1 by priority, but it is the quickest way to prove the engine end to end, so doing it first
is recommended.

## Parallel Examples

```text
# Spikes (all three at once):
T008 throughput.mjs   T009 levelup.mjs   T010 fullrestore.mjs

# Decomp readers:
T011 constants.py  T012 species.py  T013 moves.py  T014 items.py  T015 tutors.py  T016 exp.py  T017 trainers.py

# AI command groups (after T039):
T040 flow.mjs  T041 battler.mjs  T042 moves.mjs  T043 damage.mjs  T044 misc.mjs

# US1:
T060 abilities.py  T061 candidates.py  T068 static web page

# US2 alongside US1:
T069 losses.py
```

## Implementation Strategy

### MVP first
1. Phase 1, then Phase 2 through Checkpoint B. This is most of the effort; the AI interpreter
   (T038–T048) is the largest single piece.
2. US2 (evaluate a fixed team). This is the first end-to-end check that battle results are sane.
3. US1 (optimize, web page, spreadsheet). **Stop and validate** with quickstart V8 and V9.
4. US3 (explain), then Polish.

### Incremental delivery
- After T020: game data is extractable and verified.
- After T031: legality checks work on hand-written teams.
- After T048: Showdown battles against the real in-game AI.
- After US2: full League win rates for any team.
- After US1: the optimizer and web page.

### Notes
- Never reduce simulation counts to save time without the `--budget` flag, and label it when used.
- When unsure whether more runs are needed, run more (spec FR-018).
- Commit after each task or logical group, on `main`.
