# Research: Champion Team Optimizer

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-10-07

Sources: read-only surveys of `pokeplatinum/` (commit `c248fb3f8cc9934ded800e489567c5c0eeee92eb`)
and `pokemon-showdown/` (commit `c046106cbe075931b1ff8d8b800ff5be47a85f96`). Paths below are
relative to those roots (`pp/` and `ps/`). Items marked **UNVERIFIED** were not confirmed by
reading code or running anything and need a task that confirms them.

---

## R1. Where game data lives (decomp)

**Decision**: Extract directly from the decomp's source JSON/CSV/asm with Python; never use built
binaries (there is no build directory) or Showdown data as a source.

| Data | Source | Notes |
|---|---|---|
| Species stats, types, abilities, exp rate, base exp, EV yield, evolutions, learnsets | `pp/res/pokemon/<name>/data.json` | `by_level`, `by_tm`, `by_tutor`, `egg_moves`; `base_stats` orders speed before sp. atk |
| Alternate forms with own stats | `pp/res/pokemon/<sp>/forms/<form>/data.json`, `form_registry.json` | 12 forms; order hard-coded in `pp/tools/dataproc/src/speciesproc.c:227` |
| Constant IDs | `pp/generated/*.txt` | ID = 0-based line index unless `= N` |
| TM/HM → move | `pp/res/items/data/tmNN.json` / `hmNN.json` (`teachesMove`) | |
| Shard tutors | `pp/res/pokemon/move_tutors.json` | 38 entries with shard costs and `TUTOR_LOCATION_*` |
| Special tutors | `scripts_route_210_grandma_wilma_house.s` (Draco Meteor), `scripts_route_228_north_house.s` (starter ultimates; post-game area) | Hard-coded in scripts |
| Moves | `pp/res/moves/<name>/data.json` | Power/type/acc/PP/priority/effect/flags |
| Items | `pp/res/items/data/<name>.json` | `holdEffect`, price |
| Exp tables | `pp/res/pokemon/.shared/exp_tables.csv` | Column order = `generated/exp_rates.txt` |
| Ability slot | `pp/src/pokemon.c:4746` | `personality & 1` selects ability 2 when present |
| Nature | `pp/src/pokemon.c:2410` | `personality % 25` |

**Rationale**: Constitution I. The C packers in `pp/tools/dataproc/src/*.c` are the reference for
encodings and are cited in extractor tests.

**Alternatives rejected**: Showdown's `data/mods/gen4pt` learnsets (second-hand); building the ROM
and parsing NARCs (needs the toolchain; no benefit over reading the sources).

## R2. What counts as "obtainable before the Champion"

**Decision**: Build an **availability ledger**. Each entry is one acquisition source: wild slot,
gift, egg, static encounter, NPC trade, item ball, hidden item, NPC item gift, shop, Game Corner,
tutor. Each entry has a map header, quantity (1, n, or unlimited), the gates found on its path, and
a source line reference. An entry is pre-Champion unless one of these automatic rules marks it
post-game:

1. **Script gates**: its script path checks `FLAG_GAME_COMPLETED`, `CheckGameCompleted`, or
   `GetNationalDexEnabled` (National Dex is granted only after the Hall of Fame:
   `scripts_sandgem_town_pokemon_research_lab.s:539`).
2. **Region gates**: its map is reachable only through a gated edge. The map graph is built from
   warp events (`res/field/events/*.json`), script warps and ships (`Warp`, `TakeShipFrom*`), and
   overworld-matrix adjacency (`res/field/matrices/map_matrix_000.json`). An edge is cut when its
   trigger script has a rule-1 gate. Example: the Battle Zone's only entry is the Snowpoint ship,
   gated by `FLAG_GAME_COMPLETED` at `scripts_snowpoint_city.s:178-210`.
3. **Encounter-slot gates** (`src/overlay006/wild_encounters.c`):
   - swarms: enabled only after the game is completed;
   - Poké Radar: given with the National Dex;
   - dual-slot and Trophy Garden: require the National Dex;
   - Great Marsh: `before_national_dex` list only;
   - Super Rod: given in the Fight Area;
   - underground fossils: only the pre-National-Dex weights are non-zero (Skull/Armor by trainer
     ID parity).

