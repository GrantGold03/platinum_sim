# platsim: Pokemon Platinum Champion team optimizer

You give `platsim` six species. It looks for the build with the **lowest average team level after
beating Cynthia** that still clears the Elite Four plus Champion gauntlet reliably (default ≥ 75%) and
keeps the final level gap at 10 or less. It can also battle-test a team you already have, check its
legality, and trace any rule back to the game source.

The output is advice to a person: the moves, held items and abilities your six should carry, and
the levels they need, **assuming you play the battles competently** (constitution v1.5.0, Principle
VII): you know the League's teams, you switch when a matchup is bad, you take the free switch Shift
offers after a KO, and you do not misclick. The simulated player that finds those levels is a stand-in
for that player; it never reads the opponent's dice, and the report names which player policy
produced every number. Your Pokemon are assumed to be **average ones, not bred or trained**: a neutral
nature, IVs of 15 in every stat (the middle of 0 to 31), EVs of 85 in every stat (the full 510 spread
evenly, as ordinary play does), and maximum friendship. A team with better natures or IVs needs
slightly lower levels than the tool reports; a careless player needs higher ones.

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
- **The player is a stand-in for a competent human** (constitution v1.5.0, Principle VII). What it
  does well: it knows the League's parties, moves and items as the game stores them and the visible
  battle state; it looks two turns ahead, choosing moves and switches on expected damage with the
  game's own trainer AI sampled for the opponent's replies; it takes the Shift free switch after a KO
  when a bench member is better placed. What it does not model: payoffs past two turns (weather,
  Wish, Taunt, Substitute setups), Hidden Power, Magnitude and the other moves listed under feature
  024, and the opponent's random draws (it never reads them; a human cannot either). A change to its
  strength is a change to the levels the tool reports, which is why such changes are made
  reference-first with the level cost stated. **The policy is `expectimax2-v4`** (the default everywhere since
  2026-11-03, feature 018): `expectimax2-v2`'s model, leaf and horizon with a smaller search budget (4 root
  samples instead of 8, 1 second-ply sample instead of 2, first-ply branches below weight 0.05 valued by the
  leaf), 1.64x faster single process. It was validated reference-first against v2 on 2,000 paired runs per team
  on four fixed teams (no statistically supported drop at 0.80 to 0.95 clear rate) and adopted on that gate; a
  follow-up check near the 0.75 qualification threshold found v4 about 2 to 3 points weaker (p 0.006 on 2,000
  pairs, p 0.007 on 4,000), which cost one start level on five of six members in a quick B2 optimization, so
  for the lowest possible levels name `--player-policy expectimax2-v2` (the reference, still registered).
  Details and every number: `specs/018-expectimax2-v4/validation-log.md`. v2 (the default from 2026-10-08)
  replaced `expectimax2-v1`, which lost to `greedy-v1` on some optimizer teams because
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
  - **Daily gifts are unlimited, with one exception** (011). The Route 221 house gives Black Belt,
    Expert Belt and Focus Sash in rotation, but only when a party Pokémon is at that day's random
    level, so each counts as **1 copy** (user decision). The Pastoria City house gives one of 17
    resist berries a day, and Amity Square's walking partner and Gift Man give 9 berries. NPC gifts
    whose item is set in a called routine, picked at random, or read from a table are all counted.
  - **Munchlax and Snorlax are allowed** (003; this reverses 001's exclusion). Munchlax comes from
    honey trees at levels 5–15 (only some trees, depending on Trainer ID) and always holds
    **Leftovers**. So Leftovers may be held by any number of members **only when Munchlax or
    Snorlax is on the team**. With post-game items allowed, the Victory Road item ball adds one copy
    for any team.
  - **Held items the optimizer offers** (per moveset; each limited copy goes to one member): the best
    HP-restoring berry, the type-boost item for the strongest attack's type, Leftovers (when allowed),
    Expert Belt, and Wise Glasses or Muscle Band to match the strongest attack's category (014; Expert Belt and
    Wise Glasses have 1 copy each, Muscle Band none); then **Wide Lens** (accuracy x1.1, unlimited copies) for a set
    with an attack that can miss and **Razor Claw** (+1 critical-hit stage, 2 copies; Weavile's evolution uses one)
    for any set with an attack (025; Scope Lens has no pre-Champion copy). Items are picked by hold effect from the decomp. A held
    item the battle uses up when it triggers is never offered unless it is a berry (013; today Focus Sash,
    White Herb, Mental Herb, Power Herb, Berry Juice).
  - **Candidate move sets** (026): each member's ten-move pool is built by marginal coverage (each next move is the one
    that is the best answer to the most League opponents the pool does not yet answer, cost-free moves first), and a set's
    dead moves (never the best choice given the set's other moves) are replaced by live ones where the member learns any;
    a filler stays only when nothing live is left (Staraptor's fourth slot beside Return, Close Combat and Aerial Ace) and
    the report names it. Single-copy TMs and items wanted by several members go to the member whose coverage gains the
    most, and the others' sets are built without them, so every offered set can be taught on that team.
  - **TMs are single-use.** Each TM has as many copies as the game gives before the Champion. Shop
    and Game Corner TMs are unlimited.
  - **No bag items in battle.** Only held items have an effect. Between battles the team is healed
    (HP, status, faints). PP carries over, except that Leppa Berries can be farmed.
  - Every member has **IV 15, EV 85 in each stat, a neutral nature (Hardy) and maximum friendship**:
    the average Pokemon a player has, not a bred or trained one (constitution v1.5.0). NPC trades and
    gifts use the values the game fixes for them. Every report states these assumptions in its provenance
    (`member_defaults`, with the members the game fixes differently; 025). **No PP Ups**: every move has base PP, on both sides.
  - Level-up moves are **auto-learned as in the game** when a member has fewer than 4 moves.
    Otherwise the prompt is declined. Evolution is always declined.
  - Abilities: when there are two, both are tested and the better one is kept. A tie keeps the
    first. An ability the battle code never checks (Stench, Illuminate) is not tested.
- A draw or a hit on the 1,000-turn limit counts as a loss.
- **Required HMs** (006, none by default). Each required HM must be in some team member's
  **final** four-move set, the one used against Cynthia.
  - **Where to set it:** step 3 on the web page, or `--require-hm surf` (repeatable) on
    `optimize`, `evaluate` and `validate`.
  - **How the optimizer handles it:** it places each missing HM on the member that loses least,
    by replacing that member's weakest attack. A boost move is replaced only as a last resort. The
    battles are then run with that real moveset.
  - **Refusals:** if none of the six can learn a required HM under the active rules, the run is
    refused before any battle, naming the HM.
  - **Checks and records:** the validator checks it on its own (`REQUIRED_HM_MISSING`). Reports
    record `required_hms` when it is set.
  - **Which HMs the story needs:** see `hm_requirements.md`. Surf and Waterfall are needed to
    reach the League.

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
| `validate TEAM` | Legality check only (TEAM is JSON or a Showdown export) | `--json`, the five `--allow-...` rule flags (see Ground rules), `--require-hm` |
| `evaluate TEAM` | Battle-tests a fixed team over the full gauntlet | `--runs` (min, default 2000), `--seed` (default `0`), `--workers` (default: CPU count), `--player-policy` (default `expectimax2-v4`; `expectimax2-v2` is the reference), `--budget {quick,standard,thorough}`, `--min-clear` (default 0.75), `--max-runs` (default 20000), `--out` (default `runs/evaluate-<time>-<hash>/`), the five `--allow-...` rule flags, `--require-hm`, `--sampling {full,adaptive}` (default `adaptive` since feature 021 on the user's decision; `full` is the reference), `--floor` (adaptive only, default 0.98), `--battle-style {set,shift}` (feature 023: `shift`, the game's default, a free switch after a KO, is the default since 2026-11-04; `set` is the reference) |
| `explain SUBJECT` | Traces a fact to the decomp | `tmNN`, `hmNN`, `species:<key>`, `item:<key>`, `move:<key>`, `trainer:<key>`, `divergence:<id>`; `--json`, `--level` (`move:` only, default 100) |
| `serve` | Local web UI and HTTP API on 127.0.0.1 | `--port` (default 8000), `--runs-dir` (default `runs/`) |
| `optimize S1 … S6` | Finds the lowest-level qualifying build for six species and writes the same four reports plus a resumable `state.json` | `--min-clear` (default 0.75), `--seed` (default `default`), `--workers` (default: CPU count; never changes results), `--budget {quick,standard,thorough}` (default `standard`), `--player-policy` (default `expectimax2-v4`; the strong player for the level search, setup check and confirmation, feature 018; the screening stages keep `greedy-v1`), `--out` (default `runs/optimize-<hash of the request>/`; rerunning resumes), `--force-new`, the five `--allow-...` rule flags, `--require-hm`, `--sampling {full,adaptive}` (the confirmation stage's sampling, feature 022; default `full`), `--floor` (adaptive only, default 0.98), `--battle-style {set,shift}` (every stage's battles, feature 023; default `shift` since 2026-11-04, `set` is the reference) |
| `bench` | Times the battle player on the fixed 40-gauntlet seed set, single process and worker pool, and checks both halves ran the same battles (feature 015; `node sim/bench.mjs` alone gives the single-process figures and records the replay fixture; since feature 017 the single-process half also reports the trainer-AI interpreter step count) | `--policy` (default `expectimax2-v4`), `--n` (default 20 per team), `--block` (default `a`), `--teams` (default `bench,ref`), `--trainers`, `--workers` (default: CPU count), `--no-single`, `--json` |
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

The same command under today's defaults (2026-11-04: player `expectimax2-v4` since 018, adaptive sampling at floor
0.98 since 021, Shift battle style since 023; `runs/readme-shift/ref-2000`, 10:20:59 to 10:22:46 PM EST, alone):

```console
$ uv run platsim evaluate tests/fixtures/reference_team.json --runs 2000 --seed fixed --workers 16
platsim evaluate [adaptive]: Elite Four proven after 189 full runs (floor 0.98); 189 banked states; 67 results past the switch discarded
platsim evaluate: full runs: 189 in 62.9s; cleared 182/189; Cynthia-only runs 1811 (won 1761); Cynthia top-up ...
runs 2000  player expectimax2-v4  opponent decomp-ai  budget standard  sampling adaptive  style shift
adaptive sampling: full 189 / Cynthia-only 1811 runs, switch at 189, banked states 189, floor 0.98; statistic composite (delta interval)
gauntlet clear rate 0.9715  95% CI [0.9642, 0.9788]  half-width 0.0073
Cynthia P(win | reached) 0.9715  [0.9633, 0.9779]  battles 2000
expected final levels 60.82 / 60.84 / 60.02 / 60.05 / 60.37 / 60.00  avg 60.35  gap max 2.0
threshold 0.75  qualified True  borderline False
  loss cause: cynthia garchomp 26
  loss cause: cynthia milotic 18                                                          # exit 0, 107 s wall
```

The clear rate rises from 0.9445 to 0.9715 (the free switch before each of Cynthia's Pokemon; feature 023's acceptance
measured 0.951 to 0.974 on this team with full gauntlets) and the wall time falls from 769 s to 107 s (adaptive sampling
and the cheaper player). The optimizer headline below is still the 2026-10-08 Set result with `expectimax2-v2`; it has
not been rerun under today's defaults (hours of pool time).

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
      warnings and platsim version (0.3.0 since feature 004; older runs show the version they recorded);
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
| `expectimax2-v2` (the reference player; `expectimax2-v4` is the default since feature 018) | **2.1–2.8 gauntlets/s** on 16 workers: 2.62 (T056 benchmark team), 2.82 (reference team), 2.34–2.61 (T076 optimizer confirmation), 2.14–2.25 (`runs/final-defaults` confirmation); 2.74 on 8 workers |
| `expectimax2-v1` | 1.79 gauntlets/s (T056 benchmark team, 16 workers) |
| `greedy-v1` | 55.8 gauntlets/s (T056 benchmark team, 16 workers) |
| Bare engine | 59 gauntlets/s ceiling (T008 spike, no AI or policy) |

Feature 015 (2026-10-31, `uv run platsim bench`, the fixed set of 40 gauntlets: 20 x benchmark team + 20 x
reference team, seeds `prof-a-*`, all five trainers, decisions byte-identical before and after):

| Setup | `main` c751fb2 | after 015 | ratio |
|---|---|---|---|
| `expectimax2-v2`, single process | 0.386 gauntlets/s, 34.2 ms/decision | 0.779 gauntlets/s, 16.6 ms/decision | 2.02x |
| `expectimax2-v2`, 16 workers (40 jobs, tail-bound) | 1.91 gauntlets/s (20.9 s) | 3.22 gauntlets/s (12.4 s) | 1.68x |
| `expectimax2-v1`, single process | 0.273 gauntlets/s | 0.523 gauntlets/s | 1.92x |

Feature 015 changed `sim/`, so `sim_code_hash` changed: optimizer checkpoints (`state.json`) written before it do
not resume; rerun with `--force-new` or a new `--out`. Details: `specs/015-exact-ai-speedups/validation-log.md`.

Feature 016 (2026-11-01, same fixed set and tool, decisions byte-identical; `main` re-measured the same day):

| Setup | `main` 19519ed (after 015) | after 016 | ratio |
|---|---|---|---|
| `expectimax2-v2`, single process | 0.725 gauntlets/s, 17.8 ms/decision | 1.049 gauntlets/s, 12.0 ms/decision | 1.45x |
| `expectimax2-v2`, 16 workers (40 jobs, tail-bound) | 2.91 gauntlets/s (13.7 s) | 3.99 gauntlets/s (10.0 s) | 1.37x |
| `expectimax2-v1`, single process | 0.475 gauntlets/s | 0.706 gauntlets/s | 1.49x |

Feature 016 changed `sim/` again (`sim_code_hash`), with the same consequence for earlier checkpoints. Its three
changes (type-chart plan replayed per damage roll, the trainer AI's pre-variance damage memoised per decision,
shared id mappers) are checked by a randomized equivalence test and the replay test; `PLATSIM_AI_CHECK=1` makes the
AI recompute every memoised value and fail on a difference (`sim/ai/INTERFACE.md`). Details:
`specs/016-exact-damage-speedups/validation-log.md`.

Feature 017 (2026-11-02, same fixed set and tool, decisions byte-identical; `main` re-measured in the same session):

| Setup | `main` f6d845c (after 016) | after 017 | ratio |
|---|---|---|---|
| `expectimax2-v2`, single process | 1.014 gauntlets/s, 12.4 ms/decision | 1.244 gauntlets/s, 9.8 ms/decision | 1.23x |
| `expectimax2-v2`, 16 workers (40 jobs, tail-bound) | 4.07 gauntlets/s (9.8 s) | 4.55 gauntlets/s (8.8 s) | 1.12x |
| `expectimax2-v1`, single process | 0.700 gauntlets/s | 0.856 gauntlets/s | 1.22x |
| Trainer-AI script instructions per run (v2) | 143.0 M | 15.9 M | 9.0x fewer |

Feature 017 changed `sim/` again (`sim_code_hash`), with the same consequence for earlier checkpoints. Its three
changes (runs of consecutive effect checks in the trainer-AI script answered by a parse-time table, the player's
damage inputs taken from the trainer AI's per-decision memo instead of rebuilt from the live battle, one speed
comparison per hypothetical state shared by the player and the trainer AI) are checked by an exhaustive dispatch
equivalence test (every table x every effect value), a speed-pair equivalence test over 1,000 real views against the
kept reference, the replay test, and `PLATSIM_AI_CHECK=1`, which now also recomputes the shared battler and field
structs and the speed pair. `node sim/bench.mjs` and `platsim bench` report the interpreter step count
(`interp_steps`, `interp_dispatches`). Details: `specs/017-exact-dispatch-speedups/validation-log.md`.

Feature 018 (2026-11-02/03, same fixed set and tool): a NEW policy, `expectimax2-v4`, with a smaller search budget; its
decisions differ from v2's by design, so the comparison is paired (same seeds and opponents) and reference-first:

| Setup, same 40 gauntlets, same session | `expectimax2-v2` | `expectimax2-v4` | ratio |
|---|---|---|---|
| single process | 1.279 gauntlets/s, 9.6 ms/decision, 44.7 AI calls/decision | 2.097 gauntlets/s, 5.3 ms/decision, 17.8 AI calls/decision | 1.64x |
| 16 workers (40 jobs, tail-bound) | 4.85 gauntlets/s (8.3 s) | 6.56 gauntlets/s (6.1 s) | 1.35x |
| B2 `optimize --budget quick` end to end (16 workers) | 407 s | 350 s | 0.86 |

Validation (`specs/018-expectimax2-v4/validation-log.md`): each budget knob alone and then the combination, 2,000
paired gauntlets against v2 on four fixed teams (the two policy fixtures and the two feature-014 B2 results), McNemar
exact at alpha 0.05, with a pairing control. Switch beam 1 was worse on one team and was dropped; the adopted set (root
samples 4, second-ply samples 1, floor 0.05) showed no statistically supported drop on any team (deficits 0.3 to 1.05
points, p 0.33 to 0.71). A follow-up check at the qualification threshold (the v2 B2 team at its own levels, clear rate
near 0.79) found v4 weaker by 2 to 3 points with p 0.006, pooled p 0.007 over 4,000 pairs, and the quick B2
optimization with v4 settled one start level higher on five of six members (expected average final level 54.30 vs
53.34; the same species, moves and items). v4 was adopted as the default on the user's decision, with this cost on
record; `--player-policy expectimax2-v2` gives the reference player wherever a policy can be named. v4 has its own
replay-fixture entry (`node sim/bench.mjs --policy expectimax2-v4` prints `digest_full 05fa8cb1…`), is deterministic per
seed, and beats `greedy-v1` on the benchmark team (p 2.7e-70 at 400 paired). v1 and v2 are byte-identical to before.
`platsim optimize` gained `--player-policy`; a checkpoint made with another strong player is never resumed.

Feature 019 (2026-11-03, `specs/019-e4-sampling-spike/`, measurement only, no behaviour change): a spike on adaptive Elite Four
sampling (run full gauntlets until every Elite Four member's pass rate is proven, then Cynthia-only battles from banked post-Lucian
states, clear rate = Elite Four pass rate x Cynthia's conditional rate). Measured on the pool with stop-on-loss: the Elite Four
is 72 to 75% of battle time; on the reference team the rule would make 81 to 91% of a 2,000-run evaluation Cynthia-only (floors 0.99
and 0.98) with the verdict unchanged, a projected 1.9 to 2.9x; on a Lucian-heavy team it never switches. The composite estimate
matches the ten stored evaluations, but the conservative product interval chosen for the spike turns four threshold teams borderline,
so the follow-on waits on a decision about the interval (details: the feature's validation log and FUTURE-FEATURES section 8).

Feature 020 (2026-11-03, `specs/020-lead-spike/`, measurement only, no behaviour change): a spike on choosing the lead (the
first party slot). Six leads × 2,000 paired gauntlets on three optimizer-built teams: the six fixed leads span 8.7 to 10.2 points of
clear rate, almost all at Cynthia. The best lead chosen on the first 1,000 pairs and tested on the second 1,000 beat the first-listed
lead on no team with statistical support (b2main +2.0 points, p 0.12; on the other two the first-listed Garchomp was already best), so
the optimizer gets no lead search for now; naming the lead in every output is the follow-on that stands. Today the lead is the first
species listed in the optimize request.

Feature 021 (2026-11-03, `specs/021-adaptive-e4-sampling/`): **adaptive Elite Four sampling** in `platsim evaluate`, the
default since the user's decision after its acceptance (`--sampling full` gives the reference). Full gauntlets run in request-seed order until every Elite Four member's Wilson 95% lower bound reaches
`--floor` (default 0.98; 0.99 was the spike's assumption and switches only on the strongest teams); every full run that reaches Cynthia banks her starting state; the remaining runs are Cynthia-only
battles from banked states, drawn deterministically with reserved seed index 98 (the top-up keeps 99). The clear rate is then the
Elite Four pass rate times Cynthia's conditional win rate over all her battles, with a log-scale delta-method 95% interval, and
the threshold, half-width and borderline rules apply to that interval; when the floor is never reached every run is full and the
report keeps the full method's statistics. Results computed past the switch are discarded so result.json is independent of
worker count and batch size (the discard counts are logged, not written to result.json, because they depend on the chunk size). Reports carry `sampling` and `sampling_detail` (full and
Cynthia-only runs, switch run, banked states, the Elite Four pass rate and both intervals); per-trainer rates come from the
full runs; loss causes include Cynthia-only losses. `--sampling full` is the reference; the user chose adaptive at floor 0.98 as the default on the acceptance below. Acceptance (paired on
the same seeds, 2,000 runs, standard budget, `specs/021-adaptive-e4-sampling/validation-log.md` T017): on all five legal
acceptance teams the adaptive estimate lies inside the full run's interval and the verdict agrees; the reference team ran 1.94x
faster at floor 0.99 (switch after 563 full runs); the B2 teams do not reach 0.99 (Lucian about 0.99 on them) and ran 1.70 to
2.06x faster at floor 0.98; bench-010 B3 never switches and costs nothing. The policy benchmark fixture cannot be evaluated this
way (placeholder sources). The optimizer's stages keep full gauntlets.

Feature 022 (2026-11-04, `specs/022-confirm-adaptive-sampling/`): the optimizer's **confirmation stage** can use the same adaptive
sampling (`optimize --sampling adaptive`, `--floor`; default `full`), including the borderline extension by the 021 rule; the level
search and the setup check keep full gauntlets. The runner-up comparison stays paired by runs that share a seed: full runs by run
index below both switch runs, Cynthia-only runs by their ordinal, the surplus excluded and counted (`optimizer/pairing.py`); a better
runner-up is confirmed from its own runs. state.json's confirm attempts record the run mix and provenance names the sampling per
stage. Acceptance (`specs/022-confirm-adaptive-sampling/validation-log.md` T017): the confirmation alone at the standard count was
2.33x faster on the 014 b2-main team with the same verdict and containment, and 1.00x on bench-010 B3 (the floor is never reached;
both sides extended to 4,000 runs); the pairing control reproduced the full method's McNemar counts exactly on the full-kind pairs;
a run killed during the confirmation and resumed gives byte-identical result.json (the provenance's stage records are now written
in canonical key order, which also fixes a pre-existing key-order difference after any resume). The B2 quick end-to-end comparison
failed the clarified containment rule by 0.002: at the quick count of 500 runs the full method's first attempt was borderline and
bumped a level while the adaptive attempt passed one level lower, the same team at equal levels (0 discordant pairs). The user kept
`full` as the optimizer's default (2026-11-04); adaptive is available with `--sampling adaptive`.

Feature 023 (2026-11-04, `specs/023-shift-battle-style/`): the **Shift battle style**, the game's default, as
`--battle-style {set,shift}` on `evaluate` and `optimize`; **the user chose `shift` as the default on the acceptance
below (2026-11-04)**; `set` (Showdown's behaviour) stays the reference. Game rule (decomp `battle_controller_player.c:4144-4160`): after a turn in which the trainer's active Pokemon
fainted and the player's did not, in a single battle with a usable replacement on the player's side, the trainer's next
Pokemon (chosen by the trainer AI before the prompt, against the player's current active) is named and the player may
switch for free before it enters; the switch is a normal switch (stat stages reset, no Pursuit) and no move is used before
the next command selection. The worker drives it through the engine's own switch flag and instant-switch path (no edit to
the vendored tree); the player policies answer with their existing scoring (expectimax2 values stay against each bench
switch with the announced foe on the field; greedy compares its member scores); the trainer AI is unchanged. Under `set`
nothing changes (the replay fixtures and every stored result are byte-identical); under `shift` the style is echoed in the
result, named in the summary, provenance, xlsx and web view, and in the optimizer's fingerprint when non-default. Two ledger
entries: `mech-shift-prompt` (corrected) and `mech-shift-entry-order` (accepted: the engine orders the two entries and their
entry effects by speed, the game puts the player first and runs abilities by category). Acceptance
(`specs/023-shift-battle-style/validation-log.md` T020; 2,000 paired gauntlets per team, v4, same seeds; control 0 discordant):

| team | Set clear rate [95% CI] | Shift clear rate [95% CI] | only Shift / only Set | p (exact) | Cynthia Set -> Shift | Lucian Set -> Shift | offers / gauntlet | switch share | prompted battles won | wall Shift/Set |
|---|---|---|---|---|---|---|---|---|---|---|
| ref | 0.9510 [0.9406, 0.9596] | 0.9740 [0.9661, 0.9801] | 93 / 47 | 0.000126 | 0.952 -> 0.975 | 1.000 -> 1.000 | 20.9 | 0.69 | 9944/9995 | 1.04x |
| b2main | 0.9120 [0.8988, 0.9236] | 0.9870 [0.9810, 0.9911] | 170 / 20 | 7.91e-31 | 0.921 -> 0.989 | 0.993 -> 0.999 | 21.3 | 0.64 | 9971/9997 | 1.07x |
| b2branch | 0.7755 [0.7567, 0.7932] | 0.9785 [0.9712, 0.9840] | 433 / 27 | 2.37e-95 | 0.782 -> 0.980 | 0.995 -> 1.000 | 21.0 | 0.63 | 9952/9995 | 0.96x |
| b3 | 0.7605 [0.7413, 0.7787] | 0.9850 [0.9787, 0.9895] | 471 / 22 | 7.93e-111 | 0.859 -> 0.987 | 0.886 -> 0.999 | 21.0 | 0.66 | 9967/9997 | 0.91x |

B2 quick (`--seed 014-b2`, 16 workers): Set winner levels [54, 52, 54, 54, 54, 55] clear 0.8860 [0.8552, 0.911] (n 500, 2 confirm attempts, wall 407 s); Shift winner levels [51, 52, 52, 53, 52, 53] clear 0.9300 [0.9042, 0.9492] (n 500, 2 attempts, wall 416 s); same species, moves and items; expected average final level 54.30 (Set) vs 52.79 (Shift).

Feature 024 (2026-11-09, `specs/024-variable-power-moves/`): the optimizer **offers four variable-power moves**: Return,
Grass Knot, Low Kick and Gyro Ball, whose data power is 1 because the game computes it at use. One shared helper in the
battle code (`sim/variable_power.mjs`, mirrored by `src/platsim/decomp/weights.py`) holds the game's formulas from the
decomp: Return `friendship*10/25` (the simulator assumes maximum friendship, 255, as the legality layer does, so 102);
Grass Knot and Low Kick from the target's weight tier (100 hg: 20, 250: 40, 500: 60, 1000: 80, 2000: 100, heavier: 120;
the first limit at or above the weight, so a weight exactly on a limit takes the lower tier); Gyro Ball `1 + 25 *
target speed / user speed`, capped at 150. The strong player's lookahead and the trainer-AI port already used these
formulas and now call the helper; the screening player greedy-v1 scores the four moves through it (Gyro Ball from the
two Pokemon's speed stats at their levels, not the in-battle speed value: an approximation of the screening heuristic).
Candidate generation scores them per League opponent (Gyro Ball from the member's speed at the candidate level against
each opponent's at its level) and offers them in **extra candidate sets appended after today's sets**, so every set the
optimizer offered before is still offered first and unchanged; the archived 010 attempt had let such sets displace a
member's coverage set and lost about ten points on the B2 team. **Not offered**, with the reason: Hidden Power (IVs are a
uniform 15 by assumption, so its type and power would be fixed by that); Frustration (power 1 at friendship 255);
Magnitude, Wring Out, Crush Grip, Punishment, Flail, Reversal, Fling, Trump Card, Natural Gift, Present, Spit Up (no
player computes their power yet); fixed-damage, OHKO and counter moves (not attacks for candidate scoring). Eruption and
Water Spout keep their data power 150. Ledger: `mech-weight-tier-boundary` (accepted): the engine's Low Kick and Grass
Knot break at weight >= limit, so Flint's Flareon (exactly 250 hg) is 40 in the game and 60 in the engine; the player's
model and the optimizer follow the game. Checkpoints from before this feature do not resume (code hashes changed).
**Acceptance (`specs/024-variable-power-moves/validation-log.md` T017 to T023, 2026-11-09).** The first run failed its
gate: the branch's B2 quick winner (a Staraptor with Return) lost to today's at equal levels (0.778 vs 0.823, p 2e-4) although
today's candidate sets were untouched, because appending options had changed the screen's random sample under its 81-team cap
(only 43 of 81 teams shared; today's winner never screened). The user chose the **screen superset**: the screen's capped list is
built from today's options only, so its first 81 teams are exactly today's, and the extra sets ride beyond the cap as single-slot
deviations (14 teams on B2 quick, about 7% more screening). On the rerun the first 81 screened teams are identical to today's, the
winner is **the same team, moves, items and levels** as today's (0 discordant pairs at equal levels), and the two unaffected teams
evaluate identically on both codes: on this team the four moves are offered and not chosen. Recorded results are unchanged.

Feature 025 (2026-11-13, `specs/025-h4-wide-lens-razor-claw/`, the first H4 held-item group): the optimizer **offers Wide
Lens and Razor Claw**, chosen by hold effect (`HOLD_EFFECT_ACCURACY_UP`, `HOLD_EFFECT_CRITRATE_UP`) with a pre-Champion copy
(Wide Lens unlimited; Razor Claw 2, one of which Weavile's evolution consumes; Scope Lens 0, so never offered). The battle
player already modelled both (hit chance x1.1; +1 crit stage). Three changes to candidate generation, all additive to the
item lists but not to the move lists: (1) **every move's value carries a critical-hit term**, 1 + P(crit) from the game's stage
table (`battle_lib.c` `sCriticalStageRates`: 1/16, 1/8, 1/4, 1/3, 1/2; a crit doubles damage), so a high-crit move (Stone Edge,
Slash, Night Slash, Shadow Claw) is worth 1/16 more than its power alone said and some sets re-rank; (2) **choosing an item
re-evaluates the member's moves under it**: for the lens the attacks are re-valued with accuracy x1.1 (capped at 100), so
Fire Blast's penalty against Flamethrower shrinks, for the claw with the extra crit stage; a pool and four-move sets are
ranked under that valuation exactly as today's are, and up to three sets that differ from today's are appended per item as
item-conditioned extra sets, each paired with its item (the sets are the next-best under the item, so one may contain no
move the item affects); (3) the **dominance rule that drops strictly worse moves is widened** from "same type, category,
accuracy, priority, more power, plain loser" to: same type and category, at least as good on power, accuracy, priority, PP
and effect, strictly better on one, where the effect axis has a cost class (charge and recharge turns, recoil, self stat
drops, lock-ins, crash damage, Explosion and the like: a move with a cost loses the axis to one without; two different
secondary effects are incomparable). On the benchmark teams this drops Dig under Earthquake, Dive under Waterfall and Take Down
under Rock Climb (the three pairs the dominance assessment found) and keeps Fire Blast vs Flamethrower, Close Combat vs
Brick Break and Thunderbolt vs Discharge; because PP is an axis, Cut no longer drops Tackle. A self stat drop is a cost by
the user's decision and lasts only until the member switches; the player's model resets every stage on a switch (pinned by
`sim/test/switch_reset.test.mjs`). The screen's capped list is built from today's base options; every appended option (the
024 variable-power sets, the item-conditioned sets, and each base set with Wide Lens or Razor Claw) is screened beyond the cap
as a single-slot deviation of the baseline, counted by kind in the screen stage (`extras_screened`). Every report's provenance
gains `member_defaults` (the average-Pokemon assumptions). Checkpoints from before this feature do not resume.
**Acceptance (`specs/025-h4-wide-lens-razor-claw/validation-log.md` T019 to T021, 2026-11-13).** B2 quick on both codes: the
same six species; no member holds Wide Lens or Razor Claw (offered, screened as 89 extra teams beyond the 81-team cap, not
chosen); the branch winner differs on three members by the crit term's re-rank and is better at equal levels (0.923 vs 0.886
on 2,000 paired gauntlets, p 6e-5) at the same expected average final level (52.79); the two unaffected teams evaluate
identically on both codes; every difference between the pre-feature candidate lists and the branch's over 36 benchmark members
is attributed to a dominated move, the crit term or an appended set or item (0 unexplained). The first run's 10 "defect" lines
were a gap in the attribution helper (a set the crit term re-ranked out and the item valuation re-added), fixed and rerun with
identical measurements.

Feature 026 (2026-11-13, `specs/026-marginal-coverage-sets/`): **candidate sets by marginal coverage, no dead fourth move,
and the team's TMs allocated.** Found reviewing 025's B2 winner: Infernape carried Fire Blast / Flamethrower / Close Combat /
Fire Punch, where Flamethrower and Fire Punch are dead (never the best choice against any League opponent once the other
moves are there), because the pool was the ten highest standalone scores (five redundant Fire and Fighting moves) and
coverage ties broke on the score sum. Now (1) the **pool is built greedily by marginal coverage**: the first move by score,
each next the one adding the most coverage, over every legal attack and the offered variable-power moves, so Grass Knot and
Brick Break enter where they answer someone; the rest of the pool fills by score. (2) **Dead moves are replaced** by the legal
move adding the most coverage; a filler stays only when nothing live is left, and the player-facing report (team text,
summary, the spreadsheet's Evaluation sheet) says so per member ("Rotom: Thunder, Ominous Wind are filler: no better
option: its two strongest moves cover every League opponent"). Sets differ pairwise by two moves as before; a one-apart
all-live set is offered only where the two-apart set would carry a dead move. (3) **Cost moves** (the 025 cost class) enter
in two tiers: a charge-turn, recharge or lock-in move (Fly, Solar Beam, Giga Impact) only for an opponent no cost-free move
hits at all; a recoil or self-stat-drop move (Close Combat, Overheat, Brave Bird) when it answers an opponent no cost-free
candidate answers. (4) **Contested single-copy resources** are allocated across the team: a TM wanted by more first sets than
it has copies goes to the member whose coverage gains the most from it (on B2, Earthquake and Stone Edge stay with Garchomp;
Brick Break and Aerial Ace go to Weavile), the others' lists are rebuilt without it, and a resource with no copy left after the
first sets is withheld from the other members' later sets, so every offered set is buildable beside the others' first sets and
the repair step has nothing to replace at the baseline. The result on the six B2 species: Infernape offers Fire Blast / Close
Combat / Earthquake / Grass Knot and two more all-live sets member by member (on the B2 team, without the TMs Garchomp holds,
Fire Blast / Flamethrower / Close Combat / Grass Knot with Flamethrower named as the filler); Garchomp and Rotom unchanged;
Staraptor takes Return (its same-type 102-power move) with Fly and Giga Impact kept out; Floatzel and Weavile gain Brick Break.
Dead moves in offered base sets over the 36 benchmark members: 92 before, 0 after outside the 9 members listed with a reason.
Candidate generation for six members: 0.9 s before, 1.2 s after, 4.8 s with the allocation. Checkpoints from before this
feature do not resume.
**Acceptance (`specs/026-marginal-coverage-sets/validation-log.md` T016 to T017, 2026-11-13).** B2 quick on both codes: the
branch's winner starts two levels lower on average ([52, 50, 50, 50, 51, 53] against [51, 52, 52, 52, 53, 53]) with a higher
clear rate (0.944 against 0.938), an expected average final level of 51.69 against 52.79, and at the lower levels beats today's
team 0.9485 to 0.7555 on 2,000 paired gauntlets (p 5e-66); the two unaffected teams evaluate identically on both codes; every
list difference over 36 benchmark members is attributed (0 unexplained); no offered set needed repair on the B2 team. The
first run failed its own gate only because the script did not strip the new report field; fixed and rerun with identical
measurements.

Measured run times:

| Run | Wall time |
|---|---|
| `evaluate` reference team, 2,000 runs, standard | 769 s on 16 workers, 790 s on 8 |
| `evaluate` reference team, 2,000 runs, standard, today's defaults (v4, adaptive 0.98, Shift; 2026-11-04) | 107 s on 16 workers |
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

- **Battle style is Shift by default since 2026-11-04 (feature 023).** Platinum's default is Shift (after the
  trainer's Pokemon faints and yours does not, the trainer's next Pokemon is named and you may switch for free before
  it enters). `--battle-style set` keeps Showdown's behaviour as the reference; every result made before 2026-11-04
  (the README's headline numbers included) was made under Set and reads lower than the game's rule allows. Under
  Shift the order of the two entries and their entry effects follows the engine (speed order), an accepted ledger
  divergence (`mech-shift-entry-order`).
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
  policy/             greedy-v1, expectimax2-v1, expectimax2-v2 (the reference), expectimax2-v4 (default since 018)
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
uv run pytest -q -m "not battle_sim"                       # fast mode: every test that does not start the battle worker
uv run pytest -q -m battle_sim                             # only the tests that start the battle worker
uv run pytest -q -m browser tests/browser/                 # web page in the system Chrome (about 1 min)
uv run pytest -q --ignore=tests/integration/test_policy_strength.py -k "not v7"   # skips the two long ones
(cd sim && node --test test/*.test.mjs)                    # Node suites (372 tests, about 3 min)
uv run pytest -q --durations=25                            # full suite with the 25 slowest tests listed (the merge gate)
```

The full pytest run includes long tests: the policy-strength benchmark (2,000 paired gauntlets ×
3 policies, plus 400 × 2 on the reversal team), the V7 evaluate determinism check (2 × 2,000
gauntlets) and two `quick` optimizes.
- **Full pytest:** the last full run was on 2026-11-04 (feature 023 merge gate):
  `uv run pytest -q --durations=25` gave **614 passed, 4 xfailed in 4,936 s (1 h 22 min)** plus 2 unit tests whose fake pool
  did not echo the battle style, fixed (test file only) and rerun green; 616 tests in all. Earlier: 2026-11-03 (018 gate)
  561 passed in 55 min plus 2 tests that pinned the old default player name, fixed and rerun green. The same suite took 2 h 09 min on 2026-10-30
  before feature 015, 1 h 20 min after it, 1 h 05 min after 016 and 55 min after 017: the three slowest tests
  (`test_optimize_small.py` quick optimize 1,248 s, `test_policy_strength.py` paired benchmark 743 s with v4 at 2,000
  pairs, `test_evaluate.py` V7 401 s) all run the battle player. Do not commit during a full run: each process
  caches `repo_commit`, so a commit mid-run fails `test_web_process_determinism.py` (seen on 2026-10-26). The 4
  xfails are strict, documented story-rank controls. See `specs/018-expectimax2-v4/validation-log.md`
  (T037) and `specs/012-fast-test-mode/validation-log.md`.
- **Merge rule:** the full pytest suite (`uv run pytest -q`) and the Node suite both pass before every merge.
  The fast mode and the battle set are for iterating only; neither is enough for a merge.
- **Fast mode** (feature 012): `battle_sim` marks every test that starts the battle worker
  (`node sim/worker.mjs`), directly, through a fixture, or in a child process. The split is checked in every
  run: a stand-in `node` (`tests/node_shim/node`, put first on `PATH` by `tests/_battle_split.py`) logs each
  worker start, an unmarked test that starts the worker fails at its teardown, and an unmarked test using a
  fixture that started it, a start outside any test, or a marked test that never reached the worker fail the
  session. The "battle split" section at the end of each run lists the counts and each marked test's route.
  On 2026-11-04 the fast mode gave 583 passed, 30 deselected, 4 xfailed in 632 s (10.5 min; 535 on 2026-11-02, 528 before feature 018); its slowest test
  is `test_extract.py::test_extract_twice_identical_check_and_corruption` (220 s). The battle set is 28 tests
  (26 before features 015 and 016 added the bench tests).
- **Browser tests** need Google Chrome installed (`google-chrome` on `PATH`) and skip with a reason
  otherwise. Playwright drives it with `channel="chrome"`, so no Playwright browser download is needed.
- **Node suite:** on 2026-11-02 it gave **351 pass, 0 fail, exit 0 in about 2.5 min** (347 before feature 018, 334
  before 017, 314 before 015 and 016; the replay test now covers three policies, 120 gauntlets, 20-45 s on 16 worker
  threads). Known flake, not a regression:
  `sim/test/seeds.test.mjs` compares two raw battle logs including their `|t:|` timestamp lines and fails when
  the two battles straddle a second boundary (seen once on 2026-10-31; a rerun passes). With
  `PLATSIM_AI_FREEZE=1` the cached AI structs are frozen and `PLATSIM_AI_CHECK=1` recomputes every memoised AI
  value, including (since 017) the shared battler and field structs and the speed pair (`sim/ai/INTERFACE.md`); both
  runs are recorded in the 015/016/017 validation logs.

These environment variables shrink or redirect the long tests:

| Variable | Default | Used by |
|---|---|---|
| `PLATSIM_STRENGTH_N`, `PLATSIM_STRENGTH_WORKERS` | 2000, CPU count | `test_policy_strength.py` (T056) |
| `PLATSIM_REVERSAL_N` | 400 | `test_policy_strength.py` (reversal team) |
| `PLATSIM_EVALUATE_N`, `PLATSIM_EVALUATE_WORKERS` | 2000, CPU count | `test_evaluate.py` V7 |
| `PLATSIM_EVALUATE_FAST_N` | 40 | `test_evaluate.py` fast check |
| `PLATSIM_T072_N`, `PLATSIM_T072_FIXTURE`, `PLATSIM_T072_WORKERS` | 200, `reference_team.json`, CPU count | `test_final_levels.py` |
| `PLATSIM_OPTIMIZE_WORKERS` | CPU count (second run uses 7) | `test_optimize_small.py` (T058) |
| `PLATSIM_SCREENSHOT_DIR` | unset (no screenshots) | `tests/browser/test_page.py`: saves light, dark and 360 px screenshots |

For example: `PLATSIM_STRENGTH_N=160 uv run pytest -q -s tests/integration/test_policy_strength.py`.
pytest puts its temp files under `/dev/shm/platsim-pytest-<pid>` and removes them at exit.
