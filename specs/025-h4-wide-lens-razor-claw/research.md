# Research: H4, Wide Lens and Razor Claw

Sources read 2026-11-13 (read only): `src/platsim/optimizer/{candidates,run,resources}.py`, `src/platsim/evaluate.py`,
`src/platsim/report/{json_report,xlsx}.py`, `src/platsim/legality/models.py`, `sim/damage.mjs` (hit chance, crit chance, the
crit stage table), `sim/policy/expectimax2.mjs` (item handling, switches), the decomp (`battle_lib.c:7097-7135`), the ledger
copy counts (one build), the 014 and 024 specs and scripts, and the dominance assessment's probe.

## R1. Which items, and how they are chosen (FR-001, FR-002)

- **Finding**: `held_item_candidates` (`candidates.py:498-536`) builds a per-moveset list in a fixed order (HP berry, a type
  boost for the strongest attack, Leftovers when team-gated, Expert Belt and the class booster), filters single-use items and
  returns `[None]` when empty. Items are found by hold effect through `load_items()`; copies through `_item_copies(led, const)`
  (`:491-495`, the ledger's pre-Champion count under the active options; `UNLIMITED` for buyable or farmable). Wide Lens is
  `HOLD_EFFECT_ACCURACY_UP` param 10 (unlimited); Razor Claw and Scope Lens are `HOLD_EFFECT_CRITRATE_UP` (2 and 0 copies).
- **Decision**: two rules appended after the existing list, by hold effect: the `ACCURACY_UP` item when any attack in the
  moveset has `0 < accuracy < 100`; the `CRITRATE_UP` item when the moveset has an attack (`is_attack` or an offered variable
  move); each only when `_item_copies != 0`, so Scope Lens never appears. The appended items live in a separate
  `MemberCandidates.items_extra[moveset]` list, so today's `items` lists are untouched and the screen can tell base items from
  appended ones (R4). The single-use filter applies to both lists. Copy limits need no new code: `resources.repair` already
  resolves conflicts in candidate order (`resources.py:111-125, 191-197`); a unit test pins a third Razor Claw being refused,
  the 014 Expert Belt test's shape.

## R2. The move value under an item, and the crit term (FR-001a, FR-001b)

- **Finding**: `move_value(const, move, level)` (`candidates.py`) multiplies power, accuracy (`1.0` when the data says 0),
  STAB, the base attacking stat, the effect weight and the type multiplier per opponent; it has no crit term. The player's
  model applies `ACCURACY_UP` as `hitRate * (100 + param) / 100` and `CRITRATE_UP` as +1 crit stage (`expectimax2.mjs:628`,
  `damage.mjs:819-832`), reading the stage rates from the decomp's `sCriticalStageRates` (`battle_lib.c:7097-7103`: 16, 8, 4, 3,
  2; `BattleSystem_CalcCriticalMulti` at `:7105-7135`, a critical hit doubles damage).
- **Decision**: `move_value(const, move, level, item_effect=None)`:
  - accuracy factor `min(1.0, acc * (100 + param) / 100)` when `item_effect == "HOLD_EFFECT_ACCURACY_UP"` (param from the item
    record);
  - crit term `1 + 1 / CRIT_STAGE_RATES[stage]` for every call, `stage = (1 if the move's effect is a high-critical-ratio effect
    else 0) + (1 if item_effect == "HOLD_EFFECT_CRITRATE_UP" else 0)`, capped at 4; `CRIT_STAGE_RATES` parsed once from
    `battle_lib.c` by name as `type_chart()` parses the type table (`candidates.py:126-138` precedent), so the table has its
    decomp citation and a test pins `[16, 8, 4, 3, 2]`; the high-crit effects are the decomp constants whose name contains
    `HIGH_CRITICAL` (`BATTLE_EFFECT_HIGH_CRITICAL`, `_POISON_HIT`, `_BURN_HIT`), listed in the module.
  - The base-stage crit term applies to today's valuation too (clarification 2), so rankings move wherever a high-crit move
    competes; the B1 to B5 snapshot diff attributes those moves (R8).

