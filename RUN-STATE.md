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

## Next: user testing, then merge (handoff written 2026-10-10)
- **State:** all 41 tasks (T001–T041) are done and committed on branch `002-webui-redesign`.
  - `c872971` is the redesign; `25b41b1` has the converge fixes; a later docs commit refreshes stale docs.
  - `main` is still at `f55e5d8`, so the branch is a fast-forward of main. There is no git
    remote, so nothing has been pushed.
- **Do NOT merge without the user's go-ahead.** The user does hands-on testing first, in a new session.
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
  - The version always reads "platsim 0.1.0" until `pyproject` is bumped (R5). Runs from before
    002 say "platsim version not recorded".
  - The ETA is rough. Confirm-stage time on standard varied 1.3k–11.4k s (R2).
  - The final-defaults warning text contains "(FR-019)". That is feature 001's requirement id,
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
- pyproject is still 0.1.0, so the version label doesn't change between runs (R5).
- `/proc/<pid>/task/<pid>/children` doesn't exist on this kernel; use `pgrep -P` to find child processes.
- The id `results` is already used by the species list (`index.html`), so the new right column
  is `#results-col`.
