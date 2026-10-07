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