Findings already confirmed:
- NPC trades: Abra (Oreburgh), Chatot (Eterna), and Haunter (Snowpoint) are pre-Champion.
  **Magikarp (Foppa, Route 226) is post-game.**
- Post-game: Survival Area tutor, Route 228 tutor, Super Rod, swarms, Poké Radar, the Regis,
  Regigigas, Heatran, Cresselia, and Dialga/Palkia at Spear Pillar.

TM copy counts are the sum of referenced visible-item scripts (`scripts_visible_items.s`, IDs
7000+), NPC gifts (`Common_GiveItemQuantity` / `AddItem` quantities), and hidden items
(`include/data/field/hidden_items.h`; none are TMs). TMs sold in shops are unlimited:
- Veilstone Dept. Store 3F: TM83, 17, 54, 20, 33, 16, 70, 38, 25, 14, 22, 52, 15.
- Game Corner (`src/scrcmd_game_corner_prize.c:22-41`): TM90, 58, 75, 32, 44, 89, 10, 27, 21, 35,
  24, 13, 29, 74, 68.

Only visible-item scripts that an events JSON actually references count. Some scripts are named
`Unused*`, and some maps are named `unused_*` or `dp_*`; these count only if the map graph reaches
them.

**Correction (T023–T026, 2026-10-07)**: the premise that the National Dex is granted only after the Hall of Fame
is **false**. The only grant (`scripts_sandgem_town_pokemon_research_lab.s:539`) needs `FLAG_FIRST_ARRIVAL_ETERNA_CITY`
and `CheckLocalDexCompleted` (all 210 Sinnoh species seen, `src/pokedex.c:28`, :801). Seven species are seen only in
Elite Four or Champion battles, which count as seen even when lost. The user decided that **National Dex sources are
not allowed** (spec FR-003a); `ALLOW_NATIONAL_DEX = False` in `availability/ledger.py`. Event-only items (Member Card,
Oak's Letter, Secret Key, Azure Flute) come only from Mystery Gift handlers (`src/scrcmd_mystery_gift.c:540/582/628/670`)
and are unobtainable.

**Warp-on-wall rule (2026-10-08)**: a warp whose tile and all four neighbours are collision tiles cannot be stepped on, so
it is cut from strict reachability (`mapgraph._collision_warps`; warps moved by scripts and maps without tile data are
skipped). This removed 18 warps and 14 maps (421 → 407 reachable), all unused or DP-leftover maps. TM04 (only in an unused
Eterna condominium 4F, warp at `events_eterna_city_condominiums_3f.json:72-76`) and Focus Band became unavailable.

**Rationale**: FR-003 requires post-game status to come from the game's own gates. These three
rules are mechanical, cite their source lines, and are testable with positive controls (the Battle
Zone, Survival Area tutor and Foppa trade MUST come out post-game; the Route 212 tutor and the
Oreburgh gym TM76 MUST come out pre-Champion).

**Alternatives rejected**:
- A hand-written list of post-game areas (violates Constitution I).
- Tile-level walkability from binary land data (`map_data_*.bin`): large effort for little gain,
  since post-game is gated by scripts, not terrain. Matrix cells marked `MAP_HEADER_EVERYWHERE`
  are treated as non-connecting; a reviewed test fixture confirms that known pre-Champion maps
  (all 8 gyms, Victory Road, Pokémon League) are reachable.

**UNVERIFIED / to confirm in tasks**:
- Which map headers use `encounters_unknown_533–557`.
- Which maps have honey trees.
- Whether Victory Road is gated by a badge check.
- Whether the Snowpoint tutor has no story gate (inferred only from finding no flag check).

## R3. The League gauntlet (opponents, order, healing)

**Decision**: Opponent data comes from the first-run trainer files.

| Order | Trainer | File | ID | AI flags | Bag items |
|---|---|---|---|---|---|
| 1 | Aaron | `res/trainers/data/elite_four_aaron.json` | 261 | BASIC, EVAL_ATTACK, EXPERT | 2× Full Restore |
| 2 | Bertha | `elite_four_bertha.json` | 262 | same | 2× Full Restore |
| 3 | Flint | `elite_four_flint.json` | 263 | same | 2× Full Restore |
| 4 | Lucian | `elite_four_lucian.json` | 264 | + SETUP_FIRST_TURN | 2× Full Restore |
| 5 | Cynthia | `champion_cynthia.json` | 267 | BASIC, EVAL_ATTACK, EXPERT | 4× Full Restore |

- First-run vs rematch is chosen by `FLAG_ARRESTED_CHARON_STARK_MOUNTAIN` (post-game), so the
  first-run files apply.
- Trainer Pokémon (`src/trainer_data.c:176-316`):
  - IVs = `iv_scale*31/255`, which is 30 for all five teams.
  - 0 EVs.
  - Personality comes from an LCRNG seeded with `ivScale+level+species+trainerID`, iterated
    `trainerType` times, then `<<8` plus a gender modifier. Nature = personality % 25; the
    modifier is even, so the ability is always slot 1.
  - These derived values MUST be computed by a Python port of this routine and tested.
- Order and healing: rooms run Aaron → Bertha → Flint → Lucian → Cynthia, and the player cannot
  walk back. No League script heals the party. The plan follows spec FR-012 (restore between
  battles with bag items). **UNVERIFIED** in code that the bag is usable between rooms; it is
  standard gameplay and is recorded as an assumption.
- Evolution happens only after a won battle (`BATTLE_STATE_CHECK_EVOLUTION`, `battle_main.c:274`).
  Spec default: decline.

## R4. Battle engine: Showdown integration

**Decision**: Run one **long-lived Node worker per CPU core**, using Showdown's in-process API
(`new Battle({...})`, `battle.makeChoices`, `battle.sides[i].activeRequest`) from the built `dist/`.
Python talks to the workers over newline-delimited JSON on stdin/stdout.

- **Format**: `gen4customgame`. It has no clauses and no validation, and it is `debug: true`, so HP
  is reported exactly. gen4pt differs from gen4 only in learnsets and tiers; its `scripts.ts` just
  inherits gen4, so its battle mechanics are the same as gen4. The turn-1000 hard limit counts as
  a loss.
- **Seeds**: `sodium,<32 hex>` (ChaCha20). Each gauntlet run gets a seed derived from
  (master seed, run index, battle index).
- **Data corrections**: at worker startup, a project-owned patch layer mutates
  `Dex.mod('gen4').data` (Pokedex/Moves/Items) to match decomp values for every divergence-ledger
  entry marked "corrected". This must happen before the first `Dex.*.get()`, because results are
  cached. Nothing in `ps/` source is edited.
- **Build**: `npm ci && node build` inside `ps/`. This writes `node_modules/` and `dist/` only, and
  needs network access once to download npm packages (free). Every spawn uses `--skip-build`; the
  worker imports `dist/sim` directly.

**Rationale**:
- Startup cost: Dex data loading is about 0.5–1.5 s per process (`ps/sim/dex.ts` header
  comments), so one process per battle is far too slow.
- Hooks: the in-process API lets the worker add the game-layer behaviour Showdown lacks (R5–R7).

**Alternatives rejected**:
- `pokemon-showdown simulate-battle` per battle: startup cost dominates.
- Adding a `data/mods/platinum` folder inside `ps/`: this edits the vendored tree (Constitution II).
- A pure-Python simulator: reimplements mechanics (Constitution II).

## R5. Things Showdown does not do, and how the game layer adds them

Searched `ps/sim`, `ps/data/mods/gen4`, `ps/data/mods/gen4pt`: no bag items, no experience, no
mid-battle level-up, no heuristic AI.

| Gap | Decision | Ledger status |
|---|---|---|
| Opponent trainer AI | R6 | accepted until validated |
| Opponent Full Restores | `TrainerAI_ShouldUseItem` (`trainer_ai.c:4056`) decides; the worker applies it by injecting a project-defined pseudo-move "Trainer Item: Full Restore" that heals to full, cures status, and runs before moves (the game resolves item use before moves). Item counts and the slot-consumption quirk (`trainer_ai.c` loop has no break) follow the code. | corrected-by-patch; impact: message/animation order only |
| Experience and level-up | Worker tracks participation the game's way (`battle_lib.c:1456-1479`, `battle_script.c:455-626`) and computes exp per `BtlCmd_CalcExpGain` (`battle_script.c:2186`) and `BattleScript_GetExpTask` (`:9685`): trainer ×1.5, Lucky Egg ×1.5, Exp. Share split, traded ×1.5. On a level-up the worker updates the Showdown Pokémon's level and recomputes stats with the decomp formula (`src/pokemon.c:564`), raising current HP by the max-HP gain as the game does. | corrected-by-patch if mid-battle stat update works (spike task T-spike-2); otherwise "levels applied between battles", accepted with stated impact |
| Level-up moves | Spec default: keep current moves. | n/a |
| Player bag items | Forbidden by spec (FR-011). | n/a |

### R5 – Spike results (2026-10-07)

**T009, mid-battle level-up (`sim/spikes/levelup.mjs`): WORKS.**
- Method: set `pokemon.level` and `pokemon.set.level`, then `stats = battle.spreadModify(species.baseStats, set)`.
  Assign `baseStoredStats` and `storedStats`, set `baseMaxhp` and `maxhp` to `stats.hp`, and raise
  `hp` by the max-HP increase.
- Verified with the same seed:
  - the stats equal a freshly built level-70 copy (maxhp 252; atk 208, def 159, spa 138, spd 145,
    spe 168);
  - HP rose by exactly the max-HP gain (114 → 183 with max 183 → 252);
  - later damage differs.
- These numbers are Showdown's stat formula. Matching it against the decomp formula
  (`pokemon.c:564`) is T034.
- **Decision**: level-ups are applied mid-battle. The ledger entry is `corrected-by-patch`.

**T010, opponent Full Restore pseudo-move (`sim/spikes/fullrestore.mjs`): WORKS, with one gap.**
- Injected into `Dex.mod('gen4').data.Moves` before the first get: priority 7, category Status,
  target self. Its `onHit` calls `sethp(maxhp)`, `cureStatus()` and removes confusion. It is added
  to the user's move slots for the turn it is chosen, then removed.
- Basic case: Milotic at 39/195 HP and poisoned was healed to 195/195 and cured, **before** p1's
  Extreme Speed (+1).
- Torment, two consecutive uses: both succeed.
- **Gap**: under Taunt, Showdown blocks it (`|cant|p2a: Milotic|move: Taunt|Trainer Full Restore`,
  from `ps/data/mods/gen4/moves.ts:1411-1418`, which disables every `Status`-category move). In the
  game, Taunt does not stop a trainer's bag item. **T047 MUST fix this**, e.g. via a runtime patch
  of the gen4 Taunt condition that exempts `trainerfullrestore`, plus a test.
- Other interactions T047 MUST handle or ledger, because the pseudo-move is still a "move" to
  Showdown: it sets `lastMove` (affects Encore, Disable, Mirror Move, Copycat), Sucker Punch
  targeting it, Pressure PP deduction, Choice lock (no League mon holds a Choice item), and Heal
  Block.

**Found during T008: PP Ups.** Showdown gives every move 3 PP Ups at construction
(`ps/sim/pokemon.ts:361`). For example, Cynthia's Spiritomb has Dark Pulse at 24 PP; base is 15.
The game sets trainer Pokémon moves to `MoveTable_CalcMaxPP(move, ppUps)`
(`BoxPokemon_SetMoveSlot`, `pp/src/pokemon.c:3925`). `ppUps` is 0 for a freshly built trainer
Pokémon because `Pokemon_Init` zeroes its data (`pp/src/pokemon.c:294`), so trainer moves get base PP.
- PP carries over between League battles, so this matters.
- **T034 MUST overwrite `maxpp`/`pp` after construction.** For opponents: base PP.
- For the player: PP Ups/PP Max are items whose pre-Champion availability is finite or unknown. The
  user decided (2026-10-07): **no PP Ups for the player either**, so every move has base PP (spec
  FR-008).

## R6. Opponent AI: running the game's own AI scripts

**Decision**: Write an **interpreter in the Node worker** that runs the decomp's AI bytecode
(`src/battle/trainer_ai/script.s`, ~8,100 lines; the five League trainers need ~6,450 lines: Basic,
EvalAttack, Expert, SetupFirstTurn) by parsing the assembly text with the macro definitions in
`asm/macros/aicmd.inc` (109 commands, `include/data/scripts/aicmd.h`). Each command is implemented
against a state adapter over the live Showdown battle.

- Move choice follows `TrainerAI_Init`, `TrainerAI_EvalMoves` and `TrainerAI_MainSingles`: start
  every score at 100, run each flagged section for every move, take the max, and break ties
  randomly.
- Switch and item choice come first, in the order `TrainerAI_PickCommand` uses (`trainer_ai.c:3989`):
  switch (`:3894`), then item (`:4056`), then fight.
- Post-KO replacement follows `BattleAI_PostKOSwitchIn` (`battle_lib.c:7923-8090`), including the
  documented u8 score overflow bug.
- The AI's damage estimates call the game's damage formula (`BattleSystem_CalcMoveDamage`,
  `battle_lib.c:6601-7080`). This formula is ported to JS and used **only** as the AI's internal
  estimator and as a cross-check against Showdown damage (Constitution V). It never resolves real
  damage.
- AI randomness (tie breaks, damage roll `100 - rand%16`) draws from the run's seeded PRNG stream.

**Rationale**: FR-010 requires the in-game AI. Interpreting the original script text keeps the
behaviour traceable line-by-line to the decomp. A hand-written "Cynthia-like" AI would be the
internally-consistent-but-unfaithful code the user warned against.

**Alternatives rejected**:
- Showdown's random AI (not the game).
- A hand-ported heuristic summary of the scripts (loses fidelity, can't be audited line-by-line).
- Running the ROM in an emulator for every battle (orders of magnitude slower; no Showdown).

**Risk**: AI fidelity can't be tested end-to-end without the cartridge. Mitigation:
- per-command unit tests built from the script semantics;
- golden traces for hand-built positions, where the expected move is computed by hand from the
  script;
- a recorded ledger entry for every command left unimplemented (each one fails loudly if reached).

An emulator-based golden-trace harness using the user's ROM is a possible later validation step
(out of scope for v1).

## R7. The player's policy: strong look-ahead that stays affordable

**Decision**: Use **model-based 2-ply expectimax** in the worker. It does not clone battles.

1. Enumerate the player's legal actions from the Showdown request (≤4 moves + ≤5 switches).
2. Predict the opponent's reply **by running the same AI interpreter** on the hypothetical state.
   The game's AI is a known function of the state, and modelling that is what an expert player
   does.
3. Score outcomes with the ported damage formula over its 16 damage rolls, plus accuracy and crit
   chance. Speed order follows the game's turn-order rules.
4. Look one more ply ahead (the next turn's best reply).
5. Evaluate leaf states by a documented heuristic: HP fraction × remaining-mon weights, the
   opponent's Full Restores left, and status.

The policy is named `expectimax2-v1` in every report (FR-013).

**Rationale**: Cloning Showdown state means a full `Battle` construction plus a JSON round trip
that includes the whole log (`ps/sim/state.ts`). At roughly 9 actions × several samples × ~25 turns
× 5 battles × thousands of runs, that is too slow (see R8). An analytical model of one or two turns
gives the "skilled human" quality FR-013 asks for at a small fraction of the cost.

**Alternatives rejected**:
- Clone-based MCTS (cost).
- Greedy highest-damage (rejected by the user, Q2).

**Open item**: The policy's strength is checked by benchmark against the greedy baseline on fixed
teams. `expectimax2-v1` must beat greedy by a statistically supported margin, or it is not called
"strong".

### R7 – Measured (T056, 2026-10-07)

- **Setup**: 2,000 paired seeds (master `t056-policy-strength`), `tests/fixtures/reference_team.json` at level 57,
  opponent `decomp-ai`, 16 workers.

  | Policy | Cleared | Rate | Wilson 95% | Gauntlets/s (16 workers) |
  |---|---|---|---|---|
  | greedy-v1 | 316 | 0.158 | [0.143, 0.175] | 52.2 |
  | expectimax2-v1 | 1040 | 0.520 | [0.498, 0.542] | 1.64 |

- **Significance**: McNemar exact, 860 seeds cleared only by expectimax2 vs 136 only by greedy, p = 3.56e-129.
  `expectimax2-v1` is therefore "strong" relative to greedy (FR-013). A coordinator rerun at N = 160 reproduced 92/160
  vs 26/160 exactly.
- **Cost**: about 50 ms per decision, about 32× slower than greedy; around 75% of that is running the AI for
  prediction. **This dominates the optimizer budget** (see R8). At 1.64 gauntlets/s, the standard preset's ≥ 2,000
  confirmation runs take about 20 minutes per finalist on this machine.
- **Known model gaps** are listed in the header of `sim/policy/expectimax2.mjs`: unmodelled status/setup moves, weather
  never expiring, hazards, multi-hit moves, and so on.

> **Note (2026-10-08, T076)**: the "R7 – Measured (T056)" numbers above were produced on an earlier engine. Rerun
> with the same seeds after later fixes (exp payout ordering, NPC-trade boost, auto-learn, new data files), greedy-v1
> clears 298/2000 (was 316) and expectimax2-v1 1020/2000 (was 1040). The conclusion is unchanged. Results are
> reproducible per code version only; the worker does not yet fingerprint the `sim/` code in its hello.

### R7 – v2 correction (2026-10-08)

- **Problem**: v1 was not uniformly stronger than greedy. On optimizer screening finalists (400 paired seeds)
  greedy-v1 cleared 348 vs v1 109, and on the optimizer's own winner 394 vs 348.
- **Causes**:
  1. The search horizon rewarded delaying KOs. A ply-1 KO lets the AI's replacement act inside the search, while a
     ply-2 KO never shows it, so v1 switched instead of attacking 516 of 1,027 times.
  2. The leaf weights were mis-scaled. A logistic fit on 78,585 decisions gives the value of keeping a member alive
     as about 0.25 and a Full Restore as about 0.10, against v1's 1.0 and 0.45.
- **Fix**: `expectimax2-v2` values a ply-1 KO branch at the leaf immediately (koStop) and uses the fitted weights. It
  is now the default; v1 stays registered unchanged so recorded results remain reproducible.
- **Acceptance** (600 fresh paired seeds, `x2v2-accept`): v2 is not significantly worse than greedy on any team,
  and is significantly better on the reference team (568 vs 442, p = 1.8e-23) and the benchmark team (519 vs 100,
  p = 9.3e-111). On the reversal team it is at parity (504 vs 522, p = 0.16; 353 vs 344 on another 400 seeds).
- **Throughput**: about 2.6 gauntlets/s on 16 workers (v1 about 1.7).
- **Caveat**: v2's leaf weights were fitted on greedy-played games.

## R8. Simulation budget and search strategy

**Facts**: 16 cores and 30 GB RAM on this machine. Showdown has no published throughput figure.

**Decision**: Measure before committing (spike task T-spike-1). The working estimate is
**UNVERIFIED** until that benchmark runs.

- **Sample size for SC-003** (Wilson 95% interval at p≈0.75, ±2 points): about 1,800 gauntlet runs.
  The plan uses ≥ 2,000 for the final evaluation of the winning team.
- **Search** (FR-016–FR-019, Constitution IV):
  1. **Prune**: legal move pools per member; drop moves strictly dominated by another legal move
     of the same type, category and accuracy class with higher power and no side effects. TM copy
     limits are constraints across the team. Abilities follow FR-008c.
  2. **Screen**: successive halving over candidate builds at a fixed level vector, using paired
     seeds. Rounds of 100 → 200 → 400 runs; keep the top third each round.
  3. **Level search**: for the surviving builds, find the lowest uniform level offset that
     clears ≥ threshold (bisection), then lower members one at a time while respecting the
     10-level final gap and threshold. Final levels include gauntlet exp, so the objective uses
     simulated final levels, not starting levels.
  4. **Confirm**: ≥ 2,000 runs on the winner and runner-up, paired. Report "better" only if the
     difference is supported (FR-019).
- **Qualification rule**: estimated clear rate ≥ threshold (default 0.75) **and** CI half-width
  ≤ 2 points. When the interval straddles the threshold, the result is marked `borderline` and
  more runs are added, up to a cap, before deciding.
- **Ability screening** (FR-008c): 200 paired runs; equal if not significant.
- **Champion share** (FR-017, SC-003): `stop_on_loss` means Cynthia is only reached by runs that
  beat all four Elite Four members. After the full runs, the tool **tops up Cynthia-only battles**.
  It starts each one from a team state recorded after Lucian in a full run that reached Cynthia
  (levels, exp, PP, held items), drawing those states with replacement and using new seeds.
  - It keeps going until Cynthia's win-rate interval is within the target **and** she has more
    battles than any Elite Four member.
  - Her win rate is reported separately, as P(win | reached Cynthia).
  - The full-gauntlet clear rate still comes only from full runs.
- **Budget presets** (FR-018). The CI target applies to both the gauntlet and Cynthia:

  | Preset | Screening rounds | Ability screen | Confirm (per finalist) | CI half-width target | Meets SC-003? |
  |---|---|---|---|---|---|
  | `standard` (default) | 100 → 200 → 400 | 200 | ≥ 2,000, more until the target is met | ±2 points | yes |
  | `thorough` | 200 → 400 → 800 | 400 | ≥ 5,000, more until the target is met | ±1.5 points | yes |
  | `quick` | 50 → 100 → 200 | 100 | 500 | none | **no**: labelled `quick` in every output, for testing only |

  Only `standard` and `thorough` can produce a result marked `qualified`.
- **Never silently loosened**: lower run counts only via an explicit `--budget` flag, and the
  report shows the loosened settings.
- **Policy per stage** (user decision 2026-10-07, after T056 measured expectimax2-v1 at about 1.6 gauntlets/s on 16
  workers): ability screening and successive-halving screening use `greedy-v1`; the level search and confirmation
  use `expectimax2-v1`. Qualification and every reported rate come from `expectimax2-v1` only. Run time is not a hard
  constraint, so prefer more expectimax2 runs whenever in doubt (FR-018).

### R8 – Measured (T008, 2026-10-07)

`node sim/spikes/throughput.mjs`: 500 battles per process, `gen4customgame`. p2 is Cynthia's
first-run team from `champion_cynthia.json`; p1 is her species at level 60 with 15 IVs and 85 EVs.
Both sides choose `default`, so there is **no AI and no player policy** in these numbers.

| Setup | Battles/s | Mean turns |
|---|---|---|
| 1 process | 42.9 | 25.7 |
| 16 processes in parallel (16 logical CPUs) | 18.9 each, **295 combined** | 25.8–26.0 |

- A gauntlet is up to 5 battles, so the engine ceiling is about **59 gauntlets/s** on this machine.
  At that rate, 2,000 confirmation runs take about 34 s before any AI or policy cost.
- The real throughput depends on the cost of the AI interpreter and `expectimax2-v1`. Re-measure
  after T048 and T056.
- Checkpoint A threshold (≥ 5 battles/s per process): **met**.

## R9. Language and tool split

**Decision**:
- **Python 3.14** (installed): extraction, availability ledger, legality validator, optimizer,
  statistics, reports, and the web server.
- **Node 22.22** (installed; Showdown requires ≥22.18): the sim worker, game layer, AI interpreter
  and player policy. Written as plain ES modules, with no TypeScript build step.
- Python env managed with `uv` (installed at `~/.local/bin/uv`).

**Rationale**: The user asked for Python, with Node where needed. The AI and the player policy
must run in the same process as the battle for speed, so they live in Node.

## R10. Frontend and spreadsheet

**Decision**:
- **Web page**: one static HTML page with CSS and a small amount of plain JavaScript. Species search
  and the add-to-team interaction need a few lines of JS; there is no framework and no build step.
- **Server**: served by a FastAPI app. Optimizations run for minutes to hours, so they run as
  background jobs: the page submits a job and polls progress.
- **Spreadsheet**: `.xlsx` via `openpyxl`, with a CSV mirror of the team sheet. It is produced for
  every completed job and is downloadable from the page. Each move row carries its source
  (level-up at Lv N, pre-evolution level-up, TM/HM with copy source, tutor with location and shard
  cost, egg).

**Alternatives rejected**:
- A JS framework (unneeded).
- Python stdlib `http.server`: workable, but FastAPI gives tested request validation and
  background jobs with less code.

## R11. Testing

- `pytest` for Python.
- `node --test` for the worker.

Required suites (constitution workflow):
- extraction known-values;
- availability positive/negative controls (R2);
- legality valid/invalid sets;
- divergence ledger;
- determinism (same seed → identical log);
- exp formula against hand-computed cases;
- AI per-command and golden traces;
- damage-formula cross-check (decomp port vs Showdown, same inputs, all 16 rolls).
