# Quickstart: Lead Spike

Prerequisites: `uv sync` done, Node 22, the branch checked out, nothing else running (`pgrep -a -x node; pgrep -a pytest`
both empty). Times logged in US Eastern.

1. **Hashes before** (and again at the end): `uv run python -c "from platsim import version; print(version.sim_code_hash(), version.platsim_code_hash())"`.
2. **Unit tests**: `uv run pytest -q tests/unit/test_lead_spike.py` → all pass (positive and negative controls, pairing refusal).
3. **Recordings, one team at a time, alone** (about 17 min each):
   `uv run python specs/020-lead-spike/scripts/lead_runs.py --team b2main`
   `uv run python specs/020-lead-spike/scripts/lead_runs.py --team b2branch`
   `uv run python specs/020-lead-spike/scripts/lead_runs.py --team b2v2`
   Expected: six files per team under `runs/020-evidence/`, 2,001 lines each; lead 0 is Garchomp-first on every team.
4. **Analysis** (seconds): `uv run python specs/020-lead-spike/scripts/lead_analysis.py --out runs/020-evidence/lead_analysis.json`
   Expected: per team the six-row table with spread, the split-sample block (control 0 discordant), the screening
   block; the summary names the go / no-go for the confirmation-stage check.
5. **Record and gate**: validation log, FUTURE-FEATURES section 8, RUN-STATE; Node suite green, fast-mode pytest green,
   hashes unchanged, `git diff --stat main -- sim src/platsim` empty; the full suite skipped with the reason logged.
