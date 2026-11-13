# Tasks: H4, Wide Lens and Razor Claw

**Input**: Design documents from `/specs/025-h4-wide-lens-razor-claw/`

**Prerequisites**: plan.md, spec.md (three clarifications), research.md (R1-R9), data-model.md,
contracts/candidates-items-and-dominance.md, contracts/provenance-member-defaults.md, quickstart.md

**Tests**: requested by the spec (FR-005, FR-004a, FR-007, SC-001 to SC-003): Python unit tests for the crit table, the move
value under an item, the item rules, copy refusal, item-conditioned extras, the dominance controls and the provenance block; one
Node test for the model's switch reset; the attributed snapshot diff and the equal-levels check in the acceptance.

**Organization**: by user story. US1 (the items with re-evaluation, the crit term, the dominance widening, the screen's appended
options) is the MVP; US2 the provenance block; US3 the acceptance on both codes and the docs.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1, US2, US3
- Measurements (T002, T020, T023) run alone on the machine with Eastern start and end times in the validation log; no
  commit or suite while one runs; raw evidence under `runs/025-evidence/` (local, gitignored), small files copied to
  `specs/025-h4-wide-lens-razor-claw/evidence/`. Never pipe a gating command into `tail`.

## Path Conventions

- Package: `src/platsim/` (behaviour change: `platsim_code_hash` changes); `sim/` code untouched (`sim_code_hash` unchanged;
  one new test under `sim/test/`, excluded from the hash); ledger unchanged
- Tests: `tests/unit/`, `sim/test/`
- Feature scripts: `specs/025-h4-wide-lens-razor-claw/scripts/`; log: `specs/025-h4-wide-lens-razor-claw/validation-log.md`
- The B2 quick request: `platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2 --workers 16`

---

## Phase 1: Setup and the pre-feature side

**Purpose**: record today's behaviour while the branch's code still equals `main` (R8), before any code change.

- [X] T001 Create `specs/025-h4-wide-lens-razor-claw/scripts/`, `specs/025-h4-wide-lens-razor-claw/evidence/`, `runs/025-evidence/`; start `specs/025-h4-wide-lens-razor-claw/validation-log.md` with the branch point (`main` 3a91eac), the Eastern start time, `git diff --stat main -- src sim tests pyproject.toml` (must be empty) and the before-values of `sim_code_hash`, `platsim_code_hash` and the ledger version (only `platsim_code_hash` is expected to change)
- [X] T002 Write `specs/025-h4-wide-lens-razor-claw/scripts/acceptance.py --side main` adapted from `specs/024-variable-power-moves/scripts/acceptance.py` (R8): `assert_idle`; (a) B2 quick into `runs/025-evidence/b2-main` (`--force-new`, wall); (c) the two identity evaluations (`tests/fixtures/reference_team.json` and the 014 b2-main team written to `runs/025-evidence/teams/b2main.json`; `--runs 200 --budget quick --seed 025-ident`) into `runs/025-evidence/ident-main/{ref,b2main}`; the snapshot `specs/025-h4-wide-lens-razor-claw/evidence/candidates-main.json`: for B2's six species at the job's `prune.ref_level` and for every B1 to B5 member (`runs/bench-010/B*/result.json` species at their recorded levels) the `member_candidates` call arguments, `movesets`, `setup_moveset`, `ranked` (all), `pool`, `pruned`, `scores` and `items` per set; **run it now, alone** (about 12 min), log Eastern times and the code hashes from each result.json; commit `docs(025): pre-feature evidence (B2 quick on main's code, identity evaluations, candidate snapshot B2 and B1-B5)`; push

---

## Phase 2: Foundational

**Purpose**: the decomp-backed tables every story reads.

