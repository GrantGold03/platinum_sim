# Tasks: H4, King's Rock / Razor Fang

**Input**: `specs/031-h4-kings-rock/` (spec.md, plan.md, research.md R1 to R6, data-model.md, contracts/optimizer.md, quickstart.md)

**Branch**: `031-h4-kings-rock` from `main` 5d8650d, main checkout. Times US Eastern (read the clock with `date`, never estimate).
Measurements alone (`pgrep -a -x node; pgrep -a pytest` empty); never pipe a gating command into `tail`; never amend or force-push;
never edit `src/` or `sim/` while an acceptance, check or suite runs; never key a cache on `id()` alone; paired checks use 030's
`paired_policies.py --battle-style shift` with `file:` team paths and `--master-suffix` for fresh seeds; engine tests drop Showdown's
duplicate split lines; evidence under `runs/031-evidence/` (local) with copies under `specs/031-h4-kings-rock/evidence/`.

## Phase 1: Setup (pre-feature evidence, before any code change)

- [x] T001 Start `specs/031-h4-kings-rock/validation-log.md` (before-values: both code hashes, the ledger version; `git diff --stat
      main -- src sim tests pyproject.toml` empty) and adapt 029's scripts into `specs/031-h4-kings-rock/scripts/`: `acceptance.py`
      (`runs/031-evidence`, identity seed `031-ident`, `NEW_ITEMS = {kings_rock, razor_fang}`, flinch-item holders reported per winner),
      `attribution.py` (an appended-items list may gain `kings_rock` at its end; new extras allowed only of kind `flinch_item`; anything
      else a defect), `equal_levels.py` (master `031-equal|B2`), `hand_check.py` (each B2 member's appended items and `flinch_item`
      extras), and 030's `paired_policies.py` (with `--master-suffix`)
- [x] T002 Run the pre-feature side alone (about 15 min): `uv run python specs/031-h4-kings-rock/scripts/acceptance.py --side main --workers 16 > runs/031-evidence/acceptance-main.txt 2> runs/031-evidence/acceptance-main.err; echo exit=$?`;
      copy outputs and the snapshot to `evidence/`; log; Commit 1 `docs(031): pre-feature evidence and scripts`; push

## Phase 2: Foundational

- [x] T003 Engine-versus-game checks (FR-001, R1) in `sim/test/kings_rock.test.mjs` (030's pattern; the holder faster than Flint's
      Houndoom; seeds scanned): (a) a single-hit affected move: flinch rate over 400 seeds within a 99% interval of 10%; (b) a two-hit
      affected move (Double Kick): rate over 400 seeds near 19% and more than one roll per use (a flinch after the first hit's miss is
      impossible to tell apart, so test the rate); (c) Air Slash with the item: rate near 37%; (d) a substitute, Inner Focus, Shield Dust
      and a slower holder: never over 100 seeds each (no League Pokemon has Shield Dust or Inner Focus or uses Substitute: the test
      sets the target's ability with the battle API, or adds a substitute volatile, before the turn; the slower-holder case uses a
      holder slower than Houndoom); record against the decomp; ledger entries for confirmed differences
      (`src/platsim/divergence/mechanics.py`, then `uv run platsim divergences`)

## Phase 3: User Story 1 - The battle engine flinches as the game does (Priority: P1) 🎯 MVP

- [x] T004 [US1] Run `sim/test/kings_rock.test.mjs` and the Node suite (exit code kept; replay unchanged: no player change); record the
      rates with their intervals; Commit 2 `test(031): King's Rock engine checks against the game`; push

## Phase 4: User Story 2 - The optimizer offers the flinch item (Priority: P2)

