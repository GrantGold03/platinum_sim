# Contract: feature 020 scripts

Run from the repository root with `uv run python specs/020-lead-spike/scripts/<name>.py`. They read the repository
and `runs/`, write only under `runs/020-evidence/` (or `--out`), never modify `sim/`, `src/` or `tests/`. Exit 0 on
success, 1 when a pass criterion fails (numbers still written), 2 on a precondition failure (missing file, machine not
idle, seed-list mismatch).

## lead_runs.py

- `--team b2main|b2branch|b2v2` (one team per invocation) · `--leads 0,1,2,3,4,5` · `--runs 2000` · `--workers 16` ·
  `--out-dir runs/020-evidence`
- Refuses to start unless the machine is idle. For each lead in order: rotate (R1), run `run_full_gauntlets` with
  min_runs = max_runs = runs, target None, the default player, `log: "summary"`; write `<team>-lead<i>.jsonl` (R7);
  print one summary line per lead (clear rate, per-trainer rates, wall, gauntlets/s).

## lead_analysis.py

- `--evidence-dir runs/020-evidence` · `--teams b2main,b2branch,b2v2` · `--out runs/020-evidence/lead_analysis.json`
- Pure functions (tested in `tests/unit/test_lead_spike.py`): `rotate(team, i)`, `load_recording(path)`,
  `check_paired(rec_a, rec_b)` (identical seed lists or raise), `lead_row(rec, start_levels)`, `choose_best(recs, n)`
  (R2, returns index and tie flag), `held_out(chosen, first, lo=1000, hi=2000)` and `naive(chosen, first)` (both via
  `platsim.stats.mcnemar_exact`), `control(first)` (0 discordant), `screening(recs)` (R5), `level_gains(rows)` (R6).
- Prints per team: the six-row table with spread; the split-sample block (chosen lead, held-out counts and p and
  verdict, naive counts and p labelled selection-biased, control); the screening block; the chosen lead's gain versus
  the others. Then the summary: per team supported_gain, and the go / no-go for the confirmation-stage check.
- With fewer than six recordings for a team (the smoke), the table prints for the leads present and the split-sample and
  screening blocks are skipped with a one-line note; the summary then marks that team as not judged.
- Controls in the tests: synthetic recordings where one lead clears 10 points more on independent Bernoulli draws (seeded; a 5-point case is printed for information only) must give verdict A on the held-out half; six identical recordings must give `indistinguishable` with 0
  discordant pairs; two recordings with different seed lists must raise.
