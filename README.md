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
- **The player uses a named look-ahead policy**, `expectimax2-v2` (the default everywhere since
  2026-10-08). It replaced `expectimax2-v1`, which lost to `greedy-v1` on some optimizer teams because
  its search rewarded delaying KOs and its leaf weights were mis-scaled (research R7 – v2 correction).
  In 600 fresh paired runs v2 beat greedy on the reference team (568 vs 442, p = 1.8e-23) and was at
  parity on the team where v1 had lost. `expectimax2-v1` stays registered for comparison.
  On the T056 benchmark team (2,000 paired runs, rerun 2026-10-08) v2 cleared 1,706, v1 1,020 and
  greedy 298.
- **Legality** (checked by an independent validator on every output):
  - Nothing post-game: the cutoff is the first Champion win, decided by the game's own story gates.
  - One cartridge only. No trades with another game, so trade evolutions are rejected by default.
    In-game NPC trades are allowed and get boosted exp.
  - **Egg moves are off by default.** A Day Care egg is still a legal species source.
  - **One-of-a-kind choices hold for the whole team** (004). A team may use only one starter line.
    Several members of that line are fine, because breeding the chosen starter gives more. A team
    may also use only one fossil line. Before the National Dex, Skull Fossils (Cranidos) are dug
    only with an odd Trainer ID and Armor Fossils (Shieldon) only with an even one
    (`src/underground/mining.c`). Each revival uses up one fossil, and fossils can be dug again
    and again.
  - **A Day Care egg needs a real pair** (004). Ditto can't be caught before the Champion, so an
    egg needs a mother that can be female and a male that shares an egg group with her.
    One-time parents qualify, because breeding doesn't use them up: Riley's Riolu, the Hearthome
    Eevee, the Togepi egg, Drifloon and Spiritomb. Each egg's "Obtained from" text names where
    its parent comes from.
  - Five optional rules, all **off by default**, relax this. Each is a flag on `validate`,
    `evaluate` and `optimize` and a checkbox on the web page. All five are recorded in
    `provenance.legality_options`, and the validator enforces them (constitution 1.2.0, Principle III).
    - `--allow-egg-moves` and `--allow-trade-evolutions` (001 FR-005/FR-005a). With trade evolutions
      on, an item-trade evolution uses up a copy of the item. A trade-evolved Pokémon gets **no
      traded-exp boost**, because the player stays its original trainer.
    - `--allow-post-game-pokemon` (003): post-game encounters, National Dex ones included, count as
      pokemon sources.
    - `--allow-post-game-items` (003): post-game items, TMs and move tutors count, including the
      Battle Frontier BP exchange (TM04, TM08, TM61, TM73, Focus Band and more).
    - `--allow-unobtainable-pokemon`, "Pokémon unobtainable in one Platinum game" (003, widened in
      005): other-cartridge (dual-slot) encounters count. A pokemon with no source at all gets a
      made-up level-1 source, labelled "Unavailable in Platinum (allowed by rule)" in every report.
      It also lifts the 004 one-starter-line and one-fossil-line rules, as if a second Platinum
      game supplied the other choice. Each member that needs it is labelled "(from a second
      Platinum game, allowed by rule)". One-copy limits (legendaries, gifts, items) still apply.
    - Entries on maps the decomp labels `UNUSED_*` that can't be reached even after the Champion
      never count under any rule.
  - **No National Dex sources**, so no Poké Radar (user decision). This matters because Platinum
    actually grants the National Dex before the first Champion win (all 210 Sinnoh species seen,
    including some seen only in a lost League battle; research R2). Event-only items are unobtainable.
  - **Unreachable maps don't count.** A warp whose tile and all four neighbours are walls can't be
    stepped on, so it is cut from reachability (warp-on-wall rule, research R2). This makes TM04 and
    Focus Band unavailable.
  - **One-time gifts are counted once.** Copies that share the same one-time flag (item ball,
    hidden item or NPC received-flag) count as one acquisition, so TM65, TM28 and TM86 each have 1 copy.
  - **Munchlax and Snorlax are allowed** (003; this reverses 001's exclusion). Munchlax comes from
    honey trees at levels 5–15 (only some trees, depending on Trainer ID) and always holds
    **Leftovers**. So Leftovers may be held by any number of members **only when Munchlax or
    Snorlax is on the team**. With post-game items allowed, the Victory Road item ball adds one copy
    for any team.
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
| `validate TEAM` | Legality check only (TEAM is JSON or a Showdown export) | `--json`, the five `--allow-...` rule flags (see Ground rules) |
| `evaluate TEAM` | Battle-tests a fixed team over the full gauntlet | `--runs` (min, default 2000), `--seed` (default `0`), `--workers` (default: CPU count), `--player-policy` (default `expectimax2-v2`), `--budget {quick,standard,thorough}`, `--min-clear` (default 0.75), `--max-runs` (default 20000), `--out` (default `runs/evaluate-<time>-<hash>/`), the five `--allow-...` rule flags |
| `explain SUBJECT` | Traces a fact to the decomp | `tmNN`, `hmNN`, `species:<key>`, `item:<key>`, `move:<key>`, `trainer:<key>`, `divergence:<id>`; `--json`, `--level` (`move:` only, default 100) |
| `serve` | Local web UI and HTTP API on 127.0.0.1 | `--port` (default 8000), `--runs-dir` (default `runs/`) |
| `optimize S1 … S6` | Finds the lowest-level qualifying build for six species and writes the same four reports plus a resumable `state.json` | `--min-clear` (default 0.75), `--seed` (default `default`), `--workers` (default: CPU count; never changes results), `--budget {quick,standard,thorough}` (default `standard`), `--out` (default `runs/optimize-<hash of the request>/`; rerunning resumes), `--force-new`, the five `--allow-...` rule flags |
| `report --rerender RUN_DIR` | Re-renders an existing run's report with the current source-text code. No battle is re-run, the numbers are copied unchanged, and the validator runs again | `--out` (default `<RUN_DIR>-rerendered`; never overwrites existing report files; `RUN_DIR` is never modified) |

- **Resume and `--force-new`:** rerunning `optimize` with the same `--out` resumes from `state.json`.
  If the checkpoint came from different code, data, ledger, pins, runtime or legality options, the
  resume is refused, and the error suggests `--force-new`. `--force-new` moves the old checkpoint to
  `superseded-N/` and starts over. A change in `repo_commit` or `repo_dirty` alone is only logged.
- **`report --rerender`** uses the run's recorded legality options. A run that has none predates
  the flags; those runs were made with egg moves allowed and trade evolutions off. The new report
  records `provenance.rerender`, which gives the source run and its `result.json` sha256.

Examples. The outputs below were captured from real runs.

```console
$ uv run platsim extract --check
platsim extract --check: .../data/generated is up to date (10 files)                      # exit 0

$ uv run platsim divergences --check
.../data/divergences.json is up to date: 73 entries (ai/corrected=2, data/accepted=51, data/corrected=5,
exp/corrected=3, mechanics/accepted=10, mechanics/corrected=2); 5 Dex patches; version sha256:8fc3728d461fba56

$ uv run platsim validate tests/fixtures/reference_team.json
legality options: allow_egg_moves=off, allow_trade_evolutions=off
tests/fixtures/reference_team.json: legal (no violations)                                  # exit 0

$ uv run platsim validate tests/fixtures/illegal_trade_evo.json
legality options: allow_egg_moves=off, allow_trade_evolutions=off
SPECIES_TRADE_EVOLUTION: member 6 (gengar): Gengar is only reachable by trade evolution from Haunter
(EVO_TRADE), which needs a second cartridge (FR-005; enable allow_trade_evolutions / --allow-trade-evolutions to allow it)
    src: src/pokemon.c:3727, specs/001-champion-team-optimizer/spec.md:179, res/pokemon/haunter/data.json:110
tests/fixtures/illegal_trade_evo.json: ILLEGAL - 1 violation(s)                            # exit 2

$ uv run platsim explain tm26
TM26 - TM26 (ITEM_TM26)  [generated/items.txt:354, res/items/data/tm26.json:1]
  teaches MOVE_EARTHQUAKE  [res/items/data/tm26.json:30]
  phase: pre_champion  [res/field/events/events_wayward_cave_1f.json:53]
  copies used by optimizer (TM/HM pre-Champion copies): 1  ...
  purchasable pre-Champion: no  ...
  - [pre_champion] item_ball at Wayward Cave 1F ..., quantity 1  [..., res/field/scripts/scripts_visible_items.s:564]
      one-time flag: FLAG_OBTAINED_WAYWARD_CAVE_1F_TM26 (entries sharing it are one acquisition)  [...]

$ uv run platsim explain tm65
  ...
  copies used by optimizer (TM/HM pre-Champion copies): 1  ...
  shared one-time flag FLAG_RECEIVED_FANTINA_TM65: 2 pre-Champion entries, counted once (max quantity 1, not the sum 2)  ...

$ uv run platsim evaluate tests/fixtures/reference_team.json --runs 2000 --seed fixed --workers 16
platsim evaluate: full runs: 2000 in 709.0s; cleared 1889/2000; Cynthia top-up ...
runs 2000  player expectimax2-v2  opponent decomp-ai  budget standard
gauntlet clear rate 0.9445  95% CI [0.9336, 0.9537]  half-width 0.0101
Cynthia P(win | reached) 0.9450  [0.9342, 0.9542]  battles 2001
expected final levels 60.84 / 60.43 / 60.00 / 60.44 / 60.41 / 60.00  avg 60.35  gap max 2.0
threshold 0.75  qualified True  borderline False
  loss cause: cynthia garchomp 47
  loss cause: cynthia roserade 24                                                          # exit 0, 769 s wall
```

That run (T076, 2026-10-08, before the legality flags and code hashes were added) was repeated with
`--workers 8` and produced a byte-identical `result.json` (same sha256). `evaluate` writes
`result.json`, `result.xlsx`, `result.csv` and `team.txt` (a Showdown export). The older
expectimax2-v1 figure for this team (0.7930) is superseded.

```console
$ uv run platsim optimize infernape staraptor luxray garchomp gyarados gardevoir --seed fixed --workers 16 --out runs/final-defaults
platsim optimize: [calibrate] greedy-v1 at U=58: 59/100 cleared
platsim optimize: [screen] 81 candidate teams at levels [58, 58, 58, 58, 58, 58]
platsim optimize: [level_search] levels [57, 56, 56, 57, 57, 58]: 618/800 cleared -> pass, avg final 57.25
  ...
platsim optimize: [confirm] winner at levels [57, 56, 56, 57, 57, 58] (expectimax2-v2, >= 2000 runs)
platsim evaluate: clear-rate CI straddles the threshold 0.75 at n=2000: adding up to 1000 runs
  ...
platsim evaluate: full runs: 20000 in 8905.3s; cleared 14991/20000; Cynthia top-up ...
platsim optimize: [confirm] winner at levels [58, 57, 57, 58, 58, 59] (expectimax2-v2, >= 2000 runs)
platsim evaluate: full runs: 2000 in 935.4s; cleared 1729/2000; Cynthia top-up ...
platsim optimize: [done] wrote runs/final-defaults (qualified=True)
start levels infernape 58 / staraptor 57 / luxray 57 / garchomp 58 / gyarados 58 / gardevoir 59
runs 2000  player expectimax2-v2  opponent decomp-ai  budget standard
gauntlet clear rate 0.8645  95% CI [0.8488, 0.8788]  half-width 0.0150
Cynthia P(win | reached) 0.8676  [0.8520, 0.8817]  battles 2001
expected final levels 58.79 / 57.00 / 57.00 / 59.51 / 58.03 / 59.03  avg 58.23  gap max 4.0
threshold 0.75  qualified True  borderline False
WARNING: Winner and runner-up are statistically indistinguishable on paired runs (FR-019); the winner is the screening winner.
                                                                                 # exit 0, 4 h 39 min wall (4:38:49), 16 workers
```

This run (2026-10-08, default rules: no egg moves, no trade evolutions; commit `ed92a56`, `repo_dirty`
false) is the current headline result. The first confirmation, at 57/56/56/57/57/58, sat right at the
threshold: 14,991 of 20,000 cleared (74.96%). It spent about 2.5 h extending before it failed, and then
the +1 fallback qualified. The 4,000-run borderline cap added afterwards (see Budget presets) would
have sent this run to the fallback much sooner. Its new wall time has not been measured.

The winning team:

| Member | Moves | Item |
|---|---|---|
| Infernape | Fire Blast / Close Combat / Focus Blast / Flame Wheel | Sitrus Berry |
| Staraptor | Brave Bird / Close Combat / Giga Impact / Take Down | Sky Plate |
| Luxray | Thunderbolt / Thunder / Crunch / Iron Tail | Zap Plate |
| Garchomp | Earthquake / Dragon Claw / Rock Slide / Fire Blast | Earth Plate |
| Gyarados | Aqua Tail / Waterfall / Stone Edge / Ice Fang | Sitrus Berry |
| Gardevoir | Psychic / Thunderbolt / Icy Wind / Magical Leaf | Mind Plate |

- **Sources:** Chimchar is the starter gift and the other five are wild catches; no member is an egg.
  Sitrus Berry comes from the berry patch at Fuego Ironworks, and the Plates come from Underground
  mining.
- **Single-copy TMs used:** TM23, TM26, TM71 and TM80.
- `uv run platsim validate runs/final-defaults/team.txt` exits 0.
- For comparison, the hand-built all-L60 reference team above ends at an average of 60.35.
- **Superseded:** the earlier T076 result (avg 56.10, `runs/t076/v8`) gave Luxray the egg moves Ice
  Fang and Fire Fang and used the old TM counts. It is not legal under the current defaults:
  validating `tests/fixtures/t076_v8_team.json` reports `EGG_MOVE_NOT_ALLOWED` unless
  `--allow-egg-moves` is passed.

`explain species:…` (and other ledger subjects) builds the availability ledger on every call (`trainer:cynthia` took 1 s), which takes about 35 s idle (56–76 s measured in T076 while an optimize used every core); `validate` does the same (75 s in T076).

**Web UI:** run `uv run platsim serve` and open http://127.0.0.1:8000.

The page has two columns.
- A **light/dark toggle** sits top right. It follows the system setting until you pick one, and
  the browser remembers the pick.
- **Left: run setup.**
  - The five rule checkboxes. Hover over or focus "Allow trade evolutions" for what it means.
  - The Pokémon search. The list appears once you type. Pokémon that can't be used are always
    listed, crossed out with a short reason (e.g. "Unavailable in Platinum").
  - Six team slots, each showing the Pokémon's icon.
  - The minimum clear rate.
  - A **budget** selector: quick, standard (the default) or thorough.
  - The seed. Hover over or focus the word "Seed" for an explanation.
- **Right: results.**
  - **Progress:** shown only while a job is queued or running. It shows the stage, the elapsed
    time, an estimate ("about N min left", or "estimating…"), and a **Cancel** button for the
    running job and for each queued one.
  - **Run picker:** always opens on the newest finished run, and switches to a newer one when it
    finishes. Failed and cancelled runs show their reason.
  - **The run itself:**
    - a short summary: the verdict, and the clear rate. Hover over or focus the clear rate for its
      95% interval and run count;
    - "58.23 (level gap of 4)"-style final levels, the threshold, budget, legality options,
      warnings and platsim version (0.2.0 since feature 003; older runs show the version they recorded);
    - six cards with decomp sprites. Move names are coloured by type; hover over or focus a move
      for its type and source;
    - a per-trainer clear-rate chart, with intervals. Hover over, focus or tap a trainer for their
      sprite and team;
    - the four downloads.
  - The page never shows requirement ids or the word "species", and always spells "Pokémon".
    The chart shows one pop-up per trainer, with no second browser tooltip. Text that comes from older
    report files is cleaned when shown; the files themselves are not changed.

Jobs run the real optimizer one at a time (FIFO) and are stored under `runs/<job id>/`. The
picker lists the web jobs the server knows about, up to 50. Command-line runs such as
`runs/final-defaults` are not listed.

- For about the first 35 s after start the Pokémon search returns 503 while the availability ledger
  builds; it then answers normally.
- **Each web job runs in its own process group**, a spawned child, so Cancel stops it and its Node
  workers within seconds.
  - The child builds the availability ledger again, which adds about 35 s to the start of every job.
  - Stopping the server stops the running job and records it as failed ("server stopped while
    running"). If the server is killed, the child stops itself.
- Sprites come from the vendored decomp (`pokeplatinum/res/pokemon/<species>/`). They are made
  transparent when served, with nothing downloaded. The page works offline.
- The page shows a summary. The report files (`result.json`, `result.xlsx`, `result.csv`,
  `team.txt`) remain the full record, with every provenance field (constitution 1.1.0, Principle IV).
- **The HTTP API:**
  - `GET /api/species?q=`: add `trade_evolutions`, `post_game_pokemon`, `post_game_items` or
    `unobtainable_pokemon` `=1` for availability under those rules. Each item includes `sprite_icon`.
  - `POST /api/jobs` with `{"species": [...6], "budget": "quick" | "standard" | "thorough",
    "seed": "...", "min_clear": 0.75, "allow_egg_moves": false, "allow_trade_evolutions": false,
    "allow_post_game_pokemon": false, "allow_post_game_items": false, "allow_unobtainable_pokemon": false}`.
    - A non-boolean flag gives 422.
    - A team with an unusable species is refused with 422 and a reason per species.
  - `GET /api/jobs`: the newest 50, each with a `label`, `elapsed_s` and (while running) `eta_s`.
  - `GET /api/jobs/{id}`: once done, it adds `summary`, `per_trainer`, `team` and `downloads`.
  - `POST /api/jobs/{id}/cancel`:
    - 200 for a queued job;
    - 202 for a running one, which then becomes `cancelled`;
    - 409 once finished.
  - `GET /api/sprites/{species}/{front|icon}.png`.
  - `GET /api/league`: the five first-run League trainers with their party's pokemon keys (003).
  - `GET /api/trainer-sprites/{aaron|bertha|flint|lucian|cynthia}.png` (003).
  - `GET /api/jobs/{id}/{result.json|result.xlsx|result.csv|team.txt}`: 409 until the job is done.
- T076 drove this flow over HTTP. That was before the legality flags existed, and egg moves were
  allowed then. In that test a
  `quick` job for the six species above went through resolve → prune → calibrate → ability_screen →
  screen → level_search → setup_check → confirm → done in 25.6 min. It cleared 424/500 (0.848
  [0.814, 0.877]) at levels 58/58/59/58/58/58 (avg final 58.58), correctly not `qualified` because
  of the QUICK BUDGET label, and its downloaded `team.txt` passes `platsim validate`.
- The redesigned page is checked in a real browser by `uv run pytest -m browser tests/browser/`
  (Playwright driving the system Chrome; feature 002).

## Reading the result spreadsheet (`result.xlsx`)

| Sheet | Contents |
|---|---|
| **Team** (also `result.csv`) | One row per member: Slot, Species, Obtained from, Start level, Final level (expected), Ability, Ability choice, Held item, Held item source, Nature, IVs, EVs, Move 1–4, Move 1–4 source |
| **Evaluation** | Status, qualified/borderline, threshold, budget preset, runs, gauntlet clear rate with 95% CI, Champion win rate, expected final levels and gap, per-trainer clear rates, top loss causes |
| **Resources** | For each single-copy TM and limited item: who uses it, copies used, copies available |
| **Provenance** | Decomp and Showdown commits, ledger version, code hashes, repo commit and dirty flag, Node and Python versions, player and opponent policy, master seed, budget preset, legality options |
| **Divergences** | Every ledger entry that applies to this run, with its resolution and impact |

- **Move source** strings look like `Level-up Lv 48`, `Pre-evolution level-up (Gabite Lv 40)`,
  `TM26 - Item ball - Wayward Cave 1F (1 copy)`, `<place> tutor (<shard cost>)`, `Egg move` (only
  with `--allow-egg-moves`) or `Move relearner – …`.
- **"Obtained from" names the earliest place** (003). Examples: `Gift - Route 201 (Chimchar, starter)
  -> Monferno at level 14 -> Infernape at level 36` and `Wild - Wayward Cave B1F (Gible, grass) ->
  Gabite at level 24 -> Garchomp at level 48`.
  - Among the sources that are legal at the member's level, the one on the map that needs the
    fewest gym badges wins, across evolution stages.
    - Badge counts come from `data/generated/story_rank.json`, which models field-move badges,
      obstacles, water and story blockers from the decomp.
    - Known gaps: story gates driven by script variables, ledges you can only jump down, and
      Strength puzzles.
  - A location where every method is a 1% encounter is used only if nothing else qualifies.
  - A Day Care egg comes last.
  - Evolutions name their level, item, move, partner or place. The text never contains internal
    codes.
  - Reports written before 003 keep their recorded text; `platsim report --rerender` refreshes it.
- **Moves** use the simplest source:
  - level-up, then an unlimited TM/HM, then a tutor, then the relearner, then an egg move, then a
    single-copy TM.
- **Held item source** always names a real source, for example `Berry patch - Fuego Ironworks Outside
  (unlimited)` or `Underground mining - Underground (unlimited)`. An item with no nameable source is
  an error, so the column never prints `?`. To refresh an older run's text, use
  `platsim report --rerender`.
- **Ability choice** is one of `tested_better`, `tie_default`, `other_no_battle_effect`,
  `single_ability` or `fixed_by_trade`.
- **Cynthia's rate is conditional:** it is P(win | reached Cynthia). It is computed from full runs
  plus top-up battles, which start from team states recorded after Lucian. It is not the gauntlet
  rate. The gauntlet clear rate comes from full runs only.
- **qualified**: clear rate ≥ threshold, and the CI half-width is within the preset's target.
  **borderline**: the CI still straddles the threshold at the preset's borderline cap. A borderline
  result is never qualified. A "no qualifying team" result reports the best
  clear rate it reached, and at which levels, instead of a failing team.
- **Quick budget:** every output from the `quick` preset carries a `QUICK BUDGET` warning, and a
  quick result can never be `qualified`.

## Budget presets and run times

| Preset | Screening rounds (greedy-v1) | Ability screen | Confirm per finalist (expectimax2-v2) | CI half-width target | Borderline cap (total runs) |
|---|---|---|---|---|---|
| `standard` (default) | 100 → 200 → 400 | 200 | ≥ 2,000, more until the target is met | ±2 points | 4,000 |
| `thorough` | 200 → 400 → 800 | 400 | ≥ 5,000, more until the target is met | ±1.5 points | 10,000 |
| `quick` (testing only) | 50 → 100 → 200 | 100 | 500 | none, never qualifies | none (never extends) |

**Borderline cap** (research R8): sometimes the optimizer's confirmation CI straddles the threshold.
When that happens it adds runs, but only up to the cap. A team still undecided at the cap is
`borderline (not qualified)`, and the optimizer moves on to the +1-level fallback. Before the cap,
this extension could reach 20,000 runs: about 2.5 h in `runs/final-defaults`. With the cap, the
worst-case extra time per candidate is estimated at about 15 min on 16 workers (derived from
about 2.3 gauntlets/s, not measured). The cap is recorded in provenance.

Measured throughput on this machine (Ryzen 7 5700X3D, 16 threads), all vs decomp-ai, from the T076
runs on 2026-10-08:

| Setup | Throughput |
|---|---|
| `expectimax2-v2` (default player) | **2.1–2.8 gauntlets/s** on 16 workers: 2.62 (T056 benchmark team), 2.82 (reference team), 2.34–2.61 (T076 optimizer confirmation), 2.14–2.25 (`runs/final-defaults` confirmation); 2.74 on 8 workers |
| `expectimax2-v1` | 1.79 gauntlets/s (T056 benchmark team, 16 workers) |
| `greedy-v1` | 55.8 gauntlets/s (T056 benchmark team, 16 workers) |
| Bare engine | 59 gauntlets/s ceiling (T008 spike, no AI or policy) |

Measured run times:

| Run | Wall time |
|---|---|
| `evaluate` reference team, 2,000 runs, standard | 769 s on 16 workers, 790 s on 8 |
| `optimize` six species, `standard`, 16 workers (`runs/final-defaults`, before the borderline cap) | 4 h 39 min, of which about 2.5 h was the 20,000-run borderline extension |
| `optimize` same, superseded T076 rules (egg moves allowed) | 2 h 07 min (level search 82 min, confirmation 39 min) |
| `optimize` same six species, `quick`, via the web UI, 16 workers | 25.6 min |
| `optimize` `quick` in `test_optimize_small.py` (same species, seed `t058`) | 1,638 s (first run, 16 workers) |

- Derived from about 2.6/s, not measured: a `thorough` confirmation (≥ 5,000 runs) takes about
  32 min per finalist.
- 8 workers run almost as fast as 16 on this 8-core / 16-thread CPU.
- Run counts are only lowered when you pass an explicit `--budget`, and that choice is shown in the report.

## Provenance and the divergence ledger

- Every extracted fact carries a `path:line` reference into `pokeplatinum/` at the pinned commit.
  `data/generated/manifest.json` records the commit and file hashes, and `extract --check` proves the
  data regenerates exactly.
- `data/divergences.json` lists every known Showdown-vs-game difference, in four areas: data,
  mechanics, ai and exp. Each entry is either **corrected** (patched into Showdown at worker startup)
  or **accepted** (with its impact stated). `divergences` exits non-zero if any entry is unresolved.
- Every report records seeds, the decomp and Showdown commits, the ledger version, both policies, the
  budget preset and the legality options. It also records code versions:
  - `sim_code_hash` covers `sim/**/*.mjs` and `package.json`, excluding tests and spikes;
  - `platsim_code_hash` covers `src/platsim/**/*.py` and `pyproject.toml`;
  - `repo_commit`, `repo_dirty`, `node_version` and `python_version`.

  All pool workers must agree on `sim_code_hash` and the Node version.
- The same inputs and seed reproduce identical output, whatever the worker count.
- `optimize` stores this fingerprint in `state.json` and refuses to resume a checkpoint whose
  fingerprint differs. Use `--force-new` to start over.

## Known limitations and UNVERIFIED items

- **No comparison against a real cartridge or emulator.** Fidelity rests on the decomp, unit tests,
  golden positions computed by hand from the AI script, and an independent Python recomputation of
  exp and levels.
- The trainer AI's **memory** (which player abilities and items it knows, the move that last hit,
  whether the last move succeeded) is **reconstructed from Showdown's battle log**. Also unverified:
  Gyro Ball speed values, double-KO visibility, and Future Sight / Perish Song exp timing.
- **Leftovers needs Munchlax or Snorlax on the team** (003 FR-009). Its only pre-Champion source
  is wild Munchlax; the other is a post-game Victory Road item ball.
- **Availability is an under-approximation**:
  - the availability ledger does not list bred species. Day Care breeding is added as a species
    source by the legality layer;
  - Pickup, Thief and Covet are not modelled;
  - alternate forms are rejected;
  - field-move gating is not modelled;
  - 48 "uncertain" entries are treated as unavailable.
- `expectimax2-v2` keeps v1's model gaps (listed in the header of `sim/policy/expectimax2.mjs`):
  unmodelled status/setup moves, weather that never expires, hazards, and multi-hit moves. Its leaf
  weights were fitted on greedy-played games.
- The after-battle items from Pickup and Honey Gather are not simulated (accepted divergence).
- **Known gaps in the item/TM ledger**:
  - Some DP-leftover rooms (for example the old Hearthome gym leader room) are still reachable in
    the map graph. Their warp tiles are walkable but cut off from the arrival tile, and no
    connectivity check catches this yet. Their copies are deduplicated by flag anyway.
  - About 60 NPC gift sites have no detectable received flag, so they are counted without
    deduplication.
- The optimizer's winner and runner-up were statistically indistinguishable in the T076 runs and in
  `runs/final-defaults`; the report says so (FR-019).
- **Unverified:**
  - resuming after a mid-stage kill;
  - a full optimize run under the borderline cap.

## Repository layout

```text
src/platsim/          Python: everything that is not battle-time
  decomp/             readers for pokeplatinum sources (species, moves, items, tutors, trainers, exp, scripts)
  availability/       pre-Champion availability ledger, map graph, story gates
  legality/           independent validator
  divergence/         Showdown-vs-decomp comparison and ledger
  sim/                Node worker pool client, seeds, Cynthia top-up
  optimizer/          candidates, ability screen, successive-halving screen, level search, confirm (run.py)
  report/             result.json / xlsx / csv / team.txt writers, loss causes
  web/                FastAPI app, job process/cancel, result view, sprites, ETA + static page
  budget.py stats.py evaluate.py explain.py extract.py cli.py
sim/                  Node: Showdown worker, gauntlet, exp/level-up, damage port
  ai/                 decomp trainer-AI parser + interpreter
  policy/             greedy-v1, expectimax2-v1, expectimax2-v2 (default)
  spikes/  test/
data/divergences.json divergence ledger;  data/generated/ (git-ignored, from `extract`)
tests/                pytest unit/, integration/, browser/ (Playwright), fixtures/
specs/                spec, plan, research, contracts, tasks, validation log
runs/                 job outputs (git-ignored)
pokeplatinum/ pokemon-showdown/   vendored at pinned commits, not edited, git-ignored
```

## Running tests

```bash
uv run pytest -q                                           # Python suites (includes the browser tests)
uv run pytest -q -m browser tests/browser/                 # web page in the system Chrome (about 1 min)
uv run pytest -q --ignore=tests/integration/test_policy_strength.py -k "not v7"   # skips the two long ones
(cd sim && node --test test/*.test.mjs)                    # Node suites (314 tests)
```

The full pytest run includes long tests: the policy-strength benchmark (2,000 paired gauntlets ×
3 policies, plus 400 × 2 on the reversal team), the V7 evaluate determinism check (2 × 2,000
gauntlets) and two `quick` optimizes.
- **Full pytest:** the last full run was on 2026-10-11 (feature 003, T059): `uv run pytest -q -m
  "not browser"` gave 448 passed, 1 failed, 4 xfailed in 8,541 s (2 h 22 min). The failure was an
  outdated assertion in `test_evaluate.py::test_determinism_fast`: the report now records five
  rule options, not two. After fixing it, that test passed on its own (`1 passed in 189.82s`). The
  4 xfails are strict, documented story-rank controls. `uv run pytest -q -m browser tests/browser/`
  gave 4 passed. See `specs/003-webui-refinements/validation-log.md`.
- **Browser tests** need Google Chrome installed (`google-chrome` on `PATH`) and skip with a reason
  otherwise. Playwright drives it with `channel="chrome"`, so no Playwright browser download is needed.
- **Node suite:** on current code it gave **314 pass, 0 fail, exit 0 in 285 s**.

These environment variables shrink or redirect the long tests:

| Variable | Default | Used by |
|---|---|---|
| `PLATSIM_STRENGTH_N`, `PLATSIM_STRENGTH_WORKERS` | 2000, CPU count | `test_policy_strength.py` (T056) |
| `PLATSIM_EVALUATE_N`, `PLATSIM_EVALUATE_WORKERS` | 2000, CPU count | `test_evaluate.py` V7 |
| `PLATSIM_EVALUATE_FAST_N` | 40 | `test_evaluate.py` fast check |
| `PLATSIM_T072_N`, `PLATSIM_T072_FIXTURE`, `PLATSIM_T072_WORKERS` | 200, `reference_team.json`, CPU count | `test_final_levels.py` |
| `PLATSIM_OPTIMIZE_WORKERS` | CPU count (second run uses 7) | `test_optimize_small.py` (T058) |
| `PLATSIM_SCREENSHOT_DIR` | unset (no screenshots) | `tests/browser/test_page.py`: saves light, dark and 360 px screenshots |

For example: `PLATSIM_STRENGTH_N=160 uv run pytest -q -s tests/integration/test_policy_strength.py`.
pytest puts its temp files under `/dev/shm/platsim-pytest-<pid>` and removes them at exit.
