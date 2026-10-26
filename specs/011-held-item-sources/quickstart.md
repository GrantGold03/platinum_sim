# Quickstart: validating H1 (held-item sources)

Run on branch `011-held-item-sources`. Rebuild generated data after any checkout:

```bash
uv run platsim extract && uv run platsim extract --check
```

## 1. The new sources show up in plain language (US1, SC-001, SC-004)

```bash
for i in focus_sash expert_belt black_belt occa_berry belue_berry; do uv run platsim explain item:$i; done
```

Expected: a `[pre_champion]` line for the Route 221 house (1 copy, the level condition and the rotation), the
Pastoria City Southwest House (unlimited, one of 17 berries) or Amity Square (partner pickup and Gift Man), with
decomp file:line references and no project labels (`contracts/explain-text.md`).

Negative controls: `uv run platsim explain item:liechi_berry` and `item:choice_band` match the baseline in
`runs/011-evidence/explain-main.txt`.

## 2. The validator agrees (US2, SC-003)

```bash
uv run pytest tests/unit/test_validator.py -q
```

Expected: one Focus Sash holder passes; two fail on copies; Choice Band fails as unavailable.

## 3. Nothing else changes (US3, SC-002, SC-006, FR-010)

```bash
uv run pytest tests/integration/test_gift_reader.py tests/integration/test_availability_controls.py -q
```

Then the before/after comparisons against `runs/011-evidence/` (baseline from T002-T005): every changed held item
traced to the three sources; every other changed site listed in `validation-log.md`; B1-B5 candidates identical;
same-seed B2 run identical apart from provenance hashes. Finally the full suite (pytest and
`node --test sim/test/*.test.mjs`).

## 4. Hands-on (user)

Run `explain` for any of the items above and read the source lines; optionally validate a team holding Focus Sash.