- [x] T005 [US2] `src/platsim/optimizer/candidates.py`: `KINGS_ROCK_FLAG = "MOVE_FLAG_TRIGGERS_KINGS_ROCK"`, `FLINCH_ITEM_EFFECT =
      "HOLD_EFFECT_SOMETIMES_FLINCH"`, `EQUIVALENT_ITEMS = {"kings_rock": ("kings_rock", "razor_fang")}` (data-model: "the candidates
      name the first; realize assigns the first affordable member of the group; at most the group's total copies on a team");
      `extra_item_candidates` appends `kings_rock` last (after the resist berries) when the moveset has a move with the flag, never
      otherwise (FR-003)
- [x] T006 [US2] `src/platsim/optimizer/candidates.py`: extra kind `flinch_item` (R4): when the variant's candidate moves include an
      affected multi-hit move, take the variant's first-ranked base set, swap the member's highest-scoring affected multi-hit move
      (ties: the move key) in for the set's lowest-scoring move (ties: the lowest score, then the move key) (unless already in it), offer it held with `kings_rock` if not already offered; at most one per variant;
      not if the swapped-in move is dead in the League (reason in `dropped_extras`); recorded in `item_extras`, `extra_kind`,
      `extras_by_kind`
- [x] T007 [US2] `src/platsim/optimizer/resources.py`: in the member item check of `realize`, when the item is in an
      `EQUIVALENT_ITEMS` group and its copy is not affordable, use the next affordable item of the group and record it as the member's
      held item (the report and `team.txt` show the actual item); a holder beyond the group's copies is refused; team-gated copies
      (Gliscor's Razor Fang) unchanged
- [x] T008 [US2] `tests/unit/test_kings_rock.py`: appended last for sets with an affected move, not for sets without; a `flinch_item`
      extra for a known multi-hit learner (e.g. Lucario: Bone Rush) and none for a member without one; two holders realize as King's
      Rock and Razor Fang, a third refused, with Gliscor only one fits; the 36 snapshot members change only by `appended` items and
      `flinch_item` extras (031 attribution); update pins in `tests/unit/test_h4_items.py`, `tests/unit/test_shell_bell.py`,
      `tests/unit/test_resist_berries.py` that compare whole appended lists, and the 36-member attribution tests in
      `tests/unit/test_shell_bell.py` (`test_only_the_appended_items_change_over_the_36_members`) and `tests/unit/test_resist_berries.py`
      (the same name): strip `kings_rock` from `items_extra` and drop the `flinch_item` extras before their checks, as 029 did for
      028's test (analyze C1); run them with the candidate and resources tests (exit kept)
- [x] T009 [US2] Hand check and the fast suite (`uv run pytest -q -m "not battle_sim" > runs/031-evidence/fast.log 2>&1; echo exit=$?`);
      log; Commit 3 `feat(031): the flinch item offered (appended, multi-hit extras, one option with two copies)`; push

## Phase 5: User Story 3 - Accepted on both codes, and shown to help (Priority: P3)

- [x] T010 [US3] Branch side alone: `uv run python specs/031-h4-kings-rock/scripts/acceptance.py --side branch --workers 16 --runs 2000 > runs/031-evidence/acceptance.txt 2> runs/031-evidence/acceptance.err; echo exit=$?`; copy evidence
- [x] T011 [US3] Merge gate (FR-009): a supported equal-level loss, a level difference above 1.0, an attribution defect or a non-identical
      identity row (no player change): no merge, record and stop at the report
- [x] T012 [US3] Multi-hit measurement, alone, report only (FR-007, R6 amended: B5 and Torterra's Bullet Seed set; the text below
      names B3 and Lucario from before the amendment): B3 quick on the branch (the acceptance script's optimize call
      or `platsim optimize` with B3's species, quick preset; about 10 min); if Lucario is in the winner, build two team files: Lucario
      on its `flinch_item` set holding the flinch item, and the same set with its usual first item, both validated (both arms the
      same set; only the held item differs, FR-007); else the best
      multi-hit user of a winner; 030's paired script, `--master-suffix 031-multi`, `--self` 200 pairs, then 2,000 pairs; record both
      rates and the verdict
- [x] T013 [US3] Docs: validation log; `README.md` (031 block: the item rule, the copies, one option with two copies, the multi-hit
      extras, that the battles credit the item's flinches while the player does not steer toward them, the T012 result; the items
      bullet names King's Rock / Razor Fang); `FUTURE-FEATURES.md` section 0; `RUN-STATE.md`; Commit 4 `feat(031): acceptance and
      multi-hit measurement; docs`; push

## Phase 6: Gates and close

- [x] T014 Gates, nothing else running: engine diff empty; `sim` diff only the new test; hashes and ledger version as expected; Node
      suite; `uv run pytest -q --durations=25 > runs/031-evidence/full.log 2>&1; echo full exit=$?`; log and `evidence/gates.txt`
- [x] T015 Closing commit `docs(031): gates recorded; feature closed on its branch`; push; report with the merge command; merge on the user's go

## Dependencies

- T001 → T002 (before any code change) → T003 → US1 (T004) → US2 (T005 → T006 → T007 → T008 → T009) → US3 (T010 → T011 → T012 → T013)
  → T014 → T015. No commit during T002, T010, T012 or T014's measured steps.

## Parallel opportunities

- T003 (engine tests, `sim/`) beside T005-T007 (optimizer, `src/`) once T002 is done.

## Implementation strategy

- MVP = US1 (the engine verified). 15 tasks, three stories, one layer (the optimizer) plus engine tests.
