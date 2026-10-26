# Quickstart: validating H1 (held-item sources)

Run on branch `011-held-item-sources`. Always rebuild generated data after a checkout:

```bash
uv run platsim extract && uv run platsim extract --check
```

## 1. New sources show up in plain language (US1, SC-001, SC-004)

```bash
for i in focus_sash expert_belt black_belt occa_berry belue_berry; do uv run platsim explain item:$i; done
```

Expected: each shows a `[pre_champion]` line for Route 221 house (1 copy), Pastoria City Southwest House
(unlimited) or Amity Square (unlimited, partner species condition), with a decomp file:line, and no
feature number, task id or internal term (`contracts/explain-text.md`).

Negative control: `uv run platsim explain item:liechi_berry` and `item:choice_band` match `main`.

## 2. Validator agrees (US2, SC-003)

```bash
uv run pytest tests/unit/test_validator.py -q
```

Expected: one Focus Sash holder passes; two fail on copies; Choice Band fails as unavailable.

## 3. Nothing else changes (US3, SC-002, SC-005, SC-006)

```bash
uv run pytest tests/integration/test_availability_controls.py tests/integration/test_explain_item_sources.py -q
```

Then compare against the baseline saved before the code change (`runs/011-evidence/`): held-item counts
74 / 40 / 44, every changed item from the new sources, B1-B5 held-item candidates identical, and the
same-seed quick optimization identical apart from provenance hashes. Finally the full suite (pytest and
`node --test sim/test/*.test.mjs`).

## 4. Hands-on (user)

Start the web UI or run `explain` for any of the 11 items and read the source lines.
