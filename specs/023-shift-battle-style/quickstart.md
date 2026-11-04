# Quickstart: Shift Battle Style

Prerequisites: `uv sync`, Node 22, the branch checked out, nothing else running for the measured steps.

1. **Node tests**: `(cd sim && node --test test/shift.test.mjs test/replay.test.mjs test/determinism.test.mjs)` → pass
   (Shift gate and hand-walk; Set digests unchanged).
2. **Python unit tests**: `uv run pytest -q tests/unit/test_reports.py tests/unit/test_optimizer_resume.py tests/unit/test_default_policy.py tests/integration/test_divergences.py` → pass.
3. **Hand check (about 2 min, alone)**: `uv run platsim evaluate tests/fixtures/reference_team.json --runs 100 --seed q023 --battle-style shift --sampling full --workers 8 --out runs/023-evidence/hand`
   Expected: `battle_style: "shift"` in result.json and the summary line; a rerun with `--workers 3` into another
   directory is byte-identical; the same with `--battle-style set` matches a pre-feature run of the same request.
4. **Integration test**: `uv run pytest -q tests/integration/test_evaluate_shift.py` (battle_sim, a few minutes).
5. **Acceptance, alone (about 1 h)**: `uv run python specs/023-shift-battle-style/scripts/paired_styles.py --teams ref,b2main,b2branch,b3 --runs 2000 --workers 16 --self --b2quick --out runs/023-evidence/pairs > runs/023-evidence/acceptance.txt`
   Expected: one row per team (both styles' clear rates and intervals, p, verdict, per-trainer rates, offers, switches,
   outcomes, wall ratio), the control row with 0 discordant, the B2 quick pair.
6. **Gates**: Node suite green; full pytest suite green; `sim_code_hash`, `platsim_code_hash` and the ledger version changed
   (expected; pre-feature checkpoints refused).
7. **Default decision (only on the owner's go)**: the request default, the CLI default, README, the tests that pin the
   default; one commit.
