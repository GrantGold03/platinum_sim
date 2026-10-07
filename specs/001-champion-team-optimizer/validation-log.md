# Validation Log: Champion Team Optimizer

Real commands and outputs that back each completed task (Constitution V). Newest last.

## 2026-10-07: Phase 1 Setup (T001–T007)

**T001**: `uv sync` (network, authorized by the user) → exit 0. It installed fastapi 0.142.2,
uvicorn 0.54.0, openpyxl 3.1.5, pytest 9.1.1, httpx 0.28.1 and their dependencies. Import check:
```
$ uv run python -c "import sys, fastapi, uvicorn, openpyxl, httpx, pytest; print(sys.version.split()[0], fastapi.__version__, openpyxl.__version__)"
3.14.7 0.142.2 3.1.5
exit=0
```

**T002**: directory skeleton created per plan.md. `src/platsim/cli.py` is a stub returning 1 until
subcommands exist.

**T003**: `sim/package.json`, `sim/showdown.mjs`:
```
$ node -e "import('./showdown.mjs').then(m => console.log(typeof m.Battle, typeof m.Dex, typeof m.Teams, typeof m.PRNG))"
function object object function
exit=0
```

**T004**: Showdown build (network, authorized):
```
$ npm ci          → exit 0, "added 356 packages ... 37 vulnerabilities (3 low, 7 moderate, 26 high, 1 critical)"
$ node build      → exit 0 ("Config.js does not exist. Creating one with default settings...")
$ ls dist/sim/index.js → present
$ node -e "...Dex.mod('gen4').species.get('garchomp').baseStats"
{"hp":108,"atk":130,"def":95,"spa":80,"spd":85,"spe":102}
$ git -C pokemon-showdown status --porcelain → (empty; build outputs are ignored upstream)
```
These are Showdown's numbers (a smoke test only), not decomp-verified data. The audit
vulnerabilities are in server-side dependencies; the sim runs locally and offline, so they were not
acted on.

**T005**: `src/platsim/pins.py` and `tests/unit/test_pins.py`:
```
$ uv run pytest tests/unit/test_pins.py -q -p no:cacheprovider
...                                                                      [100%]
3 passed in 0.06s
pytest exit=0
```
The tests are a positive control (real repos match the pins) and two negative controls (wrong
commit raises; a local edit raises).

**T006**: `/data/generated/` added to `.gitignore`; `tests/conftest.py` fixtures added.

**T007**: `RUN-STATE.md` created.

## 2026-10-07: Phase 2a Spikes (T008–T010)

**T008**: throughput (`sim/spikes/throughput.mjs`). Team load first checked by printing Cynthia's
party (Spiritomb 58 ... Garchomp 62 with sitrusberry, IV 30, correct moves). Results:
```
single: {"battles":500,"seconds":11.651,"battlesPerSec":42.92,"meanTurns":25.73,"p1Wins":351}
parallel x16: per-process 18.67–19.46 battles/s; processes 16, total battles 8000, wall_s 27.08,
aggregate battles/s 295.4
```
Found along the way: Showdown applies 3 PP Ups to every move (Spiritomb Dark Pulse 24 PP), while
the game uses base PP for trainers. Recorded in research.md R5.

**T009**: mid-battle level-up (`sim/spikes/levelup.mjs`) → exit 0.
```
B_lead_after_change: hp 183, maxhp 252, stats atk 208 def 159 spa 138 spd 145 spe 168
fresh_level70:       maxhp 252,         stats atk 208 def 159 spa 138 spd 145 spe 168
B_hp_before_change: hp 114, maxhp 183
foeHp_after_t2: A 16, B 0
checks: statsMatchFreshLevel70 true, hpRaisedByMaxHpDelta true, laterDamageDiffers true
```

**T010**: Full Restore pseudo-move (`sim/spikes/fullrestore.mjs`) → exit 0 on the main criteria.
The first run exited 1 because of a bug in the check itself (it compared HP after the foe's Extreme
Speed hit). The check was fixed to read the heal line, and the rerun gave:
```
basic: before hp 39 psn → "|-heal|p2a: Milotic|195/195|[from] item: Full Restore" before
       "|move|p1a: Lucario|Extreme Speed"; cured true; actedBeforeExtremeSpeed true
taunt: "|cant|p2a: Milotic|move: Taunt|Trainer Full Restore"; healedToFull false   ← GAP (T047)
torment: two consecutive uses, healedToFull true, true
```

**Checkpoint A**: throughput 18.9–42.9 battles/s per process (threshold 5): met. T009 works. T010
works, with the Taunt gap and PP-Up finding recorded for T034 and T047. No plan change is needed;
research.md R5 and R8 are updated.

## 2026-10-07: Phase 2b (T011)

