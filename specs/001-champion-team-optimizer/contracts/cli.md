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
| `platsim validate TEAM` | Legality check only (FR-003–FR-008c) | `TEAM` = JSON or Showdown export | violations list; exit 2 if any |
| `platsim evaluate TEAM` | Battle-test a fixed team (User Story 2) | `--runs N` (default 2000), `--seed S`, `--workers W` | EvaluationReport JSON + xlsx/csv + `team.txt` (Showdown export) |
| `platsim optimize S1 … S6` | Optimize six species (User Story 1) | `--min-clear 0.75`, `--seed S`, `--workers W`, `--budget {standard\|thorough\|quick}` (presets in research.md R8; `quick` is labelled and never `qualified`) | EvaluationReport JSON + xlsx/csv + `team.txt` (Showdown export), or "no qualifying team" report |
| `platsim explain SUBJECT` | Trace a legality fact (User Story 3) | `tm26`, `species:garchomp`, `trainer:cynthia` | availability entries with source refs |
| `platsim serve` | Start the web UI | `--port 8000` | |

Species arguments accept display names or keys (`Garchomp`, `garchomp`). The command fails on
ambiguity or on an unknown name, listing the closest matches.
