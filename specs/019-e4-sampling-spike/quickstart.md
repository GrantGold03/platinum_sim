# Quickstart: Elite Four Sampling Spike

Prerequisites: `uv sync` done, Node 22, the repository at the feature branch, nothing else running
(`pgrep -a -x node; pgrep -a pytest` both empty). All times are logged in US Eastern.

1. **Code hashes before** (also after, at the end):
   `uv run python -c "from platsim import version; print(version.sim_code_hash(), version.platsim_code_hash())"`
   Expected: the same two hashes as `main` at the branch point.

2. **Unit tests (fast)**: `uv run pytest -q tests/unit/test_e4_estimator.py` → all pass, including the positive
   control and the not-estimable case. Then the fast suite: `uv run pytest -q -m "not battle_sim"` → green.

3. **US1, estimator on stored evidence** (seconds):
   `uv run python specs/019-e4-sampling-spike/scripts/e4_estimator.py --out runs/019-evidence/estimator.json`
   Expected: ten rows, all distinct, `contains_stored` true and `agreement` true on all,
   or a listed disagreement with its kind and `runs_needed`; exit 0 on pass, 1 on fail.

4. **US2, two recordings** (about 13 min each, alone):
   `uv run python specs/019-e4-sampling-spike/scripts/record_runs.py --team ref --out runs/019-evidence/recording-ref.jsonl`
   `uv run python specs/019-e4-sampling-spike/scripts/record_runs.py --team b3 --out runs/019-evidence/recording-b3.jsonl`
   Expected: 2,000 run lines each; the ref recording's clear rate near 0.94, B3's near 0.77 with Lucian near 0.89.

5. **US2, replay** (seconds each):
   `uv run python specs/019-e4-sampling-spike/scripts/e4_replay.py --recording runs/019-evidence/recording-ref.jsonl --out runs/019-evidence/replay-ref.json`
   `uv run python specs/019-e4-sampling-spike/scripts/e4_replay.py --recording runs/019-evidence/recording-b3.jsonl --out runs/019-evidence/replay-b3.json`
   Expected: ref: at least one floor with median Cynthia-only share ≥ 0.5, verdict_agrees in 100% and contains_full in
   ≥ 95% of orders; B3: switch_k null for every floor and order, estimate == full clear rate.

6. **US3, time share** (about 8 min, alone):
   `uv run python specs/019-e4-sampling-spike/scripts/time_share.py --out runs/019-evidence/time_share.json`
   Expected: `digests_equal` true for every team and batch; Elite Four share per team and batch; the kill flag on the
   strong team at batch 200.

7. **US3, projection**:
   `uv run python specs/019-e4-sampling-spike/scripts/projection.py --out runs/019-evidence/projection.json`
   Expected: two ratio ranges and the decision figure.

8. **Record and gate**: validation log (commands, Eastern times, hashes, outputs), FUTURE-FEATURES section 8 go / no-go
   with the fallback order on no-go, RUN-STATE START HERE; Node suite `(cd sim && node --test test/*.test.mjs)` green;
   fast-mode pytest green; hashes unchanged (step 1 repeated). The full suite is skipped on that evidence, logged.
