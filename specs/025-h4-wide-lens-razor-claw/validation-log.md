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
