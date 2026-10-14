# Data Model: Status Moves and Held Items (007)

These are additions and changes to the existing entities. Unchanged entities (Build, TeamCandidate, EvaluationReport, ledger Entry) are only referenced here.

## MoveClass (new; `optimizer/move_classes.py`, research R1)

| Field | Type | Rule |
|---|---|---|
| `effect` | `BATTLE_EFFECT_*` | every effect in `load_moves()` has exactly one MoveClass; an unknown effect raises |
| `category` | enum | in scope: `recovery`, `inflict_status`, `leech_seed`, `self_boost`, `protection`, `screen`, `weather`, `other`, `attack`, `variable_attack`; excluded: `foe_drop`, `fixed_damage`, `no_effect_singles`, `sacrifice`, `reactive`, `conditional_attack` |
| `offered` | bool | true only for the in-scope categories **and** when the player version in use models the effect (spec FR-001); otherwise the reason is "not offered: not modelled" |
| `reason` | str | for excluded categories: the reason recorded in the run (FR-002, FR-003) |
| `derived_from` | str | an `ES NNNN` script path and line, or the rule-table key |

## ItemClass (new; `optimizer/item_classes.py`, research R2)

| Field | Type | Rule |
|---|---|---|
| `item` | `ITEM_*` | — |
| `hold_effect` | `HOLD_EFFECT_*` | from the decomp item data |
| `in_battle` | bool | the effect is referenced in battle code, by name or by number |
| `excluded_reason` | str or None | `no_outcome`, `exp_ev`, `species_gate`, `not_in_battle`, or None |
| `species` | tuple or None | the species gate, if any |
| `pairs_with` | set of MoveClass effects / types / "all-attack" / None | the FR-006 pairing; None means any moveset |
| `showdown_id` | str | must exist when the item is offered (R8) |

## Candidate generation per member (changes to `MemberCandidates`)

New fields:
- `legal_status`: offered status moves after classification, sorted.
- `excluded`: `{move: reason}` for every legal move left out by MoveClass (FR-002/003). Recorded in the `prune` stage.
- `alternatives: list[Alternative]`: deterministic and sorted (R5.1).

`movesets`, `ranked` and `pool` keep their meaning. Attacks now include `variable_attack` moves, scored by the R3 formulas.

`setup_moveset` is **removed**. Its role passes to `alternatives`.

## Alternative (new)

| Field | Type | Notes |
|---|---|---|
| `slot` | int | team slot 0-5 |
| `base_moves` | tuple | the member's current moveset when generated |
| `moves` | tuple | with 1 or 2 slots replaced by offered status moves, or the same moves for an item-only swap |
| `item` | item key or None | a paired item (FR-006) or an item swap |
| `kind` | `status` / `status+item` / `structured` / `structured+item` / `item` | `structured` = a 3-4-status set built one move per category (spec FR-005) |
| `modelled` | bool | every move and the item are in the player version's `MODELLED` table |

## CandidateTest (new; one per Alternative tested, research R5, R10)

| Field | Type |
|---|---|
| `slot`, `species`, `moves`, `item`, `kind` | as in Alternative |
| `levels` | the level vector compared at (the first failing neighbour, or the bisection levels) |
| `mode` | `reference` / `prefilter` |
| `n_paired`, `rate_alt`, `rate_current`, `alt_only`, `current_only`, `p_value`, `p_holm` | McNemar exact, Holm within the member |
| `round_reached`, `round_cleared`, `round_runs` | the successive-halving round where the alternative stopped, and its counts there |
| `verdict` | `alternative better` / `current better` / `indistinguishable` / `dropped in screening` / `not tested: <reason>` |
| `confirmed` | bool or None | result of the fresh-seed-block confirm, for the winner only |
| `adopted` | bool | — |
| `not_modelled` | list | moves or items in it that the player doesn't model |

**State transitions:** offered → screened (successive halving with rounds r/2r/4r/8r, r fitted to the 100 h reference budget) → (dropped in a round | finalist) → finalist tested in full → (adopted after confirm | rejected). In prefilter mode the prefilter may drop it first ("not tested: prefilter").

## MemberSpec (changed; `optimizer/resources.py`, research R6)

- New field `adopted: tuple[str, ...] = ()`: moves adopted by a test, or under test.
- `to_dict` emits it only when non-empty, so existing JSON, `team_key` and level memos are unchanged.
- Every rebuild uses `dataclasses.replace`.
- Slot-cost tiers for required HMs, lowest is replaced first:
  1. non-adopted status;
  2. attacks by League value;
  3. non-adopted modelled boost;
  4. adopted.

## LeagueOpponent (extended; `league_opponents()`)

Adds `level`, `stats` (computed from base stats and the trainer data), and `weight_hg` (extracted from `res/pokemon/<sp>/data.json`). These are used for Low Kick/Grass Knot, Gyro Ball and Wring Out.

## Ledger Entry (no schema change; research R7)

New entries for Route 221, Pastoria SW house, Amity pickup and Amity Gift Man use the existing `npc_item_gift` kind:
- `quantity = UNLIMITED`;
- `detail` names the daily/repeat rule and the party condition;
- `src` points at the decomp script line;
- `requires_any` holds Amity's partner species.

## Player version (JS; research R4)

- `EXPECTIMAX2_V3 = 'expectimax2-v3'` with `V3_OPTS`.
- `MODELLED[version] = {effects: [...], items: [...]}`, read by Python for the `not_modelled` flags.
- New state fields:
  - `S.weather` and `S.weatherTurns`;
  - side `sc` gains spikes, tspikes, rocks, safeguard and wish;
  - per member: seeded, subHp, taunt, encore, confusion, attract, aquaRing, ingrain, choiceLock, flinch.
- All are in `signature()` and in the damage cache key.

## Provenance additions (`provenance.optimizer`)

- `candidate_mode`
- `candidate_tests: [CandidateTest…]`
- `excluded_moves: {slot: {move: reason}}`
- `item_tie_rule`
- `assumptions: {friendship: 255, ivs: 15, hidden_power: "Dark 70"}`
- `seeds.alternatives`
- `policy_per_stage.alternatives`
