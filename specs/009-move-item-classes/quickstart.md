# Quickstart: validating 009 move and item classification

```bash
uv run platsim extract --check     # rebuild with `uv run platsim extract` if not up to date
uv run pytest -q tests/unit/test_move_classes.py tests/unit/test_item_classes.py \
  tests/unit/test_required_hms_adopted.py tests/unit/test_required_hms.py
```

Expected: every move classifies; Screech is a foe drop; 6 fixed-damage effects; all 17 resist berries
battle-relevant; Amulet Coin no outcome; an adopted move survives HM placement.

Nothing else changes:
- B1-B5 candidate movesets and held items identical to `main` (`runs/009-evidence/candidates-*.json`).
- HM-placement choice identical for every candidate moveset × HM (`runs/009-evidence/hm-*.json`).
- Same-seed quick B2 run identical except the code fingerprint.

Full suite: `uv run pytest -q` and `node --test sim/test/*.test.mjs`.