- [x] T003 `src/platsim/optimizer/candidates.py`: `CRIT_STAGE_RATES` parsed once from `pokeplatinum/src/battle/battle_lib.c` (`sCriticalStageRates`, the `type_chart()` parsing precedent, cached, a `ValueError` if the table is not found or has fewer than 5 entries), `HIGH_CRIT_EFFECTS` (every decomp effect constant containing `HIGH_CRITICAL`), `crit_stage(move, item_effect) -> int` (high-crit +1, `CRITRATE_UP` +1, cap 4) and `crit_term(stage) -> float` (`1 + 1 / CRIT_STAGE_RATES[stage]`); `EFFECT_COSTS: dict[str, str]` (the R5 list, each with its reason; the own-speed-drop constant for Hammer Arm looked up in `data/generated/moves.json`) and `effect_class(effect) -> "cost" | "plain" | "secondary"`; module doc citing `battle_lib.c:7097-7135`
- [x] T004 Write `tests/unit/test_h4_items.py` part 1: `CRIT_STAGE_RATES == (16, 8, 4, 3, 2)`; `crit_stage` for a plain move 0, Slash 1, Slash under `CRITRATE_UP` 2, cap 4; `crit_term(0) == 1.0625`, `crit_term(1) == 1.125`, `crit_term(2) == 1.25`; `effect_class` for Dig (cost), Earthquake (plain), Thunderbolt (secondary), Close Combat (cost), Overheat (cost); run `uv run pytest -q tests/unit/test_h4_items.py` (exit code kept) and record

**Checkpoint**: the tables exist and are pinned.

---

## Phase 3: User Story 1 - Wide Lens and Razor Claw offered, the lists kept honest (Priority: P1) 🎯 MVP

**Goal**: the two items by hold effect and copies, appended; the move value with the crit term and the item-conditioned
accuracy factor; item-conditioned extra sets; the widened dominance rule with controls; the screen's three kinds of appended
option beyond the cap; the model's switch reset pinned.

**Independent Test**: `tests/unit/test_h4_items.py` complete and green; `sim/test/switch_reset.test.mjs` green; the hand check
of quickstart step 3; the existing optimizer unit tests green.

