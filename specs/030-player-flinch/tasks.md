# Tasks: The battle player models flinch

**Input**: `specs/030-player-flinch/` (spec.md, plan.md, research.md R1 to R7, data-model.md, contracts/player.md, quickstart.md)

**Branch**: `030-player-flinch` from `main` 9877958, main checkout. Times US Eastern. Measurements alone (`pgrep -a -x node;
pgrep -a pytest` empty); never pipe a gating command into `tail`; never amend or force-push; never edit `src/` or `sim/` while an
acceptance, check or suite runs; paired checks use 029's `paired_policies.py --battle-style shift` with `file:` for team files and
named teams `ref`, `bench`, `b2main`; engine tests drop Showdown's duplicate split lines; evidence under `runs/030-evidence/` (local)
with copies under `specs/030-player-flinch/evidence/`.

## Phase 1: Setup (pre-feature evidence, before any code change)

- [ ] T001 Start `specs/030-player-flinch/validation-log.md` (before-values: both code hashes, the ledger version; `git diff --stat
      main -- src sim tests pyproject.toml` empty) and copy 029's scripts into `specs/030-player-flinch/scripts/`: `acceptance.py`
      (`runs/030-evidence`, identity seed `030-ident`; the identity comparison **reports** each difference instead of failing (R7, spec
      US3 scenario 3); the pass rule: snapshot attribution all `identical`, equal-level pairs per the 024 rule, team build within 10 s),
      `attribution.py` (029's; every member must be `identical`), `equal_levels.py` (master `030-equal|B2`), `paired_policies.py` (029's)
- [ ] T002 Run the pre-feature side alone (about 10 min): `uv run python specs/030-player-flinch/scripts/acceptance.py --side main --workers 16 > runs/030-evidence/acceptance-main.txt 2> runs/030-evidence/acceptance-main.err; echo exit=$?`;
      copy outputs and the snapshot to `evidence/`; log; Commit 1 `docs(030): pre-feature evidence and scripts`; push

## Phase 2: Foundational

- [ ] T003 Engine-versus-game checks (FR-005, R4) in `sim/test/flinch.test.mjs` part 1 (029's pattern: `leagueBattle`, `turn()` with
      duplicate lines dropped, seeds chosen so the roll succeeds): (a) a faster flinch move flinches a slower target (`|cant|...|flinch`,
      no move by the target); (b) a slower flinch move never flinches; (c) Inner Focus blocks; (d) a substitute blocks; (e) Steadfast
      raises Speed one stage; (f) Fake Out fails on its user's second turn out and works on the first; record each against the decomp
      (R1, R3); ledger entries for confirmed differences (`src/platsim/divergence/mechanics.py`, then `uv run platsim divergences`)

## Phase 3: User Story 1 - The battle player knows flinch (Priority: P1) 🎯 MVP

- [ ] T004 [US1] `sim/policy/expectimax2.mjs`: `FLINCH_EFFECTS` (R2: the eight effect names); in `execMove`, for each landing outcome
      when `X.opts.flinch !== false`, `foeMovesLater` is true, the move's effect is in `FLINCH_EFFECTS` and is not on a charge turn, the
      target survives, has no substitute (`!t.fresh && t.ref.volatiles.substitute`) and lacks Inner Focus (unless the user has Mold
      Breaker): split the branch with p = min(1, `rec.effect_chance` x (2 if the user has Serene Grace)) / 100 into a flinched copy
      (`t.flinched = true`) and the rest; data-model: "`flinched` (boolean, false by default; set only within a turn by a landing flinch
      move whose target moves later; cleared when the target's move is lost, and at end of turn)"
