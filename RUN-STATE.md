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

## Next
- Wait for the user's review of Checkpoint A, then T011+ (decomp readers).
- Decided: no PP Ups for anyone (spec FR-008); T034 resets PP to base.

## Traps
- Resist berries (HOLD_EFFECT_WEAKEN_SE_*): their battle effect is not located in the decomp C yet, so they are excluded from the optimizer until found (validation-log, T037).
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
