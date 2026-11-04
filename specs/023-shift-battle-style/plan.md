# Implementation Plan: Shift Battle Style

**Branch**: `023-shift-battle-style` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/023-shift-battle-style/spec.md`

## Summary

A battle-style option, `set` (today's behaviour, the default until the owner's decision) or `shift` (the game's
default), on every worker request. Under Shift the gauntlet loop, at the moment the engine asks only the trainer for a
replacement, takes the trainer AI's choice (already made against the player's current Pokemon, as in the game), names it
to the player policy, and on a switch sets the engine's switch flag on the player's standing Pokemon and rebuilds the
request so both sides switch instantly with no move between and one turn end (research R1): no engine edit. Policies
answer through an optional `shiftChoice(ctx, incoming)`: expectimax2 values stay against each bench switch with the
announced foe placed on the field by its existing one-ply valuation, greedy compares its member scores (R3). The
per-battle record and a log line carry each offer under Shift only; under Set nothing is added, so every digest stays
(R4). Python threads the field through every request builder, the report, provenance, the summary, the xlsx, the web
view and the optimizer's fingerprint-when-non-default (R5); two ledger entries record the prompt (corrected) and the
entry-ordering difference (accepted) (R2, R6). Acceptance pairs Shift against Set on four teams and runs B2 quick under
each style (R8); the owner then chooses the default.

## Technical Context

**Language/Version**: Node 22 (`sim/`, ES modules, `node --test`); Python 3.12 (`uv`, pytest)

**Primary Dependencies**: the vendored Showdown `Battle` driven in process (`sim/gauntlet.mjs`), `sim/policy/expectimax2.mjs`
(`makeContext`, `cloneState`, `doSwitch`, `valuePly2`), `sim/policy/greedy.mjs` (`memberScore`), `sim/ai/opponent.mjs`
(`decide`), `src/platsim/evaluate.py`, `sampling.py`, `sim/champion.py`, `report/{json_report,losses,xlsx}.py`,
`optimizer/{api,run,screen,levels,abilities}.py`, `sim/pool.py`, `divergence/mechanics.py`, `web/result_view.py`, `cli.py`

**Storage**: result.json (`battle_style` field, provenance), state.json (fingerprint), `data/divergences.json`
(two entries, new version), evidence under `runs/023-evidence/` with small copies under `specs/023-shift-battle-style/evidence/`

**Testing**: Node tests (`sim/test/shift.test.mjs`: the gate's four exclusions, the hand-walked battle, the policy controls
for every player, the Set guard through the existing replay and determinism tests); Python unit tests (request field,
report round trip, fingerprint rule, CLI defaults and validation, ledger ids); one `battle_sim` integration test
(evaluate under Shift, two worker counts, byte-identical); the full pytest suite and the Node suite as the merge gate

**Target Platform**: this Linux machine, 16-worker pool

**Project Type**: battle worker + player policies + Python CLI/library plumbing

**Performance Goals**: Shift's cost per offer is one policy valuation at ply-2 depth per candidate (no root samples);
the wall ratio Shift/Set is measured per team and reported, not gated

**Constraints**: Set byte-identical (fixture digests, determinism tests, stored results); no edit to `pokemon-showdown/`;
the trainer AI unchanged; the search's model of later turns unchanged (clarification 1); no aggregation of offer counts
into standard reports (clarification 2); measurements alone on the machine; `sim_code_hash`, `platsim_code_hash` and
`divergence_ledger_version` change, so pre-feature checkpoints stop resuming (R5)

**Scale/Scope**: `sim/gauntlet.mjs` (the offer), `sim/worker.mjs` (validation, hello), two policy files, one Node test
file, one mechanics ledger file + regenerated JSON, about fourteen Python files touched by one to three lines each
(request builders, echo checks, report, provenance, CLI, fingerprint), four Python test files, one acceptance script,
docs. Three stories; four commits plus the optional flip. **Size note**: the Python plumbing is wide but shallow; if the
owner prefers a smaller branch, the optimizer-side plumbing (`run.py`, `screen.py`, `levels.py`, `abilities.py`, `api.py`,
the fingerprint) can be split off with the B2 quick acceptance row into a follow-on, leaving evaluate-only Shift here.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I. Decomp is ground truth | Pass | The rule's gate, order and effects come from the decomp citations in FUTURE-FEATURES section 3 and the spec; the ledger entries cite them. |
| II. Showdown is the engine | Pass | No edit to the vendored tree: the free switch goes through the engine's own request and choice path (R1); the ordering difference is a recorded divergence (R2). |
| III. Legality of every output | Pass (not touched) | Teams and the validator are unchanged. |
| IV. Reproducible, honest evaluation | Pass | Same seeds and opponents under both styles; the policy's extra samples are seeded statelessly so no other decision moves; results independent of worker count; the style named in every result and provenance. |
| V. Verified claims, positive controls | Pass | Gate tests with the four exclusions, the hand-walked battle, must-switch and must-stay controls per policy, the pairing control (Shift vs Shift 0 discordant), numbers recorded either way. |
| VI. Reference-first speed | Pass | Not an approximation: a game rule behind an option; the policy's answer uses the existing valuation at the existing depth; Set stays available as the reference; wall times recorded. The greedy field-ability caveat (R3) is a limitation of the control player, listed below. |
| Workflow and gates | Pass | Through Spec Kit; behaviour change under `sim/` and `src/platsim`, so the Node suite and the full pytest suite gate the merge; measurements alone with Eastern times. |

**Post-design re-check (after Phase 1)**: unchanged. One item for Complexity Tracking (below).

## Project Structure

### Documentation (this feature)

```text
specs/023-shift-battle-style/
├── plan.md, research.md (R1-R8), data-model.md, quickstart.md
├── contracts/
│   ├── worker-and-policy.md     # the request field, the offer, the policy hook, the per-battle record, the log line
│   └── cli-and-reports.md       # --battle-style, the report/provenance/fingerprint fields, the ledger entries
├── scripts/paired_styles.py     # acceptance: paired Shift vs Set per team, the control, the B2 quick pair
├── evidence/, validation-log.md, tasks.md
```

### Source Code (repository root)

```text
sim/gauntlet.mjs                    # the offer: gate, c2 once, shiftChoice, switchFlag + makeRequest, per-battle shift record, log line; echo
sim/worker.mjs                      # battle_style validation; hello battle_styles
sim/policy/expectimax2.mjs          # scoreShift + shiftChoice on the v1/v2/v4 policies; _internal helpers; header note
sim/policy/greedy.mjs               # memberScore(foe=), shiftChoice
sim/bench.mjs                       # runRecorded forwards shiftChoice
sim/test/shift.test.mjs             # NEW: gate exclusions, hand-walk, policy controls, Set unchanged
src/platsim/divergence/mechanics.py # mech-shift-prompt (corrected), mech-shift-entry-order (accepted)
data/divergences.json               # regenerated
src/platsim/evaluate.py             # evaluate/evaluate_team(battle_style); request; echo; provenance; report; summary; out dir
src/platsim/sampling.py, sim/champion.py, report/losses.py   # request builders + echo checks
src/platsim/optimizer/{api,run,screen,levels,abilities}.py   # OptimizeRequest.battle_style; fingerprint; provenance; requests
src/platsim/sim/pool.py             # _PROVENANCE battle_styles
src/platsim/report/{json_report,xlsx}.py, web/result_view.py # field, row, key
src/platsim/cli.py                  # evaluate/optimize --battle-style
tests/unit/{test_reports,test_optimizer_resume,test_default_policy}.py, tests/integration/{test_divergences,test_web_result_view,test_optimize_small}.py  # pins updated
tests/integration/test_evaluate_shift.py  # NEW battle_sim: Shift determinism across worker counts; style in the report
```

**Structure Decision**: the offer lives in the gauntlet loop beside the two `choose` calls, since that is the one place
that sees both sides' requests; the policy hook is optional so every existing or test policy stays valid; the Python
field follows `player_policy` through every builder so no replay or top-up can mismatch.

## Complexity Tracking

| Item | Why | Simpler alternative rejected because |
|---|---|---|
| greedy's `memberScore` against a not-yet-active foe misses that foe's field abilities (R3) | greedy is the control player, never the default; its answer is used for the control positions and comparisons only | reading field abilities for a benched Pokemon would need a second damage path; labelled unverified for Shift accuracy, not used for results |
| the lookahead places our member before the foe and so drops our member's Intimidate on the new foe (R3) | the game's entry order; the real battle applies it | modelling both directions needs a `doSwitch` variant; the approximation affects only the one-ply valuation of the offer, recorded in the policy header |
