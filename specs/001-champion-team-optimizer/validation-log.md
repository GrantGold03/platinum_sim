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
