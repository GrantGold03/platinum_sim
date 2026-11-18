# Tasks: Dead moves in the extra candidate sets

**Input**: `specs/027-extras-dead-moves/` (spec.md, plan.md, research.md R1 to R5, data-model.md, contracts/, quickstart.md)

**Branch**: `027-extras-dead-moves` from `main` 63d6329, main checkout. Times US Eastern. Measurements alone (`pgrep -a -x node;
pgrep -a pytest` empty); never pipe a gating command into `tail`; never amend or force-push; never edit `src/` while an
acceptance or suite runs; evidence under `runs/027-evidence/` (local) with small copies under `specs/027-extras-dead-moves/evidence/`.

**Tests**: requested by the spec (named controls, base sets byte-identical, the attributed comparison).

## Phase 1: Setup (pre-feature evidence, before any code change)

- [ ] T001 Start `specs/027-extras-dead-moves/validation-log.md` (before-values: `sim_code_hash`, `platsim_code_hash`, the ledger
      version; `git diff --stat main -- src sim tests pyproject.toml` empty) and adapt 026's scripts into
      `specs/027-extras-dead-moves/scripts/`: `acceptance.py` (`runs/027-evidence`, identity seed `027-ident`, `member_notes` among
      the volatile fields; the snapshot records per extra set its kind, item and dead moves under its own valuation, using the
      logic of `evidence/pre/extras_dead_probe.py`; the branch side prints the dead-moves-in-extras table and pass also requires
      0 base-set defects and 0 dead moves in extras outside sets with a recorded filler), `attribution.py` (026's plus: any base
      set, base-set item list or setup set difference is `defect`; extra-set differences are `extras_rule` when the branch's
      extra is all-live under its own valuation or carries a `filler_reasons` entry, else `defect`), `equal_levels.py` (master
      `027-equal|B2`), `hand_check.py` (each B2 member's extras with kind, item, dead moves under own valuation,
      `dropped_extras`, the generation time of `member_candidates` for six and of the full team build with the allocation,
      `run._build_cands`, SC-006); `acceptance.py` also times the full team build on both sides
- [ ] T002 Run the pre-feature side alone (about 10 min): `uv run python specs/027-extras-dead-moves/scripts/acceptance.py --side main --workers 16 > runs/027-evidence/acceptance-main.txt 2> runs/027-evidence/acceptance-main.err; echo exit=$?`;
      copy the outputs, the winner's `result.json`/`team.txt` and the snapshot to `evidence/pre/`; log; Commit 1
      `docs(027): pre-feature evidence and scripts`; push

**Checkpoint**: the baseline exists on today's code.

---

## Phase 2: Foundational

- [ ] T003 `src/platsim/optimizer/candidates.py` `choose_sets(ranked, k, cands, vals, scores, cost_tier=None, exclude=frozenset(), require=None)`
      (R1): repaired sets in `exclude` are skipped and sets for which `require(set)` is false are never accepted; omitted
      arguments reproduce today's behaviour exactly
- [ ] T004 [P] `tests/unit/test_extras_dead_moves.py` part 1: on 026's synthetic values, `choose_sets` with defaults equals the
      call without the new arguments; `exclude` skips a set the repair produces; `require` rejects a set; run and record

---

## Phase 3: User Story 1 - Extra sets earn their slots too (Priority: P1) 🎯 MVP

**Goal**: every extra set all-live under its own valuation or carrying a recorded filler; dead-defining extras dropped.

**Independent Test**: the B2 controls at level 48 and the base sets byte-identical to 026's snapshot.

- [ ] T005 [US1] `candidates.py` `member_candidates`: variable-power extras via `choose_sets(ranked_extra, k, cands, vals, scores, exclude=frozenset(chosen), require=has_live_variable)`
      where `has_live_variable(s)` ⇔ an offered variable move in `s` is not in `dead_moves(s, vals)`; item extras per
      conditioning item via `choose_sets(rank_sets(pool_i, vals_i, sc_i, 4), k, cands, vals_i, sc_i, exclude=frozenset(chosen + extras + picked so far), require=item_matters)`
      where `item_matters(s)` ⇔ Wide Lens: a move in `s` with 0 < accuracy < 100; Razor Claw: a damaging move in `s`; kinds,
      items, order and `extra_kind` as today
