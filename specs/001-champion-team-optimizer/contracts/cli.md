# Contract: `platsim` command line

All commands:
- print human-readable progress to stderr;
- write machine-readable output to the paths given;
- exit 0 on success, 2 on invalid input (illegal species/set, with reasons), and 1 on internal
  error.

| Command | Purpose | Key options | Output |
|---|---|---|---|
| `platsim extract` | Regenerate `data/generated/` from the pinned decomp | `--check` (fail if output would change) | generated JSON + `manifest.json` (decomp commit, file hashes) |
| `platsim divergences` | Compare Showdown gen4 data with decomp data; refresh the ledger | | `data/divergences.json`, non-zero exit on unresolved entries |
| `platsim validate TEAM` | Legality check only (FR-003–FR-008c) | `TEAM` = JSON or Showdown export; `--json`; legality flags (below) | first line `legality options: …`, then the violations list; exit 2 if any. `--json` adds `legality_options` |
| `platsim evaluate TEAM` | Battle-test a fixed team (User Story 2) | `--runs N` (default 2000), `--seed S`, `--workers W`; legality flags (below) | EvaluationReport JSON + xlsx/csv + `team.txt` (Showdown export); `provenance.legality_options` |
| `platsim optimize S1 … S6` | Optimize six species (User Story 1) | `--min-clear 0.75`, `--seed S`, `--workers W`, `--budget {standard\|thorough\|quick}` (presets in research.md R8; `quick` is labelled and never `qualified`); legality flags (below) | EvaluationReport JSON + xlsx/csv + `team.txt` (Showdown export), or "no qualifying team" report; `provenance.legality_options` and `provenance.optimizer.request.legality_options` |
| `platsim explain SUBJECT` | Trace a legality fact (User Story 3) | `tm26`, `species:garchomp`, `trainer:cynthia` | availability entries with source refs |
| `platsim serve` | Start the web UI | `--port 8000` | |
| `platsim report --rerender RUN_DIR` | Regenerate an existing run's report with the current source-selection code; no battle is re-simulated (battle-relevant sets and NPC-trade status are checked unchanged; the validator re-runs) | `--out DIR` (default `RUN_DIR-rerendered`; never `RUN_DIR`, never over existing report files) | result.json/xlsx/csv + `team.txt` with numbers copied unchanged and `provenance.rerender` (source run, its result.json sha256, re-rendering code hash) |

Legality flags (`validate`, `evaluate`, `optimize`; `LegalityOptions` in
`src/platsim/legality/models.py`; user decisions 2026-10-08). Both are off by default:
- `--allow-egg-moves`: egg moves are legal sources. Off, a move that would be legal only as an egg
  move (or is declared `egg`) gives `EGG_MOVE_NOT_ALLOWED`. A Day-Care egg stays a legal species
  source either way.
- `--allow-trade-evolutions`: `EVO_TRADE` / `EVO_TRADE_WITH_HELD_ITEM` evolutions are legal (they need
  a second cartridge for the trade). The held item must have a pre-Champion copy and is used up, so it
  counts against that item's copies like an evolution stone. The source text ends "(trade evolution;
  needs a second cartridge for the trade)". A trade-evolved Pokemon of the player's own keeps the player
  as OT, so it gets no traded exp boost. Off (FR-005), such species give `SPECIES_TRADE_EVOLUTION`.
The options are part of the optimizer's job fingerprint (`state.json`): a checkpoint made with other
options is never resumed. `report --rerender` uses the run's recorded `provenance.legality_options`;
a run that has none predates the options and was made with egg moves allowed and trade evolutions off.

Species arguments accept display names or keys (`Garchomp`, `garchomp`). The command fails on
ambiguity or on an unknown name, listing the closest matches.