**T011**: `src/platsim/decomp/constants.py` (C-enum semantics, aliases, masks refused).
```
$ uv run pytest tests/unit/test_constants.py -q -p no:cacheprovider
5 passed in 0.22s
pytest exit=0
```
Positive control: every `FLAG_UNK_0xNNNN` name in `generated/vars_flags.txt` (more than 50 of them) equals its embedded hex
value, which confirms the alias and continue-counting semantics. SPECIES_GARCHOMP = 445 (`generated/species.txt:446`).

## 2026-10-07: T027, T033, T054 (utilities agent; re-run by the coordinator)

```
$ uv run pytest tests/unit/test_models.py tests/unit/test_seeds.py tests/unit/test_stats.py -q -p no:cacheprovider
23 passed in 0.54s
pytest exit=0
$ node --test sim/test/seeds.test.mjs
# pass 2   # fail 0   node exit=0
```
- **Seeds**: Python and Node give identical seeds over 100 inputs. A derived seed gives an identical Showdown log
  across two runs, and a different seed gives a different log (positive control).
- **Stats**: `runs_needed(0.75, 0.02)` = 1799 (Wilson), against "about 1,800" in R8. The Wilson CI is checked against
  the Newcombe 1998 Table I values that the agent recalled from memory (**UNVERIFIED** against the paper); one row
  (0/20) is also worked by hand.
- **Models**: these hold structure only; legality is enforced by T029. The Showdown export round trip is defined
  as `import(export(t)) == showdown_set()` for each build, because the export format cannot carry provenance.

## 2026-10-07: T055 report writers (agent; re-run by the coordinator)

```
$ uv run pytest tests/unit/test_reports.py -q
11 passed in 0.17s
pytest exit=0
```
- Uses synthetic fixtures only. The report writer refuses contradictory reports, e.g. `quick` together with
  `qualified`.
- `team.txt` for a no-qualifying report is written so that `import_team` rejects it.
- The import into Showdown itself is **UNVERIFIED**.
- **Infrastructure**: pytest temp directories now go in `/dev/shm/platsim-pytest-<pid>` (removed at exit;
  `tests/conftest.py`) and the pytest cache is disabled, so no temp files land in `/tmp` or the repo.

## 2026-10-07: T012–T017 + decomp stat formula (agent; re-run by the coordinator)

```
$ uv run pytest tests/unit/test_species.py tests/unit/test_moves.py tests/unit/test_items.py tests/unit/test_tutors.py tests/unit/test_exp.py tests/unit/test_trainers.py tests/unit/test_decomp_stats.py tests/unit/test_constants.py -q
49 passed in 0.87s
pytest exit=0
$ git -C pokeplatinum status --porcelain | wc -l
0
```
- **Spot check by the coordinator**: Garchomp in `res/pokemon/garchomp/data.json:2-9` is 108/130/95/spe 102/spa 80/spd 85.
  The loader gives `{'hp':108,'atk':130,'def':95,'spa':80,'spd':85,'spe':102}`, abilities `['ABILITY_SAND_VEIL', None]`,
  and its src includes `generated/species.txt:446`.
- **T012**: the 20 species were chosen per the task. Expected values were copied from each `data.json` with line
  citations, not typed by hand.
- **T017**: `header.trainerType` is the trainer class ID (`tools/dataproc/.../trainerproc.c:152`), so the LCRNG
  iterates 65–69 times for the League. `trainerIDs` is the `TRAINER_*` index (`src/encounter.c:751`). The gender
  modifier is 120 for Bertha and Cynthia and 136 for the others. Personalities were checked by a hand-worked LCRNG
  step and an independent closed-form jump-ahead. **UNVERIFIED** against a ROM or emulator.
- **Quirks for later tasks**:
  - Egg moves live only on the base species of a line, so legality checks must walk back through pre-evolutions.
  - Gift and trainer Pokémon take their ability from the base form (`pokemon.c:473-484`).
  - Experience 0 gives level 1.
  - Form personal IDs are 496 + their index (Rotom-Wash = 504).

## 2026-10-07: T037 damage formula port (agent; re-run by the coordinator)

```
$ cd sim && node --test test/damage.test.mjs
# damage cross-check: 109 combinations, 102 exact 16-roll matches, 7 known divergences, 6 zero-damage (immunity) cases
# tests 114   # pass 114   # fail 0   node exit=0
```
- **Divergences** (game behaviour kept in the port; listed in `sim/test/damage_divergences.json` for T053): type-chart
  sequential truncation; Sniper before variance; Expert Belt rounding; final-modifier chaining; base-power modifier
  rounding (Dry Skin); stat modifier before stages (Choice Band at -1); Metronome-item float (analytic only).
- **Not covered by the port** (listed in the module header): variable-power and variable-type moves (the caller
  supplies them), fixed, OHKO and multi-hit moves, Substitute, Focus Sash, Sturdy and Endure, and HP capping.
