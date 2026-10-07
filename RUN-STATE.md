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
- 2026-10-07: Phase 2 complete (T011–T057): decomp readers, availability ledger (no National Dex, per the user),
  legality validator, Showdown worker with decomp stats/PP/exp, the decomp trainer AI (default opponent), greedy-v1
  and expectimax2-v1 (52.0% vs 15.8%, p=3.6e-129), pool, Cynthia top-up, divergence ledger, report writers.

## Next
- **Checkpoint B reached** (all of T001–T057 done; see validation-log). The user reviews it before Phase 3+.
- In progress: wild held items as a ledger source, with Munchlax excluded (spec FR-006a, user decision 2026-10-07).
- Open user decision: the game auto-learns a level-up move when a mon has fewer than 4 moves (`battle_script.c:10021-10035`),
  while the spec says always decline.
- Replace `tests/fixtures/reference_team.json` with a legal team (it is currently illegal: Alakazam is trade-only).
- Budget concern: `expectimax2-v1` runs at about 1.6 gauntlets/s on 16 workers, so 2,000 confirmation runs take about 20 min
  per finalist. The optimizer's search must screen with greedy-v1 and confirm with expectimax2-v1, or the budget must be
  revisited before T060+.

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
