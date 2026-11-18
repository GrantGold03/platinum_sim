# Data model: Dead moves in the extra candidate sets

## MemberCandidates (candidates.py), changes

| Field | Change |
|---|---|
| `dead_moves` | now also covers every offered extra set, judged under that set's own valuation (item-conditioned values for item sets) |
| `filler_reasons` | NEW `dict[tuple, str]`: per offered set (base or extra) that keeps a dead move, the 026 reason |
| `dropped_extras` | NEW `dict[str, dict]`: per kind with fewer than `k` extras offered, `{"offered": n, "reason": str}` |
| `no_live_reason`, `one_apart` | unchanged meaning for base sets; `one_apart` also lists extras accepted one apart |
| `summary()` | adds `filler_reasons` and `dropped_extras` |

Rules: base sets, their items and the setup set equal main's; an offered variable-power extra has a live offered variable move;
an offered item extra contains a move the item changes; no offered set repeats another.