- **OPEN, resist berries (Occa, etc.)**: the coordinator confirmed that `HOLD_EFFECT_WEAKEN_SE_*` and
  `HOLD_EFFECT_WEAKEN_NORMAL` appear only in `src/battle/trainer_ai/script.s` and `res/items/data/*.json`. No battle C,
  .s, .inc or .h file references them by name. The damage-halving code has not been located in the decomp. Until it
  is, the optimizer MUST NOT offer resist berries (Constitution I). A follow-up search is needed (e.g. effectParam
  plus a table lookup).

## 2026-10-07: resist berries located (resolves the T037 OPEN item)

The effect is in a battle **subscript**, not in C. `res/battle/scripts/subscripts/subscript_type_resist_berry.s` is called
from `subscript_update_hp.s:10`, which runs from `BattleControllerPlayer_UpdateHP`
(`src/battle/battle_controller_player.c:~3435-3438`). The subscript compares raw hold-effect numbers 19–35 and raw type
IDs; it does not use the `HOLD_EFFECT_WEAKEN_*` names, which is why the name search missed it. Coordinator check of the
file:
- line 21: `== 35` → Chilan, which needs a Normal-type move and no super-effective check;
- line 22: the super-effective gate;
- the line after `_245`: `DivideVarByValue BTLVAR_HP_CALC_TEMP, 2`, then `RemoveItem`.

The halving applies to the final HP change, rounded toward zero with a minimum of 1 (`BattleSystem_Divide`,
`battle_lib.c:3599-3619`), after the Focus Sash and Endure clamp. Counter, Mirror Coat and Shell Bell bookkeeping use the
full damage. No berry triggers on substitute hits.
- **Decision**: resist berries are allowed. The ledger (T053) gets a divergence entry: Showdown halves inside its damage
  calculation (so Counter sees the halved damage, and the order relative to Sash differs).
- **Lesson for every later task**: game mechanics also live in `res/battle/scripts/**/*.s` and compare raw numbers.
  Search by number and by subscript, not only by constant name.

## 2026-10-07: T038, T039 AI parser + adapter (agent; re-run by the coordinator)

```
$ node --test sim/test/ai_parse.test.mjs     → tests 8, pass 8, fail 0, exit 0
$ node --test sim/test/ai_adapter.test.mjs   → tests 5, pass 5, fail 0, exit 0
```
- **Parser**: aicmd.h has 109 opcodes and the parser has 109 command macros. script.s gives 3,581 instructions in
  10,607 words. From the League sections (BASIC, EVAL_ATTACK, EXPERT, SETUP_FIRST_TURN), 2,888 instructions and 77
  opcodes are reachable; none of them touches a doubles partner. Section lines: Basic_Main 52, Expert_Main 1623,
  EvalAttack_Main 6353, SetupFirstTurn_Main 6417.
- **Work order for T040–T044**: `sim/ai/OPCODES.md`, which lists every reachable opcode with its handler line, count and
  adapter queries, plus 12 traps.
- **Adapter**: every decomp move and ability maps to Showdown by number; the only name differences are 4 renames.
  Showdown's items have the same numbers as the decomp.