- [x] T005 [US1] `candidates.py` `dominates(a, b)` (contracts, data-model.md): same type and category; `a.power >= b.power`, `acc(a) >= acc(b)` with accuracy 0 read as 101, `a.priority >= b.priority`, `a.pp >= b.pp`; effect: equal effects need `a.effect_chance >= b.effect_chance`; a cost loser loses to a plain or secondary winner; a plain loser loses to a secondary winner; two different secondaries or a cost winner: incomparable; strictly better on at least one of power, accuracy, priority, PP, effect; `prune` reasons become `dominated by <winner> (same type/category; at least as good on power, accuracy, priority, PP, effect; better: <axes>)`; the old `PLAIN`-only rule is removed (the new rule contains it); docstring citing the dominance assessment
- [x] T006 [US1] `tests/unit/test_h4_items.py` part 2 (FR-005): on the real move records, Dig dropped under Earthquake, Dive under Waterfall, Take Down under Rock Climb; Fire Blast vs Flamethrower, Close Combat vs Brick Break, Thunderbolt vs Discharge both kept; a constructed pair (two synthetic move records: same type/category/power/accuracy/priority/PP, one plain, one with `BATTLE_EFFECT_DEF_SPD_DOWN_HIT`) drops the self-dropping one; the pruned reason text names the winner and the axes; run and record
- [x] T007 [US1] `candidates.py` `move_value(const_member, move_const, member_level=100, item_effect=None)` (R2): the accuracy factor `min(1.0, acc * (100 + param) / 100)` under `HOLD_EFFECT_ACCURACY_UP` with `param` read from the item `extra_item_candidates` would offer for that effect (Wide Lens, 10), and 10 when the lookup yields nothing (a constant `ACCURACY_UP_PARAM_DEFAULT` with a comment), the crit term `crit_term(crit_stage(move, item_effect))` for every call, multiplied in after the power and accuracy factors (the pre-024 multiplication order kept for the other factors); every existing caller passes no `item_effect`
- [x] T008 [US1] `tests/unit/test_h4_items.py` part 3: `move_value` of Fire Blast (85 acc) under the lens equals the base value × (0.935/0.85) exactly; Stone Edge under the claw equals the base × (1.25/1.125); a plain move's base value carries the 1.0625 term (compare against a hand computation of the formula); run and record
- [x] T009 [US1] `candidates.py` `extra_item_candidates(const_member, moveset, led) -> list[str]` (R1): the `HOLD_EFFECT_ACCURACY_UP` item when any attack in the moveset (is_attack or offered variable) has `0 < accuracy < 100` and `_item_copies != 0`; then the `HOLD_EFFECT_CRITRATE_UP` item when the moveset has an attack and `_item_copies != 0` (Razor Claw 2; Scope Lens 0 never); `is_excluded_single_use` filter; `MemberCandidates` gains `items_extra: dict[moveset, list[str]]`, `item_extras: dict[moveset, str]`, `extras_by_kind: dict[str, int]`; `summary()` reports them; `held_item_candidates` unchanged
- [x] T010 [US1] `candidates.py` `member_candidates` item-conditioned extras (R3, FR-001a): after today's `chosen`, the 024 variable-power extras and the setup variant, for each conditioning effect in order (`HOLD_EFFECT_ACCURACY_UP` if any legal attack has `0 < accuracy < 100` and copies; `HOLD_EFFECT_CRITRATE_UP` if copies): `scores_i = {m: sum(move_value(const, m, level, item_effect=effect))}` over `attacks` (plus the offered variable moves), `pool_i` the top `POOL`, combos of 4 ranked by `(-coverage, -sum, combo)` with per-opponent values under the item, up to `k` sets in rank order that are not already in `movesets` and differ from the other sets of this kind by >= 2 moves; append each to `movesets` with `items[set] = [item] + held_item_candidates(...)` deduplicated and `item_extras[set] = item`; `items_extra[set] = extra_item_candidates(...)` for every base set and 024 extra set; `extras` counts all appended kinds, `extras_by_kind` splits them; the 024 extras unchanged
- [x] T011 [US1] `tests/unit/test_h4_items.py` part 4: on fixed movesets, the lens is appended only with a missing attack and the claw with any attack, Scope Lens never, order accuracy then crit; the rule, not an example: with constructed scores (a member whose lens-conditioned top set differs from today's sets) a lens-conditioned extra set exists and carries the lens first in its items, and with scores where the lens-conditioned top set equals today's set no extra is added (identical sets excluded); today's sets unchanged in membership in both cases; the hand check (T014) reports which real B2 members gain lens or claw extras; `extras_by_kind` sums to `extras`; `resources.repair` refuses a third Razor Claw on a synthetic six-member spec where three members ask for it (the 014 Expert Belt test's shape; it falls back to the next item); run and record
- [x] T012 [US1] `src/platsim/optimizer/run.py` (R4, FR-003): `_member_options` returns base sets × `items` only (the 024 extras and the item-conditioned extras excluded, as today for the 024 extras); `_member_extra_options(mcs) -> list[tuple[str, tuple]]` returns, per member in this order, `("variable_power", (v, ms, items[ms][0]))` for the 024 extras, `("accuracy_item" | "crit_item", (v, ms, item_extras[ms]))` for the item-conditioned extras, then `("item_deviation", (v, ms, it))` for every base set and 024 extra set × each `items_extra[ms]` item; the screen appends them all beyond the cap as single-slot deviations in that order, deduplicated and validated as today, and records `extras_screened` as a dict by kind (plus the total); provenance `heuristics` notes the appended-option rule
- [x] T013 [P] [US1] Write `sim/test/switch_reset.test.mjs` (FR-004a): using `makeContext` and `_internal.cloneState`/`doSwitch` on a League battle (the `sim/test/expectimax2.test.mjs` pattern), set non-zero boosts on the active member of the model state, switch to a bench member, and assert every stage of the outgoing and of the incoming member is 0; also assert a modelled replacement after a faint (`_internal` as exported) resets stages; run `(cd sim && node --test test/switch_reset.test.mjs)` and record; `sim/` code unchanged
- [x] T014 [US1] Hand check (quickstart step 3): print the six B2 species' lists on the branch into `runs/025-evidence/b2-candidates-branch.txt` (today's sets with any crit-term reorder, the 024 extras, the lens and claw extras with items, `items_extra`, the pruned map naming dominated moves), copy to `evidence/`; run `uv run pytest -q tests/unit/test_h4_items.py tests/unit/test_optimizer_candidates.py tests/unit/test_variable_power.py tests/unit/test_optimizer_resume.py tests/unit/test_required_hms.py -m "not battle_sim"` (exit code kept; the 024 prefix test is expected to fail on the crit term and is updated in T015), record
- [x] T015 [US1] Write `specs/025-h4-wide-lens-razor-claw/scripts/attribution.py`: `attribute(snapshot_member: dict, mc: MemberCandidates) -> list[dict]` returning one record per difference in `movesets`, `pool` and `ranked` with `cause` in {"dominated", "crit_term", "appended", "defect"} (removed moves must be in `mc.pruned` with a "dominated by" reason; added sets must be in `mc.item_extras` or the 024 extras or carry only `items_extra` items; membership or order changes among surviving moves are "crit_term" with the moves named; anything else "defect"); `tests/unit/test_variable_power.py`: the 024 prefix test becomes the attributed comparison against `specs/024-variable-power-moves/evidence/b2-candidates-main.json` through that helper (imported by path with the module registered in `sys.modules`, the 019 lesson) asserting no "defect" record across movesets, pool and ranked; the extras assertions unchanged; run and record; then the fast suite `uv run pytest -q -m "not battle_sim" > runs/025-evidence/fast.log 2>&1; echo exit=$?` (about 10 min); Commit 2 `feat(025): crit term and item-conditioned move value; Wide Lens and Razor Claw appended with item-conditioned extra sets; widened dominance rule with controls; screen appends three option kinds beyond the cap; switch-reset test`; push

