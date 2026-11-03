# Contract: feature 019 scripts

All scripts run from the repository root with `uv run python specs/019-e4-sampling-spike/scripts/<name>.py`. They
read the repository and `runs/`, write only under `runs/019-evidence/` (or a path given with `--out`), and never
modify `sim/`, `src/` or `tests/`. Exit code 0 on success, 1 on a failed pass criterion (the numbers are still
written), 2 on a precondition failure (missing file, machine not idle, digest mismatch).

## e4_estimator.py

- `--dirs <dir> [...]` (default: the ten spec directories) · `--threshold 0.75` · `--out runs/019-evidence/estimator.json`
- Prints one table row per directory: stored clear rate and interval, composite (topup) estimate and Bonferroni
  interval, delta interval, half-width ratio, contains_stored, threshold verdict, full verdict, agreement and
  disagreement kind, runs_needed; marks duplicates (R8) and not-estimable cases.
- Pure functions (tested): `wilson_bounds(k, n, level)`, `product_interval(e4, cyn)`, `delta_interval(...)`,
  `verdict(estimate, interval, preset, threshold, gap)`, `composite(stored: dict, kind)`.
- Positive control (test and `--control`): a synthetic stored result with Elite Four pass 0.70 and Cynthia 0.95 must
  give `below` while a naive Cynthia-only verdict would give `qualified`.

## record_runs.py

- `--team ref|b3|file:<team.json>` · `--runs 2000` · `--workers 16` · `--master 019-record-<team>` · `--out <jsonl>`
- Refuses to start if any `node` or `pytest` process is running (`pgrep -x node`, `pgrep pytest`).
- Uses `platsim.evaluate.run_full_gauntlets` with min_runs = max_runs = runs, target None, `log: "summary"`.
- Writes the header line (provenance, Eastern start/end) then one line per run in index order.

## e4_replay.py

- `--recording <jsonl>` · `--floors 0.98,0.99,0.995` · `--orders 200` · `--seed 019-replay` · `--out <json>`
- Prints per floor: switch_k distribution, Cynthia-only share distribution, fraction of orders with
  contains_full and verdict_agrees, unvalued counts, banked states at the switch, and the identity order's row.
- Pure functions (tested): `switch_point(runs_in_order, floor)`, `composite_after(runs_in_order, k)`,
  `banked_states(runs_in_order, k)`; a test recording with a member at 0.90 must never switch at floor 0.98, and one
  with all members at 1.0 must switch by about 150 to 400 runs depending on the floor (Wilson lower bound of n/n).

## time_share.py

- `--teams ref,b3,b2v2` · `--batches 50,100,200` · `--workers 16` · `--out runs/019-evidence/time_share.json`
- Per team and batch: runs the requests plain, then hooked (`NODE_OPTIONS=--import <abs>/hooks/register.mjs`), compares
  `platsim.bench` pool-side `digest_logs`, and only on equality reads the side files (`runs/019-evidence/timing/*.jsonl`)
  and reports per-trainer battle time, turns, decisions, shares, overhead and the kill flag.
- Refuses to start if the machine is not idle. Deletes the side files it created at the end of each batch after reading them.

## hooks/register.mjs, hooks/hooks.mjs

- `register.mjs`: `register('./hooks.mjs', import.meta.url)`.
- `hooks.mjs`: a `load` hook that, for the URL ending in `sim/gauntlet.mjs`, returns the source with (a) a
  `hrtime` start/stop around each battle's turn loop, (b) a counter on the player policy's `choose` calls within the
  battle, and (c) an `appendFileSync` of one JSON line per battle to `${PLATSIM_TIMING_DIR}/${process.pid}.jsonl`.
  Any other module is passed through unchanged. The response written to stdout is not modified.

## projection.py

- `--time-share runs/019-evidence/time_share.json` · `--replay-ref <json>` · `--replay-b3 <json>` ·
  `--baseline-eval 769` · `--baseline-b2quick 350` · `--out runs/019-evidence/projection.json`
- Prints the two ratio ranges with their inputs and the decision figure (the reference-team evaluation ratio).
