# Quickstart: Adaptive Sampling in the Optimizer's Confirmation Stage

Prerequisites: `uv sync`, Node 22, the branch checked out, nothing else running for the measured steps.

1. **Unit tests**: `uv run pytest -q tests/unit/test_confirm_pairing.py tests/unit/test_optimizer_resume.py tests/unit/test_sampling.py` → pass.
2. **Hand check (about 10 min, alone)**: `uv run platsim optimize infernape staraptor luxray garchomp gyarados gardevoir --budget quick --seed q022 --sampling adaptive --floor 0.9 --workers 8 --out runs/022-evidence/hand`
   Expected: state.json's confirm attempt shows `sampling: adaptive`, a switch run and Cynthia-only runs; result.json carries the 021 fields and `provenance.sampling_per_stage`; a second run with `--workers 3` into another directory is byte-identical.
3. **Integration test**: `uv run pytest -q tests/integration/test_optimize_adaptive.py` (battle_sim, about 20 min).
4. **Acceptance, alone (about 1 h)**: `uv run python specs/022-confirm-adaptive-sampling/scripts/acceptance.py --out runs/022-evidence/acceptance.json`
   Expected: block 1 same species/moves/items (levels identical or a recorded borderline flip), containment both ways, wall ratios; block 2 containment and agreement on both teams with about 1.7x on b2-main and 1.0x on B3; block 3 byte equality; block 4 exact equality of the full-kind McNemar counts.
5. **Gates**: Node suite green; full pytest suite green; `sim_code_hash` unchanged.
6. **Default flip (only on the owner's go)**: the request default, the CLI default, README, the tests that pin the default; one commit.
