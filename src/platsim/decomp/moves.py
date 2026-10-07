"""Move reader (T013): pokeplatinum/res/moves/<name>/data.json.

Folder = MOVE_* constant without the prefix, lower-cased (tools/dataproc/src/moveproc.c:90-93).
Normalisation exactly as moveproc.c proc_move:
- a Status move with non-zero power is packed with power 0 (moveproc.c:136-142);
- accuracy > 100 is clamped to 100 (moveproc.c:144-148); accuracy 0 means "never misses";
- effect chance > 100 is clamped to 100 (moveproc.c:150-154).
"""

import json
from dataclasses import asdict, dataclass, field
from functools import cache
from typing import Any

from platsim.decomp._util import ref
from platsim.decomp.constants import load_enum
from platsim.pins import DECOMP_ROOT

MOVES_DIR = DECOMP_ROOT / "res" / "moves"
MOVEPROC = DECOMP_ROOT / "tools" / "dataproc" / "src" / "moveproc.c"


@dataclass
class Move:
    id: int
    key: str
    const: str
    name: str
    type: str
    category: str  # CLASS_PHYSICAL / CLASS_SPECIAL / CLASS_STATUS
    power: int
    accuracy: int  # 0 = never misses
    pp: int
    priority: int
    effect: str
    effect_chance: int
    range: str
    flags: list[str]
    src: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def normalise(category: str, power: int, accuracy: int, chance: int) -> tuple[int, int, int]:
    """moveproc.c:136-154: Status moves get power 0; accuracy and effect chance clamp to 100."""
    if power != 0 and category == "CLASS_STATUS":
        power = 0
    return power, min(accuracy, 100), min(chance, 100)


@cache
def load_moves() -> dict[str, Move]:
    """All moves except MOVE_NONE, keyed by MOVE_* constant."""
    enum = load_enum("moves")
    out: dict[str, Move] = {}
    for const, mid in enum.values.items():
        if not const.startswith("MOVE_") or const == "MOVE_NONE":
            continue
        key = const.removeprefix("MOVE_").lower()
        path = MOVES_DIR / key / "data.json"
        d = json.loads(path.read_text())
        power, accuracy, chance = normalise(
            d["class"], int(d["power"]), int(d["accuracy"]), int(d["effect"]["chance"])
        )
        out[const] = Move(
            id=mid,
            key=key,
            const=const,
            name=d["name"],
            type=d["type"],
            category=d["class"],
            power=power,
            accuracy=accuracy,
            pp=int(d["pp"]),
            priority=int(d["priority"]),
            effect=d["effect"]["type"],
            effect_chance=chance,
            range=d["range"],
            flags=list(d["flags"]),
            src=[str(enum.refs[const]), ref(path), ref(MOVEPROC, "if (data.power != 0")],
        )
    return out
