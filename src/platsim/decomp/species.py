"""Species reader (T012): pokeplatinum/res/pokemon/<name>/data.json plus alternate forms with data.

Rules (all read from the decomp, cited in `src`):
- Folder name = SPECIES_* constant without the prefix, lower-cased (res/pokemon/meson.build:67-71).
- Alternate forms with their own data are appended after the last species.txt entry in the order of
  `alt_forms_with_data` (tools/dataproc/src/speciesproc.c:227), which `splitenv` appends to the
  registry (tools/dataproc/src/common.c:405). Their personal-NARC index is therefore
  len(species.txt) + position, which matches Pokemon_GetFormNarcIndex (src/pokemon.c:4929).
  The set must equal the forms marked "data" in res/pokemon/form_registry.json.
- base_stats in data.json are ordered hp, attack, defense, speed, special_attack, special_defense
  (speciesproc.c proc_personal); we reorder to hp/atk/def/spa/spd/spe.
- abilities[1] is None when it is ABILITY_NONE.
- Evolution array shapes are parsed from the `switch` in speciesproc.c proc_evolutions, not typed.
- Tutor moves not present in move_tutors.json are skipped, as speciesproc.c emit_tutorables does.

SPECIES_NONE, SPECIES_EGG and SPECIES_BAD_EGG are not returned by load_species().
"""

import json
import re
from dataclasses import asdict, dataclass, field
from functools import cache
from typing import Any

from platsim.decomp._util import line_of, lines, ref
from platsim.decomp.constants import load_enum, rel
from platsim.pins import DECOMP_ROOT

POKEMON_DIR = DECOMP_ROOT / "res" / "pokemon"
SPECIESPROC = DECOMP_ROOT / "tools" / "dataproc" / "src" / "speciesproc.c"
SPECIES_H = DECOMP_ROOT / "include" / "struct_defs" / "species.h"
FORM_REGISTRY = POKEMON_DIR / "form_registry.json"
MOVE_TUTORS = POKEMON_DIR / "move_tutors.json"

_NON_SPECIES = ("SPECIES_NONE", "SPECIES_EGG", "SPECIES_BAD_EGG")
_STAT_ORDER = (
    ("hp", "hp"),
    ("atk", "attack"),
    ("def", "defense"),
    ("spa", "special_attack"),
    ("spd", "special_defense"),
    ("spe", "speed"),
)


@dataclass(frozen=True)
class Evolution:
    method: str  # EVO_* (generated/evolution_methods.txt)
    param: int | str | None  # level / ITEM_* / MOVE_* / SPECIES_* / None (shape-dependent)
    target: str  # SPECIES_*


@dataclass
class Species:
    id: int  # personal-NARC index (species.txt line index; forms after the last species)
    key: str  # folder name, or "<species>_<form>" for forms
    name: str  # pokedex_data.en.name (forms: the base species' name)
    form: str | None  # form folder name (e.g. "wash") or None
    form_index: int  # MON_DATA_FORM value (0 for the base form)
    base_species: str  # key of the base species
    types: list[str]
    base_stats: dict[str, int]
    abilities: list[str | None]
    exp_rate: str
    base_exp: int
    ev_yield: dict[str, int]
    gender_ratio: str
    base_friendship: int
    learnset_level: list[tuple[int, str]]
    learnset_tm: list[str]
    learnset_tutor: list[str]
    egg_moves: list[str]
    evolutions: list[Evolution]
    src: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["learnset_level"] = [list(x) for x in self.learnset_level]
        return d


@cache
def _header_int(name: str) -> int:
    m = re.search(rf"#define\s+{name}\s+(\d+)", SPECIES_H.read_text())
    if not m:
        raise ValueError(f"{name} not found in {rel(SPECIES_H)}")
    return int(m.group(1))


