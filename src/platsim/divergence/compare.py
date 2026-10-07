"""Divergence ledger (T053, Constitution II): Showdown gen4 data vs decomp data.

`sim/dump_dex.mjs` dumps Showdown's own (unpatched) gen4 species, moves and battle-effect items,
each tagged with the decomp key it maps to by sim/gamedata.mjs's number-based mapping (the 4
renamed moves included). This module diffs that dump against data/generated/*.json and merges in
the hand-written mechanics entries (mechanics.py) and the damage-formula divergences found by
T037 (sim/test/damage_divergences.json), then writes data/divergences.json:

    {"version": "sha256:<16 hex of the canonical entries>", "entries": [DivergenceEntry, ...]}

DivergenceEntry (data-model.md): id, area (data | mechanics | ai | exp), description,
decomp_ref, showdown_ref, resolution (corrected | accepted), impact, test_id; plus `patch`
({"table","id","path","value"}, applied by sim/gamedata.mjs prepareDex) on corrected data diffs.

Every entry cites a decomp path:line and a Showdown path:line. Decomp lines are located in the
decomp source files named by each record's `src`; Showdown lines are located by walking the mod
chain gen4 -> gen5 -> gen6 -> gen7 -> gen8 -> data/ (each mod's scripts.ts `inherit`) and taking
the first file whose entry defines the field.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from functools import cache
from pathlib import Path
from typing import Any

from platsim.pins import DECOMP_ROOT, REPO_ROOT, SHOWDOWN_ROOT

GENERATED_DIR = REPO_ROOT / "data" / "generated"
LEDGER_PATH = REPO_ROOT / "data" / "divergences.json"
DUMP_SCRIPT = REPO_ROOT / "sim" / "dump_dex.mjs"
DAMAGE_DIVERGENCES = REPO_ROOT / "sim" / "test" / "damage_divergences.json"

DATA_TEST_ID = "tests/integration/test_divergences.py::test_ledger_matches_fresh_diff"
PATCH_TEST_ID = "tests/integration/test_divergences.py::test_endure_patch_in_live_battle"

# Showdown mod chain for gen4 (pokemon-showdown/data/mods/gen{4..8}/scripts.ts line 2 `inherit`).
_MOD_CHAIN = ["data/mods/gen4", "data/mods/gen5", "data/mods/gen6", "data/mods/gen7",
              "data/mods/gen8", "data"]

STAT_JSON_KEYS = {"hp": "hp", "atk": "attack", "def": "defense", "spa": "special_attack",
                  "spd": "special_defense", "spe": "speed"}

# Decomp move flag -> Showdown move flag (only flags both sides model).
FLAG_MAP = {
    "MOVE_FLAG_MAKES_CONTACT": "contact",
    "MOVE_FLAG_CAN_PROTECT": "protect",
    "MOVE_FLAG_CAN_MAGIC_COAT": "reflectable",
    "MOVE_FLAG_CAN_SNATCH": "snatch",
    "MOVE_FLAG_CAN_MIRROR_MOVE": "mirror",
}

# Decomp range -> Showdown targets that mean the same thing in a singles battle.
RANGE_MAP = {
    "RANGE_SINGLE_TARGET": {"normal", "any", "adjacentFoe"},
    "RANGE_SINGLE_TARGET_SPECIAL": {"normal", "any", "scripted"},
    "RANGE_SINGLE_TARGET_ME_FIRST": {"adjacentFoe"},
    "RANGE_USER": {"self"},
    "RANGE_ADJACENT_OPPONENTS": {"allAdjacentFoes"},
    "RANGE_FIELD": {"all"},
    "RANGE_USER_SIDE": {"allySide", "allyTeam"},
    "RANGE_ALL_ADJACENT": {"allAdjacent"},
    "RANGE_RANDOM_OPPONENT": {"randomNormal"},
    "RANGE_OPPONENT_SIDE": {"foeSide"},
    "RANGE_USER_OR_ALLY": {"adjacentAllyOrSelf"},
    "RANGE_ALLY": {"adjacentAlly"},
}

CATEGORY_MAP = {"CLASS_PHYSICAL": "Physical", "CLASS_SPECIAL": "Special", "CLASS_STATUS": "Status"}


def toid(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def type_name(t: str) -> str:
    """TYPE_FIRE -> Fire; TYPE_MYSTERY -> ??? (Showdown's typeless/Curse type)."""
    return "???" if t == "TYPE_MYSTERY" else t.removeprefix("TYPE_").capitalize()


# ---- citations ---------------------------------------------------------------------------------

@cache
def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def decomp_json_path(src: list[str], prefix: str) -> str:
    for s in src:
        p = s.split(":")[0]
        if p.startswith(prefix):
            return p
    raise KeyError(f"no {prefix}* in src {src}")


def decomp_ref(rel: str, key: str) -> str:
    """`rel:line` of the first `"key":` in a decomp JSON file."""
    needle = f'"{key}":'
    for i, line in enumerate(_lines(DECOMP_ROOT / rel), 1):
        if needle in line:
            return f"pokeplatinum/{rel}:{i}"
    raise KeyError(f"{needle} not in pokeplatinum/{rel}")


def showdown_ref(table_file: str, sd_id: str, key: str) -> str:
    """`path:line` of the line defining `key` in Showdown entry `sd_id`, first along the gen4
    mod chain. Falls back to the entry's first line if the field is computed (no literal)."""
    start_re = re.compile(rf"^\t(?:{re.escape(sd_id)}|'{re.escape(sd_id)}'): \{{")
    key_re = re.compile(rf"^\t\t{re.escape(key)}:")
    first_entry = None
    for mod in _MOD_CHAIN:
        rel = f"{mod}/{table_file}"
        path = SHOWDOWN_ROOT / rel
        if not path.exists():
            continue
        lines = _lines(path)
        for i, line in enumerate(lines):
            if not start_re.match(line):
                continue
            first_entry = first_entry or f"pokemon-showdown/{rel}:{i + 1}"
            for j in range(i + 1, len(lines)):
                if re.match(r"^\t\},?$", lines[j]):
                    break
                if key_re.match(lines[j]):
                    return f"pokemon-showdown/{rel}:{j + 1}"
            break
    if first_entry is None:
        raise KeyError(f"no Showdown {table_file} entry {sd_id}")
    return first_entry


# ---- the dump ----------------------------------------------------------------------------------

def run_dump(generated_dir: Path = GENERATED_DIR) -> dict[str, Any]:
    proc = subprocess.run(["node", str(DUMP_SCRIPT), "--generated", str(generated_dir)],
                          capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    if proc.returncode != 0:
        raise RuntimeError(f"sim/dump_dex.mjs failed (exit {proc.returncode}): {proc.stderr}")
    return json.loads(proc.stdout)


def load_generated(generated_dir: Path = GENERATED_DIR) -> dict[str, Any]:
    read = lambda n: json.loads((generated_dir / f"{n}.json").read_text(encoding="utf-8"))  # noqa: E731
    return {"species": read("species")["species"], "moves": read("moves")["moves"],
            "items": read("items")["items"]}


# ---- diff --------------------------------------------------------------------------------------

def _entry(id_: str, description: str, dref: str, sref: str, *, patch: dict | None,
           impact: str, resolution: str | None = None, test_id: str = DATA_TEST_ID) -> dict:
    e = {"id": id_, "area": "data", "description": description, "decomp_ref": dref,
         "showdown_ref": sref, "resolution": resolution or ("corrected" if patch else "accepted"),
         "impact": impact, "test_id": test_id}
    if patch:
        e["patch"] = patch
    return e


def diff_species(dump: dict, gen: dict) -> list[dict]:
    out = []
    for sd in dump["species"]:
        rec = gen["species"][sd["decomp_key"]]
        rel = decomp_json_path(rec["src"], "res/pokemon/")
        sid = sd["id"]
        for st, dv in rec["base_stats"].items():
            sv = sd["baseStats"][st]
            if dv != sv:
                out.append(_entry(
                    f"data-species-{sid}-basestats-{st}",
                    f"{sd['name']} base {st}: decomp {dv}, Showdown gen4 {sv}.",
                    decomp_ref(rel, STAT_JSON_KEYS[st]), showdown_ref("pokedex.ts", sid, "baseStats"),
                    patch={"table": "Pokedex", "id": sid, "path": ["baseStats", st], "value": dv},
                    impact="Corrected in Showdown's Dex; battle stats are also overwritten by the decomp formula (sim/team.mjs)."))
        dtypes = list(dict.fromkeys(type_name(t) for t in rec["types"]))
        if dtypes != sd["types"]:
            out.append(_entry(
                f"data-species-{sid}-types",
                f"{sd['name']} types: decomp {dtypes}, Showdown gen4 {sd['types']}.",
                decomp_ref(rel, "types"), showdown_ref("pokedex.ts", sid, "types"),
                patch={"table": "Pokedex", "id": sid, "path": ["types"], "value": dtypes},
                impact="Type effectiveness and STAB follow the decomp after the patch."))
        # The decomp repeats a single ability in both slots (e.g. Espeon); Showdown lists it once.
        dab = list(dict.fromkeys(a for a in rec["abilities"] if a and a != "ABILITY_NONE"))
        sab = [a for a in sd["abilities"] if a]
        if [toid(a.removeprefix("ABILITY_")) for a in dab] != [toid(a) for a in sab]:
            out.append(_entry(
                f"data-species-{sid}-abilities",
                f"{sd['name']} abilities: decomp {dab}, Showdown gen4 {sab}.",
                decomp_ref(rel, "abilities"), showdown_ref("pokedex.ts", sid, "abilities"),
                patch=None,
                impact="Abilities are set explicitly per Build/trainer mon from decomp data (sim/team.mjs), so Showdown's species list is not used in battle."))
    return out


def diff_moves(dump: dict, gen: dict) -> list[dict]:
    out = []
    for sd in dump["moves"]:
        rec = gen["moves"][sd["decomp_key"]]
        rel = decomp_json_path(rec["src"], "res/moves/")
        mid, name = sd["id"], sd["name"]

        def add(field: str, sd_key: str, dv: Any, sv: Any, patch_path: list | None, patch_value: Any,
                impact: str, json_key: str | None = None, resolution: str | None = None) -> None:
            patch = ({"table": "Moves", "id": mid, "path": patch_path, "value": patch_value}
                     if patch_path else None)
            out.append(_entry(
                f"data-move-{mid}-{field}", f"{name} {field}: decomp {dv}, Showdown gen4 {sv}.",
                decomp_ref(rel, json_key or field), showdown_ref("moves.ts", mid, sd_key),
                patch=patch, impact=impact, resolution=resolution,
                test_id=PATCH_TEST_ID if (mid, field) == ("endure", "priority") else DATA_TEST_ID))

        # power: the decomp stores 1 for variable-power moves, Showdown 0 + a callback.
        if rec["power"] != sd["basePower"]:
            if sd["powerHooks"] and rec["power"] == 1 and sd["basePower"] == 0:
                add("power", "basePower", rec["power"], sd["basePower"], None, None,
                    f"None (cosmetic): the stored value is a placeholder; Showdown sets power/damage at run time ({', '.join(sd['powerHooks'])}) and the game in its effect code. Whether each run-time formula matches the game is not checked by this diff.")
            else:
                add("power", "basePower", rec["power"], sd["basePower"], ["basePower"], rec["power"],
                    "Damage uses the decomp power after the patch.")
        dacc = True if rec["accuracy"] == 0 else rec["accuracy"]
        if dacc != sd["accuracy"]:
            add("accuracy", "accuracy", rec["accuracy"], sd["accuracy"], ["accuracy"], dacc,
                "Hit chance follows the decomp after the patch.")
        if rec["pp"] != sd["pp"]:
            add("pp", "pp", rec["pp"], sd["pp"], ["pp"], rec["pp"],
                "PP follows the decomp after the patch (sim/team.mjs also resets slots to decomp base PP).")
        if rec["priority"] != sd["priority"]:
            add("priority", "priority", rec["priority"], sd["priority"], ["priority"], rec["priority"],
                "Turn order follows the decomp after the patch.")
        if type_name(rec["type"]) != sd["type"]:
            add("type", "type", type_name(rec["type"]), sd["type"], ["type"], type_name(rec["type"]),
                "Type effectiveness/STAB follow the decomp after the patch.")
        if CATEGORY_MAP[rec["category"]] != sd["category"]:
            add("category", "category", CATEGORY_MAP[rec["category"]], sd["category"], ["category"],
                CATEGORY_MAP[rec["category"]], "Physical/special split follows the decomp after the patch.",
                json_key="class")
        if sd["target"] not in RANGE_MAP.get(rec["range"], set()):
            add("target", "target", rec["range"], sd["target"], None, None,
                "Accepted: singles only; target encodings differ but no League singles case was identified where this changes the outcome. UNVERIFIED per move.",
                json_key="range")
        for dflag, sflag in FLAG_MAP.items():
            dv, sv = dflag in rec["flags"], sflag in sd["flags"]
            if dv != sv:
                add(f"flag-{sflag}", "flags", dv, sv, ["flags", sflag], 1 if dv else 0,
                    f"`{sflag}` interactions (e.g. Protect, Magic Coat, Snatch, Mirror Move, contact abilities) follow the decomp after the patch."
                    + (" UNVERIFIED whether either engine consults this flag for a field-targeting move, so the patch may change nothing." if rec["range"] == "RANGE_FIELD" else ""),
                    json_key="flags")
        # secondary effect chance: only for moves with exactly one Showdown secondary with a chance.
        sc = sd["secondaryChances"]
        if len(sc) == 1 and sc[0] is not None and rec["effect_chance"] not in (0, sc[0]):
            add("effect-chance", "secondary", rec["effect_chance"], sc[0], ["secondary", "chance"],
                rec["effect_chance"], "Secondary-effect chance follows the decomp after the patch.",
                json_key="chance")
    return out


def diff_items(dump: dict, gen: dict) -> list[dict]:
    out = []
    for sd in dump["items"]:
        rec = gen["items"][sd["decomp_key"]]
        rel = decomp_json_path(rec["src"], "res/items/data/")
        raw = json.loads((DECOMP_ROOT / rel).read_text(encoding="utf-8"))
        iid, name = sd["id"], sd["name"]
        fp = raw.get("flingPower")
        if fp is not None and sd["flingPower"] is not None and fp != sd["flingPower"]:
            out.append(_entry(
                f"data-item-{iid}-fling", f"{name} Fling power: decomp {fp}, Showdown gen4 {sd['flingPower']}.",
                decomp_ref(rel, "flingPower"), showdown_ref("items.ts", iid, "fling"),
                patch={"table": "Items", "id": iid, "path": ["fling", "basePower"], "value": fp},
                impact="Fling damage follows the decomp after the patch."))
        if sd["naturalGift"] and raw.get("naturalGiftPower"):
            ng = sd["naturalGift"]
            if raw["naturalGiftPower"] != ng["basePower"]:
                out.append(_entry(
                    f"data-item-{iid}-naturalgift-power",
                    f"{name} Natural Gift power: decomp {raw['naturalGiftPower']}, Showdown gen4 {ng['basePower']}.",
                    decomp_ref(rel, "naturalGiftPower"), showdown_ref("items.ts", iid, "naturalGift"),
                    patch={"table": "Items", "id": iid, "path": ["naturalGift", "basePower"],
                           "value": raw["naturalGiftPower"]},
                    impact="Natural Gift damage follows the decomp after the patch."))
            if type_name(raw["naturalGiftType"]) != ng["type"]:
                out.append(_entry(
                    f"data-item-{iid}-naturalgift-type",
                    f"{name} Natural Gift type: decomp {type_name(raw['naturalGiftType'])}, Showdown gen4 {ng['type']}.",
                    decomp_ref(rel, "naturalGiftType"), showdown_ref("items.ts", iid, "naturalGift"),
                    patch={"table": "Items", "id": iid, "path": ["naturalGift", "type"],
                           "value": type_name(raw["naturalGiftType"])},
                    impact="Natural Gift type follows the decomp after the patch."))
    return out


def diff_mapping(dump: dict, gen: dict) -> list[dict]:
    """Items with a decomp hold effect that Showdown gen4 does not have at all."""
    missing = [k for k in dump["mapping"]["unmapped"]["items"]
               if gen["items"][k]["hold_effect"] != "HOLD_EFFECT_NONE"]
    out = []
    for k in missing:
        rec = gen["items"][k]
        rel = decomp_json_path(rec["src"], "res/items/data/")
        out.append(_entry(
            f"data-item-{toid(k)}-missing",
            f"{rec['name']} ({rec['hold_effect']}) has no Showdown gen4 item; held, it does nothing in Showdown.",
            decomp_ref(rel, "holdEffect"), "pokemon-showdown/data/items.ts:1 (no entry; sim/gamedata.mjs mapItems reports it unmapped)",
            patch=None,
            impact=("Exp. Share/Lucky Egg: corrected by the game layer (sim/exp.mjs). " if k in ("exp_share", "lucky_egg") else "")
                   + "The other out-of-battle hold effects (money, encounter, flee, friendship, evolution) have no effect in a League trainer battle.",
            test_id="sim/test/team.test.mjs (id mapping: unmapped items listed)"))
    return out


def data_diffs(dump: dict, gen: dict) -> list[dict]:
    return diff_species(dump, gen) + diff_moves(dump, gen) + diff_items(dump, gen) + diff_mapping(dump, gen)


# ---- merge + write -----------------------------------------------------------------------------

def damage_entries(path: Path = DAMAGE_DIVERGENCES) -> list[dict]:
    out = []
    for d in json.loads(path.read_text(encoding="utf-8")):
        out.append({
            "id": f"damage-{d['id']}", "area": "mechanics",
            "description": d["description"] + f" Example: {d['example']}",
            "decomp_ref": d["decomp_ref"], "showdown_ref": d["showdown_ref"],
            "resolution": "accepted",
            "impact": "Showdown resolves real damage (Constitution II), so battle damage can differ from the cartridge by about 1-3 HP on some rolls; the AI's own damage estimate uses the game formula (sim/damage.mjs).",
            "test_id": "sim/test/damage.test.mjs",
        })
    return out


def version_of(entries: list[dict]) -> str:
    canon = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def build_ledger(dump: dict, gen: dict) -> dict:
    from platsim.divergence import mechanics

    entries = data_diffs(dump, gen) + damage_entries() + mechanics.entries()
    ids = [e["id"] for e in entries]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f"duplicate divergence ids: {dup}")
    return {"version": version_of(entries), "entries": entries}


REQUIRED = ("id", "area", "description", "decomp_ref", "showdown_ref", "resolution", "impact", "test_id")
RESOLUTIONS = ("corrected", "accepted")
AREAS = ("data", "mechanics", "ai", "exp")


def problems(entries: list[dict]) -> list[str]:
    """Entries that violate the ledger rules (missing resolution first among them)."""
    out = []
    for e in entries:
        eid = e.get("id", "<no id>")
        if e.get("resolution") not in RESOLUTIONS:
            out.append(f"{eid}: missing or invalid resolution {e.get('resolution')!r}")
        for f in REQUIRED:
            if not e.get(f):
                out.append(f"{eid}: missing {f}")
        if e.get("area") not in AREAS:
            out.append(f"{eid}: invalid area {e.get('area')!r}")
        if not re.search(r"pokeplatinum/\S+:\d+", str(e.get("decomp_ref"))):
            out.append(f"{eid}: decomp_ref has no pokeplatinum path:line")
        if not re.search(r"pokemon-showdown/\S+:\d+", str(e.get("showdown_ref"))):
            out.append(f"{eid}: showdown_ref has no pokemon-showdown path:line")
        if e.get("patch") and e.get("resolution") != "corrected":
            out.append(f"{eid}: patch on a non-corrected entry")
    return out


def summary(ledger: dict) -> str:
    from collections import Counter

    c = Counter((e["area"], e["resolution"]) for e in ledger["entries"])
    patches = sum(1 for e in ledger["entries"] if e.get("patch"))
    rows = ", ".join(f"{a}/{r}={n}" for (a, r), n in sorted(c.items()))
    return f"{len(ledger['entries'])} entries ({rows}); {patches} Dex patches; version {ledger['version']}"


def main(out: Path = LEDGER_PATH, *, dump_path: Path | None = None, ledger_in: Path | None = None,
         check_only: bool = False) -> int:
    """Regenerate the ledger (or, with ledger_in, only check an existing one). Exit 1 if any
    entry lacks a resolution or breaks the ledger rules."""
    if ledger_in is not None:
        ledger = json.loads(ledger_in.read_text(encoding="utf-8"))
    else:
        dump = json.loads(dump_path.read_text(encoding="utf-8")) if dump_path else run_dump()
        ledger = build_ledger(dump, load_generated())
    bad = problems(ledger["entries"])
    if bad:
        for b in bad:
            print(f"platsim divergences: {b}", file=sys.stderr)
        return 1
    text = json.dumps(ledger, indent=1, ensure_ascii=False) + "\n"
    if check_only:
        cur = out.read_text(encoding="utf-8") if out.exists() else None
        if cur != text:
            print(f"{out} is out of date; run `platsim divergences`", file=sys.stderr)
            return 1
        print(f"{out} is up to date: {summary(ledger)}")
        return 0
    if ledger_in is None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}: {summary(ledger)}")
    else:
        print(f"{ledger_in} ok: {summary(ledger)}")
    return 0
