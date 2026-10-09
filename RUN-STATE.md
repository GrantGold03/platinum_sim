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
