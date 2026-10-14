# RUN-STATE: Champion Team Optimizer

## Goal
Optimize six species for the lowest average level after beating Cynthia (first-run Elite Four +
Champion), clear rate ≥ 75% (user-settable), final level gap ≤ 10, pre-Champion single-cartridge
resources only. Spec: `specs/001-champion-team-optimizer/spec.md`.

## Method
- Python (`src/platsim`): decomp extraction, availability ledger, legality, optimizer, stats,
  reports, and the web UI.
- Node (`sim/`): Showdown in-process battles, plus a game layer (decomp trainer-AI interpreter,
  Full Restore, exp/level-up) and the `expectimax2-v1` player.
- Plan: `specs/001-champion-team-optimizer/plan.md`. Tasks: `.../tasks.md`.
- Validation evidence: `.../validation-log.md`.

## Done
- 2026-10-07: spec, plan, tasks, and analysis fixes committed (`4ed6c45`).
- 2026-10-07: Phase 1 setup (T001–T007). See validation-log.
- 2026-10-07: Phase 2a spikes T008–T010; **Checkpoint A reached**. Numbers are in research.md R5/R8.
- 2026-10-08: US2 (evaluate), US1 (optimizer + web; player fixed as expectimax2-v2), US3 (explain), Polish (README, quickstart V1–V9, constitution review).
- 2026-10-07: Phase 2 complete (T011–T057): decomp readers, availability ledger (no National Dex, per the user),
  legality validator, Showdown worker with decomp stats/PP/exp, the decomp trainer AI (default opponent), greedy-v1
  and expectimax2-v1 (52.0% vs 15.8%, p=3.6e-129), pool, Cynthia top-up, divergence ledger, report writers.

## Next
- **All 78 tasks are complete** (2026-10-08). The feature works end to end: extract, validate, evaluate, optimize, explain, serve.
- **Headline result** (2026-10-08, defaults: no egg moves, no trade evolutions): the six reference species qualify at
  average final level **58.23** (start 58/57/57/58/58/59, clear 0.8645). Output in `runs/final-defaults/`. The earlier
  56.10 used egg moves and the old TM counts and is superseded.
