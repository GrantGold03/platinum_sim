# Quickstart: Variable-Power Moves Offered by the Optimizer

Prerequisites: `uv sync`, Node 22, the branch checked out, nothing else running for the measured steps.

1. **Pre-feature side (before any code commit; the branch's code equals `main`)**:
   `uv run python specs/024-variable-power-moves/scripts/acceptance.py --side main --workers 16`
   Expected: `runs/024-evidence/b2-main/result.json`, `ident-main/{ref,b2main}/result.json`, `evidence/b2-candidates-main.json`;
   about 12 min.
2. **Node tests**: `(cd sim && node --test test/variable_power.test.mjs test/ai_cmds_damage.test.mjs test/replay.test.mjs test/determinism.test.mjs)` → pass
   (helper vs decomp tables; greedy scoring; recorded results unchanged).
3. **Python unit tests**: `uv run pytest -q tests/unit/test_variable_power.py tests/integration/test_divergences.py -m "not battle_sim"` → pass
   (weight pins and Node parity; per-opponent values; the additive prefix against the snapshot; the ledger).
4. **Hand check**: `uv run python -c "from platsim.optimizer import candidates as C; ..."` printing the six B2 species'
   candidate lists: today's sets first, extras after, each extra naming one of the four moves.
5. **Branch side, alone (about 15 min)**: `uv run python specs/024-variable-power-moves/scripts/acceptance.py --side branch --workers 16 > runs/024-evidence/acceptance.txt`
   Expected: the table (both winners, members with a variable move, the equal-levels row with p and the level difference,
   the identity rows byte-identical); pass by FR-009 or the recorded cause.
6. **Gates**: Node suite green; full pytest suite green; `git diff --stat main -- pokemon-showdown` empty; hashes and the
   ledger version changed (expected).
