# Data Model: No Single-Use Held Items (H2)

In-memory only. Nothing is persisted, and `data/generated/` is unchanged (research R3).

## ItemUse

One per holdable item, derived from the pinned decomp by `platsim.decomp.item_use` (cached per process).

| Field | Type | Meaning |
|---|---|---|
| `const` | `str` | `ITEM_*` constant |
| `hold_effect` | `str` | `HOLD_EFFECT_*` from the item's data file |
| `berry` | `bool` | `fieldPocket == "POCKET_BERRIES"` (research R3) |
| `single_use` | `bool` | the hold effect reaches `RemoveItem` on the holder (research R1, R2) |
| `evidence` | `list[str]` | decomp `file:line` refs: the trigger (C `case` or script guard) and the `RemoveItem` site. Empty when not single-use |

Derived: `excluded = single_use and not berry`.

Rules:
- `single_use` is a property of the hold effect: every item with the same `hold_effect` gets the same value.
  `HOLD_EFFECT_NONE` is never single-use.
- `evidence` is non-empty exactly when `single_use` is true (FR-005).

## RemoveSite (reader-internal)

One per `RemoveItem` line in `res/battle/scripts/`.

| Field | Type | Meaning |
|---|---|---|
| `ref` | `str` | `file:line` |
| `effects` | `set[str]` | hold effects attributed to it (research R2 rules 1-4) |
| `move_driven` | `bool` | reached only from move effects (Pluck/Bug Bite, Natural Gift, Fling) |

Validation (reader fails loudly): every site has `effects` non-empty or `move_driven` true. At least one site
exists. `HOLD_EFFECT_ENDURE` ends up single-use (positive control).

## Held-item candidate rule (existing, `optimizer/candidates.py`)

Unchanged inputs and order. Output gains one post-filter: drop any item whose `ItemUse.excluded` is true. If the
filter empties the list, the existing `[None]` (no item) fallback applies.