**Checkpoint**: the items are offered with re-evaluation; the lists are honest; the screen is additive.

---

## Phase 4: User Story 2 - The reports state the average-Pokemon assumptions (Priority: P2)

**Goal**: `provenance.member_defaults` in every evaluate and optimize report.

**Independent Test**: the round trip and the xlsx row in `tests/unit/test_reports.py`; a pre-feature file reads without the block.

- [x] T016 [P] [US2] Write `src/platsim/report/provenance.py`: `member_defaults_block(team) -> dict` (`nature "Hardy"`, `ivs 15`, `evs 85`, `friendship 255`, `reason` "the average Pokemon a player has, not a bred or trained one (constitution v1.5.0)", `fixed_by_game`: species of `team.builds` whose `nature != DEFAULT_NATURE` or any IV `!= DEFAULT_IV` or any EV `!= DEFAULT_EV`; `[]` when `team` is None), reading the constants from `platsim.legality.models`
- [x] T017 [US2] `src/platsim/evaluate.py` `evaluate_team`: `provenance["member_defaults"] = member_defaults_block(team)`; `src/platsim/optimizer/run.py` `_optimizer_provenance`: the block for the winner's team through `extra` (and for `_no_qualifying` with `None`); `EvaluationReport.from_dict` unchanged (absent stays absent); `tests/unit/test_reports.py`: round trip with the block, a file without it reads without it, the xlsx provenance sheet shows a row whose key is `member_defaults`; run `uv run pytest -q tests/unit/test_reports.py` (exit code kept) and record; Commit 3 `feat(025): provenance.member_defaults (the average-Pokemon assumptions) in every report`; push

---

## Phase 5: User Story 3 - Not worse on B2, measured on both codes (Priority: P3)

**Goal**: the acceptance table on both codes; the attributed diff; the docs.

**Independent Test**: the table is complete; no "defect" line in the attributed diff; the identity rows identical once the
volatile fields and `member_defaults` are removed; the equal-levels row passes FR-010 or the cause is recorded and the merge
blocked.

