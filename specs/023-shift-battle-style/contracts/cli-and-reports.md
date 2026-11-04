# Contract: CLI, reports, provenance, fingerprint, ledger

## CLI

- `platsim evaluate ... --battle-style {set,shift}` (default `set`); `platsim optimize ... --battle-style {set,shift}`
  (default read from `OptimizeRequest.battle_style`, the pinned rule). Unknown value: argparse error (exit 2). The web app
  passes nothing (default).

## Python API

- `evaluate(..., battle_style="set")`, `evaluate_team(..., battle_style="set")`; `run_full_gauntlets`, `run_adaptive`,
  `cynthia_only_request`, `champion_topup`, `collect_loss_causes`/`replay_requests`, the optimizer's stage request builders
  and `bench` all carry `battle_style`; every echo check reads `r.get("battle_style", "set")` and raises on mismatch.
- `OptimizeRequest.battle_style: str = "set"`, `InvalidRequest` on other values.

## Report and provenance

- result.json: `battle_style` at the top level (default `set` when absent on read); `provenance.battle_style`; the
  optimizer's `provenance.request.battle_style`.
- `summary_text` first line: `... sampling <x> style <set|shift>`.
- xlsx Evaluation sheet: row "Battle style" after "Sampling method".
- Web result view summary: key `battle_style`.
- `job_fingerprint`: `battle_style` only when it differs from the request default. `default_out_dir` for evaluate: the
  style enters the hash only when non-default.

## Ledger

- `mech-shift-prompt` (corrected) and `mech-shift-entry-order` (accepted) in `mechanics._ENTRIES`; `data/divergences.json`
  regenerated with `uv run platsim divergences`; `test_ledger_matches_fresh_diff`'s id list updated.
