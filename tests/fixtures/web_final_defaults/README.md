# web_final_defaults fixture

This is a frozen, byte-for-byte copy of a real optimizer run: the four report files from
`runs/final-defaults/` (2026-10-08, default legality, standard budget, qualified at an average
final level of 58.23). `job.json` wraps it as a finished web job with id
`job-20261008T000000Z-f1f1f1`, which matches `ID_RE` in `src/platsim/web/app.py`. The job has
no `platsim_version`, because the run recorded none.

The result-view tests (`tests/integration/test_web_result_view.py`) and the browser tests use
it. They copy it into a temporary runs directory with `_web_helpers.copy_fixture_run`, which
rewrites `result_paths`. Never edit the report files: the tests compare downloads byte for byte.
