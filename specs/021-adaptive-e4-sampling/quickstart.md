# Quickstart: Adaptive Elite Four Sampling in evaluate

Prerequisites: `uv sync`, Node 22, the branch checked out, nothing else running for the measured steps.

1. **Unit tests**: `uv run pytest -q tests/unit/test_sampling.py tests/unit/test_reports.py` → pass (positive control, switch rule, round trip, old JSON reads as full).
2. **Hand check, small**: `uv run platsim evaluate tests/fixtures/reference_team.json --runs 80 --seed q --budget quick --sampling adaptive --floor 0.9 --workers 8 --out runs/021-evidence/hand`
   Expected: the summary names the method; result.json has `sampling: "adaptive"`, `switch_run` about 36, `cynthia_only_runs` > 0, loss causes present; `--workers 3` to another directory gives a byte-identical result.json.
3. **Control**: the same with `--floor 1.0` → result.json byte-identical to `--sampling full` (same seed and count).
4. **Integration test**: `uv run pytest -q tests/integration/test_evaluate_adaptive.py` → pass (battle_sim).
5. **Acceptance, alone** (about 40 minutes): `uv run python specs/021-adaptive-e4-sampling/scripts/acceptance.py --out runs/021-evidence/acceptance.json`
   Expected: on all six teams the adaptive estimate inside the full interval and the same verdict; wall ratio ≥ 1.5 on the two fixtures, about 1.0 on B3; controls pass. Then `--control`.
6. **Gates**: Node suite green; full pytest suite green (`uv run pytest -q --durations=25`); `sim_code_hash` unchanged.
7. **Default flip (only on the owner's go)**: change the two defaults, README, tests; one commit.
