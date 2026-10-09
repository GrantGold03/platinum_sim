# Quickstart: validating the Web UI redesign

Every check below has an expected result. "Done" means each one was run and its output recorded
in `validation-log.md` (Principle V).

## Prerequisites

- `uv sync --group dev`. This adds `playwright` (R6). It is a one-time PyPI download, and no
  browser is downloaded.
- `/usr/bin/google-chrome` must be present, because the browser tests use `channel="chrome"`.
  Without it, the browser tests are **skipped with a reason**. A skip is not a pass.
- `node` and `pokemon-showdown/` are set up as for 001. They are only needed for the real-job
  check (V7).

## V1. Existing tests still pass (regression)

```bash
uv run pytest -q tests/integration/test_web.py
```

Baseline before this feature: `8 passed in 35.98s` (2026-10-09). Expect the same tests to pass,
plus the new ones. The baseline tests that assert the old `summary` or `table` shape get updated,
not deleted.

## V2. Sprite endpoint, with a positive control

```bash
uv run pytest -q tests/integration/test_web_sprites.py
```

The tests check:
- `infernape/front.png` → 200 `image/png`, with a `tRNS` chunk present. This is the positive
  control.
- `blissey/front.png` → 200, which proves the female-only fallback.
- `notamon/front.png` → 404.
- `..%2Fetc/front.png` → 404.

## V3. Result view mapping

```bash
uv run pytest -q tests/integration/test_web_result_view.py
```

The fixture is a copy of `runs/final-defaults` (`result.json` and `result.csv`) wrapped in a
`done` job. The tests check:
- The summary has exactly the keys in the [data model](./data-model.md).
- The Luxray ability is `"Rivalry/Intimidate (no significant difference)"`. Gardevoir is a tie
  as well. Infernape shows `"Blaze"`.
- No team entry has nature, IVs, EVs or held-item-source keys.
- `per_trainer` has 5 entries, in order aaron → cynthia, and Cynthia's rate is about 0.869.

## V4. Cancel (fake runner in a child process)

```bash
uv run pytest -q tests/integration/test_web_cancel.py
```

A module-level fake runner starts a `sleep` child (which stands in for the Node workers) and
reports progress in a loop. The tests check:
- **Positive control**: the job reaches `running` and its child pid is alive.
- After cancel: the status is `cancelled` within 10 s, the child pid is gone, and the next queued
  job starts.
- A queued job that is cancelled never starts.
- Cancelling a `done` job → 409.

## V4b. No orphaned jobs, and the process boundary leaves results unchanged

```bash
uv run pytest -q tests/integration/test_web_shutdown.py tests/integration/test_web_process_determinism.py
```

- **Shutdown**: after both SIGINT and SIGKILL of the server, the job child and its `sleep` stand-in are gone within 10 s. The positive control is that they were alive before the signal.
- **Determinism**: a 40-run `evaluate` gives a byte-identical `result.json` in a child process and in-process.

## V5. Browser walkthrough (SC-006, closes the RUN-STATE "real-browser UI check")

```bash
uv run pytest -q -m browser tests/browser/
```

The test serves the page with a fake runner and the V3 fixture run, then drives Chrome through
every acceptance scenario in User Stories 1–4:
- the two-column layout at 1920×1080, and the stacked layout at 360 px with no horizontal
  scroll;
- the search list hidden until typing;
- icons in team slots;
- the budget sent in the POST;
- the seed tooltip on hover and on focus only;
- progress visibility, elapsed time ticking, ETA text, and cancel;
- the run picker defaulting to the newest run, and switching runs;
- move-source tooltips;
- the chart with 5 bars;
- the absence of every removed field.

Screenshots of both colour schemes are saved to the session scratchpad and checked by eye.

## V6. Reports unchanged (SC-007, FR-030)

```bash
sha256sum runs/final-defaults/result.{json,csv,xlsx} runs/final-defaults/team.txt
```

Record the hashes before the change, then check that the bytes downloaded through
`/api/jobs/<fixture>/…` match them after.

## V7. One real job, end to end, compared with the command line (manual, about 2 × 25 min with `quick`)

1. Run `uv run platsim serve`, open http://127.0.0.1:8000, and wait about 35 s for the species
   data to load.
2. **Throwaway job A**: build any six available species, choose **quick**, and start it. Check:
   - progress appears, with an ETA (history for quick exists: `runs/job-…feb186`,
     `optimize-smoke-quick`);
   - elapsed time ticks.
3. **Reference job B**, queued behind A: build the six reference species (infernape, staraptor, luxray, garchomp, gyarados, gardevoir), choose **quick**, set the seed to **t058**, keep the minimum clear rate at 75% and both legality boxes unchecked, and start it. Wait until `pgrep -f sim/worker.mjs` returns pids (A's workers start after its roughly 35 s ledger build). This is the positive control. Record that pid set, then cancel **A** while it is running. Check:
   - A shows `cancelled` within 10 s;
   - none of A's recorded worker pids is still alive. Compare pid sets, because B starts new workers;
   - B starts.
4. Let B finish. Check:
   - the result panel switches to B without a reload (FR-014);
   - the old runs are listed in the dropdown.
5. Run the same request with `uv run platsim optimize infernape staraptor luxray garchomp gyarados gardevoir --budget quick --seed t058 --out <scratchpad>/cli-t058`. Then run `cmp runs/<job B>/result.json <scratchpad>/cli-t058/result.json`. Expect exit code 0, meaning byte-identical, as in feature 001's T058 (`tests/integration/test_optimize_small.py`).