- **UNVERIFIED (from the agent's report)**:
  - how Showdown's move-failed state maps to the game's "last move" clearing;
  - mapping log events to the AI's ability and item knowledge;
  - the first-turn counter after a post-KO switch;
  - Showdown weights versus decomp weights;
  - the volatile-duration counts;
  - "consecutive Protect" is capped at 2;
  - the League battle-type bits;
  - BASIC being bit 0, which comes from reading the shift loop in `trainer_ai.c:297-309`.

## 2026-10-07: T040 AI flow opcodes (agent; re-run by the coordinator)

`node --test sim/test/ai_cmds_flow.test.mjs` → tests 14, pass 14, fail 0, exit 0.
- **Opcodes**: 12, from AddToMoveScore through PopOrEnd. moveScore uses s8 wrap: 120 + 8 → 0.
- **Table scans**: they read `prog.image` and end on −1.
- **Call stack**: `mem.stack` holds instruction indices.
- **Not implemented**: PushAndGoTo, which nothing in the League sections reaches.
- **Evidence**: one end-to-end `runSection` test (ScoreMinus10, script.s:1591-1593).

## 2026-10-07: T042 AI move opcodes (agent; re-run by the coordinator)

`node --test sim/test/ai_cmds_moves.test.mjs` → tests 16, pass 16, fail 0, exit 0.
- **Opcodes**: 14. The player's moves are read from AI memory, not the truth.
- **Mutation check by the agent**: two deliberate bugs made tests 8, 9 and 15 fail; the tests passed again once the
  bugs were reverted.
- **Local helpers**: a full `AIScript_Battler` port (including partners) and `Battler_CountMoves`.
- **UNVERIFIED**: trap 6 (how a failed move maps to "last move"), and whether the lastResortCount mapping holds beyond
  one case.
- **Infrastructure**: `node --test sim/test/` fails on this Node version, so `sim/package.json` now uses
  `node --test test/*.test.mjs`.

## 2026-10-07: T044 AI misc opcodes (agent; re-run by the coordinator)

`node --test sim/test/ai_cmds_misc.test.mjs` → tests 16, pass 16, fail 0, exit 0.
- **Opcodes**: 14, plus Dummy3E/Dummy3F, which throw `ai_unimplemented` (trap 11).
- **How the tests reach their states**: weather, screens, hazards, Trick Room, Gravity, paralysis, faint and PP use are all
  reached with real moves.
- **UNVERIFIED**:
  - the doubles branches;
  - weather precedence and deep fog, which used a hand-built mask;
  - the post-KO fake-out turn.

## 2026-10-07: T019, T020, T032, T034, T035, T036 extraction + battle engine (agent; re-run by the coordinator)

```
$ uv run platsim extract --check → "data/generated is up to date (8 files)", exit 0
$ uv run pytest -q              → 90 passed, exit 0   (includes tests/integration/test_extract.py, test_worker.py)
$ node --test sim/test/exp.test.mjs sim/test/team.test.mjs sim/test/gauntlet.test.mjs sim/test/seeds.test.mjs
  → tests 30, pass 30, fail 0, exit 0
```
- **Policies**: both sides still use `placeholder-default` (Showdown's `default` choice). It is reported as such in
  every result and is NOT the game AI or a player policy (replaced by T045–T050).
- **Stats**: after a battle is built, both sides' stats are set by the decomp formula (`pokemon.c:564`). Showdown,
  the JS port and Python `calc_stats` agree for every League mon and for six player builds (including Shedinja and
  Rotom-Wash).
- **PP**: Dark Pulse has 15/15 PP on Cynthia's Spiritomb and on a player build; the control without the reset gives
  24.
- **Exp**: 15 hand-computed cases, including a traded Lucky Egg holder, a ×1.7 foreign-language trade and an Exp.
  Share holder that did not participate. Level-ups apply mid-battle at the KO.
- **Smoke gauntlet** (Python → NDJSON worker): `cleared: true`, turns 16/13/10/15/23, final levels
  [63, 60, 60, 62, 60, 60], 26 exp events. The Sitrus Berry was consumed and stayed gone, PP carried over, and
  `hello` reported the pinned commits with ledger "none".
- **Divergences found (for T053)**:
  1. Endure priority: +3 in the decomp (`res/moves/endure/data.json:20`) vs +4 in Showdown gen4
     (`data/moves.ts:4812`). NOT corrected yet.
  2. Variable-power moves: power 1 vs 0 (cosmetic).
  3. **Spec conflict**: the game auto-learns a level-up move when the Pokémon has fewer than 4 moves, with no prompt
     (`battle_script.c:10021-10035`). The spec says always decline. Flagged as `auto_learn_in_game` in exp events;
     it needs a user decision.
- **UNVERIFIED**: player happiness defaults to 255 (affects Return/Frustration); player gender comes from Showdown's
  PRNG; whether Showdown's Faint-event timing matches the game's exp timing.
- **Ledger patch shape that T053 must emit**: `{resolution:"corrected", patch:{table,id,path,value}}`.

## 2026-10-07: T041 AI battler opcodes (agent; re-run by the coordinator)

`node --test sim/test/ai_cmds_battler.test.mjs` → tests 19, pass 19, fail 0, exit 0.
- **Opcodes**: 31, each with a TAI or BL line cited. Every state is reached with real moves, and each has a
  positive control.
- **AI memory**: ability and item knowledge about the player is read from AI memory.
- **Speed compare**: its `monSpeedValues` side effect is written to `ctx.mem.monSpeedValues`; T043 and T045 read it
  from there.
- **Partner battlers**: arguments naming a partner throw (they are unreachable in the League).
- **UNVERIFIED**:
  - Quick Claw: no `speedRand` source exists yet; T045 decides it.
  - Protect chain is capped at 2.
  - No mutation testing was done.

## 2026-10-07: T043 AI damage opcodes + TrainerAI_CalcDamage (agent; re-run by the coordinator)

`node --test sim/test/ai_cmds_damage.test.mjs` → tests 17, pass 17, fail 0, exit 0.
- **Opcodes**: 6, plus `sim/ai/calcdamage.mjs` (TrainerAI_CalcDamage, TrainerAI_CalcAllDamage and the damage-roll
  draw). The no-damage-calc, alt-power, Judgment and weight tables are parsed from the C.
- **Hand-checked cases**: Explosion, Hidden Power, Gyro Ball (including the cap), fixed-damage moves, Psywave RNG, and
  Low Kick / Grass Knot weights. The kill check flips at 59 vs 58 HP.
- **Mutation check by the agent**: two deliberately broken copies of the estimator were each caught by a test.
- **UNVERIFIED**:
  - `monSpeedValues` on the first turn; Gyro Ball throws if it is missing.
  - Weather Ball with no weather throws, because the C leaves its type uninitialised.
  - `powerMul` is assumed to be 10.
  - Form weights.

## 2026-10-07: T053 divergence ledger (agent; re-run by the coordinator)

```
$ uv run platsim divergences --check
data/divergences.json is up to date: 72 entries (ai/accepted=2, data/accepted=51, data/corrected=5, exp/accepted=1,
exp/corrected=2, mechanics/accepted=9, mechanics/corrected=2); 5 Dex patches; version sha256:e48e13f16138a917
div-check exit=0
$ uv run pytest -q tests/integration/test_divergences.py tests/integration/test_worker.py → 6 passed, exit 0
```
- **Corrected data**:
  - Endure priority, decomp +3 vs Showdown +4. In a live battle the order flipped from p1,p2 to p2,p1 with the patch.
  - Counter, Mirror Coat and Metal Burst `flags.protect` set to 0.
  - Hail `flags.protect` set to 1 (whether this has any effect is **UNVERIFIED**).
- **Accepted data**: 30 variable-power placeholders, 12 move-target differences (call moves, Struggle, Conversion 2),
  and 9 hold items with no battle effect that are missing from Showdown.
- **No differences** in base stats, types or abilities (505 species), or in move power, accuracy, PP, type, category
  and main flags (467 moves).
- **Positive control**: a fake +1 attack on Garchomp produces an entry. A missing resolution exits 1.
- **Pending flips**: the Full Restore entry when T047 lands; the AI entry when T045–T048 land; the auto-learn entry on
  the user's decision.

## 2026-10-07: T049 greedy-v1, T052 worker pool (agent; re-run by the coordinator)

```
$ cd sim && node --test test/*.test.mjs → tests 243, pass 243, fail 0, exit 0
$ uv run pytest -q tests/integration/test_pool.py → 6 passed, exit 0
```
- **greedy-v1**: expected damage = the mean of the 16 decomp rolls × accuracy. Status, variable-power, fixed and OHKO
  moves score 0 (documented as conservative). It switches only when forced. Hand-computed check: Gyarados L60 vs
  Togekiss L60 move scores `[42.5, 0, 0, 43.5]`; greedy picks Surf over Hydro Pump despite Hydro Pump's higher
  nominal power × accuracy (see `sim/test/greedy.test.mjs`, which cites decomp lines).
- **Pool**:
  - Determinism: 64 gauntlets give the same results on 4 workers as on 1.
  - Crash recovery: a worker frozen with SIGSTOP and then SIGKILLed is restarted and its request is re-run.
  - A hello mismatch raises.
  - **UNVERIFIED**: there is no timeout for a worker that is alive but silent.
- **Bug fixed in `sim/gauntlet.mjs`**: the turn-1 request was built before the PP reset, so a move at 0 PP could be
  chosen. The request is now rebuilt. Placeholder output over 50 seeds is byte-identical before and after.
- **Throughput** (greedy player, opponents still `placeholder-default`, load from other agents present): about 96–118
  gauntlets/s warmed on 8–16 workers; 19.6/s on 1 worker. The CPU is a Ryzen 7 5700X3D, 8 cores / 16 threads.
- **Docs**: the stale resist-berry note in the `sim/damage.mjs` header was corrected.

## 2026-10-07: T057 Cynthia top-up (agent; re-run by the coordinator)

`uv run pytest -q tests/unit/test_reports.py tests/integration/test_champion_topup.py` → 17 passed, exit 0.
- **Real test** (player greedy-v1, opponent still `placeholder-default`, so NOT a real evaluation): 200 full runs, with
  every League member fought 200 times and Cynthia won 71. The top-up added 1,981 Cynthia battles. Cynthia's total
  was 2,181 battles, rate 0.3498, CI [0.3301, 0.3701], half-width 0.019999. Both rules were met.
- **Cap**: `max_topup=10` gives `cap_hit` with `target_met=False`.
- **Zero reach**: when nobody reaches Cynthia, no top-up runs.
- **Determinism**: results are the same with 3 and 5 workers.
- **Budget table**: `src/platsim/budget.py` is now the single preset table; `report/json_report.py` imports from it.

## 2026-10-07: T018, T021, T022 scripts parser, map graph, gates (agent; re-run by the coordinator)

`uv run pytest -q tests/unit/test_scripts.py tests/unit/test_mapgraph.py` → 22 passed, exit 0.
- **Controls**:
  - The Fight Area is unreachable. The only cut edge into it is the Snowpoint ship, `scripts_snowpoint_city.s:210`,
    gated by `FLAG_GAME_COMPLETED` at `:183`.
  - All 10 gym maps, Victory Road 1F/2F/B1F and all 19 Pokémon League maps are reachable from Twinleaf.
  - Victory Road 1F→Room 1 is post-game: the Collector stands on the warp and is only hidden after the game is
    completed.
- **Counts**: 593 headers. Strict mode reaches 429; loose mode reaches 441.
- **Uncertain edges**: listed in the agent's report and in `mapgraph` output; they are cut in strict mode.
- **OPEN, for T023/T026**:
  1. **National Dex timing**: the grant at `scripts_sandgem_town_pokemon_research_lab.s:539` sits behind
     `CheckLocalDexCompleted`, not `FLAG_GAME_COMPLETED`. Research R2's premise "National Dex means post-game" is
     therefore UNVERIFIED and must be traced. Is the lab event reachable before the Champion with a completed Sinnoh
     dex?
  2. **Newmoon Island** comes out reachable; in fact it needs an event-only item. Event and distribution-only items
     must be treated as unobtainable (FR-005, one cartridge).
  3. **Terrain** uses only the collision bit, so terrain evidence never decides an edge, only marks it uncertain.

## 2026-10-07: T045–T048 trainer-AI decision layer (agent; re-run by the coordinator)

```
$ cd sim && node --test test/*.test.mjs → tests 294, pass 294, fail 0, exit 0
$ uv run pytest -q                     → 129 passed, exit 0
$ uv run platsim divergences           → 72 entries (ai/corrected=2, ...), version sha256:0668c3641480a992, exit 0
```
- **Files**: `sim/ai/{choose,switch,items,patches,opponent}.mjs`. `decomp-ai` is registered and is now the
  **default opponent policy** (changed by the coordinator). Tests that check placeholder behaviour request it
  explicitly.
- **200-gauntlet run** (decomp-ai vs greedy-v1, from the agent's report):
  - no `ai_unimplemented` and no other error;
  - byte-identical on rerun, and a different seed gives a different result;
  - 14,770 AI decisions: 9,752 moves, 3,966 post-KO replacements, 914 Full Restores, 125 voluntary switches, 13 locked
    turns;
  - the mismatch counters never fired.
- **Throughput with the AI**: about 9.5 gauntlets/s per process.
- **Full Restore** now heals in `beforeTurnCallback` and cancels its move action. Taunt, Encore, Pressure, lastMove,
  Sucker Punch and Heal Block are handled as in the game, each tested live. The ledger entry is now `corrected`.
- **Golden positions**: 18, covering all five trainers. Each asserts the damage estimates, the score changes by script
  line, the RNG draw count and the choice.
- **Score past 127**: unreachable with League flags (static bound +25 < +28), so it is tested at the handler level
  only.
- **RNG**: the AI has its own LCRNG stream, seeded from `sha256(prngSeed|trainer-ai)`. Quick Claw `speedRand` is drawn
  at battle start and after each turn, per `battle_controller_player.c:853-856`.
- **UNVERIFIED**:
  - the AI memory reconstructed from Showdown's log (player ability/item knowledge, the move that last hit, last-move
    success);
  - Gyro Ball speed values;
  - double-KO visibility;
  - the overflow score being 64 by C arithmetic vs 65 in the bugs doc;
  - no comparison against the cartridge.

## 2026-10-07: T050 expectimax2-v1, T051 determinism, T056 strength benchmark (agent; re-run by the coordinator)

```
$ cd sim && node --test test/*.test.mjs → tests 301, pass 301, fail 0, exit 0
$ PLATSIM_STRENGTH_N=160 uv run pytest -q -s tests/integration/test_policy_strength.py   (coordinator rerun)
  greedy-v1       cleared 26/160 = 0.1625  Wilson95 [0.1134, 0.2275]
  expectimax2-v1  cleared 92/160 = 0.5750  Wilson95 [0.4975, 0.6490]
  McNemar exact: expectimax2-only=75 greedy-only=9 p=4.31e-14 verdict=A
  2 passed, exit 0
```
- **Agent's N=2000 run** (1258 s, exit 0): 1040/2000 vs 316/2000, p = 3.56e-129 (see research R7 – Measured).
- **T051**: over 200 gauntlets per policy, every p1 choice is a move or a switch. The live battle and AI RNG are never
  touched by the look-ahead; a positive control (a policy that draws from the battle PRNG) is caught.
- **Prediction check**: the shadow-state AI matches the live AI on 664/664 choices. As a control, setting the opponent
  to 1 HP changes the choice in 140/166 cases.
- **Fixture**: `tests/fixtures/reference_team.json` is a plausible level-57 team. Its formal legality is pending
  T029/T030, and its `ability_reason` values are placeholders.
- **Test fix**: `sim/test/gauntlet.test.mjs` changed its "unknown policy" name, because `expectimax2-v1` now exists.

## 2026-10-07: T023–T026 availability sources + ledger (agent; National Dex rule by the coordinator per user decision)

```
$ uv run platsim extract --check → "up to date (9 files)", exit 0
$ uv run pytest -q tests/integration/test_availability_controls.py tests/unit/test_mapgraph.py → 51 passed, exit 0
$ uv run pytest -q --ignore=tests/integration/test_policy_strength.py → 169 passed, exit 0 (before the rule change)
```
- **National Dex**: the decomp verdict is that it can be obtained before the Champion (see research R2 Correction).
  The **user decided it is not allowed** (spec FR-003a). `ALLOW_NATIONAL_DEX = False`; Poké Radar slots are now
  0 pre-Champion. The radar control asserts this.
- **Event-only items** (Mystery Gift handlers only) are unobtainable. Newmoon Island, Harbor Inn, Rotom's Room,
  Flower Paradise, Seabreak Path and Hall of Origin are unreachable. 421 maps are reachable (429 before the fixes).
- **Counts with the rule applied**:
  - entries: 2,453 pre-Champion, 1,542 post-game, 1,110 unobtainable;
  - species: 182 of 493 have a pre-Champion source (breeding is not derived, so this undercounts);
  - TMs: 36 unlimited (incl. HMs), 57 finite, 7 unavailable (TM08, 37, 42, 50, 53, 61, 73);
  - held items: 42 unlimited, 46 finite, 70 unavailable.
- **T026**:
  - `encounters_unknown_533–557` are unused filler;
  - honey trees are on 21 maps (`honey_tree.c:41-63`);
  - there is no badge gate on the way to the League;
  - the Snowpoint tutor is ungated;
  - **`pp_restore_between_battles: true`**: Leppa Berry is unlimited via a berry patch (`berry_init.h`,
    `berry_patches.c:233` yield ≥ 2). Ether, Max Ether, Elixir and Max Elixir are finite.
- **Uncertain** (48 entries, treated as not available): mostly vendor shops with no trigger.
- **Gaps**:
  - Turnback Cave rooms are not linked, though Giratina is still available from the Distortion World;
  - Pal Park is cut;
  - field-move gating is not modelled;
  - Pickup, wild held items and breeding are not sources (an under-approximation).

## 2026-10-07: T028–T031 move sources, validator, fixtures, `platsim validate` (agent; re-run by the coordinator)

```
$ uv run pytest -q tests/unit/test_validator.py → 33 passed, exit 0
$ uv run platsim validate tests/fixtures/legal_team.json → "legal (no violations)", exit 0
$ uv run platsim validate tests/fixtures/illegal_trade_evo.json → SPECIES_TRADE_EVOLUTION (Gengar from Haunter, EVO_TRADE,
  src res/pokemon/haunter/data.json:110), exit 2
```
- **Fixtures**: each illegal fixture yields exactly its one expected code. A subprocess check confirms the validator
  never imports `platsim.optimizer`, with a positive control.
- **Decisions**:
  - The relearner (Pastoria) is available and costs one Heart Scale per move.
  - Max friendship is treated as reachable (walk cycle).
  - Draco Meteor needs a Dragon-type stage.
  - Egg moves need a pre-Champion father, which is recorded in the source detail. Ditto is not pre-Champion, so
    genderless and male-only lines cannot be bred.
  - Minimum start levels come from ledger levels and evolution levels.
- **`tests/fixtures/reference_team.json` is ILLEGAL** (15 violations, file not edited):
  - Alakazam is trade-evolution only;
  - its `source` values are placeholders;
  - 9 move-source labels are wrong.
  
  The T056 benchmark is still valid as a comparison of policy strength, but the fixture must be replaced with a legal
  team before it is used for SC-006 or evaluation (T072, T071).
- **Ledger gap found by the coordinator**: wild held items are not a source.
  `res/pokemon/munchlax/data.json:21-23` holds Leftovers in both slots, and Munchlax is a pre-Champion honey-tree
  encounter, yet the ledger reports 0 Leftovers. The other copies (`scripts_visible_items.s:1517` Victory Road 1F
  Room 2, `:1601` Stark Mountain Life Orb) are correctly post-game per the map graph. **Follow-up**: add wild held
  items as an item source.
- **UNVERIFIED / conservative**:
  - alternate forms are rejected;
  - evolution cancelling is not modelled;
  - move timing within a member is not modelled;
  - Volt Tackle via Light Ball is not modelled.

## 2026-10-07: wild held items as a source; Munchlax excluded (spec FR-006a, user decision; agent, re-run by the coordinator)

```
$ uv run platsim extract --check → "up to date (9 files)", exit 0
$ uv run pytest -q tests/integration/test_availability_controls.py tests/unit/test_validator.py tests/unit/test_mapgraph.py → 89 passed, exit 0
$ uv run pytest -q --ignore=tests/integration/test_policy_strength.py → 207 passed, exit 0 (agent's run)
```
- **Held-item roll** (`src/pokemon.c:4670-4701`, read by the coordinator at `:4681-4696`):
  - If common == rare and the item is not NONE, the mon always holds it.
  - Otherwise `rand % 100`: below 45 no item, below 95 the common item, else the rare item (45 / 50 / 5%).
  - Compound Eyes changes this to 20 / 60 / 20%.
  - Trainer battles and roamers never roll.
- **Rule**: `EXCLUDED_SPECIES = {"SPECIES_MUNCHLAX"}` in `availability/ledger.py`. Munchlax and its held items are
  unobtainable; **Snorlax is also lost**, because its only pre-Champion source was evolving Munchlax.
- **Leftovers: still 0 copies pre-Champion.** Its sources were Munchlax (excluded) and the Victory Road 1F Room 2 ball
  (post-game per the map graph).
- **Counts**:

  | Held items | Before | After |
  |---|---|---|
  | unlimited | 42 | 65 |
  | finite | 46 | 38 |
  | unavailable | 70 | 55 |

  Species with a pre-Champion source: 182 → 180.
- **New items with battle relevance** (all unlimited): Babiri, Chople, Colbur, Haban, Kasib, Rindo, Shuca, Wacan and
  Yache berries; Black Sludge; Grip Claw; Quick Claw; Lagging Tail; Light Ball; Lucky Egg; Shed Shell; TwistedSpoon;
  Metal Coat; Miracle Seed; NeverMeltIce; Poison Barb; Electirizer; Magmarizer.
- **UNVERIFIED**: Thief and Covet are not modelled (catching is assumed); Compound Eyes odds are recorded only;
  scripted gift items are not covered.

## 2026-10-07: user decisions after Checkpoint B (coordinator)

- **Auto-learn follows the game.** `sim/exp.mjs` learns level-up moves into empty slots with base PP
  (`pokemon.c:3852-3871`, `battle_script.c:10021-10035`); with 4 moves the prompt is declined. Moves carry across
  battles (`state_before.moves`, `start_state.moves`). Tests: case 13 (Lucario L10→16 with 1 move learns Force Palm and
  Feint, `lucario/data.json:43-44`) and case 13b (4 moves → declined). The ledger entry is now `corrected`.
  - `cd sim && node --test test/*.test.mjs` → tests 302, pass 302, fail 0, exit 0.
  - `uv run platsim divergences` → 72 entries (exp/corrected=3), version sha256:1c030f39e80e6e42, exit 0.
- **Policy per stage**: screening uses `greedy-v1`; level search and confirmation use `expectimax2-v1` (research R8).
  Run time is not a hard constraint.
- **No Leftovers** is accepted.

## 2026-10-07: T072 independent final-level check + two exp bugs fixed (agents; re-run by the coordinator)

```
$ cd sim && node --test test/*.test.mjs → tests 308, pass 308, fail 0, exit 0
$ uv run pytest -q tests/unit/test_exp.py tests/integration/test_final_levels.py tests/integration/test_divergences.py → 34 passed, exit 0
$ uv run platsim divergences --check → exit 0
```
- **T072**: the independent Python recomputation from Showdown logs (`decomp/exp.py` `exp_gain`/`apply_exp`, written
  from the C) is compared with the worker on the new legal `reference_team.json` (greedy-v1 vs decomp-ai, 200 runs):
  final levels 200/200, final exp 200/200, every award equal. Mean final average level is 60.2925 for both, difference
  0.0000 (SC-006 ≤ 1). The hand-worked run is in `tests/fixtures/reference_team_handcalc.md`.
- **Positive controls**: dropping trainer ×1.5 leaves 41/200 matching; the old pay-at-faint rule changes 262 awards.
- **Bug fixed 1**: an NPC-trade member was never treated as traded, so the ×1.5 boost was missing (FR-008a). `team.mjs`
  now derives traded and language from `source: "npc_trade:…"` and `res/npc_trades/*.json`. Chatot (legal_team):
  2079 → 3118.
- **Bug fixed 2**: exp was paid at the faint event, before recoil. The decomp applies recoil and Life Orb in the
  after-move step (`battle_controller_player.c:3486-3494`, `:4715-4775`) and pays exp at MOVE_END (`:3968`); an
  attacker at 0 HP gets none (`battle_script.c:2204`, `:9740`). Exp is now paid when the action finishes and per
  end-of-turn step. Node cases 16–21 cover this; the positive controls fail with the old rule.
- **UNVERIFIED**: Future Sight / Perish Song payout timing (ledgered); no cartridge comparison.
