# platsim: Pokemon Platinum Champion team optimizer

You give `platsim` six species. It looks for the build with the **lowest average team level after
beating Cynthia** that still clears the Elite Four plus Champion gauntlet reliably (default ≥ 75%) and
keeps the final level gap at 10 or less. It can also battle-test a team you already have, check its
legality, and trace any rule back to the game source.

Full spec: [`specs/001-champion-team-optimizer/`](specs/001-champion-team-optimizer/), mainly
`spec.md`, `research.md` and `validation-log.md`. Principles: [`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## Ground rules

- **The decomp is the source of truth.** All game data (stats, learnsets, TM/tutor/item availability,
  trainer parties, AI, exp formula) is extracted from [`pokeplatinum`](https://github.com/pret/pokeplatinum)
  at a pinned commit. Nothing is hand-typed, and wikis or Showdown data are used only as cross-checks.
  Target: Platinum (USA) Rev 1.
- **Showdown is the battle engine.** Battles run in Pokemon Showdown's Gen 4 engine, called in-process
  from Node workers. Wherever Showdown and the decomp differ, the decomp wins, and every difference is
  recorded in the divergence ledger. The vendored Showdown tree is never edited; corrections are
  applied at runtime.
- **Opponents use the game's own trainer AI.** The decomp's AI script (`trainer_ai/script.s`) is run
  by an interpreter (`decomp-ai`), and that includes Cynthia's 4× Full Restore.
- **The player uses a named look-ahead policy**, `expectimax2-v1`. In 2,000 paired runs it cleared
  52.0% against 15.8% for the `greedy-v1` baseline (p = 3.6e-129, research R7).
- **Legality** (checked by an independent validator on every output):
  - Nothing post-game: the cutoff is the first Champion win, decided by the game's own story gates.
  - One cartridge only. No trades with another game, so trade evolutions are rejected. In-game NPC
    trades are allowed and get boosted exp.
  - **No National Dex sources**, so no Poké Radar (user decision). Event-only items are unobtainable.
  - **Munchlax is excluded** completely, which also excludes the Leftovers it holds and Snorlax.
  - **TMs are single-use.** Each TM has as many copies as the game gives before the Champion. Shop
    and Game Corner TMs are unlimited.
  - **No bag items in battle.** Only held items have an effect. Between battles the team is healed
    (HP, status, faints). PP carries over, except that Leppa Berries can be farmed.
  - Every member has **IV 15, EV 85 in each stat, and a neutral nature**. NPC trades and gifts use
    the values the game fixes for them. **No PP Ups**: every move has base PP, on both sides.
  - Level-up moves are **auto-learned as in the game** when a member has fewer than 4 moves.
    Otherwise the prompt is declined. Evolution is always declined.
  - Abilities: when there are two, both are tested and the better one is kept. A tie keeps the
    first. An ability the battle code never checks (Stench, Illuminate) is not tested.
- A draw or a hit on the 1,000-turn limit counts as a loss.

## Prerequisites and one-time setup

- Python 3.14 and [uv](https://docs.astral.sh/uv/).
- Node ≥ 22.18 (tested on 22.22.1).
- About 1 GB of disk for `node_modules`, `dist` and `.venv`.
- Network access **once**, for `uv sync` and `npm ci`. Everything after that runs offline, and no
  paid services are involved.
- Vendored sources at the pinned commits. These are git-ignored, so clone them yourself:
  - `pokeplatinum/` @ `c248fb3f8cc9934ded800e489567c5c0eeee92eb`
  - `pokemon-showdown/` @ `c046106cbe075931b1ff8d8b800ff5be47a85f96`

```bash
uv sync                                                  # Python deps into .venv/
(cd pokemon-showdown && npm ci && node build)            # writes node_modules/ and dist/ only
uv run platsim extract                                   # data/generated/ from the decomp
uv run platsim divergences                               # refresh the ledger; non-zero exit on unresolved entries
```

**The ROM is never committed** (`*.nds` is git-ignored) **and is not needed to run anything.** Its
only use is confirming the revision hash.

## Commands

All commands print progress to stderr. Exit codes: **0** success, **2** invalid input (an illegal team
or unknown species, with reasons), **1** internal error. For the full flag list, run
`uv run platsim <cmd> --help`.

| Command | What it does | Main flags |
|---|---|---|
| `extract` | Regenerates `data/generated/` from the pinned decomp | `--check`, `--out` |
| `divergences` | Compares Showdown gen4 data with the decomp and writes `data/divergences.json` | `--check`, `--out`, `--dump`, `--ledger` |
| `validate TEAM` | Legality check only (TEAM is JSON or a Showdown export) | `--json` |
| `evaluate TEAM` | Battle-tests a fixed team over the full gauntlet | `--runs` (min, default 2000), `--seed` (default `0`), `--workers` (default: CPU count), `--player-policy` (default `expectimax2-v1`), `--budget {quick,standard,thorough}`, `--min-clear` (default 0.75), `--max-runs`, `--out` (default `runs/evaluate-<time>-<hash>/`) |
| `explain SUBJECT` | Traces a fact to the decomp | `tmNN`, `hmNN`, `species:<key>`, `item:<key>`, `move:<key>`, `trainer:<key>`, `divergence:<id>`; `--json`, `--level` |
| `serve` | Local web UI and HTTP API on 127.0.0.1 | `--port` (default 8000), `--runs-dir` |
| `optimize S1 … S6` | **Being finalised.** It is not registered in the CLI yet (`uv run platsim optimize --help` exits 2 with "invalid choice"). Planned flags: `--min-clear`, `--seed`, `--workers`, `--budget` ([contracts/cli.md](specs/001-champion-team-optimizer/contracts/cli.md)) |

Examples. The outputs below were captured from real runs.

```console
$ uv run platsim extract --check
platsim extract --check: .../data/generated is up to date (10 files)                      # exit 0

$ uv run platsim divergences --check
.../data/divergences.json is up to date: 73 entries (ai/corrected=2, data/accepted=51, data/corrected=5,
exp/corrected=3, mechanics/accepted=10, mechanics/corrected=2); 5 Dex patches; version sha256:8fc3728d461fba56

$ uv run platsim validate tests/fixtures/reference_team.json
tests/fixtures/reference_team.json: legal (no violations)                                  # exit 0

$ uv run platsim validate tests/fixtures/illegal_trade_evo.json
SPECIES_TRADE_EVOLUTION: member 6 (gengar): Gengar is only reachable by trade evolution from Haunter
(EVO_TRADE), which needs a second cartridge (FR-005)
    src: src/pokemon.c:3727, specs/001-champion-team-optimizer/spec.md:173, res/pokemon/haunter/data.json:110
tests/fixtures/illegal_trade_evo.json: ILLEGAL - 1 violation(s)                            # exit 2

$ uv run platsim explain tm26
TM26 - TM26 (ITEM_TM26)  [generated/items.txt:354, res/items/data/tm26.json:1]
  teaches MOVE_EARTHQUAKE  [res/items/data/tm26.json:30]
  phase: pre_champion  [res/field/events/events_wayward_cave_1f.json:53]
  copies used by optimizer (TM/HM pre-Champion copies): 1  ...
  purchasable pre-Champion: no  ...
  - [pre_champion] item_ball at Wayward Cave 1F ..., quantity 1  [..., res/field/scripts/scripts_visible_items.s:564]

$ uv run platsim evaluate tests/fixtures/reference_team.json --runs 2000 --seed fixed
```

For that last `evaluate` command, the recorded run (validation-log, expectimax2-v1 against decomp-ai
on 16 workers) gave:
- gauntlet 0.7930 [0.7747, 0.8102];
- Cynthia P(win | reached) 0.7946 over 2,001 battles;
- expected final average level 60.32, gap 2.0, **qualified**;
- top loss causes: Cynthia's Garchomp, Lucario, Togekiss.

The output was byte-identical when rerun on 7 workers. `evaluate` writes `result.json`,
`result.xlsx`, `result.csv` and `team.txt` (a Showdown export).

`explain` builds the availability ledger on every call, which takes about 35 s.

**Web UI:** run `uv run platsim serve` and open http://127.0.0.1:8000. You can search species, fill six
slots, start a job, watch its progress, and download `.xlsx`/`.csv`. The jobs it runs call the
optimizer, which is still being finalised (`platsim.optimizer.run` does not exist yet). So far the UI
has only been tested against a stub optimizer.

## Reading the result spreadsheet (`result.xlsx`)

| Sheet | Contents |
|---|---|
| **Team** (also `result.csv`) | One row per member: Slot, Species, Obtained from, Start level, Final level (expected), Ability, Ability choice, Held item, Held item source, Nature, IVs, EVs, Move 1–4, Move 1–4 source |
| **Evaluation** | Status, qualified/borderline, threshold, budget preset, runs, gauntlet clear rate with 95% CI, Champion win rate, expected final levels and gap, per-trainer clear rates, top loss causes |
| **Resources** | For each single-copy TM and limited item: who uses it, copies used, copies available |
| **Provenance** | Decomp and Showdown commits, ledger version, player and opponent policy, master seed, budget preset |
| **Divergences** | Every ledger entry that applies to this run, with its resolution and impact |

- **Move source** strings look like `Level-up Lv 48`, `Pre-evolution level-up (Gabite Lv 40)`,
  `TM26 – <where the copy comes from>`, `<place> tutor (<shard cost>)`, `Egg move` or
  `Move relearner – …`.
- **Ability choice** is one of `tested_better`, `tie_default`, `other_no_battle_effect`,
  `single_ability` or `fixed_by_trade`.
- **Cynthia's rate is conditional:** it is P(win | reached Cynthia). It is computed from full runs
  plus top-up battles, which start from team states recorded after Lucian. It is not the gauntlet
  rate. The gauntlet clear rate comes from full runs only.
- **qualified**: clear rate ≥ threshold, and the CI half-width is within the preset's target.
  **borderline**: the CI straddles the threshold. A "no qualifying team" result reports the best
  clear rate it reached, and at which levels, instead of a failing team.
- **Quick budget:** every output from the `quick` preset carries a `QUICK BUDGET` warning, and a
  quick result can never be `qualified`.

## Budget presets and run times

| Preset | Screening rounds (greedy-v1) | Ability screen | Confirm per finalist (expectimax2-v1) | CI half-width target |
|---|---|---|---|---|
| `standard` (default) | 100 → 200 → 400 | 200 | ≥ 2,000, more until the target is met | ±2 points |
| `thorough` | 200 → 400 → 800 | 400 | ≥ 5,000, more until the target is met | ±1.5 points |
| `quick` (testing only) | 50 → 100 → 200 | 100 | 500 | none, never qualifies |

Measured throughput on this machine (Ryzen 7 5700X3D, 16 threads, 16 workers):

| Setup | Throughput |
|---|---|
| `expectimax2-v1` vs decomp-ai | **~2 gauntlets/s** (2.09 measured; 1.64 in the T056 benchmark) |
| `greedy-v1` | 52.2 gauntlets/s |
| Bare engine | 59 gauntlets/s ceiling |

- A 2,000-run standard `evaluate` takes **about 16–18 min**. The one measured run took 1,083 s.
- Derived from the 2.09/s rate, not measured: a `thorough` confirmation (≥ 5,000 runs) takes about
  40 min per finalist, and a `quick` confirmation (500 runs) about 4 min.
- Run counts are only lowered when you pass an explicit `--budget`, and that choice is shown in the report.

## Provenance and the divergence ledger

- Every extracted fact carries a `path:line` reference into `pokeplatinum/` at the pinned commit.
  `data/generated/manifest.json` records the commit and file hashes, and `extract --check` proves the
  data regenerates exactly.
- `data/divergences.json` lists every known Showdown-vs-game difference, in four areas: data,
  mechanics, ai and exp. Each entry is either **corrected** (patched into Showdown at worker startup)
  or **accepted** (with its impact stated). `divergences` exits non-zero if any entry is unresolved.
- Every report records seeds, the decomp and Showdown commits, the ledger version, both policies and
  the budget preset. The same inputs and seed reproduce identical output, whatever the worker count.

## Known limitations and UNVERIFIED items

- **No comparison against a real cartridge or emulator.** Fidelity rests on the decomp, unit tests,
  golden positions computed by hand from the AI script, and an independent Python recomputation of
  exp and levels.
- The trainer AI's **memory** (which player abilities and items it knows, the move that last hit,
  whether the last move succeeded) is **reconstructed from Showdown's battle log**. Also unverified:
  Gyro Ball speed values, double-KO visibility, and Future Sight / Perish Song exp timing.
- **There is no Leftovers before the Champion.** Its only sources are Munchlax, which is excluded,
  and a post-game item ball. The user accepted this.
- **Availability is an under-approximation**:
  - breeding is not derived as a species source;
  - Pickup, Thief and Covet are not modelled;
  - alternate forms are rejected;
  - field-move gating is not modelled;
  - 48 "uncertain" entries are treated as unavailable.
- `expectimax2-v1` has known model gaps (listed in the header of `sim/policy/expectimax2.mjs`):
  unmodelled status/setup moves, weather that never expires, hazards, and multi-hit moves.
- The after-battle items from Pickup and Honey Gather are not simulated (accepted divergence).
- `evaluate` does not add runs to settle a borderline result. The held-item source column can read
  "not recorded".
- `optimize` and the web UI's real optimizer run are not finished yet (see Commands).

## Repository layout

```text
src/platsim/          Python: everything that is not battle-time
  decomp/             readers for pokeplatinum sources (species, moves, items, tutors, trainers, exp, scripts)
  availability/       pre-Champion availability ledger, map graph, story gates
  legality/           independent validator
  divergence/         Showdown-vs-decomp comparison and ledger
  sim/                Node worker pool client, seeds, Cynthia top-up
  optimizer/          ability screening, candidates, resources (search in progress)
  report/             result.json / xlsx / csv / team.txt writers, loss causes
  web/                FastAPI app + static page
  budget.py stats.py evaluate.py explain.py extract.py cli.py
sim/                  Node: Showdown worker, gauntlet, exp/level-up, damage port
  ai/                 decomp trainer-AI parser + interpreter
  policy/             greedy-v1, expectimax2-v1
  spikes/  test/
data/divergences.json divergence ledger;  data/generated/ (git-ignored, from `extract`)
tests/                pytest unit/, integration/, fixtures/
specs/                spec, plan, research, contracts, tasks, validation log
runs/                 job outputs (git-ignored)
pokeplatinum/ pokemon-showdown/   vendored at pinned commits, not edited, git-ignored
```

## Running tests

```bash
uv run pytest -q                                           # Python suites
uv run pytest -q --ignore=tests/integration/test_policy_strength.py -k "not v7"   # skips the two long ones
(cd sim && node --test test/*.test.mjs)                    # Node suites (308 tests, ~3 min here)
```

The full pytest run includes two long tests, each 2,000 expectimax2 gauntlets. The last recorded
run without them took 630 s (232 passed). These environment variables shrink or redirect the long
tests:

| Variable | Default | Used by |
|---|---|---|
| `PLATSIM_STRENGTH_N`, `PLATSIM_STRENGTH_WORKERS` | 2000, CPU count | `test_policy_strength.py` (T056) |
| `PLATSIM_EVALUATE_N`, `PLATSIM_EVALUATE_WORKERS` | 2000, CPU count | `test_evaluate.py` V7 |
| `PLATSIM_EVALUATE_FAST_N` | 40 | `test_evaluate.py` fast check |
| `PLATSIM_T072_N`, `PLATSIM_T072_FIXTURE`, `PLATSIM_T072_WORKERS` | 200, `reference_team.json`, CPU count | `test_final_levels.py` |

For example: `PLATSIM_STRENGTH_N=160 uv run pytest -q -s tests/integration/test_policy_strength.py`.
pytest puts its temp files under `/dev/shm/platsim-pytest-<pid>` and removes them at exit.
