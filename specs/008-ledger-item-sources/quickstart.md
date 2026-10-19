# Quickstart: validating 008 ledger item sources

All local, `uv run`. Rebuild generated data on the branch you are testing; it is git-ignored and shared
between branches.

## 1. Rebuild and check

```bash
uv run platsim extract && uv run platsim extract --check
uv run pytest -q tests/integration/test_availability_controls.py tests/unit/test_validator.py tests/integration/test_extract.py
```

Expected: counts 74 unlimited / 40 finite / 44 unavailable; Focus Sash, Expert Belt, Black Belt = 1;
Liechi Berry 0; Choice Band unavailable.

## 2. Look up the new sources

```bash
uv run platsim explain item:focus_sash     # Route 221 house, 1 copy, level condition, before the Champion
```

Also one Pastoria berry and one Amity Square berry; each shows its script reference and verdict.

## 3. Before/after diff

Compare per-item availability with `runs/008-evidence/availability-main-f88cdd0.json`: every changed item
comes from the three sources.

## 4. Nothing else changes

- `held_item_candidates` for B1-B5 members: identical on both ledgers.
- A quick optimization of one benchmark team with the same seed: `result.json` byte-identical to `main`.

## 5. Full suite

```bash
uv run pytest -q
node --test sim/test/*.test.mjs
```
