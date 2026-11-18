# Validation log: feature 027 Dead moves in the extra candidate sets

Branch `027-extras-dead-moves` from `main` 63d6329, main checkout. Times US Eastern.

## T001 Setup (11:47 AM EST, 2026-11-18)

`git diff --stat main -- src sim tests pyproject.toml`: 0 lines. Before-values:

```
sim_code_hash platsim_code_hash: sha256:e968ff0f403539460e6c0260db6253ad971d1a3eb7c02feaa8c9fbe393e74b7d sha256:844bb323589a59fa48de45af7403f93f48e053498a7e60c4dc956e3fcb69037e
divergence_ledger_version: sha256:feb2a48ef2e1dd08 (026's last result; unchanged since)
```

Scripts: `attribution.py` (new for 027: `record_of` stores base sets, their items, the setup set and every extra with kind,
item and dead moves under its own valuation; `attribute` makes any base-set, base-item or setup difference a defect, and an
offered extra keeping a dead move without a filler reason a defect; other extra changes are `extras_rule`),
`acceptance.py` (026's: evidence `runs/027-evidence`, identity seed `027-ident`, `member_notes` volatile, the snapshot
through the 027 helper, both timings (six members; the full team build with the allocation, SC-006); pass also requires 0
base defects, 0 dead moves in extras without a filler reason, and the team build within 10 s), `equal_levels.py` (master
`027-equal|B2`), `hand_check.py`. Positive control on today's code: the helper reports 34 dead moves in the six B2 members'
extras at level 48 and marks them as defects.

## T002 Pre-feature side (11:47:59 to 11:59:24 AM EST, alone, exit 0; code identical to `main` 63d6329)

- B2 quick on today's code: levels [52, 50, 50, 50, 51, 53], clear 0.9440 [0.9203, 0.961] (n 500, 2 attempts), wall 517.5 s:
  the same winner as feature 026's branch acceptance (same candidate code).
- Generation, B2 at the job's reference level 47: six members 1.2 s; the full team build with the allocation 4.7 s (SC-006
  baseline).
- Identity evaluations `ident-main/{ref,b2main}` (200 runs, quick, seed 027-ident).
- Snapshot `evidence/candidates-main.json`: 36 records; **324 extra sets, 208 dead moves under each set's own valuation, 140 sets
  with one, 29 members**: the SC-001 baseline (the same totals as the level-48 recount).

## T003 to T009 Code and controls (12:00 to 12:16 PM EST)

`candidates.py`: `choose_sets(..., exclude=, require=, stats=)` (defaults reproduce the base selection, tested);
variable-power extras through it under the plain valuation with `require` = a live offered variable move and `exclude` = the
base sets; item extras through it under the item valuation with `require` = a move the item changes (Wide Lens: one that can
miss; Razor Claw: any attack) and `exclude` = every set offered so far; `MemberCandidates.dead_moves` covers the extras under
their own valuation, `filler_reasons` per set, `dropped_extras` per kind short of `k`; `one_apart` includes extras accepted one
apart. `run._member_notes` reads the set's own filler reason first.

Two older tests updated to the rule (expected): `test_marginal_coverage` now expects `dead_moves` to cover every offered set;
`test_variable_power` accepts a member with an offered variable move but no variable-power extra when the shortfall is
recorded (Rotom: Return is never live beside Thunderbolt and Shadow Ball, so by the clarify decision the kind offers none).

Hand check (`evidence/b2-candidates-branch.txt`): Fire Punch in no B2 extra; Staraptor's and Rotom's extras keep fillers with the
026 reasons; Rotom offers no variable-power extra and two Wide Lens extras (both recorded in `dropped_extras`); Weavile offers no
Wide Lens extra (no move it learns can miss among its candidates; recorded). Generation at level 48: six members 1.7 s (1.2 s
before), the full team build with the allocation **6.8 s** (4.7 s before at level 47; SC-006 bound 10 s).

Offline attribution over the 36 snapshot members: **0 defects** (base sets, their items and setup sets unchanged), 255
`extras_rule` changes; extras 324 → 271; dead moves in extras **208 → 56, all 56 with a recorded filler reason** (0 without).

```
uv run pytest -q tests/unit/test_extras_dead_moves.py tests/unit/test_marginal_coverage.py tests/unit/test_h4_items.py tests/unit/test_variable_power.py tests/unit/test_optimizer_candidates.py tests/unit/test_reports.py tests/unit/test_optimizer_resume.py -m "not battle_sim"
  → 96 passed, exit 0
uv run pytest -q -m "not battle_sim" (12:05:23 to 12:16:27 PM EST) → 631 passed, 32 deselected, 4 xfailed, exit 0
```

## T010 Branch side (12:16:50 to 12:34:01 PM EST, alone, exit 0; on 583d824; copies in `evidence/acceptance/`)