## R3. Item-conditioned extra sets (FR-001a)

- **Decision**: in `member_candidates`, after today's `chosen`, the 024 variable-power extras and the setup variant: for each
  conditioning item available to the member (`ACCURACY_UP` if any legal attack can miss and the item has copies; `CRITRATE_UP`
  if copies), re-score every attack with `move_value(..., item_effect=effect)`, cut a pool of `POOL` by that score, rank the
  four-move combos by coverage under those values, and keep up to `K_MOVESETS` sets in rank order that are not already in
  `movesets` and differ from each other by at least two moves (the 024 extras rule). Each is appended to `movesets` with
  `items[set] = [item] + the usual list for that set` and recorded in `item_extras: dict[moveset, item]`; `extras` counts them
  with the 024 extras (a second counter `item_extra_count` keeps the kinds apart for the summary). The lens-conditioned sets are
  computed before the claw-conditioned ones.
- **Alternatives**: attaching the lens only to today's sets (rejected by clarification 1: a Fire Blast set never appears then).

## R4. The screen with three kinds of appended option (FR-003)

- **Finding**: 024's screen builds the capped list from `_member_options` (base sets × their item lists) and appends
  `_member_extra_options` (variable-power extras with their first item) beyond the cap as single-slot deviations
  (`run.py` screen stage).
- **Decision**: `_member_options` returns base sets × `items` (today's lists only: for base sets `items` has no appended
  entries, since those are in `items_extra`); `_member_extra_options` returns, in this fixed order per member: the 024
  variable-power extras with their first item; the item-conditioned extra sets with their conditioning item; then each base
  set × each `items_extra` item. All are screened beyond the cap as single-slot deviations of the baseline, deduplicated and
  validated as today; the screen stage records `extras_screened` split by kind. Because the crit term changes the base lists,
  the capped list differs from the pre-feature run's; the acceptance reports the overlap (R8).

## R5. The dominance rule (FR-004, FR-004a, FR-005)

- **Finding**: `dominates(a, b)` (`candidates.py:345-349`) requires the loser's effect to be plain and the winner strictly
  higher in power; `prune` applies it over `is_attack` moves. The assessment's probe (`.specify/assessments/dominance-list/probe.py`)
  found 17 benchmark moves a wider rule drops, in three pairs.
- **Decision**: `dominates(a, b)` becomes: same type and category; `a.power >= b.power`, `acc(a) >= acc(b)` (0 read as 101),
  `a.priority >= b.priority`, `a.pp >= b.pp`; effect: equal effects compare by `effect_chance`; a loser in `EFFECT_COSTS` loses to
  a winner that is plain or not a cost; a plain loser loses to a non-cost winner with a secondary; two different non-cost
  secondaries are incomparable; and at least one of power, accuracy, priority, PP, effect strictly better. `EFFECT_COSTS` is a
  dict of decomp effect constants to a one-line reason: the charge turns (`DIG`, `FLY`, `DIVE`, `BOUNCE`, `SKIP_CHARGE_TURN_IN_SUN`,
  `CHARGE_TURN_DEF_UP`, `CHARGE_TURN_HIGH_CRIT`, `CHARGE_TURN_HIGH_CRIT_FLINCH`, `SHADOW_FORCE`), `RECHARGE_AFTER`, the recoils
  (`RECOIL_HALF`, `_THIRD`, `_QUARTER`, `RECOIL_BURN_HIT`, `RECOIL_PARALYZE_HIT`), the self stat drops (`USER_SP_ATK_DOWN_2`,
  `LOWER_OWN_ATK_AND_DEF`, `DEF_SPD_DOWN_HIT`, and the own-speed drop constant found at implementation for Hammer Arm),
  `CONTINUE_AND_CONFUSE_SELF`, `CRASH_ON_MISS`, `DOUBLE_POWER_EACH_TURN_LOCK_INTO`, `HIT_IN_3_TURNS`,
  `ALWAYS_FLINCH_FIRST_TURN_ONLY`, `RECOVER_DAMAGE_SLEEP`, `HIT_LAST_WHIFF_IF_HIT`, `LEAVE_WITH_1_HP`. The pruned map's reason
  names the winner and the strictly better axes. High-critical-ratio effects are non-cost secondaries (so the crit term, not
  dominance, favours them).
