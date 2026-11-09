# Implementation Plan: Variable-Power Moves Offered by the Optimizer

**Branch**: `024-variable-power-moves` | **Date**: 2026-11-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/024-variable-power-moves/spec.md`

## Summary

Four moves whose power the game computes at use (Return, Grass Knot, Low Kick, Gyro Ball) become offerable by the
optimizer, reference-first and from the decomp. In `sim/`, one new pure module holds the four formulas and the weight
table; the strong player's lookahead and the trainer-AI port call it (behaviour unchanged, proven by the replay fixtures)
and the screening player greedy-v1 now scores the four moves through it (every fixture team lacks them, so recorded
results stay byte-identical). In Python, a decomp weight reader and the existing stat formula let `candidates.move_value`
compute each move's power per League opponent; candidate generation stays exactly today's and then appends up to K extra
sets containing a variable-power move, ranked by today's coverage score and diverse among themselves (clarification 1).
A ledger entry records the engine's weight-tier boundary deviation. Acceptance runs the B2 quick job on the pre-feature
code (now, before any code commit, since this branch's code equals `main`) and on the branch, plays the two winners at
equal levels on 2,000 paired gauntlets, and checks two unaffected teams byte-identical; a supported loss or a two-level
rise blocks the merge (clarification 2).

## Technical Context

**Language/Version**: Node 22 (`sim/`, `node --test`); Python 3.12 (`uv`, pytest)

**Primary Dependencies**: `sim/policy/greedy.mjs` (`expectedDamage`), `sim/policy/expectimax2.mjs` (`variablePower`),
`sim/ai/calcdamage.mjs` (`WEIGHT_TO_POWER`, `speciesWeightHg`, the AI power switch), `sim/damage.mjs` (`fromShowdown`
power override), `src/platsim/optimizer/candidates.py` (`league_opponents`, `move_value`, `member_candidates`,
`held_item_candidates`), `src/platsim/optimizer/resources.py` (`_slot_cost`), `src/platsim/decomp/stats.py`
(`calc_stats`), `src/platsim/divergence/mechanics.py`, the 018 `equal_levels.py` and 022 acceptance helpers, the 019
`common.py` helpers (`assert_idle`, `eastern_now`)

**Storage**: `data/divergences.json` (one entry, new version); evidence under `runs/024-evidence/` with small copies
under `specs/024-variable-power-moves/evidence/` (including the pre-feature candidate snapshot)

**Testing**: Node: `sim/test/variable_power.test.mjs` (the helper against the decomp tables, both boundary rules, the
Gyro Ball cap and zero speed, Return at 255; greedy's expected damage for the four moves equals a fixed-power move of the
computed power); the existing replay, determinism and `ai_cmds_damage` tests as the unchanged-behaviour guard. Python:
`tests/unit/test_variable_power.py` (weight reader pins and Node parity for League species, the weight tier, Gyro Ball
per opponent, Return 102, `move_value` per opponent for Grass Knot against Rhyperior 120 and Flareon 40, the not-offered
list never offered, the additive prefix against the snapshot for the six B2 species); `test_divergences.py` ids; the
existing optimizer unit tests. Full pytest and Node suites as the merge gate.

**Target Platform**: this Linux machine, 16-worker pool

**Project Type**: battle-player helper + screening policy + optimizer candidate generation + decomp reader

**Performance Goals**: candidate generation adds per-opponent power computation for at most four moves per member and
one extra combination ranking; negligible against battles. The acceptance reports both B2 quick wall times.

**Constraints**: recorded results byte-identical (fixtures carry none of the four moves; FR-003); today's candidate sets
first and unchanged (FR-006); the decomp's boundary rule in every model (R7); no copy from the archived branches (FR-011);
pre-feature acceptance side run before any code commit (R8); measurements alone on the machine; `sim_code_hash`,
`platsim_code_hash` and the ledger version change, so pre-024 checkpoints are refused (R6)

**Scale/Scope**: one new `sim/variable_power.mjs` (about 60 lines) and edits to greedy, expectimax2 and calcdamage
(call sites only); one new `src/platsim/decomp/weights.py`; `candidates.py` (`league_opponents`, `move_value`,
`member_candidates`, `held_item_candidates`, the offered and not-offered tables), `resources._slot_cost` (level
argument); one mechanics ledger entry; two test files; two acceptance scripts; docs. Three stories, five commits.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I. Decomp is ground truth | Pass | The four formulas, the weight table and the boundary rule come from `battle_script.c`, `weight_to_power.h` and the effect scripts; weights from `res/pokemon/*/data.json` with the decomp's rounding overrides; the Python reader mirrors the Node one and is checked against it. |
| II. Showdown is the engine | Pass | No engine edit; the engine already computes the moves; the one formula difference (weight-tier boundary) goes in the ledger as accepted with its impact. |
| III. Legality of every output | Pass | Moves enter candidates only through `legal_moves`; the validator runs on every output as today. |
| IV. Reproducible, honest evaluation | Pass | Same seeds on both sides of every comparison; the equal-levels check pairs 2,000 gauntlets with the exact test; both B2 runs under identical defaults; code hashes recorded with every result. |
| V. Verified claims, positive controls | Pass | Helper tests against the decomp tables with both boundary rules; Node-Python weight parity; the additive-prefix test against a snapshot of today's output; the byte-identity check on two unaffected teams is the negative control; the acceptance records the numbers either way. |
| VI. Reference-first speed | Pass (not an approximation) | A game rule the player already models; the screening player's Gyro Ball speed is the stat at level rather than the battle value, a heuristic approximation listed below. Set and today's candidates remain available as the reference (the pre-feature run is kept). |
| Workflow and gates | Pass | Through Spec Kit; behaviour change under `sim/` and `src/platsim`, so both suites gate the merge; measurements alone with Eastern times. |

**Post-design re-check (after Phase 1)**: unchanged. Two items for Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/024-variable-power-moves/
├── plan.md, research.md (R1-R9), data-model.md, quickstart.md
├── contracts/
│   ├── sim-helper-and-greedy.md     # variable_power.mjs API; greedy's scoring of the four moves
│   └── candidates-api.md            # league_opponents, move_value(level), the additive list, summary fields, the ledger entry
├── scripts/
│   ├── acceptance.py                # pre-feature and branch sides: B2 quick, identity evaluations, snapshot, table
│   └── equal_levels.py              # adapted from 018: two winners at A's levels, 2,000 pairs, v4, today's style
├── evidence/ (b2-candidates-main.json, acceptance copies, gates), validation-log.md, tasks.md
```

### Source Code (repository root)

```text
sim/variable_power.mjs              # NEW: weightTierPower, returnPower, frustrationPower, gyroBallPower, WEIGHT_TO_POWER, speciesWeightHg
sim/ai/calcdamage.mjs               # re-exports WEIGHT_TO_POWER/speciesWeightHg; the AI switch calls the helper (edge behaviour kept)
sim/policy/expectimax2.mjs          # variablePower calls the helper (behaviour unchanged)
sim/policy/greedy.mjs               # expectedDamage: the four moves at computed power via fromShowdown({power}); header note
sim/test/variable_power.test.mjs    # NEW: helper vs decomp tables; greedy scoring; replay/determinism unchanged (existing tests)
src/platsim/decomp/weights.py       # NEW: species_weight_hg (data.json + speciesproc.c overrides), weight_tier_power
src/platsim/optimizer/candidates.py # league_opponents(+level, iv, nature); move_value(member_level) per-opponent power; OFFERED_VARIABLE / NOT_OFFERED with reasons; additive extras; ranked prefix; summary fields
src/platsim/optimizer/resources.py  # _slot_cost passes a level to move_value
src/platsim/divergence/mechanics.py # mech-weight-tier-boundary (accepted); data/divergences.json regenerated
tests/unit/test_variable_power.py   # NEW
tests/integration/test_divergences.py  # id list
```

**Structure Decision**: the formulas live in one `sim/` module imported by the three Node callers; Python mirrors the
two pure functions it needs (weight tier, Gyro Ball) and reads weights from the decomp directly, with a parity test
against Node rather than a second extraction table (which would change the data hash the fixtures pin).

## Complexity Tracking

| Item | Why | Simpler alternative rejected because |
|---|---|---|
| greedy's Gyro Ball uses the stat at level, not the game's battle speed value (R2) | the screening heuristic has no AI adapter and scores benched members too | the battle value needs a live adapter per decision; the screen only ranks candidates, the strong player decides battles; labelled an approximation of the screen |
| appending candidate options changes the screen's random combo sampling even where today's sets are untouched (R5) | the screen samples combos from the option list by RNG and caps at 81 | fixing the sampling to today's list would need a second option list; the acceptance measures the end result, which is the claim the feature makes |
