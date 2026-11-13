# Validation log: feature 025 H4, Wide Lens and Razor Claw

Branch `025-h4-wide-lens-razor-claw` from `main` 3a91eac, main checkout. Times US Eastern.

## T001 Setup (12:54 PM EST)

`git diff --stat main -- src sim tests pyproject.toml` lines: 0 (the branch's code equals `main`, so the pre-feature side can
run here). Before-values (only `platsim_code_hash` is expected to change; `sim/` gains a test file only, outside the hash):

```
sim_code_hash platsim_code_hash: sha256:e968ff0f403539460e6c0260db6253ad971d1a3eb7c02feaa8c9fbe393e74b7d sha256:eb92dee26412cbc7226f65d030a30df0a914b267f9506a67fa78064246edde42
divergence_ledger_version: sha256:feb2a48ef2e1dd08
```

## T002 Pre-feature side (12:55:39 to 1:04:39 PM EST, alone, exit 0; code identical to `main`)

`acceptance.py --side main --workers 16` (adapted from 024's; evidence `runs/025-evidence/`, copies in `evidence/pre/`):

- B2 quick on today's code (`runs/025-evidence/b2-main`): species ['garchomp', 'infernape', 'staraptor', 'rotom', 'floatzel', 'weavile'], levels [51, 52, 52, 53, 52, 53], clear 0.9300
  [0.9042, 0.9492] (n 500, 2 attempts), expected average final level
  52.79, wall 380.4 s, no member holds Wide Lens or Razor Claw (as expected). Code
  `platsim_code_hash` sha256:eb92dee26412..., `repo_commit` 741f519cd379. The same winner, levels and clear rate as
  feature 024's acceptance of this job.
- Identity evaluations `ident-main/{ref,b2main}` (200 runs, quick, seed 025-ident) for the comparison after the code change.
- Snapshot `evidence/candidates-main.json`: 36 member variants (B2's six at reference level 48; every B1 to B5 member at its
  recorded level) with the call arguments, movesets, setup, the full ranked list, pool, pruned map, scores and items per set.


## T003 to T012 Code (1:10 to 2:05 PM EST)

`candidates.py`: `CRIT_STAGE_RATES` parsed from `battle_lib.c` `sCriticalStageRates` by name = (16, 8, 4, 3, 2);
`crit_stage(move, item_effect)` (high-critical effect +1, `HOLD_EFFECT_CRITRATE_UP` +1, cap 4), `crit_term(stage) = 1 + 1/rate`;
`EFFECT_COSTS` (28 effect constants, each with a reason; Hammer Arm's own-speed drop is `BATTLE_EFFECT_SPEED_DOWN_HIT`),
`effect_class` → cost | plain | secondary. `dominance_axes`/`dominates`: same type and category; power, accuracy (0 → 101),
priority, PP at least as good; effect by class with equal effects compared on `effect_chance`; strictly better on one axis;
`prune` reasons name the winner and the better axes. `move_value(..., item_effect=None)`: lens accuracy factor
`min(1, acc × (100 + param)/100)` with the param read from the data's ACCURACY_UP item (Wide Lens, 10); the crit term multiplied
last so fixed-power values keep 024's multiplication order. `extra_item_candidates` (lens when an attack has 0 < accuracy < 100,
claw when any attack; copies and the single-use filter; the item of an effect chosen unlimited-first, then by key, so Scope Lens
with 0 copies is never offered). `member_candidates`: item-conditioned extra sets per conditioning effect (lens if any legal
attack can miss, claw always, each only with copies): attacks and offered variable moves re-valued under the item, a pool of
`POOL`, combos ranked as today, up to `k` sets not already offered and diverse among that kind, each with `items[set] = [item] +
usual`; `item_extras`, `items_extra` (base and 024 sets), `extra_kind`, `extras_by_kind`; `extras` counts all appended kinds.
`run.py`: `EXTRA_KINDS`, `_member_extra_options` yields `(kind, option)` in the order variable_power, accuracy_item, crit_item,
item_deviation; the screen records `extras_screened` as a dict by kind plus `total`; an item-conditioned set or item deviation
whose appended item the repair step takes away is dropped with a reason (the set with its usual item is a base candidate already).

Observations recorded for the log (not defects):
- Earthquake's effect in the data is `BATTLE_EFFECT_DOUBLE_DAMAGE_DIG` (a conditional bonus), so it is classed `secondary`, not
  plain; the test's plain control is Strength. Earthquake still dominates Dig (cost loser; better: power, effect).
- PP as an axis means the old R8 pair Cut (50/95/30 PP) over Tackle (35/95/35 PP) no longer drops Tackle: Tackle has more PP.
  The B2 pools are unaffected (neither is in a pool); recorded as the rule's consequence, not tuned around.
- Razor Claw is also Weavile's evolution item (Sneasel holds it): with Weavile on a team one of the two copies is consumed by the
  evolution, so only one held claw fits on such a team; `resources.realize` enforces this through the existing copies
  (`ITEM_RAZOR_CLAW` uses = 2 with one held claw). The third-claw unit test uses a no-Weavile team for the "two fit, three
  refused" case and asserts the Weavile case separately.
- Lens-conditioned extra sets are the next-best sets under the lens valuation not already offered; some contain no move that can
  miss (Floatzel's Waterfall / Surf / Ice Beam / Return), where the lens is harmless. FR-001a as specified; a "must contain a
  missable move" filter is a possible refinement (FUTURE-FEATURES).

## T004, T006, T008, T011 Unit tests (`tests/unit/test_h4_items.py`, 12 tests)

```
uv run pytest -q tests/unit/test_h4_items.py -m "not battle_sim"   → 12 passed, exit 0
```

## T013 Switch-reset test (`sim/test/switch_reset.test.mjs`; `sim/` code unchanged)

```
(cd sim && node --test test/switch_reset.test.mjs)   → tests 3, pass 3, fail 0, exit 0
```

## T014 Hand check (`evidence/b2-candidates-branch.txt`, script `scripts/hand_check.py`)

Every B2 member: today's 3 sets, then 9 extras {variable_power 3, accuracy_item 3, crit_item 3}; every set's `items_extra`
lists the lens only where an attack can miss (Staraptor's Aerial Ace / Close Combat / Secret Power / U-turn, Floatzel's and
Weavile's all-hitting sets: claw only). Pruned by the widened rule: Garchomp Dig (by Earthquake: power, effect) and Take Down
(by Rock Climb: effect), Infernape Dig, Floatzel Dive (by Waterfall: PP, effect); the three pairs of the dominance assessment.
Today's sets changed against the pre-feature snapshot for Garchomp (Shadow Claw, high crit, entered the pool; Fire Fang left),
Floatzel (Dive dominated; Crunch entered; the setup set takes Crunch) and Weavile (Shadow Claw entered; Brick Break left);
unchanged for Infernape, Staraptor, Rotom.

```
uv run pytest -q tests/unit/test_h4_items.py tests/unit/test_optimizer_candidates.py tests/unit/test_variable_power.py tests/unit/test_optimizer_resume.py tests/unit/test_required_hms.py -m "not battle_sim"
  first run: 3 failed, 55 passed (the 024 prefix test, as expected; the R8 synthetic move lacked `pp`; the appended-set bound 2K → 4K)
  after T015 and the two test updates: 58 passed, exit 0
```

## T015 Attribution helper and the 024 prefix test

`scripts/attribution.py` reads 024's snapshot shape too (`ranked_prefix`, no items) and attributes the setup set; a gone base
set is `crit_term` only where the pool changed or a high-crit move competes (a uniform stage-0 term moves nothing), a pool
entrant after a dominated exit is `dominated`. Against `specs/024-variable-power-moves/evidence/b2-candidates-main.json`:
Garchomp {moveset crit_term 2, pool crit_term 2, ranked crit_term 84}, Infernape {}, Staraptor {}, Rotom {},
Floatzel {moveset crit_term 6, setup dominated 1, pool dominated 2, ranked dominated 84}, Weavile {moveset crit_term 6, setup
crit_term 1, pool crit_term 2, ranked crit_term 84}; defects 0 for all six. `tests/unit/test_variable_power.py`: the prefix
test is now `test_todays_candidates_differ_from_024s_only_by_attributed_causes` (helper imported by path, registered in
`sys.modules`); its extras assertions kept per kind.

Fast suite (`runs/025-evidence/fast.log`, 1:25:48 to 1:35:50 PM EST):

```
601 passed, 32 deselected, 4 xfailed, 1 warning in 599.51s (0:09:59)
exit=0
```

## T016, T017 Provenance `member_defaults` (1:40 to 1:55 PM EST)

`src/platsim/report/provenance.py`: `member_defaults_block(team)` → {nature Hardy, ivs 15, evs 85, friendship 255, reason,
fixed_by_game} reading the constants from `legality/models.py`; friendship is pinned locally (255) with a test that it equals
`candidates.FRIENDSHIP`, because importing `candidates` from the report module made a circular import (`candidates` →
`optimizer.api` → `evaluate` → this module). `evaluate_team` sets `provenance["member_defaults"]`; `run.py` passes the block for
the winner's team through `_optimizer_provenance`'s `extra` and `None` for `_no_qualifying`; the optimizer's `heuristics` text
notes the appended-option rule (T012). `EvaluationReport.from_dict` unchanged: a pre-025 file reads without the block.

```
uv run pytest -q tests/unit/test_reports.py -m "not battle_sim"                              → 18 passed, exit 0
uv run pytest -q tests/unit/test_optimizer_resume.py tests/unit/test_required_hms.py -m "not battle_sim"   → 24 passed, exit 0
```

## T019, T020 Branch side, run 1 (1:39:29 to 1:54:13 PM EST, alone; `runs/025-evidence/acceptance-run1.txt`, exit 1)

`acceptance.py --side branch --workers 16 --runs 2000` on 1f894e5:

- B2 quick on the branch (`b2-branch`): same six species, levels [51, 52, 52, 52, 53, 53] (main [51, 52, 52, 53, 52, 53]: Rotom
  and Floatzel swap a level), clear 0.9380 [0.9133, 0.956] (n 500, 2 attempts), expected average final level 52.79 (main
  52.79), wall 428.5 s (main 380.4 s). **No member holds Wide Lens or Razor Claw** (the items are offered, not chosen on this
  team). The winner differs from main's on three members by the crit term's re-rank: Garchomp takes its setup set (Swords Dance
  for Aerial Ace), Floatzel Brine / Water Pulse for Blizzard / Ice Fang, Weavile Shadow Claw / X-Scissor for Avalanche / Brick Break.
- Screen: main 95 teams (81 + 14 extras), branch 170 (81 + 89 extras: variable_power 14, accuracy_item 15, crit_item 17,
  item_deviation 43); **overlap 0 of 95**: Floatzel's and Weavile's first sets changed under the crit term, every team carries
  both, so no screened team equals a main one by spec JSON (FR-003 expects the lists to differ; reported, not a gate).
- Equal levels at [51, 52, 52, 52, 53, 53], 2,000 pairs, expectimax2-v4: branch 0.9230 vs main 0.8855, only-branch 209 /
  only-main 134, p 6.06e-05, **verdict A (branch better)**; mean final level 52.79 vs 52.81; level diff 0.00.
- Identity evaluations (`ident-branch/{ref,b2main}` vs `ident-main`): both **identical** once the volatile fields are removed
  (`sim_code_hash`, `platsim_code_hash`, `repo_commit`, `repo_dirty`, `divergence_ledger_version`, `divergences`,
  `provenance.divergence_ledger_file_version`, `provenance.worker.divergence_ledger_version`, `provenance.member_defaults`).
  Found offline after the run: the script defined `compare_identity()` but never called it (an omission in my adaptation of
  024's script); fixed for run 2, which prints both rows and folds them into the pass rule.
- Attributed diff over the 36 snapshot members: 16 identical; the rest dominated (Floatzel, Gyarados, Gliscor, Lumineon: Dive
  or Dig) or crit_term; **10 DEFECT lines, all of one shape**: a set the crit term re-ranked out of today's list (already
  attributed) that the item-conditioned valuation re-added as a lens or claw extra, whose items are now `[item] + today's`; the
  helper's items rule compared today's items as a prefix and called the leading item a change. Not a code defect: the sets'
  usual items follow the conditioning item exactly as FR-001a specifies. The helper now attributes such a set as `appended`
  ("re-added as a wide_lens set") and still flags any other item change; recomputed offline over all 36 members: 0 defects
  (Floatzel 2, Weavile 1, B1/B3 Garchomp 2 each, Gallade 1 appended).
- FR-010 on run 1: verdict A, level diff 0.00, identity identical, defects 10 (helper) → `pass False` by the rule as run.
  Run 2 follows with the helper and script fixed, no `src/` change (same commit 1f894e5), so the measurements are expected to
  reproduce exactly (seeded).

## T020 Branch side, run 2 (1:56:49 to 2:11:56 PM EST, alone; `runs/025-evidence/acceptance.txt`, exit 0; copies in `evidence/acceptance/`)

Same commit 1f894e5, the helper and the script fixed (no `src/` change). Every measurement reproduced run 1 exactly
(seeded): B2 quick winner, levels, clear 0.9380, the screen counts and overlap, the equal-levels row (0.9230 vs 0.8855, p
6.06e-05, verdict A, diff 0.00). Identity rows printed and identical; defects 0. **FR-010 pass True.**

| Measure | main (3a91eac code) | branch (1f894e5) |
|---|---|---|
| B2 quick winner levels | [51, 52, 52, 53, 52, 53] | [51, 52, 52, 52, 53, 53] |
| clear rate [95% CI] (n 500) | 0.9300 [0.9042, 0.9492] | 0.9380 [0.9133, 0.956] |
| expected average final level | 52.79 | 52.79 |
| members holding Wide Lens or Razor Claw | none | none |
| screened teams (cap 81 + extras) | 95 (14 variable-power) | 170 (14 variable-power, 15 lens sets, 17 claw sets, 43 item deviations) |
| screen overlap with main's list | | 0 of 95 (Floatzel's and Weavile's first sets re-ranked by the crit term) |
| equal levels [51, 52, 52, 52, 53, 53], 2,000 pairs | 0.8855 | 0.9230 (only-branch 209, only-main 134, p 6.06e-05, verdict A) |
| identity evaluations ref / b2main | | identical without volatile fields |
| attributed diff, 36 members | | 14 identical; dominated, crit_term, appended elsewhere; 0 defects |

Reading: the two items are offered on every B2 member (lens sets where an attack can miss, claw sets everywhere, and each
base set with either item), screened (89 extras beyond the cap) and **not chosen** by the B2 quick screen; the winner's
differences from main's come from the crit term's re-rank (Garchomp's setup set, Floatzel's and Weavile's high-crit moves) and
the branch team is better at equal levels. The wall grew from 380 to 432 s (the larger screen). SC-002 (at least 17 members
with extras reviewed): all 36 snapshot members carry item-conditioned extras where the rule allows; reviewed through the
attributed diff and the B2 hand check.

## T021 FR-010 gate: pass; continue.