- [ ] T006 [US1] `candidates.py` `MemberCandidates`: `dead_moves` covers every offered extra under its own valuation (item-valued
      for item sets); `filler_reasons: dict[tuple, str]` for every offered set with a dead move (026's reason text);
      `dropped_extras: dict[str, dict]` per kind offered fewer than `k`, `{"offered": n, "reason": "no further set whose variable move is live" | "no further set the item changes" | "only duplicates of offered sets remain"}`;
      `one_apart` also lists extras accepted one apart; `summary()` adds `filler_reasons` and `dropped_extras`; `no_live_reason`
      unchanged (base sets)
- [ ] T007 [US1] `src/platsim/optimizer/run.py` `_member_notes`: the chosen set's `filler_reasons` entry from the prune-stage
      summary, else `no_live_reason` (026 behaviour)
- [ ] T008 [US1] `tests/unit/test_extras_dead_moves.py` part 2: B2 at level 48: Infernape's extras contain no Fire Punch and no
      dead move with a live replacement (own valuation); every Garchomp variable-power extra carries a live variable move; a
      synthetic member whose repaired extra duplicates a base set gets it excluded and the shortfall recorded; a synthetic
      filler extra carries its `filler_reasons` entry; every record of this feature's pre-feature snapshot
      `specs/027-extras-dead-moves/evidence/candidates-main.json` (T002, today's code; 36 members), recomputed with its stored
      call arguments (B2 at the quick job's reference level, not a fixed 48), has base sets, base-set items and setup set equal
      to the snapshot's; `_member_notes`
      uses a set's own filler reason; run with `test_marginal_coverage.py test_h4_items.py test_variable_power.py test_optimizer_candidates.py`
      (exit code kept) and record
- [ ] T009 [US1] Hand check `uv run python specs/027-extras-dead-moves/scripts/hand_check.py > runs/027-evidence/b2-candidates-branch.txt`
      (copy to `evidence/`; both timings against T002's, SC-006 at most 10 s with the allocation), the offline attributed diff
      over the 36 members (0 defects; dead moves in extras before/after, the before count from the T002 snapshot, SC-001), the
      fast suite `uv run pytest -q -m "not battle_sim" > runs/027-evidence/fast.log 2>&1; echo exit=$?`; log; Commit 2
      `feat(027): extra sets under the dead-move rule; dead-defining extras dropped; per-set filler reasons`; push

**Checkpoint**: every set the tool can recommend earns its moves.

---

## Phase 4: User Story 2 - Not worse on B2, measured on both codes (Priority: P2)

- [ ] T010 [US2] Branch side alone (about 20 min): `uv run python specs/027-extras-dead-moves/scripts/acceptance.py --side branch --workers 16 --runs 2000 > runs/027-evidence/acceptance.txt 2> runs/027-evidence/acceptance.err; echo exit=$?`;
      copy outputs and both winners' `result.json`/`team.txt` to `evidence/acceptance/`
- [ ] T011 [US2] Merge gate (FR-010): a supported loss, a level diff above 1.0, a defect, a base-set difference or a dead move in
      an extra without a recorded filler: no merge, record and stop at the report to the user; else continue
- [ ] T012 [US2] Docs: validation log (the acceptance table and reading); `README.md` (026 block: the dead-move rule now covers the
      extras; a 027 block with the acceptance); `FUTURE-FEATURES.md` (section 6: the extras item closed); `RUN-STATE.md`; Commit 3
      `feat(027): acceptance (B2 quick on both codes, equal levels, attributed diff); docs`; push

---

## Phase 5: Gates and close

- [ ] T013 Gates, nothing else running: `git diff --stat main -- pokemon-showdown` and `-- sim` empty; sim hash and ledger version
      equal to T001's, platsim hash changed; `(cd sim && node --test test/*.test.mjs)` green; `uv run pytest -q --durations=25 > runs/027-evidence/full.log 2>&1; echo full exit=$?`
      green (about 1 h 25 min); into the log and `evidence/gates.txt`
- [ ] T014 Closing commit `docs(027): gates recorded; feature closed on its branch`; push; report with the merge command
      (`git checkout main && git merge --ff-only 027-extras-dead-moves && git push`); merge only on the user's go

## Dependencies

- T001 → T002 (**before any code change**) → T003 → T004 → US1 (T005 → T006 → T007 → T008 → T009) → US2 (T010 → T011 → T012) →
  T013 → T014. No commit during T002, T010 or T013's measured steps.

## Parallel opportunities

- T004 beside T003's review; T001's four scripts are independent files; T007 (run.py) beside T005-T006 (candidates.py).

## Implementation strategy

- MVP = Phase 2 + US1; US2 measures once. Size: 14 tasks, two stories, one layer.
