"""League opponents (T017): first-run Elite Four + Cynthia, with a port of TrainerData_BuildParty
(src/trainer_data.c:176-316).

Semantics checked in the C source:
- `dto->trainerIDs[battler]` is the TRAINER_* id (index in generated/trainers.txt): it is the
  argument of StartTrainerBattle, stored at src/encounter.c:751, and it is also the trdata/trpoke
  NARC member (Trainer_LoadParty) and the JSON file index (tools/dataproc/src/trainerproc.c:115-123).
- `header.trainerType` is the trainer CLASS (TRAINER_CLASS_*), packed from the JSON "class" field
  (trainerproc.c:152) and compared against TRAINER_CLASS_RIVAL in trainer_data.c Trainer_Encounter.
- Per party member: seed = ivScale + level + species + trainerID; LCRNG_Next() is called
  trainerType (class id) times; rnd keeps the last u16 output (or the seed if the class id is 0);
  personality = (rnd << 8) + genderMod as u32, genderMod 120 for a female class else 136
  (include/data/trainer_class_genders.h).
- IVs (all six) = ivScale * MAX_IVS_SINGLE_STAT / MAX_IV_SCALE. EVs are 0 (Pokemon_InitWith).
- Ability: set inside Pokemon_InitWith from the BASE species (form 0) data:
  ability 2 if it is not ABILITY_NONE and personality & 1, else ability 1 (src/pokemon.c:473-484;
  same rule as BoxPokemon_CalcAbility, src/pokemon.c:4746).
- Nature = personality % NATURE_COUNT (src/pokemon.c:2410).
"""

import json
import re
from dataclasses import asdict, dataclass, field
from functools import cache
from typing import Any

from platsim.decomp._util import line_of, ref
from platsim.decomp.constants import load_enum, rel
from platsim.decomp.stats import nature_name
from platsim.pins import DECOMP_ROOT

TRAINERS_DIR = DECOMP_ROOT / "res" / "trainers" / "data"
TRAINER_DATA_C = DECOMP_ROOT / "src" / "trainer_data.c"
MATH_UTIL_H = DECOMP_ROOT / "include" / "math_util.h"
MATH_UTIL_C = DECOMP_ROOT / "src" / "math_util.c"
GENDERS_H = DECOMP_ROOT / "include" / "data" / "trainer_class_genders.h"
POKEMON_H = DECOMP_ROOT / "include" / "constants" / "pokemon.h"
TRAINER_STRUCT_H = DECOMP_ROOT / "include" / "struct_defs" / "trainer_data.h"

# The gauntlet order and files are research.md R3 (spec decision, not a game value).
LEAGUE = (
    "TRAINER_ELITE_FOUR_AARON",
    "TRAINER_ELITE_FOUR_BERTHA",
    "TRAINER_ELITE_FOUR_FLINT",
    "TRAINER_ELITE_FOUR_LUCIAN",
    "TRAINER_CHAMPION_CYNTHIA",
)


def _define(path, name: str) -> int:
    m = re.search(rf"#define\s+{name}\s+(\d+)L?\b", path.read_text())
    if not m:
        raise ValueError(f"{name} not found in {rel(path)}")
    return int(m.group(1))


@cache
def _gender_mods() -> tuple[int, int]:
    """(female, male) modifiers read from TrainerData_BuildParty's `? 120 : 136` expression."""
    start = line_of(TRAINER_DATA_C, "genderMod = TrainerClass_Gender(")
    text = "\n".join(TRAINER_DATA_C.read_text().splitlines()[start - 1 : start + 2])
    m = re.search(r"== GENDER_FEMALE\s*\?\s*(\d+)\s*:\s*(\d+)", text)
    if not m:
        raise ValueError(f"{rel(TRAINER_DATA_C)}:{start}: cannot parse genderMod")
    return int(m.group(1)), int(m.group(2))


@cache
def class_genders() -> dict[str, str]:
    out = {}
    for m in re.finditer(r"\[(TRAINER_CLASS_\w+)\]\s*=\s*(GENDER_\w+)", GENDERS_H.read_text()):
        out[m.group(1)] = m.group(2)
    return out


