"""Item reader (T014): pokeplatinum/res/items/data/<name>.json.

Iteration follows tools/dataproc/src/itemproc.c: every generated/items.txt name with the ITEM_
prefix and without ITEM_UNUSED_ has a data file `<stem lower-cased>.json` (itemproc.c has_data,
~line 162). A TM/HM is an item whose data has `teachesMove`.
"""

import json
from dataclasses import asdict, dataclass, field
from functools import cache
from typing import Any

from platsim.decomp._util import ref
from platsim.decomp.constants import load_enum
from platsim.pins import DECOMP_ROOT

ITEMS_DIR = DECOMP_ROOT / "res" / "items" / "data"
ITEMPROC = DECOMP_ROOT / "tools" / "dataproc" / "src" / "itemproc.c"


@dataclass
class Item:
    id: int
    key: str
    const: str
    name: str
    hold_effect: str
    effect_param: int
    price: int
    teaches_move: str | None
    src: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _has_data(const: str) -> bool:
    # itemproc.c has_data: ITEM_ prefix and not ITEM_UNUSED_
    return const.startswith("ITEM_") and not const.startswith("ITEM_UNUSED_")


@cache
def load_items() -> dict[str, Item]:
    """All items with data (including ITEM_NONE), keyed by ITEM_* constant."""
    enum = load_enum("items")
    out: dict[str, Item] = {}
    for const, iid in enum.values.items():
        if not _has_data(const):
            continue
        key = const.removeprefix("ITEM_").lower()
        path = ITEMS_DIR / f"{key}.json"
        d = json.loads(path.read_text())
        teaches = d.get("teachesMove")
        src = [str(enum.refs[const]), ref(path), ref(ITEMPROC, "static bool has_data(")]
        if teaches:
            src.append(ref(path, '"teachesMove"'))
        out[const] = Item(
            id=iid,
            key=key,
            const=const,
            name=d["name"],
            hold_effect=d["holdEffect"],
            effect_param=int(d["effectParam"]),
            price=int(d["price"]),
            teaches_move=teaches,
            src=src,
        )
    return out


@cache
def tm_moves() -> dict[str, str]:
    """'TM01'..'TM92', 'HM01'..'HM08' -> MOVE_* (from teachesMove)."""
    out = {}
    for const, item in load_items().items():
        stem = const.removeprefix("ITEM_")
        if item.teaches_move and stem[:2] in ("TM", "HM") and stem[2:].isdigit():
            out[stem] = item.teaches_move
    return out
