# Implementation Plan: Required HMs on the Team

**Branch**: `006-required-hms` (git worktree `../platinum_sim-006`) | **Date**: 2026-10-13 |
**Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-required-hms/spec.md`. User decision
(2026-10-13): a required HM must be in a final moveset.

## Summary

Users can require any of the eight HMs. Each required HM must end up in at least one member's
final 4-move set, and an HM that none of the six can learn is refused before any battle.

**Approach**:
- **Placement.** The optimizer's move pool contains only attacks, and moves are rewritten in four
  later places (research R1). So required HMs are **placed**, not searched for: a deterministic
  `place_required_hms` runs at the start of `resources.realize`. It gives each missing HM to the
  member with the cheapest legal slot, replacing that member's weakest attack. Every path to
  battle and to the report goes through `realize`, so no path can lose an HM.
- **Refusal.** A shared `unlearnable_moves` check refuses impossible requests in the optimizer and
  the web.
- **Validation.** The validator gets an independent `REQUIRED_HM_MISSING` rule.
- **Recording.** Required HMs travel on `OptimizeRequest`, not `LegalityOptions`. They enter the
  fingerprint and the reports only when non-empty, so defaults stay byte-identical.
- **Web.** A new step 3, "Required HMs", with eight checkboxes. Optimize becomes step 4.

## Technical Context

**Language/Version**: Python 3.14, and browser JavaScript (no build step).

**Primary Dependencies**: existing only.

**Storage**:
- job.json `options.required_hms` (optional);
- report `provenance.required_hms` (optional);
- no data regeneration in the main checkout. The worktree needs its own `platsim extract`.

**Testing**:
- pytest: a new `tests/unit/test_required_hms.py`, plus updates to `test_validator.py`, the
  optimizer tests and `test_web.py`. The browser test for step order is in `tests/browser/`.
- The full suite runs before merge (about 2.5 h).

**Target Platform**: Linux, local, offline.

**Project Type**: a Python CLI package with a local web UI.

**Performance Goals**: placement is O(6 members × 4 moves × HMs) per `realize` call, which is
negligible next to battles. The refusal check runs at most 8 × 6 `MS.sources` calls, once per
request.

**Constraints**:
- With no HM required, fingerprints and outputs are byte-identical (FR-009).
- The validator stays independent of the optimizer.
- `sim/` is untouched. Seeds and determinism are unchanged.

**Scale/Scope**: about 9 source and static files, 5 test files, 1 new test module and the README.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I. Decomp is ground truth | PASS | The HM ↔ move mapping comes from `decomp.items.tm_moves()` (R6). Learnability is the existing decomp-backed `MS.sources`. Nothing is hand-typed. |
| II. Showdown is the battle engine | PASS | `sim/` and Showdown are unchanged. The HM is an ordinary move in the battle team. |
| III. In-game legality | PASS | The requirement is an explicit input ("optional constraints MUST be explicit inputs"). The validator enforces it independently (`REQUIRED_HM_MISSING`, R5). Impossible inputs fail with a clear reason per HM (R3). It narrows the output, so the rules for options that widen output don't apply. |
| IV. Reproducible, statistically honest | PASS | Placement is deterministic. Required HMs are part of the fingerprint and the report provenance when set, so runs with and without them are never confused. The evaluation uses the real HM-carrying moveset, so win rates stay honest. Defaults are byte-identical. |
| V. Verified claims, positive controls | PASS | Each check has a counterpart: refusal versus a team with a Fly learner; the validator on Fly (missing) versus Waterfall (carried, Gyarados in `legal_team.json`); placement versus the unchanged TeamSpec; the default fingerprint versus the T001 record. |
| Technical constraints | PASS | Offline, no paid services. The worktree builds its own generated data with the single documented command. |
| Workflow gates | PASS | Spec Kit flow, feature branch in a worktree, merge only after the user tests, RUN-STATE updated. |

**Post-design re-check (after Phase 1)**: still PASS.

## Complexity Tracking

| Choice | Why needed | Simpler alternative rejected because |
|---|---|---|
| Placement inside `realize` instead of a search filter | Defog never enters the pool, and the 4 rewrite paths (repair, setup check, runner-up, baseline) can drop an HM (R1) | A filter can find no qualifying team, and patching every rewrite path separately would drift |

## Project Structure

### Documentation (this feature)

```text
specs/006-required-hms/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R7
├── data-model.md        # H1–H4
├── quickstart.md        # V1–V6
├── contracts/required-hms.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root of the worktree)

```text
src/platsim/
├── legality/
│   ├── movesources.py     # HM_MOVES (from decomp.items.tm_moves), unlearnable_moves()
│   └── validator.py       # validate(..., *, required_hms=()); REQUIRED_HM_MISSING
├── optimizer/
│   ├── api.py             # OptimizeRequest.required_hms
│   ├── resources.py       # place_required_hms(); realize(..., *, required_hms=())
│   └── run.py             # refusal after resolve_species; pass required_hms to every realize/validate;
│                          #   fingerprint + provenance only when non-empty
├── evaluate.py            # load_and_validate(..., required_hms)
├── report/rerender.py     # read provenance.required_hms → validate / realize
├── cli.py                 # --require-hm on optimize / evaluate / validate
└── web/
    ├── app.py             # _options: required_hms; run_one passes it; docstring
    ├── species_catalog.py # resolve_team: HM learner check (callback like 004 conflicts)
    ├── result_view.py     # summary.required_hms
    └── static/{index.html, app.js, style.css}   # step 3 card, step 4 heading, body key, summary row
README.md                  # required HMs section

tests/
├── unit/test_required_hms.py         # NEW: placement, refusal, unlearnable_moves, fingerprint default
├── unit/test_validator.py            # REQUIRED_HM_MISSING + control
├── integration/test_web.py           # 422 refusal, job.json key, step headings, checkbox scope fix
└── browser/test_page.py              # step order and HM toggles (system Chrome)
```

**Structure Decision**: no new module. Placement lives with source assignment in `resources.py`.
The learnability check lives in `movesources.py`, where the validator can use it without
importing the optimizer.

## Delivery order

1. **Setup** in the worktree: `uv sync` and `extract`, plus a baseline that includes the default
   fingerprint.
2. **US2 refusal and the validator rule** (P1). These are the cheap, safe pieces: `HM_MOVES`,
   `unlearnable_moves`, `REQUIRED_HM_MISSING`, the optimizer and web refusal.
3. **US1 placement** (P1): `required_hms` on the request, `place_required_hms` inside `realize`,
   threading it through `run.py`, evaluate, rerender and the CLI, and fingerprint and provenance
   only when set.
4. **US3 web step** (P2): the step 3 card, the renumbering, the body key, the summary row, and the
   test scope fix.
5. **Polish**: the README, a quick end-to-end optimize (V6), the full suite, RUN-STATE, and a
   commit on the branch.