@cache
def evolution_shapes() -> dict[str, tuple[str, str]]:
    """EVO_* -> (param kind, ref) parsed from speciesproc.c proc_evolutions' switch.

    Param kinds: "none" (array [method, species]), "int" ([method, n, species]), or an enum name
    ("Item", "Move", "Species") for [method, CONST, species].
    """
    src = lines(SPECIESPROC)
    start = line_of(SPECIESPROC, "static SpeciesEvolutionList proc_evolutions(datafile_t *df) {")
    shapes: dict[str, tuple[str, str]] = {}
    pending: list[tuple[str, int]] = []
    kind: str | None = None
    for lineno in range(start, len(src) + 1):
        text = src[lineno - 1]
        if text.startswith("}"):
            break
        if m := re.match(r"\s*case (EVO_\w+):", text):
            pending.append((m.group(1), lineno))
        elif "param" in text and "dp_arrelem(entry, 1)" in text:
            m = re.search(r'"enum (\w+)"', text)
            kind = m.group(1) if m else "int"
        elif "species" in text and "dp_arrelem(entry, 1)" in text:
            kind = "none"
        elif text.strip() == "break;" and pending:
            if kind is None:
                raise ValueError(f"{rel(SPECIESPROC)}:{lineno}: no shape for {pending}")
            for name, ln in pending:
                shapes[name] = (kind, f"{rel(SPECIESPROC)}:{ln}")
            pending, kind = [], None
    return shapes


def _parse_evolutions(raw: list, path) -> list[Evolution]:
    shapes = evolution_shapes()
    if len(raw) > _header_int("MAX_EVOLUTIONS"):
        raise ValueError(f"{rel(path)}: {len(raw)} evolutions > MAX_EVOLUTIONS")
    out = []
    for entry in raw:
        method = entry[0]
        if method not in shapes:
            raise ValueError(f"{rel(path)}: no evolution handler for {method}")
        kind = shapes[method][0]
        if kind == "none":
            if len(entry) != 2:
                raise ValueError(f"{rel(path)}: {entry} does not match shape [method, species]")
            out.append(Evolution(method, None, entry[1]))
        else:
            if len(entry) != 3:
                raise ValueError(f"{rel(path)}: {entry} does not match shape [method, param, species]")
            param = entry[1]
            if kind == "int" and not isinstance(param, int):
                raise ValueError(f"{rel(path)}: {entry}: expected integer param")
            if kind != "int" and not (isinstance(param, str) and param in _enum_for(kind).values):
                raise ValueError(f"{rel(path)}: {entry}: {param!r} is not an enum {kind}")
            out.append(Evolution(method, param, entry[2]))
    return out


def _enum_for(kind: str):
    return load_enum({"Item": "items", "Move": "moves", "Species": "species"}[kind])


@cache
def form_order() -> tuple[tuple[str, str, int], ...]:
    """(species folder, form folder, speciesproc.c line) in alt_forms_with_data order."""
    out = []
    start = line_of(SPECIESPROC, "static const char *alt_forms_with_data[]")
    src = lines(SPECIESPROC)
    for lineno in range(start + 1, len(src) + 1):
        text = src[lineno - 1].strip()
        if text.startswith("};"):
            break
        m = re.fullmatch(r'"(\w+)/forms/(\w+)",', text)
        if not m:
            raise ValueError(f"{rel(SPECIESPROC)}:{lineno}: cannot parse {text!r}")
        out.append((m.group(1), m.group(2), lineno))
    registry = json.loads(FORM_REGISTRY.read_text())
    data_forms = {(sp, f) for sp, forms in registry.items() for f, t in forms.items() if t == "data"}
    if data_forms != {(sp, f) for sp, f, _ in out}:
        raise ValueError("form_registry.json 'data' forms differ from speciesproc.c alt_forms_with_data")
    return tuple(out)


@cache
def tutorable_moves() -> frozenset[str]:
    return frozenset(e["move"] for e in json.loads(MOVE_TUTORS.read_text()))


def _tm_marker_ok(marker: str) -> bool:
    items = load_enum("items")
    num_tms = items["ITEM_TM92"] - items["ITEM_TM01"] + 1  # include/constants/items.h:79
    num_hms = items["ITEM_HM08"] - items["ITEM_HM01"] + 1  # include/constants/items.h:80
    m = re.fullmatch(r"(TM|HM)(\d+)", marker)
    if not m:
        return False
    n = int(m.group(2))
    return 1 <= n <= (num_tms if m.group(1) == "TM" else num_hms)