- **Optional follow-ups** (see validation-log T077):
  - two stale comments in `sim/` (`sim/policy/greedy.mjs:2` calls v1 the strong player; `sim/gauntlet.mjs:41` names only
    v1). Deliberately left alone: any `sim/` edit changes `sim_code_hash`, so fix them with the next real sim change;
  - with `--allow-trade-evolutions`, an NPC-trade pre-evolution (e.g. Gaspar's Haunter) is not offered as a source for
    the trade evolution (Gengar). Allowing it would need the Everstone removed and the NPC OT kept, so the traded-exp boost still applies;
  - `sim/` code hash in provenance;
  - fix the "? (unlimited)" item-source text;
  - optimize resume test;
  - cartridge or emulator comparison.

## Traps
- Battle mechanics also live in `res/battle/scripts/**/*.s` subscripts that compare RAW numbers (e.g. resist berries in `subscript_type_resist_berry.s`). Never conclude "not in the decomp" from a name-only grep.
- Showdown applies 3 PP Ups to every move (`sim/pokemon.ts:361`); T034 must reset PP.
- Showdown Taunt blocks the Full Restore pseudo-move; T047 must patch this.
- The session scratchpad disappeared mid-session; `/dev/shm` was used once for throughput output and
  was cleaned up.
- Showdown `npm ci` reports 37 audit vulnerabilities (server-side deps). The sim runs locally and
  offline; not acted on.
- Always pass `--skip-build` if `pokemon-showdown simulate-battle` is ever used; otherwise it
  rebuilds.
- Dex data must be patched before the first `Dex.*.get()` (results are cached).
- `pokeplatinum` has no build dir: read sources (`res/`, `generated/*.txt`), not headers.

# 002 Web UI redesign (started 2026-10-09)

## Goal
Redesign the `platsim serve` page with the specification in `specs/002-webui-redesign/spec.md`:
- run setup on the left and results on the right;
- a short summary, a per-trainer chart and sprite team cards;
- a run picker;
- progress with an ETA and Cancel.

Reports must stay byte-identical (FR-030).

## Method
The plan is `specs/002-webui-redesign/plan.md` and the task list is `tasks.md` (T001–T037).
Tests are written before the code. Each web job runs in a spawned child process with its own
process group, so Cancel can stop it and its Node workers within 10 s. Sprites come from the
decomp PNGs, with transparency added when they are served. The constitution was amended to v1.1.0
(Principle IV: report files vs. views).

## Done
- 2026-10-09: spec, plan and tasks written, plus 5 analyze passes (the last had no critical or high findings).
- 2026-10-09: T001: the `playwright` dev dependency and the `browser` marker were added.
- 2026-10-09: T002–T005 (Phase 1 and 2): baseline recorded (8 passed, report hashes in validation-log), fixture `tests/fixtures/web_final_defaults/` created, test helpers split, job state extended. The web tests still give 8 passed.
- 2026-10-09: US1 + US2 (T006–T019): result view, sprites, two-column page, budget, seed tooltip. 11 + 9 tests pass, and screenshots were checked at 1920 and 360 px.
- 2026-10-09: US3 (T020–T029): eta.py, job_process.py (spawn + setsid + parent-death guard), cancel endpoint, shutdown hook. Cancel, shutdown (SIGINT 0.2 s, SIGKILL 0.1 s) and child-vs-in-process determinism (byte-identical) all pass.

- 2026-10-09: US4 (T030–T031), browser walkthrough (T032), report hashes unchanged (T034).
- 2026-10-09: T033 full suite: 381 passed, 2 deselected in 2:27:51; browser 2 passed. FR/SC map in validation-log.
- 2026-10-09: T035 real quick jobs via `platsim serve`: cancel of a running job took 0.2 s with all 16 worker pids gone; job B (`runs/job-20261009T193751Z-1fdb5e`) is byte-identical to the CLI result.json (cmp exit 0). The status line was stale after a finish; fixed and covered by a new browser test (3 passed).
- 2026-10-10: /speckit-converge found 4 gaps, now fixed (T038–T041): control-name check, full "obtained from" text, ability-tie label for more than two abilities, empty-runs test. Browser 4 passed, web 21 passed.
- 2026-10-09: T036 README, T037. 002 is complete and committed on branch `002-webui-redesign`, not merged.

## 002 handoff (written 2026-10-10; resolved 2026-10-11: tested, then merged into main with 003)
- **State:** all 41 tasks (T001–T041) are done and committed on branch `002-webui-redesign`.
  - `c872971` is the redesign; `25b41b1` has the converge fixes; a later docs commit refreshes stale docs.
  - `main` is still at `f55e5d8`, so the branch is a fast-forward of main. There is no git
    remote, so nothing has been pushed.
- (Historical.) The user tested and gave the go-ahead; main was fast-forwarded on 2026-10-11 (see the 003 section).
- **To test:**
  - `git switch 002-webui-redesign`, then `uv run platsim serve`, then open http://127.0.0.1:8000.
  - The search returns 503 for about 35 s while the ledger builds.
  - Each web job adds about 35 s at its start (the child rebuilds the ledger).
  - Stop with Ctrl-C. Shutdown stops a running job and records it as failed ("server stopped while running").
- **Web jobs in `runs/`** (the picker lists only these; CLI runs like `final-defaults` are not listed):
  - `job-20261008T115114Z-feb186`: the T076 quick job, from before 002;
  - `job-20261008T235244Z-2d8f18`: a standard job, qualified;
  - `job-20261009T193750Z-a1822a`: the T035 throwaway (6× Garchomp), cancelled;
  - `job-20261009T193751Z-1fdb5e`: the T035 reference quick job, not qualified (quick never qualifies),
    byte-identical to the CLI.
- **Things the user may notice (by design, or open questions rather than spec defects):**
  - The status line keeps its last message (e.g. "Run cancelled") while an older run is picked.
  - (Resolved: 0.2.0 since 003.) The version always read "platsim 0.1.0" until `pyproject` was bumped (R5). Runs from before
    002 say "platsim version not recorded".
  - The ETA is rough. Confirm-stage time on standard varied 1.3k–11.4k s (R2).
  - (Resolved in 003: the page cleans requirement ids from recorded text.) The final-defaults warning text contains "(FR-019)". That is feature 001's requirement id,
    and it comes from `result.json`, not the page.
  - Cards are taller because the full "obtained from" text now wraps (T039).
- **After user testing:**
  - Fix any findings on the branch.
  - Run the web subset + browser tests (about 2 min): `uv run pytest -q tests/integration/test_web*.py`
    and `uv run pytest -q -m browser tests/browser/`.
  - Merge only on the user's go-ahead (`git switch main && git merge --ff-only 002-webui-redesign`).
- **Not in any commit, on purpose** (not part of 002; leave them alone unless the user asks):
  - `.claude/skills/speckit-assess-*`
  - `.specify/extensions.yml`, `.specify/extensions/`, `.specify/assessments/`
  - the deleted `.claude/scheduled_tasks.lock`
- **Lost with the old session's scratchpad** (results already in
  `specs/002-webui-redesign/validation-log.md`):
  - the screenshots;
  - the CLI comparison output (sha256 `d71fbb32…` is recorded);
  - the Playwright driver for quickstart V7. To redo V7, follow quickstart V7 by hand, or rewrite
    the driver: serve, then submit A and B via the page, `pgrep -f sim/worker.mjs`, click
    `#progress button.danger`, poll `/api/jobs/<id>`.

