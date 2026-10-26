# Tasks: Held-Item Sources (held items, slice H1)

**Input**: Design documents from `specs/011-held-item-sources/` (spec.md, plan.md, research.md,
contracts/explain-text.md, quickstart.md). Rewritten 2026-10-26 after the from-scratch re-plan; T001-T005 (baseline
on `main`'s code) are kept as done.

**Tests**: Required by the plan (Constitution V): one positive and one negative control per reader gap (G1-G4),
written first and shown to fail on `main`'s reader; the explain-text check (FR-007); validator checks (FR-005).

## Conventions

- Temp files go in the session scratchpad; evidence worth keeping goes in `runs/011-evidence/` (git-ignored).
- Never `git commit -a`: the user's uncommitted deletion of `.claude/scheduled_tasks.lock` stays out.
- `data/generated/` is shared between branches: rebuild with `uv run platsim extract` before any check.
- Record every result with real output in `specs/011-held-item-sources/validation-log.md`.
- No archived 008 code or text is copied (FR-009). 008's results are read only in T024, after the build.
- Rules are keyed to script commands, never to map or script names (FR-010).
- Push every commit that touches `src/` or `tests/`. Do not merge.
- The ledger fixture: `build_ledger()` from `platsim.availability.ledger` (module-scoped, as in
  `tests/integration/test_availability_controls.py:31-33`). Gift entries: `platsim.availability.sources.npc_gift_entries()`.

## Phase 1: Setup (baseline, code = `main`) — done

- [X] T001 Create `specs/011-held-item-sources/validation-log.md`: branch, base, `git diff --stat f88cdd0 HEAD -- src tests sim` (empty)
- [X] T002 Rebuild with `uv run platsim extract`; save `runs/011-evidence/availability-main.json` and per-item copies `runs/011-evidence/main-availability-items.json` (66/37/55)
- [X] T003 [P] Save `explain` for Black Belt, Expert Belt, Focus Sash, the 8 Pastoria berries, Belue Berry, Liechi Berry and Choice Band to `runs/011-evidence/explain-main.txt`
- [X] T004 [P] Save B1-B5 held-item candidates to `runs/011-evidence/main-candidates.json` (93 entries)
- [X] T005 Quick optimization of B2, seed `011-sc006`, to `runs/011-evidence/sc006-main` (1493.9 s, sha256 `0dbeab6a...`)

## Phase 2: Foundational (the gift reader; blocks every story)

**Goal**: `npc_gift_entries` finds the items at the Route 221 house, the Pastoria City SW house and both Amity Square
sources through four general improvements (research R1).

- [X] T006 Write `tests/integration/test_gift_reader.py` with these controls, each asserting on `npc_gift_entries()` entries whose `src[0]` starts with the given file:line (find the exact give lines in the decomp, research R1):
  - G1 positive: `scripts_route_221_house.s:39` gives exactly `{ITEM_BLACK_BELT, ITEM_EXPERT_BELT, ITEM_FOCUS_SASH}`;
  - G2 positive: `scripts_pastoria_city_southwest_house.s:20` gives exactly the 17 items whose ids are `ITEM_OCCA_BERRY` + 0..16 (ids read from `platsim.decomp.items.load_items()`, not typed);
  - G3 positive: `scripts_amity_square.s:375` gives exactly the 9 berries set at `:311-344`;
  - G4 positive: `scripts_amity_square.s:940` gives exactly the `ITEM_*` entries of `sBerryAndAccessoryManOptions` (`src/scrcmd_amity_square.c`), and no `ACCESSORY_*` subject appears in any entry;
  - negative: every `npc_item_gift` entry in the baseline `runs/011-evidence/availability-main.json` is still produced with the same subject, map, quantity and source (skip with a clear message if the evidence file is absent, since it is git-ignored), and `Ledger.item_copies` is 0 for `ITEM_LIECHI_BERRY` and `ITEM_CHOICE_BAND`.
  Run it; record in the log that the four positive controls fail and the negative controls pass on `main`'s reader
- [X] T007 G1 in `src/platsim/availability/sources.py` `_const_dataflow`: carry a call stack in each work item so that a `Return` (`platsim.decomp.scripts.ends_procedure(cmd) == "return"`) continues at the command after the call that entered the routine, with the routine's values; keep a bound on stack depth and on re-visits so the fixed point terminates. Run the G1 test; record
- [X] T008 G2 in `_const_dataflow`: `GetRandom VAR, n` (find the primitive's op name in `platsim.decomp.scripts`) sets the offsets `0..n-1`; `AddVar VAR, ITEM_X` on a set of offsets gives the items at `id(ITEM_X) + offset` by item id from `load_items()`; any other arithmetic stays `?`. Run the G2 test; record
- [X] T009 G3 in `src/platsim/availability/sources.py`: a cached map of every saved variable (not `VAR_0x8000`-`VAR_0x800F` temps, not `VAR_MAP_LOCAL_*`, not `VAR_RESULT`) to the set of literal values written to it by `SetVar` in all script files, or `?` if any write to it is non-literal; `SetVar TRACKED, SAVED_VAR` in `_const_dataflow` takes that set. Run the G3 test; record
- [X] T010 G4 in `src/platsim/availability/sources.py`: (a) a script command whose C handler returns an element of a static C array (find the handler for `GetAmitySquareBerryOrAccessoryIDFromMan` from the command table in the decomp, parse the array it indexes) yields that array's values into its destination variable; implement it as a general reader of "handler indexes one static array", not a name list; (b) `npc_gift_entries` reads `AddItem VAR, VAR` with the item variable's values from `_const_dataflow` (only `ITEM_*` values count). Run the G4 test; record
- [X] T011 Daily-random-level rule in `npc_gift_entries`: a daily give whose path (reuse the walk of `_daily_guard`) runs `GetDailyRandomLevel` counts each possible item as 1 copy (a per-item once flag), not unlimited (user, 2026-10-14). Add a test to `tests/integration/test_gift_reader.py`: the three Route 221 items each have quantity 1; Pastoria's daily berries keep `main`'s daily rule
- [X] T012 Rebuild (`uv run platsim extract`, `uv run platsim extract --check`); record wall time against T002 (44.6 s; over 1.5× is investigated). Run `uv run pytest -q tests/integration/test_gift_reader.py tests/integration/test_availability_controls.py`; record (the 66/37/55 pins are expected to fail until T017)
- [X] T013 FR-010 list: with a scratchpad script, diff `data/generated/availability.json` `entries` against `runs/011-evidence/availability-main.json` (added, removed, changed); group by script file; recompute per-item copies (`snapshot.py`) and diff against `runs/011-evidence/main-availability-items.json`. Record in the log every site with changed entries and its items, and every item whose copies changed. **Gate:** if any held item (hold effect not `HOLD_EFFECT_NONE`) changes availability and is not from the Route 221 house, the Pastoria SW house or Amity Square, stop and report it to the user before going on. Check in particular the Veilstone prize exchange (double counting with `game_corner_entries`) and scratch-off cards (research R3)
- [X] T014 Commit `src/platsim/availability/sources.py` and `tests/integration/test_gift_reader.py` as "feat(011): gift reader follows calls, random offsets, saved variables and C tables"; push

## Phase 3: User Story 1 - New item sources appear in the item catalog (P1)

**Goal**: the sources show in `explain` with refs, copies and verdicts, in plain English.
**Independent test**: `explain` for Focus Sash, Expert Belt, Black Belt, Occa Berry and Belue Berry (quickstart 1).

- [X] T015 [US1] Add the text check to `tests/integration/test_gift_reader.py` per `contracts/explain-text.md`: run `platsim.explain.explain()` for `item:focus_sash`, `item:occa_berry`, `item:belue_berry`; for each source line at the Route 221 house, Pastoria SW house or Amity Square, fail on the rule 2 patterns and on a missing decomp file:line. Positive control: a made-up line containing `T053` and `dataflow` is rejected. Run it; record the result on the T014 code
- [X] T016 [US1] Write the reasons in `npc_gift_entries` (`src/platsim/availability/sources.py`) per the contract table: Route 221 (level condition with its file:line, the rotation order read from the script's `CallIfEq` order, 1 copy each), Pastoria (one of N berries), Amity pickup (found while walking with a partner; any starter can be the partner, citing `scripts_amity_square.s:646-677`), Gift Man (one of the man's 9 berries or 7 accessories, counts read from the parsed table), other newly read sites ("one of N possible items"). Keep `main`'s existing phrases. Run T015's check; it passes
- [X] T017 [US1] Update the count pins in `tests/integration/test_availability_controls.py:522-526` to the values measured in T013, with a comment naming the changed items and the date; rebuild and run `uv run pytest -q tests/integration/test_availability_controls.py tests/integration/test_extract.py tests/integration/test_explain.py tests/integration/test_gift_reader.py`; record (SC-001, SC-002, SC-004)
- [X] T018 [US1] Save `explain` for the T003 items to `runs/011-evidence/explain-branch.txt`; diff against `explain-main.txt`; record that Liechi Berry and Choice Band are unchanged (FR-006); quote the new Focus Sash, Occa Berry, Belue Berry lines and one Gift Man line in the log (FR-001-FR-004)

## Phase 4: User Story 2 - The validator accepts teams that hold these items (P1)

**Goal**: validator and ledger agree. **Independent test**: quickstart 2.

- [X] T019 [US2] Add `test_focus_sash_one_copy` to `tests/unit/test_validator.py`, modelled on the existing `ITEM_COPIES` test (`:228-233`): assert `led.item_copies("ITEM_FOCUS_SASH") == 1` (ledger value); one holder gives no error; two holders give `["ITEM_COPIES"]`. Run the file (it includes the existing Choice Band `ITEM_UNAVAILABLE` test); record (SC-003, FR-005)

## Phase 5: User Story 3 - Nothing else changes (P2)

**Goal**: optimizer inputs and results unchanged. **Independent test**: quickstart 3.

- [X] T020 [P] [US3] Recompute B1-B5 candidates with `snapshot.py` to `runs/011-evidence/branch-candidates.json`; compare with T004; record identical or explain each difference (FR-008, SC-006)
- [X] T021 [US3] Commit T015-T019 (src and tests) as "feat(011): plain-English reasons for the new item sources; validator test"; push. Then the same quick optimization as T005 to `runs/011-evidence/sc006-branch`; diff `result.json` field by field against `sc006-main`; record that only provenance hashes differ, or explain each difference (SC-006)

## Phase 6: Polish

- [ ] T022 [P] Full suite in the background: `uv run pytest -q` (about 2.5 h) and `node --test sim/test/*.test.mjs`; record pass/fail counts and explain every failure or changed count (SC-005)
- [X] T023 [P] Check that no archived code was used: `git diff 73af068 -- src tests` contains none of the strings `_const_dataflow_literal`, `007 dataflow`, `new_site`; record (FR-009)
- [X] T024 After the build only (FR-009, Clarifications Q2): compare T013's held-item changes and site list with `specs/008-ledger-item-sources/validation-log.md`; check each difference against the decomp and record it; change nothing to match 008
- [ ] T025 Update `README.md` where it lists item sources or held-item counts, `FUTURE-FEATURES.md` (held-items slices: H1 done pending the user's test, H2 next) and `RUN-STATE.md`; commit docs (not the lock deletion)
- [ ] T026 Hand over for the user's hands-on test (quickstart 4) with the T013 site list and any T024 differences. Do not merge

## Dependencies

- T001-T005 done.
- T006 → T007 → T008 → T009 → T010 → T011 → T012 → T013 (gate) → T014.
- T014 → T015 → T016 → T017 → T018 (US1).
- T019 (US2) after T014; it can run alongside US1.
- T020 after T017 (final data); T021 after T018-T020.
- T022 after T021; T023 and T024 any time after T021; T025 → T026 last.

## Parallel opportunities

- T019 alongside T015-T018 (different test file).
- T020 alongside T021's commit.
- T022 (2.5 h, background) alongside T023-T025.

## Implementation strategy

Gaps land one at a time, each with its failing test made to pass (T007-T010), so a wrong reading points at one
change. The T013 gate keeps the general fix from silently moving other held items (FR-010). US1 is the user's test
surface; US2 the legality guard; US3 the acceptance gate (no optimizer change). 26 tasks (5 done), 3 stories.