- [ ] T005 [US1] `sim/policy/expectimax2.mjs`: in `doMove`, after the sleep and freeze checks and before paralysis (the game's status-
      check order): a flinched Pokemon clears the mark, sets `lastMoveOk = false`, gains +1 Speed stage with Steadfast (`clampStage`),
      and loses its move; `endOfTurn` clears any mark; Fake Out (`ALWAYS_FLINCH_FIRST_TURN_ONLY`) fails when its user has been out a full
      turn (`activeTurns > 0`, R3; confirm against T003 (f)); the header's "flinch not modelled" line updated; `sim/gauntlet.mjs`: v4 knob
      `flinch=0|1` (029's pattern)
- [ ] T006 [US1] `sim/test/flinch.test.mjs` part 2 (the model's cases, spec US1 scenarios 1 to 8): faster foe's Air Slash: a flinched
      branch with p 0.30 where the member's move does not happen; slower foe: no flinched branch at all (FR-012); the player's faster
      member: the foe flinches; substitute, Inner Focus, already moved: none; Serene Grace doubles; Steadfast +1 Speed; Fake Out first
      turn only; knob off: outcome lists identical to today's; then the Node suite (the replay test green with the knob off; if the
      default replay fixture changes, re-record it only after confirming the change is flinch and state the difference); greedy-v1
      unchanged; record; Commit 2 `feat(030): the player models flinch; v4 knob; engine checks`; push

## Phase 4: User Story 2 - The change is measured reference-first (Priority: P2)

- [ ] T007 [US2] Player check, alone (FR-008, R6, about 45 min), 029's paired script, `--a expectimax2-v4 --b 'expectimax2-v4?flinch=0'`:
      pairing control `--self` on `ref`, 200 pairs (0 discordant); `ref`, `bench`, `b2main`, 2,000 pairs each, outputs under
      `runs/030-evidence/pairs-<team>`; conditions control: the reference arm's clear rate on `b2main` within 0.944 [0.920, 0.961];
      **a supported loss on any team stops the feature** (record and report)
- [ ] T008 [US2] Speed (SC-004, R5): two 500-pair runs on `ref` with the arms in both orders; each arm's gauntlets per second = the mean
      of its two positions; the model must be at least 75% of the reference; over the bound: stop and report for the owner's decision
      (prune or stop); record T007 and T008 in the log; Commit 3 `docs(030): player check and speed`; push

## Phase 5: User Story 3 - Accepted on both codes (Priority: P3)

- [ ] T009 [US3] Branch side alone: `uv run python specs/030-player-flinch/scripts/acceptance.py --side branch --workers 16 --runs 2000 > runs/030-evidence/acceptance.txt 2> runs/030-evidence/acceptance.err; echo exit=$?`; copy evidence
- [ ] T010 [US3] Merge gate (FR-011): a supported loss in T007, a speed under 75% in T008, a snapshot difference, a supported equal-level
      loss or a level difference above 1.0: no merge, record and stop at the report; identity differences are reported with the reason
      (flinch), not failures
- [ ] T011 [US3] Docs: validation log (player check table per team, speed, acceptance table); `README.md` (030 block: what flinch
      modelling changes per team and the speed cost, what the player still does not model: the Fangs' status chances, confusion,
      infatuation; Principle VII); `FUTURE-FEATURES.md` section 0 (flinch done; 031 King's Rock / Razor Fang next, Shield Dust blocks the
      item flinch); `RUN-STATE.md`; Commit 4 `feat(030): acceptance; docs`; push

## Phase 6: Gates and close

- [ ] T012 Gates, nothing else running: engine diff empty; `sim` diff only the player, the knob and the test; `src` diff only a ledger
      entry if T003 found one; hashes and ledger version as expected; Node suite; `uv run pytest -q --durations=25 > runs/030-evidence/full.log 2>&1; echo full exit=$?`; log and `evidence/gates.txt`
- [ ] T013 Closing commit `docs(030): gates recorded; feature closed on its branch`; push; report with the merge command; merge on the user's go

## Dependencies

- T001 → T002 (before any code change) → T003 → US1 (T004 → T005 → T006) → US2 (T007 → T008) → US3 (T009 → T010 → T011) → T012 →
  T013. No commit during T002, T007, T008, T009 or T012's measured steps.

## Parallel opportunities

- T003's engine cases beside T004-T005 once T002 is done (different parts of the same test file come later).

## Implementation strategy

- MVP = US1. 13 tasks, three stories, one layer (the player).
