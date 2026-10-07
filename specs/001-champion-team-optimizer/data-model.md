# Data Model: Champion Team Optimizer

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

All game entities are generated from the decomp by `platsim extract` into `data/generated/`
(JSON). Each generated record carries `src` (a list of `"path:line"` references) and the dataset
carries `decomp_commit`. Generated data MUST NOT be hand-edited (Constitution, Technical
Constraints).

## Game data (generated)

### Species
| Field | Type | Rule / source |
|---|---|---|
| id | int | line index in `generated/species.txt` |
| key | str | e.g. `garchomp` (folder name) |
| name | str | `pokedex_data.en.name` |
| types | [str, str] | may repeat for mono-type |
| base_stats | {hp, atk, def, spa, spd, spe} | reordered from decomp (speed before sp. atk) |
| abilities | [str, str\|null] | slot 2 null if `ABILITY_NONE` |
| exp_rate | enum | `generated/exp_rates.txt` |
| base_exp | int | `base_exp_reward` |
| ev_yield | stats | |
| learnset_level | [(level, move)] | ≤ 20 entries |
| learnset_tm | [tm_id] | `TMnn` / `HMnn` |
| learnset_tutor | [move] | |
| egg_moves | [move] | optional |
| evolutions | [{method, param, target}] | method enum `generated/evolution_methods.txt` |
| src | [ref] | |

Validation: every move and ability referenced exists; ≤ 7 evolutions.

### Move
`id, key, name, type, category, power, accuracy (0 = never misses), pp, priority, effect, effect_chance, range, flags, src`.

### Item
`id, key, name, hold_effect, effect_param, price, src`. A **TM** is an Item that also has `teaches_move`.

### Tutor
`move, location (ROUTE_212 | SNOWPOINT_CITY | SURVIVAL_AREA | DRACO_METEOR | ROUTE_228), shard_cost {red, blue, yellow, green}, extra_requirement (e.g. max friendship, Dragon type), map_header, src`.

### AvailabilityEntry
One way of obtaining a species, item, TM or tutor.

| Field | Type | Notes |
|---|---|---|
| kind | enum | wild_slot, gift, egg, static, roamer, npc_trade, item_ball, hidden_item, npc_item_gift, shop, game_corner, tutor, underground |
| subject | species / item / move | |
| map_header | str | |
| quantity | int \| "unlimited" | shops and daily-respawn hidden items are unlimited |
| fixed_mon | FixedMon \| null | for trades/gifts: IVs, personality, held item, OT flag |
| gates | [Gate] | each with `{kind: script_flag \| national_dex \| region \| slot_type, ref}` |
| phase | `pre_champion` \| `post_game` | derived from gates, never set by hand |
| src | [ref] | |

### FixedMon (NPC trade / gift with fixed values)
`species, level|null, ivs|null, personality|null → nature, ability_slot; held_item; is_traded (bool → boosted exp)`.
Fields left null by the game fall back to the defaults (FR-008).

### OpponentTrainer
`trainer_id, key, order (1–5), ai_flags [str], bag_items [item], party [OpponentMon], src`.

### OpponentMon
`species, level, moves[4], held_item, iv (all = iv_scale*31/255), personality, nature, ability, src`.
Personality is computed by the Python port of `TrainerData_BuildParty` and tested.

### DivergenceEntry
`id, area (data | mechanics | ai | exp), description, decomp_ref, showdown_ref, resolution (corrected | accepted), impact, test_id`.

## Run data

### Build (one team member)
| Field | Type | Rule |
|---|---|---|
| species | Species key | must have pre-Champion availability, no trade evolution (FR-003, FR-005) |
| source | AvailabilityEntry ref | wild/gift/npc_trade; selected by the optimizer (FR-008b) |
| start_level | int 1–100 | chosen by the optimizer; ≥ the minimum level at which the species/form is obtainable |
| moves | [MoveChoice ×1–4] | |
| ability | str | FR-008c |
| ability_reason | enum | tested_better, tie_default, other_no_battle_effect, single_ability, fixed_by_trade |
| held_item | Item key \| null | |
| nature | str | `Hardy` (neutral) unless fixed by FixedMon |
| ivs | stats | 15 each unless fixed |
| evs | stats | 85 each (FR-008) |

### MoveChoice
`move, source_kind (level_up | pre_evo_level_up | tm | hm | tutor | egg | relearner), detail (e.g. "Lv 48", "TM26 – Veilstone Dept. Store (unlimited)", "Route 212 tutor – 2R/4B/2Y"), availability_ref`.

### TeamCandidate
`builds[6], resource_use {tm_id: copies_used, item: copies_used}`.
Validation (enforced by the legality validator, which is independent of the optimizer):
- `copies_used ≤ quantity`;
- unique items are held by at most one member;
- final level gap ≤ 10.

### GauntletRun
`seed, battles [ {trainer, won, turns, log_hash, state_before} ×≤5 ], final_levels[6], cleared (bool)`.

`state_before` is the team state at the start of that battle (`{levels[6], exp[6], pp[6][4], items[6]}`,
the worker contract's `start_state` shape). It is present when `log` is `summary` or `full`.

### EvaluationReport
| Field | Notes |
|---|---|
| team | TeamCandidate |
| n_runs | |
| clear_rate, clear_ci95 | Wilson interval |
| per_battle | `{trainer: {rate, ci95, battles}}` from full runs only |
| champion_rate, champion_ci95, champion_battles | P(win \| reached Cynthia) from full runs plus the top-up (task T057); `champion_battles` includes top-up battles |
| budget_preset | `standard` \| `thorough` \| `quick` (research R8) |
| expected_final_levels[6], expected_avg_final_level, final_level_gap_max | |
| loss_causes | top opponent mons present at losses |
| threshold, qualified, borderline | FR-015 |
| player_policy, opponent_policy | e.g. `expectimax2-v1`, `decomp-ai@c248fb3` |
| seeds | master seed + derivation scheme |
| decomp_commit, showdown_commit, divergence_ledger_version | |

### Job (web)
`id, status (queued | running | done | failed), species[6], options, progress {stage, runs_done, best_so_far}, result_paths {json, xlsx, csv}, error`.

State transitions: `queued → running → done | failed`. There are no other transitions. A job
interrupted by a restart resumes from its last checkpoint or is marked `failed` with its reason.