- **The switch reset (FR-004a)**: the player's model resets all boosts on its modelled switches (`expectimax2.mjs:650` the
  outgoing member, `:658` the incoming, `:1107` in replacement scoring); a Node test in `sim/test/` asserts it on a cloned root
  state with boosts set (test only; `sim/` code unchanged, the sim hash unchanged).

## R6. The provenance block (FR-007)

- **Finding**: `evaluate.py` builds `provenance` (`:433-457`) and the optimizer merges `extra` into `_optimizer_provenance`
  (`run.py:714-743`); the xlsx provenance sheet loops over every provenance key (`xlsx.py:168-169`), so a new key shows up
  JSON-dumped; defaults live in `legality/models.py:42-44` (`DEFAULT_IV`, `DEFAULT_EV`, `DEFAULT_NATURE`); friendship is Showdown's
  default 255, set nowhere; NPC-trade members get fixed IVs and nature from `opt.fixed_mon` (`resources.py:293-305`) and the
  `Build` carries `nature`, `ivs`, `evs` (`models.py:192-201`).
- **Decision**: one helper `member_defaults_block(team)` in `src/platsim/report/provenance.py` (new, small) returning
  `{"nature": "Hardy", "ivs": 15, "evs": 85, "friendship": 255, "reason": "the average Pokemon a player has, not a bred or
  trained one (constitution v1.5.0)", "fixed_by_game": [species whose build nature, IVs or EVs differ from the defaults]}`;
  `evaluate_team` puts it in `provenance["member_defaults"]`; the optimizer passes it through `extra`; `from_dict` leaves it
  absent for old files; a `test_reports` round trip and an xlsx row check. The 025 acceptance script adds
  `provenance.member_defaults` to the volatile list for the identity comparison.

## R7. Fingerprints and checkpoints

- `platsim_code_hash` changes (candidates, run, evaluate, provenance); `sim_code_hash` and the ledger version do not (only a
  Node test is added, under `sim/test/`, excluded from the hash). Pre-025 checkpoints are refused by the code fingerprint; no
  `STATE_VERSION` bump (the 024 precedent).

## R8. Acceptance (FR-006, FR-009, FR-010)

- **Decision**: `specs/025-h4-wide-lens-razor-claw/scripts/acceptance.py` adapted from 024's: `--side main` (before any code
  change) runs B2 quick, the two identity evaluations, and the snapshot of B2's six species at the job's reference level and of
  B1 to B5's members at their recorded levels (movesets, setup, pool, ranked prefix, items per set, pruned map); `--side
  branch` runs B2 quick, the identity comparison with `provenance.member_defaults` added to the volatile fields, the
  equal-levels check (024's `equal_levels.py` copied with master `025-equal|B2`), the screen overlap (how many of the main run's
  81 teams appear in the branch's screened list; `extras_screened` by kind), the members holding Wide Lens or Razor Claw, and
  the **attributed diff** per member: moves missing from the branch's pool or sets must appear in the branch's pruned map as
  dominated (cause 1); new sets must be item-conditioned extras or carry an appended item (cause 3); any remaining difference
  in order or membership among surviving moves is attributed to the crit term (cause 2) and listed with the moves involved;
  a set or move that fits none is a defect and fails the run. Pass rule: 024's FR-009.
- **Cost**: about 35 min of pool time (two B2 quick runs about 6 min each, four identity evaluations about 1 min each, the
  equal-levels run about 5 min) plus the gates (Node suite 3 min, full pytest about 1 h 30 min).

## R9. Size and split

- Four changes ride together: the items with re-evaluation (R1, R3), the crit term (R2), the dominance widening (R5) and the
  provenance block (R6). They share one acceptance run and one snapshot diff, which is why they ride together; if tasks pass
  about 30, the provenance block is the piece to split into its own small feature (it has no acceptance dependency).