## Traps
- Any edit under `src/platsim/web/*.py` changes `platsim_code_hash`. An unfinished `state.json`
  written before such an edit refuses to resume without `--force-new` (research R8). All five
  existing `runs/*/state.json` files have finished, so none is affected today.
- A web job runs in its own session (`setsid`), so Ctrl-C on the server no longer reaches it.
  The shutdown hook and the parent-death guard (T026/T027) must be in place, or the job keeps
  running after the server stops (analysis U1).
- Bump `pyproject.toml` with each feature, or the page's version label doesn't change between runs (R5). It is 0.2.0 since 003.
- `/proc/<pid>/task/<pid>/children` doesn't exist on this kernel; use `pgrep -P` to find child processes.
- The id `results` is already used by the species list (`index.html`), so the new right column
  is `#results-col`.

# 003 Web UI refinements (started 2026-10-11)
- Source: `webui_changes.md`, removed after the merge; see `git show 24df0df:webui_changes.md` (the user's notes from testing 002). Spec: `specs/003-webui-refinements/spec.md`,
  with both clarifications answered. `.specify/feature.json` now points at 003.
- No separate branch was made: 003 was built on `002-webui-redesign` (the user's choice) and merged with it.
- It reverses 001's Munchlax exclusion (`ledger.EXCLUDED_SPECIES`). Leftovers is allowed only when Munchlax or
  Snorlax is on the team.
- 2026-10-11: spec clarified (post-game pokemon and post-game items are separate rules; reports carry the new
  source text; one post-game Leftovers counts with post-game items on; earliest location = badge gates).
- 2026-10-11: plan written: plan.md, research.md R1–R14, data-model, contracts, quickstart. It stays on branch
  002 (the user's choice).
- 2026-10-11: tasks.md written (T001–T062).
- 2026-10-11: /speckit-analyze found 1 critical, 3 high, 5 medium and 6 low issues. All 15 were fixed on the user's
  go-ahead:
  - constitution amended to v1.2.0 (Principle III: explicit, off-by-default rules may widen the output);
  - added T002a (constitution check) and T042a (re-render the stored web runs; originals untouched). As built,
    the new runs use normal job ids, not `-r003` folders (see validation-log);
  - FR-018 now guarantees unchanged sets and battle numbers, not "nothing else changes";
  - honey-tree pokemon (Aipom, Burmy, Cherubi, Combee, Heracross) are available today only as a level-1
    Day Care egg; checked live, research R5 corrected;
  - story ranks go into `data/generated/story_rank.json`;
  - the synthetic source kind is `outside_platinum`.
- 2026-10-11: /speckit-implement started. Done so far:
  - T001–T002a: baseline in `specs/003-webui-refinements/baseline/` and the validation log;
  - Phase 2 (display_text, a catalogue per options value);
  - US1 (wording, always-listed excluded pokemon, trade tooltip). Web 56 passed, browser 4 passed.
  - A background agent is building story_rank (T033/T038/T039).
- 2026-10-11: US2 done: rules, Munchlax/Leftovers, unreachable maps, Frontier exchange, data regenerated. Story rank
  done by an agent (31 passed, 4 xfailed with decomp evidence).
- 2026-10-11: US3, US4 and US5 done. T001–T057 and T061 are done.
  - Three stored web runs were re-rendered: *-75665e, *-c86e64, *-0c1874.
  - The version is 0.2.0.
- 2026-10-11: T059 full suite: 448 passed, 1 failed, 4 xfailed (2 h 22 min). The failure was a stale assertion in
  `test_evaluate.py::test_determinism_fast` (expected 2 legality keys, reports now carry 5). Fixed; rerun 1 passed.
  Browser 4 passed. Coverage table in `specs/003-webui-refinements/validation-log.md`. T058, T059, T061 marked.
- 2026-10-11: T060 passed. The web job `runs/job-20261011T222457Z-c4aa1b` and the CLI run (seed t058, quick)
  give byte-identical result.json (`cmp` exit 0, sha256 b665cfa9…). It has five legality keys and platsim 0.2.0,
  and every T001 baseline hash is OK. T001–T062 are all done.
- 2026-10-11: user follow-up: "Pokémon" spelling in all page text, and the double box on trainer hover (SVG
  <title> native tooltip) removed. Web 35 passed, browser 4 passed; server on :8000 restarted with the change.
- 2026-10-11: committed as 24df0df on 002-webui-redesign; main fast-forwarded to it on the user's go-ahead
  (f55e5d8..24df0df, includes the 002 commits). Not pushed.
- Open for the user: story rank is per map. Route 218 and Ravaged Path rank 0 by their early edge, though their
  grass is later.
- Traps found in research (all fixed in 003 unless noted; kept for the reasoning):
  - Honey-tree entries had level=None, so movesources skipped them as wild sources and named a level-1 Day Care
    egg instead (corrected R5, analysis H3). Fixed: levels 5–15 are parsed from the decomp.
  - `Ledger.species_sources` and `breed_mothers` caches were not keyed on options (R2). Fixed: keyed on options.
  - POST also covered maps that are never reachable (UNUSED_*, condominium) (R3). Fixed: `Classified.unreachable`.
  - Encounter rates were lost in `_merge_wild` (R8). Fixed: `rate_percent` is summed.
  - `mapgraph.py` treats sea water as land, so its hop counts are useless for story order (R9). Still true; story order
    comes from `story_rank.py`, which has its own Surf- and badge-aware graph. Don't use mapgraph hops for it.
  - The Battle Frontier BP exchange (`scrcmd.c` `ScrCmd_PokeMartFrontier`) was not extracted, so TM04, TM08, TM61
    and TM73 looked as if they had no source at all (R3). Fixed: `frontier_exchange_entries` (41 items, post-game).
  - Wild Gabite is only on Victory Road, but Gible is in Wayward Cave B1F (17–20, pre-Champion). The earliest
    location wins across evolution stages (user, 2026-10-11), so Garchomp is named from Gible.

## 004 breeding and fossil choices (started 2026-10-13)
- **Branch**: `004-breeding-source-limits`. Nothing is committed yet. The spec, plan, research,
  data-model, contracts and quickstart are in `specs/004-breeding-source-limits/`.
- **Status** (2026-10-13): all 36 tasks are done. The full suite gave `478 passed, 4 xfailed`
  (2:27:46, exit 0). Committed on `004-breeding-source-limits` (`efbb110`). **Merged into `main`**
  by fast-forward on 2026-10-13, at the user's request.
- **How to test by hand**:
  - Run `uv run platsim serve` on this branch. Restart any old server first, because it runs
    the old code.
  - Then try these teams:
    - Torterra + Infernape + 4 others → refused ("only one starter").
    - Infernape + Monferno → accepted.
    - Rampardos + Bastiodon → refused (Trainer ID).
  - "Obtained from" for a bred member names the parent's source.
- **Not committed on purpose** (they predate 004 and are unrelated):
  - the `.claude/scheduled_tasks.lock` deletion;
  - `.claude/skills/speckit-assess-*`;
  - `.specify/assessments/`, `.specify/extensions*`.
- **Lost with the session scratchpad**: the probe scripts and the HM knockout scripts. The
  method for the HM answer: patch `story_rank.move_stage`, then flood per badge stage seeded
  at the Pokémon Centers already reached.
- **Done**:
  - (group, choice) on entries and options;
  - starter lines limited to one per team (validator, optimizer, web 422);
  - fossils grouped by Trainer ID parity, with revivals unlimited and each using up a fossil;
  - breeding requires a compatible father (`compatible_father`) and a mother that can be female
    (`female_possible`, the game's gender formula);
  - breed text names the parent's source;
  - the engine team count is 55,192,424,630 (a test);
  - the 188 allowed species and 98 final forms are unchanged (a test);
  - version 0.3.0, and the README is updated.
- **Defect** (observed 2026-10-13): Day-Care breed options have no `exclusive_group`. As a
  result, Torterra (gift) + Infernape (bred) is accepted, and so is any mix of starter lines.
  Fossil revivals ignore the Trainer ID parity (`mining.c:647-648`) and are capped at one copy.
- **Target**: species-only teams of six distinct species go from 56,574,476,596 to
  55,192,424,630 (starter rule alone: 55,379,676,751). Two closed forms agree.
- **Scratch scripts** (lost with the session scratchpad):
  - the allowed-list generator, which produced `allowed_pokemon.md`;
  - the team counter;
  - the breed probes.

  The method is written in research R9.
- **Traps**:
  - Breeding from one female is legal for one-time parents (Eevee, Riolu, Togepi, Drifloon,
    Spiritomb). Do not remove those breed sources.
  - Run probe scripts with `python -u`, or the output buffers and looks hung.
  - `allowed_pokemon.md` at the repo root was generated on 2026-10-13 and is committed with 004.
    It is the reference for `test_allowed_final_forms` and must not change under 004.
  - Each story_rank stage floods from Twinleaf. To test whether an HM is still needed late, seed
    at the Pokémon Centers already reached, not at every door of a town; every door also includes
    doors behind obstacles.

## 006 required HMs (started 2026-10-13)
- **Where**: git worktree `../platinum_sim-006`, branch `006-required-hms`, from `main` at
  `dccb3a4`. `pokeplatinum` and `pokemon-showdown` are symlinks to the main checkout (excluded in
  `.git/info/exclude`).
  - `data/generated/` and `.venv` don't exist here yet. Run `uv sync` and `uv run platsim extract`
    before any test.
- **Why a worktree**: the 005 full suite was running in the main checkout.
- **Status** (2026-10-14): all 28 tasks are done. The full suite gave 488 passed and 2 failed.
  One failure was a test fix (summary keys). The other was environmental (no `runs/` in the
  worktree); both pass on rerun, see `validation-log.md`. A quick end-to-end optimize with Surf and
  Waterfall required passed, and its result validates. Committed on `006-required-hms`. **Not
  merged.**
- **How to test by hand**:
  - From the worktree, run `uv run platsim serve --port 8001`; the main checkout serves 005 on
    8000.
  - Step 3 has 8 HM toggles. Check Fly with Garchomp ×6 → expect a 422 "No team member can learn
    Fly".
  - Check Surf with a team that can learn it → the result carries Surf, and the summary shows
    "Required HMs: Surf".
- **Merge note**: 005 (`d8f90e9`) and 006 both branch from `main` `dccb3a4`. Both touch
  `index.html`, `app.js`, `cli.py`, `movesources.py`, `validator.py`, `resources.py`, `README.md`
  and the test files; expect small conflicts. Merge 005 first, then rebase or merge 006 and rerun
  the suite.
- **Includes** `hm_requirements.md` (linked from the README).
- **Design**: required HMs are placed inside `resources.realize`, replacing the cheapest attack slot; a filter is not enough, because Defog never enters the move pool and 4 rewrite paths can drop an HM.
- **User decisions**:
  - A required HM must be in a final moveset, not merely learnable.
  - The web gets a new step 3 with eight toggles, all off by default.
  - A required HM that no team member can learn is refused before the run.
