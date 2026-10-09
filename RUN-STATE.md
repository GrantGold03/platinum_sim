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
  - real-browser UI check;
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
- 2026-10-09: T036 README, T037. 002 is complete and committed on branch `002-webui-redesign`, not merged.

## Next
- The user does hands-on testing of `platsim serve` before merging `002-webui-redesign` into main.
  Do NOT merge without their go-ahead.
- Open: FR-028 control labels are not asserted by any test (validation-log T033 table).
- The "real-browser UI check" gap is closed: `uv run pytest -m browser tests/browser/`.

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
