# Tasks: Candidate sets by marginal coverage

**Input**: `specs/026-marginal-coverage-sets/` (spec.md, plan.md, research.md R1 to R8, data-model.md, contracts/, quickstart.md)

**Branch**: `026-marginal-coverage-sets` from `main` 7c466ae, main checkout. Times US Eastern. Measurements run alone
(`pgrep -a -x node; pgrep -a pytest` empty); never pipe a gating command into `tail`; never amend or force-push; evidence under
`runs/026-evidence/` (local) with small copies under `specs/026-marginal-coverage-sets/evidence/`.

**Tests**: requested by the spec (named controls, the attributed comparison, the report round trip); written beside the code.

## Phase 1: Setup (pre-feature evidence, before any code change)

- [ ] T001 Start `specs/026-marginal-coverage-sets/validation-log.md` (before-values: `platsim.version.sim_code_hash()`,
      `platsim_code_hash()`, the ledger version from a result; `git diff --stat main -- src sim tests pyproject.toml` must be
      empty) and write the scripts under `specs/026-marginal-coverage-sets/scripts/`: `acceptance.py` (025's with `EVIDENCE =
      runs/026-evidence`, `IDENT_SEED = "026-ident"`, no `NEW_ITEMS` table; the snapshot records per member and per set the dead
      moves computed by the helper; the branch side adds the dead-moves table, the allocation record from `b2-branch/state.json`
      `stages.prune.allocation`, the count of `baseline_repairs` and of screen `dropped` reasons containing "repair" (expected 0),
      and `pass` also requires 0 defects and 0 baseline repairs), `attribution.py` (025's plus R5: its own greedy marginal pool and
      score pool recomputed from the snapshot's call with `C.move_value`/`C.coverage`, cause `marginal_pool` for a pool entrant
      with positive marginal gain to the pool before it and a pool leaver with zero marginal to the new pool, a set change whose
      moves lie in the new pool and that removed a dead move or is in `mc.one_apart`; `dead_table(snapshot, mcs)` before/after;
      everything else as 025), `equal_levels.py` (master `026-equal|B2`), `hand_check.py` (025's plus dead moves per set,
      `no_live_reason`, `one_apart`, and the allocation record of the B2 team at level 48 via `run._build_cands`)
- [ ] T002 Run the pre-feature side alone (about 10 min): `uv run python specs/026-marginal-coverage-sets/scripts/acceptance.py --side main --workers 16 > runs/026-evidence/acceptance-main.txt 2> runs/026-evidence/acceptance-main.err; echo exit=$?`
      → `runs/026-evidence/b2-main`, `ident-main/{ref,b2main}`, `specs/026-marginal-coverage-sets/evidence/candidates-main.json`
      (36 members with dead moves per set) and the candidate-generation time for the six B2 species on today's code (SC-006,
      printed by the script); copy `acceptance-main.txt/json`, the winner's `result.json`/`team.txt` to `evidence/pre/`; record
      in the log; Commit 1 `docs(026): pre-feature evidence and scripts`; push

**Checkpoint**: the comparison baseline exists on today's code.

---

## Phase 2: Foundational (definitions every story uses)

- [ ] T003 `src/platsim/optimizer/candidates.py` (contracts/candidates-marginal.md, data-model.md): `marginal(move, moveset,
      vals) -> float`, `dead_moves(moveset, vals) -> list[str]`, `live_moves(cands, vals, scores) -> list[str]` (best against at
      least one opponent given the top two by score), `takeover(move, moveset, vals) -> set[int]` (opponent indexes where it
      becomes the best), `_prefer_cost_free(candidates, moveset, vals, scores) -> str | None` (R3: the best cost move only if its
      takeover has an opponent no cost-free candidate takes over, else the best cost-free; ties by score then name; `effect_class`
      from 025); `MemberCandidates` fields `dead_moves: dict[tuple, list[str]]`, `no_live_reason: str | None`, `one_apart:
      list[tuple]`, `unavailable: frozenset[str]`, in `summary()`
- [ ] T004 [P] `tests/unit/test_marginal_coverage.py` part 1 (synthetic `vals` over three opponents): `marginal` and `dead_moves`
      on a redundant pair, `live_moves` with a weaker other-type move that is best against one opponent, `takeover`, the cost
      preference (a cost move with the same takeover loses; a cost move with an extra opponent wins); run and record

**Checkpoint**: the definitions are pinned.

---

## Phase 3: User Story 1 - Every offered slot earns its place (Priority: P1) 🎯 MVP

**Goal**: the marginal pool, the ranking, the dead-move rule with the one-apart relaxation, the extras under the same rule, the
filler-move note in the report.

**Independent Test**: the named controls on the six B2 species at level 48; the synthetic member; the report round trip.

- [ ] T005 [US1] `candidates.py` `pool_by_marginal(cands, vals, scores, size=POOL)` (R1): first by score; each next by the largest
      `coverage(pool + [m]) - coverage(pool)` with the cost preference, ties by score then name; `tests/unit/test_marginal_coverage.py`
      part 2: a synthetic member whose ten highest scores are one type while a weaker other-type move is best somewhere (the
      marginal pool holds it, the score pool does not); Solar Beam-like cost move not taken when a cost-free move has the same
      takeover, taken when nothing cost-free covers its opponent; run and record
- [ ] T006 [US1] `candidates.py` `rank_sets(pool, vals, scores, size=4)` key `(-coverage, -Σ marginal, -Σ score, combo)` and
      `choose_sets(ranked, k, cands, vals, scores) -> (sets, one_apart, no_live_reason)` (R2: per combo replace each dead move by
      the legal move with the highest marginal given the other three with the cost preference, re-checking; pass 1 all-live and
      two apart; pass 2 all-live one apart; pass 3 sets with dead moves two apart with the reason "no better option: the two
      strongest moves cover every League opponent"; duplicates skipped; deterministic); `tests/unit/test_marginal_coverage.py`
      part 3 on synthetic values: five live moves give three all-live sets with `one_apart` non-empty; nothing live gives
      today's sets and the reason; a dead move replaced from outside the pool; run and record
- [ ] T007 [US1] `candidates.py` `member_candidates(const, variant, ref_level, led, k=K_MOVESETS, team=None, unavailable=frozenset())`:
      `legal` minus `unavailable`; `cands = attacks + variable` with one `scores`/`vals` table; `pool = pool_by_marginal(...)`;
      `ranked = rank_sets(...)`; `chosen, one_apart, reason = choose_sets(...)`; the setup set from the best three by coverage with
      the dead-move replacement among them; the 024 variable extras over the marginal pool ∪ variable moves (at least one variable
      move, not already offered, diverse among themselves) and the 025 item-conditioned extras with a marginal pool under the item
      valuation and `rank_sets`; `dead_moves` per offered set; fields filled; `extra_item_candidates`, `held_item_candidates`,
      `prune`, `dominates`, `move_value` unchanged
- [ ] T008 [US1] `tests/unit/test_marginal_coverage.py` part 4, real members (B2 species at level 48 with `team=`): Infernape no
      Fire Punch in any offered set, no dead move, Grass Knot in an offered set, three sets with `one_apart` non-empty, Solar Beam
      not offered; Floatzel and Weavile: Brick Break in the pool and in an offered set, no dead move; Rotom: sets equal the
      pre-feature snapshot's (`evidence/candidates-main.json`), `no_live_reason` set; Garchomp and Staraptor: sets equal the
      snapshot's; every B2 member: `extras_by_kind` sums to `extras`, each 025 item-conditioned set starts with its item; run
      and record
- [ ] T009 [US1] Update the pinned tests: `tests/unit/test_optimizer_candidates.py` (the set bounds, any pinned set), `tests/unit/test_variable_power.py`
      (the attributed comparison against `specs/024-variable-power-moves/evidence/b2-candidates-main.json` imports
      `specs/026-marginal-coverage-sets/scripts/attribution.py` by path, registered in `sys.modules`; 0 defects; the extras
      assertions per kind), `tests/unit/test_h4_items.py` (item-conditioned extras on B2 still hold; pins that named a set
      updated to the rule); run `uv run pytest -q tests/unit/test_marginal_coverage.py tests/unit/test_optimizer_candidates.py tests/unit/test_variable_power.py tests/unit/test_h4_items.py -m "not battle_sim"` (exit code kept) and record
- [ ] T010 [US1] Hand check: `uv run python specs/026-marginal-coverage-sets/scripts/hand_check.py > runs/026-evidence/b2-candidates-branch.txt`
      (sets, pools, dead moves per set, `one_apart`, `no_live_reason`, the candidate-generation time for the six B2 species
      against T002's, SC-006; copy to `evidence/`); read it against the spec's Overview table and record; then the fast suite `uv run pytest -q -m "not battle_sim" > runs/026-evidence/fast.log 2>&1; echo exit=$?`;
      Commit 2 `feat(026): candidate pool and sets by marginal coverage; dead-move rule with the one-apart relaxation; cost preference; extras under the same rule`; push
- [ ] T011 [P] [US1] Report note (contracts/report-filler-note.md): `src/platsim/report/json_report.py` `EvaluationReport.member_notes:
      list[str]` default `[]`, `from_dict` tolerant; `src/platsim/report/team_txt.py` appends a blank line and a `Notes:` block
      when notes exist; `src/platsim/legality/models.py` `import_team` skips a block whose first line starts with `Notes:`;
      `src/platsim/evaluate.py` `summary_text` prints the notes after the per-battle lines; `src/platsim/report/xlsx.py` Team sheet
      gains a Note column; `tests/unit/test_reports.py`: round trip with notes, a pre-026 file reads with `[]`, `import_team(team_text(r))`
      still equals the builds' sets with a note present, the xlsx column, the summary line; run `uv run pytest -q tests/unit/test_reports.py -m "not battle_sim"` and record
- [ ] T012 [US1] `src/platsim/optimizer/run.py`: the winner's `member_notes` from each member's `MemberCandidates.no_live_reason`
      for its chosen set ("<Name>: <moves> are filler: no better option, its two strongest moves cover every League opponent"),
      set on the report before `write_all`; `_no_qualifying` none; a fake-pool test in `tests/unit/test_marginal_coverage.py`
      asserts the note for a member whose chosen set carries dead moves; run and record; Commit 3 `feat(026): filler-move note in the player-facing report`; push

**Checkpoint**: every offered set is all-live or explained; the user is told.

---

## Phase 4: User Story 3 - Offered sets the team can actually build (Priority: P3)

**Goal**: contested single-copy resources allocated by coverage gained; lists rebuilt without lost resources; zero repair
notes for the baseline. (Ordered before story 2 so the acceptance measures the whole feature; split rule of plan R8.)

**Independent Test**: the B2 team's allocation record (TM26, TM71), Infernape rebuilt with a live move it can learn, zero
baseline repairs; a no-contest team equal to member-by-member lists.

- [ ] T013 [US3] Write `src/platsim/optimizer/allocation.py` (contracts/allocation.md, R6): `needs(species, variant, moveset,
      level, led) -> dict[str, int]` (the cheapest `movesources.sources` choice per move whose `uses_of` is affordable alone; a
      resource-free source needs nothing; HMs never counted, the game never consumes them), `contested(cands, consts, level,
      led) -> dict[str, list[int]]` (members whose first set needs the resource, when more than `resources.copies`),
      `remaining(cands, consts, level, led) -> dict[str, int]` (copies left after every first set is charged),
      `allocate(consts, variants, ref_level, led, cands) -> (cands, record)`: step 1, gain per contender = coverage of its
      first set minus the coverage of its best all-live set with the resource's moves `unavailable`; the top `copies` by gain
      (ties by slot) keep it; the others' `unavailable` extended and `member_candidates` rebuilt; step 2 (R6 3b), moves needing
      a resource with zero copies left charged to other members' first sets become `unavailable` for that member; rebuild; loop
      to step 1 until no first set changes, bounded by the number of single-copy resources; `record` per resource `{copies,
      contenders: [[species, gain]], given_to, rebuilt, unavailable: {species: [moves]}}`
- [ ] T014 [US3] `src/platsim/optimizer/run.py`: `_build_cands` returns `(cands, allocation)` through `allocate`; the prune stage
      stores `allocation`; `_optimizer_provenance` carries it (`extra`); `checkpoint` fingerprint unchanged in shape
- [ ] T015 [US3] `tests/unit/test_marginal_coverage.py` part 5: the B2 team at level 48: `allocation` names TM26 and TM71 with
      Garchomp and Infernape as contenders and gains, the loser rebuilt, Infernape's offered sets containing a live move it can
      learn on that team; for every member and every one of its offered sets (today's, the 024 extras, the 025 item-conditioned
      sets, the setup set) `resources.realize` of that set with the other five members' first sets at level 48 is not a Refusal
      and `resources.repair` on each such deviation returns no notes; the record shows which Infernape moves became
      unavailable and that no first set changed on the last loop; a team with no contested resource gives lists equal to
      member-by-member; a synthetic two-member case where the lower slot wins a TM on gain; run and record; Commit 4 `feat(026): contested single-copy resources allocated by coverage gained; lists rebuilt`; push

**Checkpoint**: the screen's sets are the sets a player can teach.

---

## Phase 5: User Story 2 - Not worse on B2, measured on both codes (Priority: P2)

**Goal**: the acceptance table on both codes; the attributed diff with `marginal_pool` verified; the dead-moves table; docs.

**Independent Test**: the table complete; no `defect`; identity rows identical; zero baseline repairs; FR-012 passes or the
merge is blocked with the cause recorded.

- [ ] T016 [US2] Run the branch side alone (about 20 min): `uv run python specs/026-marginal-coverage-sets/scripts/acceptance.py --side branch --workers 16 --runs 2000 > runs/026-evidence/acceptance.txt 2> runs/026-evidence/acceptance.err; echo exit=$?`;
      copy `acceptance.txt`, `acceptance-branch.json`, both winners' `result.json`/`team.txt` to `evidence/acceptance/`
- [ ] T017 [US2] FR-012 gate: a supported loss at equal levels, a level diff above 1.0, a `DEFECT` line or a baseline repair:
      no merge, record in the validation log and FUTURE-FEATURES, stop at the report to the user; else continue
- [ ] T018 [US2] Docs: validation log (the acceptance table and reading: dead moves before and after, the allocation, the winner's
      Infernape set, the equal-levels verdict, the identity rows, the attributed diff summary); `README.md` (the candidate
      description: pool by marginal coverage, the dead-move rule and the no-live-move exception with the report note, the
      team-aware allocation; the 026 block with the acceptance); `FUTURE-FEATURES.md` (section 6 entry closed; the cross-category
      user-conditioned dominance idea recorded as considered and not chosen; the defence-aware value as a later idea); `RUN-STATE.md`
      START HERE; Commit 5 `feat(026): acceptance (B2 quick on both codes, equal levels, attributed diff, allocation); docs`; push

---

## Phase 6: Gates and close

- [ ] T019 Gates, nothing else running: `git diff --stat main -- pokemon-showdown` empty and `git diff --stat main -- sim` empty;
      `sim_code_hash` and the ledger version equal to T001's, `platsim_code_hash` different; `(cd sim && node --test test/*.test.mjs)`
      green; `uv run pytest -q --durations=25 > runs/026-evidence/full.log 2>&1; echo full exit=$?` green (about 1 h 45 min);
      outputs with Eastern times into the log and `evidence/gates.txt`
- [ ] T020 Closing commit `docs(026): gates recorded; feature closed on its branch`; push; report with the merge command
      (`git checkout main && git merge --ff-only 026-marginal-coverage-sets && git push`). Merge only on the user's go

## Dependencies

- Phase 1 (T001 → T002, **before any code change**) → Phase 2 (T003 → T004) → US1 (T005 → T006 → T007 → T008 → T009 → T010;
  T011 ∥ T005-T010; T012 after T007 and T011) → US3 (T013 → T014 → T015) → US2 (T016 → T017 → T018) → T019 → T020.
- T002 must run while `git diff --stat main -- src sim tests pyproject.toml` is empty; T016 after T015's commit; no commit
  during T002, T016 or T019's measured steps.
- Split rule (plan R8): if T013 needs changes in `resources.realize`/`repair`, stop after T012, move T013-T015 to feature 027,
  and run T016-T020 on stories 1 and 2 with the B2 limitation recorded.

## Parallel opportunities

- T004 ∥ T003's review; T011 (report files) ∥ T005-T010 (candidates); T001's four scripts are independent files.

## Implementation strategy

- MVP = Phase 2 + US1 (T003-T012): the lists are honest and the user is told.
- US3 is one new module plus a call site; US2 measures everything once, after US3.
- Size: 20 tasks, three stories, two layers plus a report line; within the limits with the split rule in place.