- [x] T018 [P] [US3] `specs/025-h4-wide-lens-razor-claw/scripts/equal_levels.py`: the 024 script with master `025-equal|B2` and the same JSON output
- [x] T019 [US3] `acceptance.py --side branch` (R8): B2 quick into `runs/025-evidence/b2-branch`; the identity evaluations into `ident-branch/*` compared with `ident-main/*` after removing the volatile fields of 024 plus `provenance.member_defaults`; the screen overlap (how many of `b2-main/state.json` `screen.candidates` appear in `b2-branch`'s, by spec JSON; `extras_screened` by kind); the members of both winners holding Wide Lens or Razor Claw; `equal_levels.py runs/025-evidence/b2-main runs/025-evidence/b2-branch 2000`; the pass rule of 024's FR-009; the **attributed diff** per snapshot member through `scripts/attribution.py` (T015's helper, the same rule the unit test uses): recompute `member_candidates` with the recorded call arguments and list every record; a "defect" record prints `DEFECT` and sets exit 1; print the table and write `acceptance-branch.json`
- [x] T020 [US3] Acceptance run alone (about 20 min, Eastern times): `uv run python specs/025-h4-wide-lens-razor-claw/scripts/acceptance.py --side branch --workers 16 --runs 2000 > runs/025-evidence/acceptance.txt 2> runs/025-evidence/acceptance.err; echo exit=$?`; copy `acceptance.txt`, `acceptance-branch.json`, both winners' `result.json` and `team.txt`, the equal-levels JSON and the attributed diff to `specs/025-h4-wide-lens-razor-claw/evidence/acceptance/`
- [x] T021 [US3] If FR-010 fails or a `DEFECT` line appears: no merge; record the finding in the validation log and FUTURE-FEATURES section 0 and stop at the report to the user; if it passes: continue
- [x] T022 [US3] Validation log: the acceptance table with the reading (which members took which item, the lens or claw sets chosen or not, the screen overlap and appended counts, the equal-levels verdict, the attributed diff summary); README: the H4 block (the two items and why, the not-yet list with reasons, the item-conditioned re-evaluation and the crit term, the widened dominance rule and its controls, the assumptions block in reports), the optimizer's candidate description updated; FUTURE-FEATURES sections 0 (H4 done, next groups) and 8 (the dominance ride-along landed); RUN-STATE START HERE; Commit 4 `feat(025): acceptance (B2 quick on both codes, equal levels, attributed diff); docs`; push

---

## Phase 6: Gates and close

- [x] T023 Gates, in order, nothing else running: `git diff --stat main -- pokemon-showdown` empty and `git diff --stat main -- sim` only under `sim/test/`; after-values: `sim_code_hash` and the ledger version equal to T001's, `platsim_code_hash` different; `(cd sim && node --test test/*.test.mjs)` green; the full pytest suite `uv run pytest -q --durations=25 > runs/025-evidence/full.log 2>&1; echo full exit=$?` green (about 1 h 30 min); each output with Eastern times into the log; copy a gates summary to `specs/025-h4-wide-lens-razor-claw/evidence/gates.txt`
- [x] T024 Closing commit `docs(025): gates recorded; feature closed on its branch`; push; report to the user with the merge command (`git checkout main && git merge --ff-only 025-h4-wide-lens-razor-claw && git push`, or a merge commit if `main` moved). Merge only on the user's go

---

## Dependencies and execution order

- Phase 1 (T001 → T002, **before any code change**) → Phase 2 (T003 → T004) → US1 (T005 → T006 → T007 → T008 → T009 → T010
  → T011 → T012; T013 ∥ T009-T012; T014 → T015) → US2 (T016 → T017) → US3 (T018 ∥ T019 → T020 → T021 → T022) → T023 → T024.
- T002 must run while `git diff --stat main -- src sim tests pyproject.toml` is empty; T020 after T017's commit; no commit
  during T002, T020 or T023's measured steps.
- T021 blocks the feature on a failed FR-010 or a defect line (the user decides the next step).

## Parallel opportunities

- T013 ∥ T009-T012 (a Node test file); T016 ∥ T005-T015 (a new Python module); T018 ∥ T019.

## Implementation strategy

- MVP = Phase 2 + US1: the items and the honest lists, with the screen additive.
- US2 is independent and small; US3 measures everything in one run.
- Size: 24 tasks, three stories, two layers (candidates and screen; reports). Within the limits; R9's split point (US2) is
  not needed at this count.
