# Implementation Plan: H4, Wide Lens and Razor Claw

**Branch**: `025-h4-wide-lens-razor-claw` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/025-h4-wide-lens-razor-claw/spec.md`

## Summary

Two held items the battle player already models and the game provides before the Champion become offerable: Wide Lens (the
accuracy item, unlimited) and Razor Claw (the crit-stage item, two copies), chosen by hold effect and copy count and appended
after the existing item candidates (R1). Each item re-values the member's moves: the move value gains an item-conditioned
accuracy factor and a critical-hit term read from the decomp's crit stage table, the base-stage crit term applying to every
valuation (R2); the sets that win under an item are appended as item-conditioned extra sets paired with it (R3). The screen
keeps building its capped list from the base options and screens every appended option beyond the cap, now three kinds in a
fixed order (R4). The R8 dominance rule gains PP and an effect cost class including self stat drops, pinned by controls, with a
Node test asserting the player's model resets stat stages on a switch (R5). Every report gains a `member_defaults` provenance
block (R6). Acceptance is the 024 protocol with an attributed diff of the B1 to B5 candidate lists and a screen-overlap count
instead of the prefix guarantee (R8).

## Technical Context

**Language/Version**: Python 3.12 (`uv`, pytest); Node 22 only for one new test under `sim/test/`

**Primary Dependencies**: `src/platsim/optimizer/candidates.py` (`held_item_candidates`, `move_value`, `member_candidates`,
`dominates`, `prune`, `MemberCandidates`), `src/platsim/optimizer/run.py` (screen stage, `_member_options`,
`_member_extra_options`, `_optimizer_provenance`), `src/platsim/optimizer/resources.py` (repair, copy limits),
`src/platsim/evaluate.py` (provenance), `src/platsim/report/{json_report,xlsx}.py`, `src/platsim/legality/models.py` (the
defaults), `src/platsim/decomp/moves.py` and `items.py` (records), the decomp `battle_lib.c` (crit stage table), the 024
acceptance and equal-levels scripts, the 019 helpers

**Storage**: result.json (`provenance.member_defaults`), state.json (`prune` summaries with `item_extras`, screen
`extras_screened` by kind), evidence under `runs/025-evidence/` with small copies under the feature's `evidence/`

**Testing**: Python unit tests (`tests/unit/test_h4_items.py`: the two item rules on fixed movesets, copy refusal of a third
Razor Claw, the crit table pin, the crit term and the lens factor in `move_value`, item-conditioned extras, the dominance
controls incl. the self-drop pair, the pruned reasons; `tests/unit/test_reports.py`: the provenance block round trip and the xlsx
row); one Node test (`sim/test/switch_reset.test.mjs`: the model's boosts reset on a cloned-root switch); the existing optimizer
tests; the full pytest and Node suites as the merge gate

**Target Platform**: this Linux machine, 16-worker pool

**Project Type**: optimizer candidate generation + screen + report provenance; no battle-player change

**Performance Goals**: candidate generation grows by two item-conditioned rankings per member (each a pool cut and a
combination ranking, about the cost of today's) and stays in seconds; the screen grows by the appended options beyond the cap
(on B2 quick: at most 6 members × (up to 3 lens sets + up to 3 claw sets + base sets × 2 items)), reported as wall time

**Constraints**: `sim/` code untouched (sim hash unchanged); today's base item lists untouched; every diff from the pre-feature
snapshot attributed to one of three causes; measurements alone with Eastern times; pre-feature side before any code change;
`platsim_code_hash` changes (pre-025 checkpoints refused)

**Scale/Scope**: `candidates.py` (two item rules, `items_extra`, the crit table and term, the lens factor, item-conditioned
extras, the dominance rule and cost table, summary fields), `run.py` (appended options of three kinds, screen records),
`evaluate.py` + a new `report/provenance.py` (the block), `resources.py` (unchanged unless the item lists need the extra list
in repair: decided at implementation), two test files, one Node test, the acceptance and equal-levels scripts, docs. Three
stories, five commits. **Size note (R9)**: the provenance block splits off cleanly if tasks pass about 30.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I. Decomp is ground truth | Pass | Items by decomp hold effect and copies from the ledger; the crit stage table parsed from `battle_lib.c` by name and pinned; the cost class a table of decomp effect constants with reasons. |
| II. Showdown is the engine | Pass (not touched) | No engine or battle-player change; the player already applies both items. |
| III. Legality of every output | Pass | Items offered only with pre-Champion copies; the validator and repair run on every output as today. |
| IV. Reproducible, honest evaluation | Pass | Same seeds on both sides of every comparison; appended options in a fixed order so results are worker-count independent; the provenance block names the assumptions. |
| V. Verified claims, positive controls | Pass | Dominance controls positive and negative incl. the self-drop pair; the crit table pin; the switch-reset test; the attributed diff fails on an unexplained difference; the identity rows as the negative control. |
| VI. Reference-first speed | Pass (not an approximation) | The pre-feature winner is kept as the reference; the equal-levels gate blocks a loss. |
| VII. A competent human player is the user | Pass | The items are what a competent player would try (the lens on a missing move, the claw on a high-crit user); the re-valuation mirrors that reasoning; the assumptions block makes the average-Pokemon standard visible in every report. |
| Workflow and gates | Pass | Through Spec Kit; behaviour change under `src/platsim`, so both suites gate the merge; measurements alone with Eastern times. |

**Post-design re-check (after Phase 1)**: unchanged. No Complexity Tracking item: nothing is an approximation of a reference;
the dominance cost class is a ranking rule with controls.

## Project Structure

### Documentation (this feature)

```text
specs/025-h4-wide-lens-razor-claw/
├── plan.md, research.md (R1-R9), data-model.md, quickstart.md
├── contracts/
│   ├── candidates-items-and-dominance.md   # item rules, move_value(item_effect), item-conditioned extras, screen kinds, dominance
│   └── provenance-member-defaults.md       # the block, where it is written, how old files read
├── scripts/
│   ├── acceptance.py                       # sides main/branch; snapshot of B2 and B1-B5; attributed diff; screen overlap
│   └── equal_levels.py                     # the 024 script with master 025-equal|B2
├── evidence/ (snapshots, acceptance copies, gates), validation-log.md, tasks.md
```

### Source Code (repository root)

```text
src/platsim/optimizer/candidates.py   # CRIT_STAGE_RATES (parsed), HIGH_CRIT_EFFECTS, EFFECT_COSTS; dominates/prune; move_value(item_effect); held_item_candidates + items_extra; item-conditioned extras; summary fields
src/platsim/optimizer/run.py          # _member_options (base) / _member_extra_options (three kinds, fixed order); screen records extras by kind; provenance extra
src/platsim/report/provenance.py      # NEW: member_defaults_block(team)
src/platsim/evaluate.py               # provenance["member_defaults"]
tests/unit/test_h4_items.py           # NEW
tests/unit/test_reports.py            # provenance block round trip, xlsx row
sim/test/switch_reset.test.mjs        # NEW (test only; sim hash unchanged)
```

**Structure Decision**: all candidate logic stays in `candidates.py` beside today's rules so the snapshot diff has one source;
the appended-option kinds are enumerated in one function in `run.py` so their order is fixed in one place; the provenance
block is a pure helper so both commands and the tests share it.

## Complexity Tracking

None. The feature carries four changes (R9) by design because they share one acceptance run; the split point is named.
