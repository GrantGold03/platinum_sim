# Contract: `platsim.decomp.item_use`

Internal Python interface, used by the optimizer and the tests. No CLI, web or report-file change (FR-008).

```python
def item_uses() -> dict[str, ItemUse]
    """ITEM_* -> ItemUse for every item load_items() returns. Cached.
    Raises ItemUseReadError if any RemoveItem site is unattributed, a subscript name does not resolve,
    or no hold effect is single-use."""

def is_excluded_single_use(item: str) -> bool
    """True when the item (ITEM_* const or lower-case key, as held_item_candidates returns) is single-use
    and not a berry. None / unknown key -> False."""
```

Guarantees, each checked by a test:

| Call | Result |
|---|---|
| `item_uses()["ITEM_FOCUS_SASH"]` | `single_use=True, berry=False`, evidence cites `subscript_move_followup_message.s:17-18` |
| `item_uses()["ITEM_SITRUS_BERRY"]` | `single_use=True, berry=True` |
| `item_uses()["ITEM_BERRY_JUICE"]` | `single_use=True, berry=False` |
| White Herb, Mental Herb, Power Herb | `single_use=True, berry=False` |
| Leftovers, Focus Band, Quick Claw, Sticky Barb, Silk Scarf | `single_use=False` |
| `{c for c, u in item_uses().items() if u.single_use and not u.berry}` | contains the five items above; every extra member is listed in the validation log with its decomp check |

`held_item_candidates(...)` (existing signature, unchanged): no returned item has
`is_excluded_single_use(item) == True`.
