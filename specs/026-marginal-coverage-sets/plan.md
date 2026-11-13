# Implementation Plan: Candidate sets by marginal coverage

**Branch**: `026-marginal-coverage-sets` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/026-marginal-coverage-sets/spec.md`

## Summary

Candidate generation (`src/platsim/optimizer/candidates.py`) builds each member's ten-move pool greedily by marginal coverage
contribution over every legal attack plus the offered variable-power moves, ranks four-move sets by coverage then the sum of
marginal contributions, and offers sets with no dead move while a live replacement exists (diversity two apart first, one apart
before a dead move, a dead move only for members with nothing live, who are listed with the reason). A cost-free move is
preferred to a cost move answering the same opponents. The 024 and 025 extras use the same rule under their valuations. A new
module `optimizer/allocation.py` resolves contested single-copy resources across the team (coverage gained decides; required
moves keep theirs) and each member's lists are rebuilt without the resources it lost, so the screen's sets are buildable and the
repair step has nothing to replace. The player-facing report gains a filler-move line per affected member. Acceptance is the
025 protocol on both codes with the attribution helper extended (cause `marginal_pool`, verified by recomputing both pools) and a
dead-moves table before and after.

## Technical Context

**Language/Version**: Python 3.12 (`uv`), the Node battle worker untouched (`sim/` hash must not change)

**Primary Dependencies**: `platsim.optimizer.candidates` (pool, ranking, extras), `platsim.optimizer.resources` (`copies`,
`realize`, `repair`), `platsim.legality.movesources` (`sources`, `uses_of`), `platsim.report` (team text, summary, xlsx),
`platsim.evaluate.summary_text`; feature 025's scripts (`acceptance.py`, `attribution.py`, `equal_levels.py`, `hand_check.py`)

**Storage**: `runs/026-evidence/` (local, gitignored) with small copies under `specs/026-marginal-coverage-sets/evidence/`

**Testing**: pytest (`tests/unit/test_marginal_coverage.py` new; `test_optimizer_candidates.py`, `test_variable_power.py`,
`test_h4_items.py`, `test_reports.py` updated); the Node suite unchanged (gate only)

**Target Platform**: this Linux machine, 16 workers, measurements alone

**Project Type**: CLI/library (optimizer + reports)

**Performance Goals**: candidate generation for the six B2 species at most twice today's (SC-006; today about 6 s per member
with the 025 item-conditioned extras: measured in the unit tests at about 38 s for six); the greedy pool is 10 passes over at most
about 40 moves × 30 opponents; the allocation adds one rebuild per member that loses a resource

**Constraints**: deterministic lists (ties by score then name); `sim/` unchanged; the validator re-checks every team; the
diversity threshold relaxes to 1 only where the alternative carries a dead move (FR-004a); no change to dominance, items, the
player, the damage model or what qualifies; the pre-feature prefix guarantee does not hold (every difference attributed)

**Scale/Scope**: three stories, two layers (candidates; team resources) plus a report line. Size warning (feature-size memory):
story 3 is the second layer; if the task count passes about 30 or the allocation needs changes in `resources.realize`, split
story 3 into feature 027 and ship stories 1 and 2 (the plan keeps story 3 self-contained: one new module, one `member_candidates`
parameter, one state record)

## Constitution Check

| Principle | Status | Note |
|---|---|---|
| I. Game data from the decomp | Pass | no new game data; move values, copies and sources are the existing decomp-backed readers |
| II. The battle engine is Showdown | Pass | `sim/` untouched; the sim hash is a gate |
| III. Legality is independent | Pass | the allocation only changes which sets are offered; `realize` and the validator still check every team; the repair step stays as the safety net |
| IV. Reproducible | Pass | every tie broken by score then name; seeds unchanged; the identity evaluations prove the battle side unchanged |
| V. Verified claims, positive controls | Pass | named controls (Infernape, Floatzel, Weavile changed; Garchomp, Staraptor unchanged; Rotom listed; a synthetic member), the attribution helper recomputes both pools, the dead-moves table, the equal-levels check |
| VI. Reference-first | Pass | the 025 acceptance protocol on both codes; a supported loss blocks the merge |
| VII. A competent human player | Pass | the feature's motivation (no dead fourth move); the filler line tells the user which slots are free; cost moves are not sold for a one-opponent gain when a cost-free move exists |

Post-design re-check: unchanged (no violation; the only size risk is story 3, handled by the split rule above).

## Project Structure

### Documentation (this feature)

```text
specs/026-marginal-coverage-sets/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── candidates-marginal.md
│   ├── allocation.md
│   └── report-filler-note.md
├── scripts/            (acceptance.py, attribution.py, equal_levels.py, hand_check.py: adapted from 025)
├── evidence/           (small copies)
└── tasks.md            (/speckit-tasks)
```

### Source Code (repository root)

```text
src/platsim/optimizer/candidates.py   pool_by_marginal, rank_sets, choose_sets (dead-move rule, FR-004a), live/dead helpers,
                                      cost preference, MemberCandidates fields (dead_moves, no_live_reason, one_apart, unavailable)
src/platsim/optimizer/allocation.py   NEW: contested resources across the team, allocation by coverage gained, rebuild
src/platsim/optimizer/run.py          _build_cands through the allocation; the prune stage records the allocation and the
                                      candidate summaries; the filler notes into the report
src/platsim/report/json_report.py     EvaluationReport.member_notes (default [], absent tolerated)
src/platsim/report/team_txt.py        the notes block after the export; legality/models.import_team skips it
src/platsim/evaluate.py               summary_text prints the notes
src/platsim/report/xlsx.py            Team sheet "Note" column
tests/unit/test_marginal_coverage.py  NEW: the controls of story 1 and 3, the report note
tests/unit/test_optimizer_candidates.py, test_variable_power.py, test_h4_items.py, test_reports.py   pins updated
specs/026-marginal-coverage-sets/scripts/   acceptance, attribution (marginal_pool, dead-moves table), equal_levels, hand_check
```

## Phase 0: Research

See [research.md](research.md): R1 marginal pool and the live/dead definitions on the real lists, R2 the set selection with the
FR-004a relaxation, R3 the cost preference, R4 extras under the same rule, R5 the attribution extension, R6 the allocation
design, R7 the report note and the importer, R8 size and split rule.

## Phase 1: Design

[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md).

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| Allocation as its own module with a rebuild loop | contested resources are a team property; member lists must not know other members | resource-aware repair only (the clarify option B) was rejected by the owner: the screen must see buildable sets |
| Attribution recomputes both pools | a pool change is otherwise unfalsifiable (every change "is the new rule") | labelling all pool changes marginal_pool |
| Importer tolerance for the notes block | team.txt must stay importable while carrying the note | summary-only note (the spec says team text and summary) |