class LCRNG:
    """src/math_util.c LCRNG_SetSeed / LCRNG_Next (u32 state, returns state >> 16 as u16)."""

    def __init__(self, seed: int):
        self.mul = _define(MATH_UTIL_H, "LCRNG_MULTIPLIER")
        self.inc = _define(MATH_UTIL_H, "LCRNG_INCREMENT")
        self.state = seed & 0xFFFFFFFF

    def next(self) -> int:
        self.state = (self.state * self.mul + self.inc) & 0xFFFFFFFF
        return self.state >> 16


def trainer_personality(iv_scale: int, level: int, species_id: int, trainer_id: int,
                        class_id: int, female_class: bool) -> int:
    rnd = (iv_scale + level + species_id + trainer_id) & 0xFFFFFFFF
    rng = LCRNG(rnd)
    for _ in range(class_id):
        rnd = rng.next()
    female, male = _gender_mods()
    return ((rnd << 8) + (female if female_class else male)) & 0xFFFFFFFF


def trainer_iv(iv_scale: int) -> int:
    return iv_scale * _define(POKEMON_H, "MAX_IVS_SINGLE_STAT") // _define(TRAINER_STRUCT_H, "MAX_IV_SCALE")


@dataclass
class OpponentMon:
    species: str
    form: int
    level: int
    moves: list[str]
    held_item: str
    iv: int
    iv_scale: int
    personality: int
    nature: str
    ability_slot: int  # 1 or 2
    ability: str
    src: list[str] = field(default_factory=list)


@dataclass
class OpponentTrainer:
    trainer_id: int
    key: str
    const: str
    name: str
    trainer_class: str
    class_id: int
    order: int
    ai_flags: list[str]
    bag_items: list[str]
    double_battle: bool
    party: list[OpponentMon]
    src: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def load_trainer(const: str, order: int = 0) -> OpponentTrainer:
    from platsim.decomp.species import by_constant

    trainers = load_enum("trainers")
    classes = load_enum("trainer_classes")
    species_enum = load_enum("species")
    species = by_constant()
    tid = trainers[const]
    key = const.removeprefix("TRAINER_").lower()
    path = TRAINERS_DIR / f"{key}.json"
    d = json.loads(path.read_text())
    cls = d["class"]
    class_id = classes[cls]
    female = class_genders()[cls] == "GENDER_FEMALE"
    decl = line_of(TRAINER_DATA_C, "static void TrainerData_BuildParty(")  # forward declaration
    build_ref = ref(TRAINER_DATA_C, "static void TrainerData_BuildParty(", decl + 1)
    party = []
    search_from = 1
    for i, m in enumerate(d["party"]):
        sp = m["species"]
        sid = species_enum[sp]
        pers = trainer_personality(m["iv_scale"], m["level"], sid, tid, class_id, female)
        base = species[sp]  # Pokemon_InitWith uses base-species abilities
        slot = 2 if base.abilities[1] is not None and pers & 1 else 1
        moves = list(m.get("moves") or [])
        mon_line = line_of(path, f'"species": "{sp}"', search_from)
        search_from = mon_line + 1
        party.append(
            OpponentMon(
                species=sp,
                form=int(m["form"]),
                level=int(m["level"]),
                moves=moves,
                held_item=m.get("item", "ITEM_NONE"),
                iv=trainer_iv(m["iv_scale"]),
                iv_scale=int(m["iv_scale"]),
                personality=pers,
                nature=nature_name(pers),
                ability_slot=slot,
                ability=base.abilities[slot - 1],
                src=[f"{rel(path)}:{mon_line}", build_ref],
            )
        )
    return OpponentTrainer(
        trainer_id=tid,
        key=key,
        const=const,
        name=d["name"],
        trainer_class=cls,
        class_id=class_id,
        order=order,
        ai_flags=list(d["ai_flags"]),
        bag_items=list(d["items"]),
        double_battle=bool(d["double_battle"]),
        party=party,
        src=[str(trainers.refs[const]), str(classes.refs[cls]), ref(path), ref(GENDERS_H, f"[{cls}]")],
    )


@cache
def load_league() -> tuple[OpponentTrainer, ...]:
    return tuple(load_trainer(c, i + 1) for i, c in enumerate(LEAGUE))
