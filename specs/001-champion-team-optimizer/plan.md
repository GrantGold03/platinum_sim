# Implementation Plan: Champion Team Optimizer

**Branch**: `001-champion-team-optimizer` (no git repo yet) | **Date**: 2026-10-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-champion-team-optimizer/spec.md`

## Summary

Given six species, find the build with the lowest expected average level after beating Cynthia.
The build must clear the first-run Elite Four and Champion gauntlet at least 75% of the time
(user-settable), with a final level gap of at most 10. Only pre-Champion, single-cartridge
resources may be used.

- **Python** (3.14):
  - extracts all game data and a source-gated availability ledger from the `pokeplatinum` decomp;
  - validates legality independently of the optimizer;
  - runs a staged search (prune → successive-halving screen → level search → paired confirmation);
  - serves a small HTML/CSS page;
  - writes an `.xlsx` team sheet with every move's source.
- **Node worker pool** (22): battles run on Showdown's in-process engine (`gen4customgame`).
  A game layer adds what Showdown lacks:
  - the decomp's own trainer AI, run by an interpreter over `trainer_ai/script.s`;
  - opponent Full Restores;
  - experience and level-ups per the decomp formulas;
  - a model-based 2-ply expectimax player.

Details and sources: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.14 (extraction, legality, optimizer, stats, web, reports); Node.js 22.22 plain ES modules (sim worker, game layer, AI interpreter, player policy)

**Primary Dependencies**:
- Pokémon Showdown (vendored, `dist/sim`);
- FastAPI and uvicorn (web);
- openpyxl (xlsx);
- pytest (tests).

No other third-party battle or data libraries.

**Storage**:
- Files only.
- `data/generated/*.json`: extracted, reproducible.
- `data/divergences.json`: ledger.
- `runs/<job-id>/`: job state, checkpoints, reports.

**Testing**: pytest (Python); `node --test` (worker)

**Target Platform**: Local Linux desktop (16 cores, 30 GB RAM), offline after setup; browser on localhost

**Project Type**: Local tool: Python package with CLI and web UI, plus a Node sim-worker subproject

**Performance Goals**:
- Measured in spike T-spike-1 before the budget is fixed.
- Working target: ≥ 30 gauntlet runs/s across 16 workers with `expectimax2-v1` (**UNVERIFIED**).
- Final evaluation ≥ 2,000 runs per finalist.

**Constraints**:
- Every game fact comes from the decomp at a pinned commit.
- Showdown source is not edited; data patched at runtime.
- Deterministic under seed.
- 95% CI half-width ≤ 2 points on gauntlet and Champion clear rates.
- Simulation counts are never silently reduced.

**Scale/Scope**:
- 493 species, ~467 moves, 5 opponent trainers, 1 local user, 1 job at a time.
- Typical optimize: tens to hundreds of thousands of gauntlet runs (estimate; refined after the
  spike).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Principle | Gate | Pre-research | Post-design |
|---|---|---|---|
| I. Decomp is ground truth | All game data extracted by code from `pokeplatinum` with `path:line` refs; post-game status derived from game gates, not a list | PASS (plan) | PASS: R1, R2, data-model `src` fields, `extract --check` |
| II. Showdown is the battle engine | No reimplemented mechanics; divergences ledgered; opponent policy named; vendored tree not edited | PASS with justification | PASS: R4/R5. Damage-formula port is used only as the AI's estimator and as a cross-check (see Complexity Tracking). Patches applied at runtime via `Dex.mod('gen4').data`. |
| III. Legality of every output | Independent validator on every output; TM/item copy limits; explicit constraints | PASS | PASS: `legality/` package separate from `optimizer/`; `validate` CLI; runs on every report |
| IV. Reproducible, honest stats | Seeds, Wilson CIs, paired comparisons, provenance in every result | PASS | PASS: R8; worker determinism guarantee; Provenance sheet |
| V. Verified claims, positive controls | Known-value tests; positive controls for negative results; no "done" without output | PASS | PASS: R11 suites; R2 controls (Battle Zone, Survival tutor, Foppa = post-game; Route 212 tutor, TM76 = pre) |
| Tech constraints | Offline runtime; ROM never committed; generated data reproducible | PASS | PASS: network only at setup (`npm ci`, `uv sync`) |

No unjustified violations. ERROR conditions: none.

## Project Structure

### Documentation (this feature)

```text
specs/001-champion-team-optimizer/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1: cli.md, http-api.md, worker-protocol.md, spreadsheet.md
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
pyproject.toml                 # package "platsim", console script `platsim`
src/platsim/
├── decomp/                    # readers for pokeplatinum sources (json, .s scripts, .h tables, csv)
│   ├── constants.py           #   generated/*.txt enums
│   ├── species.py, moves.py, items.py, tutors.py, trainers.py, exp.py
│   ├── stats.py               #   decomp stat formula (reference for Showdown set conversion)
│   └── scripts.py             #   field-script parser (gift/item/warp/gate commands)
├── availability/              # ledger, map graph, gate rules (R2)
├── legality/                  # independent validator (Constitution III)
├── divergence/                # Showdown-vs-decomp comparison + ledger
├── sim/                       # worker pool client (NDJSON), seeds
├── optimizer/                 # pruning, successive halving, level search, ability screening
├── stats.py                   # Wilson CI, paired comparison (statistics, not game stats)
├── report/                    # JSON, xlsx/csv writers
├── web/                       # FastAPI app + static/index.html, style.css, app.js
└── cli.py
sim/                           # Node worker (plain ES modules)
├── worker.mjs                 # NDJSON loop, Showdown import, runtime data patches
├── gauntlet.mjs               # 5-battle run, restore between battles
├── exp.mjs                    # participation + exp + level-up (decomp formulas)
├── damage.mjs                 # port of BattleSystem_CalcMoveDamage (AI + cross-check only)
├── ai/
│   ├── parse.mjs              # reads trainer_ai/script.s + aicmd.inc at startup
│   ├── interp.mjs             # 109-command interpreter
│   ├── adapter.mjs            # battle-state queries over Showdown objects
│   └── items.mjs, switch.mjs  # ShouldUseItem / ShouldSwitch / PostKOSwitchIn
├── policy/
│   ├── greedy.mjs             # baseline
│   └── expectimax2.mjs        # player policy (R7)
└── test/
data/
├── generated/                 # platsim extract output (never hand-edited)
└── divergences.json
tests/                         # pytest: unit/, integration/, fixtures/
runs/                          # job outputs (git-ignored)
pokeplatinum/  pokemon-showdown/   # vendored, pinned, not edited
```

**Structure Decision**:
- One Python package (`src/platsim`) holds everything that is not battle-time.
- One Node subproject (`sim/`) holds everything that runs inside a battle, for speed.
- The vendored repos stay untouched apart from Showdown's build outputs (`node_modules/`, `dist/`).

## Phases after this plan (for `/speckit-tasks`)

1. **Spikes** (de-risk first; each produces measured numbers):
   - T-spike-1: Showdown worker throughput (random vs greedy).
   - T-spike-2: mid-battle level-up by mutating a Showdown Pokémon's level and stats.
   - T-spike-3: injecting a pseudo-move for opponent Full Restore.
2. **Data**: extractors + known-value tests → availability ledger + controls → legality validator.
3. **Engine**: worker + seeds + determinism → exp/level-up → damage port + cross-check → AI
   interpreter (Basic → EvalAttack → Expert → SetupFirstTurn) → Full Restore → divergence ledger.
4. **Evaluate** (User Story 2, MVP): greedy policy first, then `expectimax2-v1` with its strength
   benchmark.
5. **Optimize** (User Story 1): pruning, ability screening, successive halving, level search,
   confirmation.
6. **Explain** (User Story 3), **reports** (xlsx/csv), **web UI**.

## Complexity Tracking

| Violation / complexity | Why needed | Simpler alternative rejected because |
|---|---|---|
| Port of the decomp damage formula in JS alongside Showdown's | The game's AI scores moves with its own damage estimate (`TrainerAI_CalcDamage` → `BattleSystem_CalcMoveDamage`); the expectimax player needs fast analytical damage; and Constitution V needs a cross-check of Showdown damage | Using Showdown's damage for AI estimates would make the AI follow Showdown, not the game, wherever they differ. Real damage is still resolved only by Showdown. |
| AI bytecode interpreter (~109 commands) | FR-010 requires the in-game AI; interpreting the original script text keeps every decision traceable to decomp lines | A hand-written summary AI can't be audited against the decomp and silently drifts |
| Two languages (Python + Node) | The user asked for Python; Showdown is Node, and battle-time logic must share its process for speed | Python-only would mean a reimplemented simulator (Constitution II) or one subprocess round-trip per decision (too slow) |
| Map graph for availability | FR-003 forbids a hand list of post-game areas | A hand list is quicker but violates Constitution I |
