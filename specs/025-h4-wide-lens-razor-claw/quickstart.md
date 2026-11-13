# Quickstart: H4, Wide Lens and Razor Claw

Prerequisites: `uv sync`, Node 22, the branch checked out, nothing else running for the measured steps.

1. **Pre-feature side (before any code change)**: `uv run python specs/025-h4-wide-lens-razor-claw/scripts/acceptance.py --side main --workers 16`
   → `runs/025-evidence/b2-main`, `ident-main/*`, `evidence/candidates-main.json` (B2 at the job's reference level; B1 to B5
   at their recorded levels, with items and pruned maps); about 12 min.
2. **Unit tests**: `uv run pytest -q tests/unit/test_h4_items.py tests/unit/test_reports.py tests/unit/test_optimizer_candidates.py -m "not battle_sim"`;
   `(cd sim && node --test test/switch_reset.test.mjs)`.
3. **Hand check**: print the six B2 species' candidate lists on the branch: today's sets (reordered where a high-crit move
   competes), the 024 extras, the lens- and claw-conditioned extras with their items, `items_extra` per base set, the pruned
   map naming Dig, Dive or Take Down where the member learns them.
4. **Branch side, alone (about 20 min)**: `uv run python specs/025-h4-wide-lens-razor-claw/scripts/acceptance.py --side branch --workers 16 > runs/025-evidence/acceptance.txt`
   → both winners, the members holding a new item, the screen overlap and `extras_screened` by kind, the identity rows, the
   equal-levels row, the attributed diff per member (no "defect" lines); the FR-010 verdict.
5. **Gates**: Node suite green; full pytest suite green; `sim_code_hash` and the ledger version unchanged, `platsim_code_hash`
   changed; `git diff --stat main -- pokemon-showdown sim` shows only `sim/test/`.
