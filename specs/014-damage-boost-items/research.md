# Research: Damage-Boosting Held Items (H3)

Read on 2026-10-29 at `main` = `3078dad` (H2 merged). Decomp refs are under `pokeplatinum/`.

## R1. The group, by hold effect

**Decision**: The group is every item whose `hold_effect` is `HOLD_EFFECT_POWER_UP_SE`, `HOLD_EFFECT_POWER_UP_PHYS` or
`HOLD_EFFECT_POWER_UP_SPEC`, read from `platsim.decomp.items.load_items()` (item data `res/items/data/*.json`). The
three constants are names of decomp hold effects, like the existing `HP_BERRY_EFFECT` and `type_boost_items()` in
`candidates.py`, not item names.

**Evidence**: one item per effect today: Expert Belt (param 20), Muscle Band (10), Wise Glasses (10). Ledger copies
(`led.item_copies`): 1, 0, 1. Sources (`platsim explain`): Expert Belt at `scripts_route_221_house.s:39`, Wise
Glasses at `scripts_celestic_town_northwest_house.s:69` (one-time flag `:70`), Muscle Band at the Battle Frontier only
(post-game). H2's reader marks none of the three single-use.

**Damage model**: `sim/damage.mjs:381-382` (PHYS/SPEC power ×(100+param)/100 on the matching class) and `:639`
(SE damage ×(100+param)/100). The `sim/test/damage.test.mjs` cases cover Expert Belt (`:150`, `:209`), Muscle Band
(`:151`, `:203`) and Wise Glasses (`:152`). The battle player (`sim/policy/expectimax2.mjs`) uses `calcDamage`
from `damage.mjs`, so it already scores these items. No `sim/` change.

## R2. Where the new candidates go

**Decision**: In `held_item_candidates` (`src/platsim/optimizer/candidates.py`), after the existing berry,
type-boost and Leftovers entries and before the H2 filter:
1. If the moveset has an attack: every `POWER_UP_SE` item with `_item_copies(led, const) != 0`, sorted by key.
2. The strongest attack is the existing `best` (`max(attacks, key=(sum(move_value), m))`). If its
   `load_moves()[best].category` is `CLASS_PHYSICAL`, add each `POWER_UP_PHYS` item with a copy. If it is
   `CLASS_SPECIAL`, add each `POWER_UP_SPEC` item with a copy.
3. Duplicates are skipped (an item already in the list is not added again).

The existing items keep their order and positions (FR-004). The baseline member option (`run._baseline` uses
`mc.items[ms][0]`) is therefore unchanged, and so is the HP berry first.

**Alternatives considered**: offering Expert Belt only when the best attack is super-effective against much of the
gauntlet. Rejected for this slice: it needs a new gauntlet-type model, and the search already scores each option.
It can be revisited if the run-time cost (R4) is too high. Replacing the type-boost item with a booster: rejected,
because it would change existing candidates (FR-004).

## R3. Limited copies

**Decision**: No change. `resources.realize` already refuses an item source whose copies are used by earlier members
(`src/platsim/optimizer/resources.py:195`, `_affordable`). A new test mirrors
`test_single_copy_tm_is_never_given_twice` (`tests/unit/test_optimizer_candidates.py:65`): two members specified
with `expert_belt`. Realize, then assert at most one holds it and the validator returns no violations. Positive
control: the ledger reports 1 copy, so a second holder would be a violation.

## R4. Search cost

`run._member_options` (`run.py:197`) lists (variant, moveset, item) for every moveset and item, so each item added
to a moveset adds options for the screen stage. Per moveset the list grows from 2-3 items to up to 4-5. The effect
on wall time is measured, not predicted: B2 quick on `main` was 1259 s (013 T003) and 1123 s on the 013 branch
(T017). The same command on both sides here gives the ratio (FR-010). A slowdown is reported, not a failure
(spec Assumptions).

No approximation is added (no new cap or pre-filter), so Principle VI does not apply.

## R5. B2 comparison (user: quick budget, one team)

**Decision**:
1. `uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2`, on
   `main` and on the branch, each `/usr/bin/time`d.
2. Equal-levels comparison, written fresh in a scratchpad script `equal_levels.py` (not the archived 010 script):
   - Load each side's final team from its `result.json` `team` with `platsim.evaluate.load_and_validate`.
   - Set every member of both teams to the branch team's start levels. Check that `main`'s team is still legal
     at those levels (validator `[]`), as 010 did. If it is not, stop and report.
   - Play both with `platsim.evaluate.run_full_gauntlets` on one pool, master `014-equal|B2`, exactly 2,000 runs,
     player `expectimax2-v2` (the optimizer's `POLICY`).
   - McNemar exact on the per-run `cleared` (`platsim.stats.mcnemar_exact`, alpha 0.05); mean final level from
     `platsim.evaluate.final_level_stats` on each side.
   - Pass: verdict is not "main better", and the branch team's expected average final level is not higher.
3. If the two final teams are identical (no member chose a new item), the comparison is trivially equal. Record
   that, and also record which items the branch run's screen stage tried (from `state.json`), so the new options are
   shown to have been considered.

**Run cost (local only)**: two quick optimizations of about 20 min each, plus 2 × 2,000 gauntlets. 013's quick
confirm stage ran 500 gauntlets inside a 20-minute run, so 4,000 is estimated at 30-60 min. It is measured, not
assumed.

## R6. Report and explain (FR-008)

`run.py:673` fills `held_item_sources` / `held_item_source_refs` from `team_sources(real.team, led)`, which
reads the ledger. `platsim explain item:expert_belt` and `item:wise_glasses` already show the sources (checked
2026-10-29). Test: realize a team with `wise_glasses` and check that `team_sources` names
`MAP_HEADER_CELESTIC_TOWN_NORTHWEST_HOUSE` with a decomp ref.

## R7. Divergences

`damage-expert-belt-rounding` and `damage-final-modifier-chaining` (`data/divergences.json`, accepted) now affect
player teams holding Expert Belt. No ledger change: they were recorded for opponents (Cynthia's Lucario) and
already apply to any holder. The divergence test layer (Constitution, Development Workflow) is unchanged.