def _build(sid: int, key: str, folder, name: str, form: str | None, form_index: int, base: str):
    path = folder / "data.json"
    d = json.loads(path.read_text())
    moves = load_enum("moves").values
    abilities_enum = load_enum("abilities").values
    types_enum = load_enum("pokemon_types").values

    types = list(d["types"])
    abilities = list(d["abilities"])
    for t in types:
        if t not in types_enum:
            raise ValueError(f"{rel(path)}: unknown type {t}")
    for a in abilities:
        if a not in abilities_enum:
            raise ValueError(f"{rel(path)}: unknown ability {a}")
    if abilities[1] == "ABILITY_NONE":
        abilities[1] = None

    ls = d["learnset"]
    by_level = [(int(lv), mv) for lv, mv in ls["by_level"]]
    if len(by_level) > _header_int("MAX_LEARNSET_ENTRIES"):
        raise ValueError(f"{rel(path)}: more than MAX_LEARNSET_ENTRIES level-up moves")
    for _, mv in by_level:
        if mv not in moves:
            raise ValueError(f"{rel(path)}: unknown move {mv}")
    for marker in ls["by_tm"]:
        if not _tm_marker_ok(marker):
            raise ValueError(f"{rel(path)}: bad TM/HM marker {marker}")
    tutor = [m for m in ls["by_tutor"] if m in tutorable_moves()]
    egg = list(ls.get("egg_moves", []))
    for mv in tutor + egg:
        if mv not in moves:
            raise ValueError(f"{rel(path)}: unknown move {mv}")

    src = [
        ref(path, '"base_stats"'),
        ref(path, '"types"'),
        ref(path, '"abilities"'),
        ref(path, '"exp_rate"'),
        ref(path, '"learnset"'),
        ref(path, '"evolutions"'),
    ]
    return Species(
        id=sid,
        key=key,
        name=name,
        form=form,
        form_index=form_index,
        base_species=base,
        types=types,
        base_stats={k: int(d["base_stats"][j]) for k, j in _STAT_ORDER},
        abilities=abilities,
        exp_rate=d["exp_rate"],
        base_exp=int(d["base_exp_reward"]),
        ev_yield={k: int(d["ev_yields"][j]) for k, j in _STAT_ORDER},
        gender_ratio=d["gender_ratio"],
        base_friendship=int(d["base_friendship"]),
        learnset_level=by_level,
        learnset_tm=list(ls["by_tm"]),
        learnset_tutor=tutor,
        egg_moves=egg,
        evolutions=_parse_evolutions(d["evolutions"], path),
        src=src,
    )


@cache
def load_species() -> dict[str, Species]:
    """All species (ids 1..last national dex) and data-forms, keyed by `key`."""
    sp_enum = load_enum("species")
    out: dict[str, Species] = {}
    names: dict[str, str] = {}
    for const, sid in sp_enum.values.items():
        if const in _NON_SPECIES:
            continue
        folder_name = const.removeprefix("SPECIES_").lower()  # res/pokemon/meson.build:69-70
        folder = POKEMON_DIR / folder_name
        d = json.loads((folder / "data.json").read_text())
        name = d["pokedex_data"]["en"]["name"]
        names[folder_name] = name
        s = _build(sid, folder_name, folder, name, None, 0, folder_name)
        s.src.insert(0, str(sp_enum.refs[const]))
        out[folder_name] = s

    registry_len = len(sp_enum.values)  # splitenv appends forms after every species.txt line
    per_species: dict[str, int] = {}
    for pos, (base, form, lineno) in enumerate(form_order()):
        per_species[base] = per_species.get(base, 0) + 1
        key = f"{base}_{form}"
        s = _build(
            registry_len + pos,
            key,
            POKEMON_DIR / base / "forms" / form,
            names[base],
            form,
            per_species[base],
            base,
        )
        s.src.insert(0, f"{rel(SPECIESPROC)}:{lineno}")
        out[key] = s
    return out


def by_constant() -> dict[str, Species]:
    """Base-form species keyed by SPECIES_* constant."""
    return {f"SPECIES_{s.key.upper()}": s for s in load_species().values() if s.form is None}