| Measure | main (63d6329 code) | branch (583d824) |
|---|---|---|
| B2 quick winner | levels [52, 50, 50, 50, 51, 53], clear 0.9440 | **identical team, moves, items and levels**, clear 0.9440 |
| equal levels, 2,000 pairs | 0.9485 | 0.9485 (0 discordant pairs, verdict indistinguishable) |
| expected average final level | 51.69 | 51.69 |
| screened teams | 188 (107 extras) | 173 (92 extras: variable_power 14, accuracy_item 14, crit_item 18, item_deviation 46); overlap 145 of 188 |
| identity evaluations ref / b2main | | identical without volatile fields |
| attributed diff, 36 members | | 0 defects (base sets, items, setup sets unchanged) |
| dead moves in extra sets | 208 in 324 extras | 56 in 271, all with a recorded filler reason |
| generation (six members / team with allocation) | 1.2 s / 4.7 s | 1.7 s / 6.9 s (SC-006 bound 10 s) |

Reading: the extras now carry no dead move with a live replacement; 53 extras are no longer offered (duplicates, or a defining
variable move or item that adds nothing); the screen spends 15 fewer runs; the B2 winner does not use an extra set on either code,
so it is unchanged, as expected when only the extras change.

## T011 Merge gate: pass; continue.

## T013 Gates, run 1 (12:34:36 PM to 2:04:47 PM EST, on d46e707; `runs/027-evidence/gates-run1.txt`, `full-run1.log`)

Vendored and sim diffs empty; sim hash and ledger version unchanged; platsim hash changed; Node 384 pass. **Full pytest: 1 failed,
662 passed, 4 xfailed (1:27:21), exit 1**: `test_base_sets_items_and_setup_equal_the_pre_feature_snapshot` for `B1|SPECIES_GYARADOS`
(base sets and items differed); the same test passed alone and in the 96-test batch.

Diagnosis: the id-keyed caches (see the spec's "Defect found by the gates"). A direct test: 19,999 stale coverage reads in 20,000
trials. A recomputation of all 36 members with an identity-checked cache patched in at runtime: 0 base-set and 0 extra differences
from the current code in that process, and 0 from the pre-feature snapshot. The owner chose to fix it in this feature (option A).

Fix: `candidates._cov` entries hold `(table, coverage)` and are used only when the table is the same object; `allocation._USES_CACHE`
and `_LEGAL_CACHE` hold `(ledger, value)` likewise. Regression tests `test_coverage_cache_never_returns_a_stale_value` and
`test_allocation_caches_are_per_ledger_object` fail before the fix (2 failed) and pass after; the candidate batch 98 passed, exit 0.
Hand check rerun on the fixed code (`evidence/b2-candidates-branch.txt`). Next: the branch acceptance and the full suite on the
fixed code.

## T010 Branch side, run 2 on the fixed code (2:11:35 to 2:29:14 PM EST, alone, exit 0; on c4977a3)

Every measurement reproduced run 1: the B2 winner identical (levels [52, 50, 50, 50, 51, 53], clear 0.9440), equal levels 0.9485
vs 0.9485 with 0 discordant pairs, identity rows identical, 0 defects, dead moves in extras 208 → 56 all with filler reasons,
extras 324 → 271, screen 173 teams. Team build with the allocation 7.3 s (bound 10 s). Merge gate: pass.

## T013 Gates, run 2 (2:29:36 to 3:57:10 PM EST, nothing else running except read-only assessment notes; on 83aef9c)

```
git diff --stat main -- pokemon-showdown: 0 lines; -- sim: 0 lines
sim_code_hash after:     sha256:e968ff0f403539460e6c0260db6253ad971d1a3eb7c02feaa8c9fbe393e74b7d  (= T001)
platsim_code_hash after: sha256:6dba14967a6a37f0cbaa614ab7bd2bb3b84acdab302f7b471ffbfbe43a6ab454  (was 844bb323...: pre-027 checkpoints are refused)
divergence_ledger_version after: sha256:feb2a48ef2e1dd08  (= T001)
(cd sim && node --test test/*.test.mjs): tests 384, pass 384, fail 0, exit 0
uv run pytest -q --durations=25 (2:32:15 to 3:57:10 PM EST): 665 passed, 4 xfailed, 1 warning in 5091.80s (1:24:51), exit 0
```

The suite grew from 655 to 665 passed (the 10 tests of `test_extras_dead_moves.py`); the base-set pin that failed in run 1 passes.
During this run the owner's `precomputed-movesets` assessment wrote notes under `.specify/assessments/` (file reads and one light
species count; no timing measurement). **All gates green on the final code; the feature is closed on its branch. Merge on the
user's go.**

## T014 Close

Merge: `git checkout main && git merge --ff-only 027-extras-dead-moves && git push` (`main` at 63d6329 has not moved).
