"""Move sources (T028): every legal way a team member can know a move at a given level.

Public API
- `source_options(species, ledger)` -> [SourceOption]: every pre-Champion way to own `species`
  (FR-003/FR-005/FR-008b): a ledger acquisition entry (wild / gift / static / roamer / GiveEgg /
  NPC trade) followed by zero or more evolutions, or Day-Care breeding. Trade evolutions are
  included only when `ledger.options.allow_trade_evolutions` (see "Legality options"). Each option has
  an `id` (what `Build.source` holds), the chain of `stages` with the lowest level each stage can
  exist at, `min_level` (FR-007 / data-model "start_level >= minimum obtainable level"), the NPC
  trade `fixed_mon`, and the items its evolutions consume.
- `sources(species, move, level, ledger, option=None)` -> [MoveChoice]: every legal source of
  `move` for `species` at `level` (union over options when `option` is None).
- `explain(species, move, level, ledger, option=None)` -> [str]: why near-miss sources fail.
- `uses_of(choice)` -> {ITEM_*/TMnn: copies}: what a MoveChoice consumes (TM copy, Heart Scale,
  shards, the father's TM).

Rules (each traced in the decomp; refs are attached to the MoveChoice `availability_ref` and to
`SourceOption.src`):
- Level-up: a stage learns its level-up move at level N when it levels into N
  (battle_script.c level-up learning) and gets the last four level-up moves at or below its level
  when created (BoxPokemon_SetDefaultMoves, pokemon.c). So a move is a natural level-up move of a
  stage iff enter <= N <= max level of the stage, or N is in the default moveset of the first stage
  at a level it is obtainable at.
- Pre-evolution level-up: the pre-evolution must learn the move at a level *below* its level-based
  evolution level (tasks.md T028; conservative - cancelling evolution would allow more). For a
  non-level evolution the pre-evolution may learn it up to start_level minus the number of
  level-ups the later evolutions still need.
- Move relearner: Pastoria City east house (OpenMoveReminderMenu, one Heart Scale per move,
  scripts_pastoria_city_east_house.s). It teaches the *current* species' level-up moves at or below
  the current level (move_reminder_data.c MoveReminderData_GetMoves). Available iff its map is
  reachable pre-Champion (ledger) and Heart Scales have a pre-Champion source (ledger).
- TM/HM: species TM compatibility (data.json by_tm) and ledger.tm_copies > 0. A TM taught to a
  pre-evolution stage that is compatible is also accepted (the move is kept on evolution).
- Shard tutors: species tutor bitmask (learnset_tutor), tutor map pre-Champion
  (ledger.tutor_available), shards with a pre-Champion source.
- Draco Meteor: Wilma (Route 210) teaches any party member whose type 1 or 2 is Dragon, at max
  friendship (scripts_route_210_grandma_wilma_house.s). Any stage of the chain that is Dragon type
  qualifies. Max friendship is treated as reachable for every Pokemon: the walk-cycle row of
  sFriendshipChangeTable is +1 at every friendship tier with no cap below MAX_FRIENDSHIP_VALUE
  (pokemon.c Pokemon_UpdateFriendship), and walking is unlimited.
- Route 228 starter tutor: only if ledger.tutor_available("ROUTE_228") (it is post-game).
- Egg move: only when `ledger.options.allow_egg_moves` and the member was bred (option kind "breed"); the egg species' egg move list
  (LoadSpeciesEggMoves, daycare.c), passed by the *father* (Egg_BuildMoveset). The father must be
  pre-Champion obtainable, able to be male (not female-only / genderless, not Ditto), not in the
  Undiscovered group, share an egg group with a female-capable mother of the line
  (Egg_AreEggGroupsCompatible), and learn the move by a non-egg method. The father is recorded in
  the detail string.

Legality options (legality/models.LegalityOptions, read from `ledger.options`; a ledger view per
option set comes from `Ledger.with_options`; every cache here keys on the options):
- allow_egg_moves (default False): off, no egg-move MoveChoice is ever produced (the validator
  reports EGG_MOVE_NOT_ALLOWED when the move would be an egg move with the flag on). A Day-Care
  egg ("breed" option) stays a species source either way: hatching a species is not an egg move,
  and the source preference ranks it last (used only for a breeding-only path).
- allow_trade_evolutions (default False, FR-005): on, EVO_TRADE (pokemon.c
  Pokemon_GetEvolutionTargetSpecies, case EVO_CLASS_BY_TRADE) and EVO_TRADE_WITH_HELD_ITEM become
  evolution steps. The evolution happens when the Pokemon is received in the trade, with no level-up
  (the stage enters at the pre-evolution's level). The held item must have a pre-Champion copy
  (ledger.item_copies) and is used up (evolution.c Evolution_ProcessEvolutionEffects sets
  MON_DATA_HELD_ITEM to ITEM_NONE for EVO_TRADE_WITH_HELD_ITEM), so it is counted in
  `SourceOption.consumes` like an evolution stone. The option keeps the id of its acquisition
  entry, and its detail says "trade evolution; needs a second cartridge for the trade". Trading a
  Pokemon away and back never rewrites its OT (trade_room/application.c calls
  UpdateMonStatusAndTrainerInfo with mode 5, which only touches an egg's met data), so a
  trade-evolved member of the player's own is still OT and gets no traded exp boost; only NPC-trade
  sources do (sim/team.mjs tradeOrigin).
- Breeding mothers (`breed_mothers`) still use ledger.species_sources, which never includes trade
  evolutions (conservative).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from platsim.decomp._util import line_of, ref
from platsim.decomp.items import load_items, tm_moves
from platsim.decomp.moves import load_moves
from platsim.decomp.species import POKEMON_DIR
from platsim.decomp.species import by_constant as _by_constant
from platsim.decomp.tutors import (
    draco_meteor_tutor,
    map_header_for_script,
    shard_tutors,
    starter_ultimate_tutors,
)
from platsim.legality.models import DEFAULT_LEGALITY, MoveChoice
from platsim.pins import DECOMP_ROOT

PP = DECOMP_ROOT
POKEMON_C = PP / "src" / "pokemon.c"
EVOLUTION_C = PP / "src" / "evolution.c"
DAYCARE_C = PP / "src" / "overlay005" / "daycare.c"
MOVE_REMINDER_C = PP / "src" / "move_reminder_data.c"
SCRIPTS = PP / "res" / "field" / "scripts"
RELEARNER_SCRIPT = SCRIPTS / "scripts_pastoria_city_east_house.s"
TRADE_ROOM_C = PP / "src" / "applications" / "trade_room" / "application.c"
DAYCARE_SCRIPT = SCRIPTS / "scripts_day_care_common.s"
POKEMON_H = PP / "include" / "constants" / "pokemon.h"

UNLIMITED = "unlimited"
ACQUIRE_KINDS = ("wild_slot", "gift", "egg", "static", "roamer", "npc_trade")
# Display labels of the acquisition kinds ("Obtained from" column, contracts/spreadsheet.md).
ACQUIRE_LABELS = {"wild_slot": "Wild", "gift": "Gift", "egg": "Gift egg", "static": "Static encounter",
                  "roamer": "Roamer", "npc_trade": "NPC trade"}
BREED = "breed"  # SourceOption.kind of Day-Care breeding
TRADE_METHODS = frozenset({"EVO_TRADE", "EVO_TRADE_WITH_HELD_ITEM"})
# Methods whose int param is a level threshold ("param <= monLevel" in
# Pokemon_GetEvolutionTargetSpecies, pokemon.c). Classified from the C below, see _level_methods().
ITEM_METHODS = frozenset({"EVO_USE_ITEM", "EVO_USE_ITEM_MALE", "EVO_USE_ITEM_FEMALE"})
HELD_ITEM_METHODS = frozenset({"EVO_LEVEL_WITH_HELD_ITEM_DAY", "EVO_LEVEL_WITH_HELD_ITEM_NIGHT"})


# ---------------------------------------------------------------------------------------------
# Decomp refs and small tables


@cache
def _level_methods() -> frozenset[str]:
    """EVO_* cases of the by-level switch that compare `param <= monLevel` (pokemon.c)."""
    src = POKEMON_C.read_text().splitlines()
    start = line_of(POKEMON_C, "case EVO_CLASS_BY_LEVEL: {")
    end = line_of(POKEMON_C, "case EVO_CLASS_BY_TRADE:", start)
    out, current = set(), []
    for text in src[start:end - 1]:
        if m := re.match(r"\s*case (EVO_\w+):", text):
            current.append(m.group(1))
        elif "speciesEvolutions[i].param <= monLevel" in text:
            out.update(current)
        elif text.strip() == "break;":
            current = []
    # EVO_LEVEL_SHEDINJA has no comparison of its own: Shedinja appears when Nincada evolves into
    # Ninjask (EVO_LEVEL_NINJASK, same level param) - evolution.c Evolution_ProcessEvolutionEffects.
    if "EVO_LEVEL_NINJASK" in out:
        out.add("EVO_LEVEL_SHEDINJA")
    return frozenset(out)


@cache
def refs() -> dict[str, list[str]]:
    """Decomp refs backing each rule (attached to MoveChoices, options and violations)."""
    return {
        "default_moves": [ref(POKEMON_C, "static void BoxPokemon_SetDefaultMoves(BoxPokemon *boxMon)")],
        "evolution": [ref(POKEMON_C, "u16 Pokemon_GetEvolutionTargetSpecies(")],
        "evolution_item_consumed": [ref(EVOLUTION_C, "case EVO_LEVEL_WITH_HELD_ITEM_DAY:")],
        "trade_evolution": [
            ref(POKEMON_C, "case EVO_CLASS_BY_TRADE:"),
            ref(EVOLUTION_C, "case EVO_TRADE_WITH_HELD_ITEM:"),
            ref(TRADE_ROOM_C, "UpdateMonStatusAndTrainerInfo(receivingMon"),
        ],
        "relearner": [
            ref(RELEARNER_SCRIPT, "CheckItem ITEM_HEART_SCALE"),
            ref(RELEARNER_SCRIPT, "OpenMoveReminderMenu"),
            ref(RELEARNER_SCRIPT, "RemoveItem ITEM_HEART_SCALE"),
            ref(MOVE_REMINDER_C, "GET_LEVEL(levelUpMoves[i]) > level"),
            map_header_for_script(RELEARNER_SCRIPT.stem)[1],
        ],
        "egg": [
            ref(DAYCARE_C, "static void Egg_BuildMoveset("),
            ref(DAYCARE_C, "// Egg moves from the father"),
            ref(DAYCARE_C, "static u8 LoadSpeciesEggMoves("),
            ref(DAYCARE_C, "static u8 BoxMon_GetPairDaycareCompatibilityScore("),
        ],
        "breed": [
            ref(DAYCARE_SCRIPT, "GiveEggFromDaycare"),
            ref(DAYCARE_C, "static u16 Egg_DetermineEggSpeciesAndParentSlots("),
            ref(DAYCARE_C, "Pokemon_InitWith(mon, species, EGG_POKEMON_LEVEL"),
            ref(POKEMON_H, "#define EGG_POKEMON_LEVEL"),
            map_header_for_script("scripts_solaceon_town")[1],
            map_header_for_script("scripts_pokemon_day_care")[1],
        ],
        "friendship": [
            ref(POKEMON_C, "[FRIENDSHIP_EVENT_WALK_CYCLE] = { 1, 1, 1 }"),
            ref(POKEMON_C, "void Pokemon_UpdateFriendship("),
            ref(POKEMON_H, "#define MAX_FRIENDSHIP_VALUE"),
        ],
    }


@cache
def _species_raw(const: str) -> dict:
    sp = by_constant()[const]
    return json.loads((POKEMON_DIR / sp.key / "data.json").read_text())


def egg_groups(const: str) -> tuple[str, ...]:
    return tuple(_species_raw(const)["egg_groups"])


def gender_ratio(const: str) -> str:
    return _species_raw(const)["gender_ratio"]


def _can_be_female(const: str) -> bool:
    return gender_ratio(const) not in ("GENDER_RATIO_MALE_ONLY", "GENDER_RATIO_NO_GENDER")


def _can_be_male(const: str) -> bool:
    return gender_ratio(const) not in ("GENDER_RATIO_FEMALE_ONLY", "GENDER_RATIO_NO_GENDER")


@cache
def _preds() -> dict[str, list[tuple[str, object]]]:
    """target SPECIES_* -> [(pre-evolution SPECIES_*, Evolution)] over base forms."""
    out: dict[str, list] = {}
    for const, sp in by_constant().items():
        for ev in sp.evolutions:
            out.setdefault(ev.target, []).append((const, ev))
    return out


def _root(const: str) -> str:
    """Egg species before incense / gender adjustments: the species' `offspring` field
    (tools/dataproc/src/speciesproc.c proc_offspring), read by Pokemon_GetBaseSpeciesFromPersonalData
    in Egg_DetermineEggSpeciesAndParentSlots (daycare.c)."""
    return _species_raw(const).get("offspring") or const


@cache
def _incense_table() -> tuple[tuple[str, str, str, str], ...]:
    """(baby, incense, species without incense, ref) from daycare.c sIncenseBabyTable."""
    out = []
    for i, text in enumerate(DAYCARE_C.read_text().splitlines(), start=1):
        if m := re.match(r"\s*\{ (SPECIES_\w+), (ITEM_\w+), (SPECIES_\w+) \},", text):
            out.append((m.group(1), m.group(2), m.group(3), f"{_rel(DAYCARE_C)}:{i}"))
    return tuple(out)


@cache
def _gender_split_eggs() -> dict[str, tuple[str, str]]:
    """Mother root -> extra egg species decided by the offspring gender (daycare.c
    Egg_DetermineEggSpeciesAndParentSlots: Nidoran F -> Nidoran M, Illumise -> Volbeat)."""
    out = {}
    text = DAYCARE_C.read_text().splitlines()
    for i, line in enumerate(text, start=1):
        if m := re.match(r"\s*if \(eggSpecies == (SPECIES_\w+)\) \{", line):
            body = "\n".join(text[i:i + 6])
            alts = re.findall(r"eggSpecies = (SPECIES_\w+);", body)
            for alt in alts:
                if alt != m.group(1):
                    out[m.group(1)] = (alt, f"{_rel(DAYCARE_C)}:{i}")
    out.pop("SPECIES_MANAPHY", None)  # Manaphy is event-only (not obtainable on one cartridge)
    return out


@cache
def by_constant():
    """Cached view of decomp.species.by_constant() (that function rebuilds its dict per call)."""
    return _by_constant()


def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(PP.resolve()))


def human_map(header: str | None) -> str:
    if not header:
        return "?"
    words = header.removeprefix("MAP_HEADER_").split("_")
    return " ".join(w if re.fullmatch(r"\d+[A-Z]*|B\d+F|\d+F", w) else w.capitalize() for w in words)


def species_name(const: str) -> str:
    """Display name: the decomp's pokedex name (upper case in Gen 4 data) in title case."""
    return by_constant()[const].name.title().replace("'D", "'d")


# ---------------------------------------------------------------------------------------------
# Acquisition options


@dataclass(frozen=True)
class Stage:
    species: str  # SPECIES_*
    enter: int  # lowest level this stage can exist at on this path
    via: str | None = None  # evolution method into this stage (None for the acquired stage)
    out_level: int | None = None  # level threshold of the level-based evolution out of this stage


@dataclass(frozen=True)
class SourceOption:
    id: str
    kind: str  # wild_slot | gift | egg | static | roamer | npc_trade | breed
    acquired: str  # SPECIES_* obtained (the first stage)
    map_header: str | None
    level_lo: int
    level_hi: int
    stages: tuple[Stage, ...]
    fixed_mon: dict | None = None
    quantity: int | str = UNLIMITED
    exclusive_group: str | None = None
    consumes: tuple[tuple[str, int], ...] = ()  # evolution items used up
    detail: str = ""
    src: tuple[str, ...] = ()
    mothers: tuple[str, ...] = ()  # breed: female-capable mothers of the line (Ditto excluded)

    @property
    def member(self) -> str:
        return self.stages[-1].species

    @property
    def min_level(self) -> int:
        return self.stages[-1].enter


def _needs_levelup(method: str | None) -> bool:
    return method is not None and method not in ITEM_METHODS and method not in TRADE_METHODS


def stage_max(opt: SourceOption, i: int, level: int) -> int:
    """Highest level at which stage i can still learn a move, for a member at `level`."""
    if i == len(opt.stages) - 1:
        return level
    m = level - sum(1 for st in opt.stages[i + 1:] if _needs_levelup(st.via))
    if opt.stages[i].out_level is not None:
        m = min(m, opt.stages[i].out_level - 1)
    return m


def _default_moves(const: str, lvl: int) -> list[str]:
    """BoxPokemon_SetDefaultMoves: add level-up moves at or below lvl in order; when four are
    known, the oldest is dropped (BoxPokemon_ReplaceMove)."""
    known: list[str] = []
    for n, mv in by_constant()[const].learnset_level:
        if n > lvl:
            break
        if mv in known:
            continue
        if len(known) == 4:
            known.pop(0)
        known.append(mv)
    return known


def options_of(ledger):
    """The ledger view's LegalityOptions (models.DEFAULT_LEGALITY for a plain ledger)."""
    return getattr(ledger, "options", None) or DEFAULT_LEGALITY


def source_options(species: str, ledger) -> list[SourceOption]:
    cache_ = ledger.derived.setdefault("legality_options", {})
    key = (species, options_of(ledger))
    if key not in cache_:
        cache_[key] = _options(species, ledger, frozenset())
    return cache_[key]


def min_level(species: str, ledger) -> int | None:
    opts = source_options(species, ledger)
    return min((o.min_level for o in opts), default=None)


def _options(species: str, led, stack: frozenset[str]) -> list[SourceOption]:
    if species in stack or species not in by_constant():
        return []
    stack = stack | {species}
    out: dict[str, SourceOption] = {}

    def add(o: SourceOption) -> None:
        cur = out.get(o.id)
        if cur is None or o.min_level < cur.min_level:
            out[o.id] = o

    for c in led.pre(subject=species):
        e = c.entry
        if e.kind not in ACQUIRE_KINDS:
            continue
        if e.kind == "npc_trade":
            req = e.fixed_mon["requested_species"]
            lo = min((o.min_level for o in _options(req, led, stack)), default=None)
            if lo is None:
                continue  # nothing to hand over
            hi = 100
        elif e.level:
            lo, hi = e.level
        else:
            continue  # level unknown: conservative, not an option
        oid = f"{e.kind}:{species}@{e.map_header}"
        what = ", ".join(x for x in (species_name(species), e.detail) if x)
        detail = f"{ACQUIRE_LABELS.get(e.kind, e.kind)} - {human_map(e.map_header)} ({what})"
        add(SourceOption(oid, e.kind, species, e.map_header, lo, hi, (Stage(species, lo),), e.fixed_mon,
                         e.quantity, e.exclusive_group, (), detail, tuple(e.src)))
    for o in _breed_options(species, led):
        add(o)
    trade_ok = options_of(led).allow_trade_evolutions
    for pre, ev in _preds().get(species, []):
        if ev.method in TRADE_METHODS and not trade_ok:
            continue
        need: list[str] = []
        if isinstance(ev.param, str) and ev.param.startswith("ITEM_"):
            need.append(ev.param)
            if led.item_copies(ev.param) == 0:
                continue
        if isinstance(ev.param, str) and ev.param.startswith("SPECIES_") and not led.species_sources(ev.param):
            continue
        from platsim.availability.ledger import _location_evolution_maps

        loc = _location_evolution_maps().get(ev.method)
        if loc is not None and not any(h in led.reached for h in loc):
            continue
        for po in _options(pre, led, stack):
            prev = po.stages[-1]
            if ev.method in _level_methods():
                enter = max(int(ev.param), prev.enter + 1)
                out_level = int(ev.param)
            elif ev.method in ITEM_METHODS or ev.method in TRADE_METHODS:
                enter, out_level = prev.enter, None  # no level-up: evolves on use / on receipt
            else:
                enter, out_level = prev.enter + 1, None
            if ev.method == "EVO_LEVEL_KNOW_MOVE":
                k = _earliest_know(po, ev.param, led)
                if k is None:
                    continue
                enter = max(enter, k + 1)
            stages = po.stages[:-1] + (Stage(prev.species, prev.enter, prev.via, out_level), Stage(species, enter, ev.method))
            consumes = dict(po.consumes)
            for it in need:
                if ev.method in ITEM_METHODS or ev.method in HELD_ITEM_METHODS or ev.method == "EVO_TRADE_WITH_HELD_ITEM":
                    consumes[it] = consumes.get(it, 0) + 1
            if ev.method in TRADE_METHODS:
                held = f" holding {load_items()[ev.param].name}" if need else ""
                how = f"trade evolution{held}; needs a second cartridge for the trade"
                esrc = tuple(refs()["evolution"]) + tuple(refs()["trade_evolution"])
            else:
                how, esrc = ev.method, tuple(refs()["evolution"])
            o = SourceOption(po.id, po.kind, po.acquired, po.map_header, po.level_lo, po.level_hi, stages,
                             po.fixed_mon, po.quantity, po.exclusive_group, tuple(sorted(consumes.items())),
                             po.detail + f" -> {species_name(species)} ({how})",
                             po.src + esrc + tuple(by_constant()[pre].src[6:7]), po.mothers)
            add(o)
    return sorted(out.values(), key=lambda o: (o.min_level, o.id))


def _earliest_know(po: SourceOption, move: str, led) -> int | None:
    """Earliest level at which the last stage of `po` can know `move` (EVO_LEVEL_KNOW_MOVE)."""
    st = po.stages[-1]
    sp = by_constant()[st.species]
    best = None
    for n, mv in sp.learnset_level:
        if mv == move:
            k = n if n >= st.enter else (st.enter if relearner_available(led) else None)
            if k is not None and (best is None or k < best):
                best = k
    if _tm_marker(st.species, move, led) or _shard_tutor(st.species, move, led):
        best = st.enter if best is None else min(best, st.enter)
    return best


# --- breeding ----------------------------------------------------------------------------------


def daycare_available(led) -> bool:
    man = map_header_for_script("scripts_solaceon_town")[0]
    lady = map_header_for_script("scripts_pokemon_day_care")[0]
    return man in led.reached and lady in led.reached


def _egg_species_of_mother(mother: str, led) -> list[str]:
    root = _root(mother)
    out = [root]
    for baby, incense, without, _ in _incense_table():
        if root == baby:
            out = [without] + ([baby] if led.item_copies(incense) != 0 else [])
    if root in _gender_split_eggs():
        out.append(_gender_split_eggs()[root][0])
    return out


def breed_mothers(led) -> dict[str, tuple[list[str], bool]]:
    """egg species -> (female-capable mothers obtainable pre-Champion, ditto_possible)."""
    key = "legality_breed_mothers"
    if key in led.derived:
        return led.derived[key]
    res: dict[str, tuple[list[str], bool]] = {}
    if daycare_available(led):
        ditto = bool(led.species_sources("SPECIES_DITTO"))
        for const in by_constant():
            groups = egg_groups(const)
            if "EGG_GROUP_UNDISCOVERED" in groups or "EGG_GROUP_DITTO" in groups:
                continue
            if not led.species_sources(const):
                continue
            for egg in _egg_species_of_mother(const, led):
                mothers, d = res.setdefault(egg, ([], False))
                if _can_be_female(const) and const not in mothers:
                    mothers.append(const)
                res[egg] = (mothers, d or ditto)
        res = {k: v for k, v in res.items() if v[0] or v[1]}
    led.derived[key] = res
    return res


def _breed_options(species: str, led) -> list[SourceOption]:
    bm = breed_mothers(led).get(species)
    if not bm:
        return []
    mothers, ditto = bm
    via = ", ".join(species_name(m) for m in mothers[:3]) + ("" if mothers else "") + (" or Ditto" if ditto else "")
    lvl = int(re.search(r"#define EGG_POKEMON_LEVEL\s+(\d+)", POKEMON_H.read_text()).group(1))
    return [SourceOption(f"breed:{species}@{map_header_for_script('scripts_pokemon_day_care')[0]}", BREED, species,
                         map_header_for_script("scripts_pokemon_day_care")[0], lvl, lvl, (Stage(species, lvl),),
                         None, UNLIMITED, None, (), f"Day Care egg (mother: {via})", tuple(refs()["breed"]),
                         tuple(mothers))]


# ---------------------------------------------------------------------------------------------
# Move sources

_USES: dict[tuple[str, str, str], dict[str, int]] = {}


def uses_of(choice: MoveChoice) -> dict[str, int]:
    """Resources consumed by a MoveChoice made here: {"TMnn": 1} / {"ITEM_HEART_SCALE": 1} /
    shards. HMs are never consumed (ledger.tm_copies)."""
    return dict(_USES.get((choice.move, choice.source_kind, choice.detail), {}))


def _mk(move: str, kind: str, detail: str, src: list[str], uses: dict[str, int] | None = None) -> MoveChoice:
    _USES[(move, kind, detail)] = dict(uses or {})
    return MoveChoice(move=move, source_kind=kind, detail=detail, availability_ref="; ".join(dict.fromkeys(src)))


def relearner_available(led) -> bool:
    header = map_header_for_script(RELEARNER_SCRIPT.stem)[0]
    return header in led.reached and led.item_copies("ITEM_HEART_SCALE") != 0


def _where(led, item: str) -> tuple[str, list[str]]:
    labels = {"shop": "Shop", "game_corner": "Game Corner", "item_ball": "Item ball", "hidden_item": "Hidden item",
              "npc_item_gift": "Gift", "underground": "Underground"}
    entries = [c for c in led.pre(subject=item) if c.entry.kind in labels]
    entries.sort(key=lambda c: (c.entry.quantity != UNLIMITED, c.entry.kind != "shop"))
    if not entries:
        # Never a display placeholder: a copy that cannot be named is not a legal copy.
        raise NoNamedSource(f"{item} has copies in the ledger but no nameable pre-Champion source")
    e = entries[0].entry
    return f"{labels[e.kind]} - {human_map(e.map_header)}", list(e.src[:1])


def _tm_marker(const: str, move: str, led) -> str | None:
    sp = by_constant()[const]
    for marker in sp.learnset_tm:
        if tm_moves().get(marker) == move and led.tm_copies(marker) != 0:
            return marker
    return None


def _shard_tutor(const: str, move: str, led):
    sp = by_constant()[const]
    if move not in sp.learnset_tutor:
        return None
    shards = {"red": "ITEM_RED_SHARD", "blue": "ITEM_BLUE_SHARD", "yellow": "ITEM_YELLOW_SHARD", "green": "ITEM_GREEN_SHARD"}
    for t in shard_tutors():
        if t.move != move or not led.tutor_available(t.location):
            continue
        if any(n and led.item_copies(shards[c]) == 0 for c, n in t.shard_cost.items()):
            continue
        return t
    return None


def _tm_choice(move: str, marker: str, led, extra: str = "") -> MoveChoice:
    item = f"ITEM_{marker}"
    copies = led.tm_copies(marker)
    where, wsrc = _where(led, item)
    n = "unlimited" if copies == UNLIMITED else f"{copies} cop{'y' if copies == 1 else 'ies'}"
    kind = "hm" if marker.startswith("HM") else "tm"
    uses = {marker: 1} if kind == "tm" and copies != UNLIMITED else {}
    return _mk(move, kind, f"{marker} - {where} ({n}){extra}", wsrc + load_items()[item].src[1:2], uses)


def _tutor_choice(move: str, t, extra: str = "") -> MoveChoice:
    c = t.shard_cost
    shards = {"red": "ITEM_RED_SHARD", "blue": "ITEM_BLUE_SHARD", "yellow": "ITEM_YELLOW_SHARD", "green": "ITEM_GREEN_SHARD"}
    loc = human_map("MAP_HEADER_" + t.location)
    return _mk(move, "tutor", f"{loc} tutor ({c['red']}R/{c['blue']}B/{c['yellow']}Y/{c['green']}G){extra}",
               list(t.src), {shards[k]: v for k, v in c.items() if v})


def _choices(opt: SourceOption, move: str, level: int, led, allow_egg: bool = True, why: list[str] | None = None) -> list[MoveChoice]:
    why = why if why is not None else []
    out: list[MoveChoice] = []
    sp = by_constant()
    if level < opt.min_level:
        why.append(f"{species_name(opt.member)} via {opt.id} is not obtainable below Lv {opt.min_level}")
        return out
    n_st = len(opt.stages)
    relearn = relearner_available(led)
    rsrc = refs()["relearner"]
    draco_stage = None
    for i, st in enumerate(opt.stages):
        mx = stage_max(opt, i, level)
        member = i == n_st - 1
        if mx < st.enter:
            continue  # this stage never exists long enough on this path to learn anything
        name = species_name(st.species)
        lsrc = [sp[st.species].src[5]] if len(sp[st.species].src) > 5 else []
        for n, mv in sp[st.species].learnset_level:
            if mv != move:
                continue
            if n > mx:
                why.append(f"{name} learns it at Lv {n} by level-up, above the highest level it can learn moves at on this path ({mx})")
                continue
            natural = n >= st.enter or (i == 0 and any(move in _default_moves(st.species, a) for a in range(opt.level_lo, min(opt.level_hi, mx) + 1)))
            if natural:
                if member:
                    out.append(_mk(move, "level_up", f"Level-up Lv {n}", lsrc + refs()["default_moves"]))
                else:
                    out.append(_mk(move, "pre_evo_level_up", f"Pre-evolution level-up ({name} Lv {n})", lsrc + refs()["evolution"]))
            if relearn:
                as_ = "" if member else f", as {name} (Lv <= {mx})"
                out.append(_mk(move, "relearner", f"Move relearner - Pastoria City (1 Heart Scale; {name} Lv {n} move{as_})",
                               lsrc + rsrc, {"ITEM_HEART_SCALE": 1}))
            elif not natural:
                why.append(f"{name} Lv {n} is below the level it is obtained at ({st.enter}) and the move relearner is not available")
        marker = _tm_marker(st.species, move, led)
        if marker:
            out.append(_tm_choice(move, marker, led, "" if member else f" (taught to {name})"))
        else:
            for m in sp[st.species].learnset_tm:
                if tm_moves().get(m) == move:
                    why.append(f"{m} has no pre-Champion copy (ledger)")
        t = _shard_tutor(st.species, move, led)
        if t:
            out.append(_tutor_choice(move, t, "" if member else f" (taught to {name})"))
        elif move in sp[st.species].learnset_tutor:
            locs = [x.location for x in shard_tutors() if x.move == move]
            why.append(f"shard tutor(s) {locs} for this move are not available before the Champion (ledger)")
        if move == draco_meteor_tutor().move:
            if "TYPE_DRAGON" in sp[st.species].types:
                draco_stage = name  # the latest Dragon-type stage is reported
            else:
                why.append(f"Draco Meteor tutor needs a Dragon-type party member; {name} is {sp[st.species].types}")
        for ut in starter_ultimate_tutors():
            if ut.move == move and st.species in ut.species:
                if led.tutor_available("ROUTE_228"):
                    out.append(_mk(move, "tutor", f"Route 228 tutor ({name}, max friendship)", ut.src + refs()["friendship"]))
                else:
                    why.append(f"Route 228 starter tutor ({ut.map_header}) is post-game: not available before the Champion (ledger)")
    if draco_stage is not None:
        dm = draco_meteor_tutor()
        if led.tutor_available("DRACO_METEOR"):
            out.append(_mk(move, "tutor", f"Draco Meteor tutor - Route 210 (Dragon type {draco_stage}, max friendship)",
                           dm.src + refs()["friendship"]))
        else:
            why.append("Draco Meteor tutor is not available before the Champion (ledger)")
    root = opt.stages[0].species
    if move in sp[root].egg_moves:
        if not allow_egg:
            why.append("egg move (fathers must learn it by a non-egg method)")
        elif not options_of(led).allow_egg_moves:
            why.append(f"egg move of {species_name(root)}: egg moves are not allowed (enable allow_egg_moves / "
                       "--allow-egg-moves)")
        elif opt.kind != "breed":
            why.append(f"egg move of {species_name(root)}, but this member is not bred (source {opt.id})")
        else:
            f = find_father(root, opt.mothers, move, led)
            if f is None:
                why.append(f"egg move of {species_name(root)} but no pre-Champion father in a shared egg group learns it by a non-egg method")
            else:
                father, fc = f
                out.append(_mk(move, "egg", f"Egg move (father: {species_name(father)} - {fc.detail})",
                               refs()["egg"] + [sp[root].src[5]] + ([fc.availability_ref] if fc.availability_ref else []),
                               uses_of(fc)))
    # dedupe keeping order
    seen, res = set(), []
    for c in out:
        k = (c.source_kind, c.detail)
        if k not in seen:
            seen.add(k)
            res.append(c)
    return res


def find_father(egg_species: str, mothers: tuple[str, ...], move: str, led):
    """A pre-Champion father for `move` (see module doc). The father's own source follows the move
    preference order (`move_source_key`: no limited copy first, then level-up < TM/HM < tutor <
    relearner), then the simplest father source (`option_class`), then the species constant.
    Returns (SPECIES_*, MoveChoice of the father's own source) or None."""
    key = ("legality_father", egg_species, move, options_of(led))
    if key in led.derived:
        return led.derived[key]
    mgroups = {g for m in mothers for g in egg_groups(m)}
    best = None
    for const in sorted(by_constant()):
        if const == "SPECIES_DITTO" or not _can_be_male(const):
            continue
        groups = set(egg_groups(const))
        if "EGG_GROUP_UNDISCOVERED" in groups or not (groups & mgroups):
            continue
        for o in source_options(const, led):
            for c in _choices(o, move, 100, led, allow_egg=False):
                score = (*move_source_key(c, led)[:2], OPTION_RANK[option_class(o)], const)
                if best is None or score < best[0]:
                    best = (score, const, c)
    res = None if best is None else (best[1], best[2])
    led.derived[key] = res
    return res


def sources(species: str, move: str, level: int, ledger, option: SourceOption | None = None) -> list[MoveChoice]:
    opts = [option] if option is not None else source_options(species, ledger)
    seen, out = set(), []
    for o in opts:
        for c in _choices(o, move, level, ledger):
            k = (c.source_kind, c.detail)
            if k not in seen:
                seen.add(k)
                out.append(c)
    return out


def explain(species: str, move: str, level: int, ledger, option: SourceOption | None = None) -> list[str]:
    why: list[str] = []
    opts = [option] if option is not None else source_options(species, ledger)
    if not opts:
        return [f"{species} has no pre-Champion source"]
    for o in opts:
        _choices(o, move, level, ledger, why=why)
    if move not in load_moves():
        why.append(f"{move} is not a move")
    return list(dict.fromkeys(why)) or [f"{species_name(species)} cannot learn {move} by any method in the decomp data"]


# ---------------------------------------------------------------------------------------------
# Source preference: the simplest legal source first
#
# A member usually has several legal ways to be obtained and to know each move. Which one is
# *reported* (and used for team-wide copy accounting) follows this documented order. Sources never
# change a battle, EXCEPT an NPC trade (fixed IVs/nature/ability, boosted exp, FR-008a): so trade
# vs non-trade is never decided here - it is an explicit optimizer choice (FR-008b,
# optimizer/candidates.Variant), and a caller that ranks trade and non-trade options together
# (validator.from_showdown) gets non-trade first.
#
# Species source (`option_sort_key`), best first:
#   0 the member species itself from a wild slot / gift / gift egg / static / roamer entry;
#   1 such an entry for a pre-evolution, then evolve (fewer evolutions first);
#   2 NPC trade (only reached when a caller mixes trade and non-trade options, see above);
#   3 Day-Care egg: only when no other option makes the member legal (an egg move, or a
#     breeding-only path). Callers can drop BREED options entirely (a future "no egg sources" flag).
#   Ties: the cheaper move sources (`move_cost`), then fewer evolutions, the lowest minimum level, id.
#
# Move source (`move_source_key`), best first:
#   sources consuming no limited copy before any source consuming one (team-wide copy limits,
#   FR-004/FR-006: a single-copy TM is spent only when nothing unlimited works), then by kind:
#   level-up / pre-evolution level-up < TM/HM (unlimited) < tutor < move relearner < egg move.
#   So the full order is: level-up < unlimited TM/HM < tutor < relearner < egg (no limited copy)
#   < single-copy TM < other limited sources < egg whose father needs a limited copy.

OPTION_RANK = {"own": 0, "pre_evolution": 1, "npc_trade": 2, BREED: 3}
MOVE_KIND_ORDER = {"level_up": 0, "pre_evo_level_up": 0, "tm": 1, "hm": 1, "tutor": 2, "relearner": 3, "egg": 4}


def option_class(opt: SourceOption) -> str:
    if opt.kind == BREED:
        return BREED
    if opt.kind == "npc_trade":
        return "npc_trade"
    return "own" if len(opt.stages) == 1 else "pre_evolution"


def option_sort_key(opt: SourceOption, move_cost: int = 0) -> tuple:
    return (OPTION_RANK[option_class(opt)], move_cost, len(opt.stages), opt.min_level, opt.id)


def resource_copies(res: str, led) -> int | str:
    """Pre-Champion copies of a resource named in `uses_of` ("TM26" or "ITEM_*")."""
    return led.tm_copies(res) if re.fullmatch(r"(TM|HM)\d\d", res) else led.item_copies(res)


def consumes_limited(choice: MoveChoice, led) -> bool:
    return any(resource_copies(r, led) != UNLIMITED for r in uses_of(choice))


def move_source_key(choice: MoveChoice, led) -> tuple:
    return (int(consumes_limited(choice, led)), MOVE_KIND_ORDER.get(choice.source_kind, 9), choice.detail)


def move_cost(choices, led) -> int:
    """Sum of the move-source ranks of `choices` (option tie-break in `option_sort_key`)."""
    return sum(10 * k[0] + k[1] for k in (move_source_key(c, led) for c in choices))


# ---------------------------------------------------------------------------------------------
# Held-item sources (FR-002b "held item and its source", FR-006/FR-006a)


class NoNamedSource(ValueError):
    """An item the ledger counts as obtainable but whose source cannot be named: a legality error
    (the copy count would be unsupported), never a display placeholder."""


ITEM_SOURCE_LABELS = {"shop": "Shop", "game_corner": "Game Corner", "berry_tree": "Berry patch",
                      "npc_item_gift": "Gift", "item_ball": "Item ball", "hidden_item": "Hidden item",
                      "underground": "Underground mining", "wild_held_item": "Wild held item"}
_ITEM_SOURCE_ORDER = tuple(ITEM_SOURCE_LABELS)  # display preference among sources of equal quantity


@dataclass(frozen=True)
class ItemSource:
    kind: str
    text: str  # "<Kind> - <where>" without the quantity
    quantity: int | str
    src: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"{self.text} ({_copies_text(self.quantity)})"


def _copies_text(n: int | str) -> str:
    return UNLIMITED if n == UNLIMITED else f"{n} cop{'y' if int(n) == 1 else 'ies'}"


def item_const(item: str) -> str:
    return item if item.startswith("ITEM_") else f"ITEM_{item.upper()}"


def item_sources(item: str, led) -> list[ItemSource]:
    """Every named pre-Champion source of `item` (ledger), one per (kind, map, wild holder), best
    first: unlimited before finite, then ITEM_SOURCE_LABELS order, then text."""
    item = item_const(item)
    groups: dict[tuple, list] = {}
    for c in led.pre(subject=item):
        e = c.entry
        if e.kind in ITEM_SOURCE_LABELS:
            groups.setdefault((e.kind, e.map_header, getattr(e, "via_species", None)), []).append(e)
    out = []
    for (kind, header, via), es in groups.items():
        if kind == "wild_held_item" and via:
            text = f"{ITEM_SOURCE_LABELS[kind]} - {species_name(via)} at {human_map(header)}"
        elif kind == "underground":
            parities = {p for e in es for p in ("odd", "even") if f"{p} TID" in (e.detail or "")}
            only = f" ({parities.pop()} Trainer ID only)" if len(parities) == 1 else ""
            text = f"{ITEM_SOURCE_LABELS[kind]} - {human_map(header)}{only}"
        else:
            text = f"{ITEM_SOURCE_LABELS[kind]} - {human_map(header)}"
        qty = UNLIMITED if any(e.quantity == UNLIMITED for e in es) else sum(int(e.quantity) for e in es)
        src = tuple(dict.fromkeys(s for e in es for s in e.src[:2]))
        out.append(ItemSource(kind, text, qty, src))
    out.sort(key=lambda s: (s.quantity != UNLIMITED, _ITEM_SOURCE_ORDER.index(s.kind), s.text))
    return out


def held_item_source(item: str, led, option: SourceOption | None = None) -> tuple[str, list[str]]:
    """("Held item source" text, src refs) for a held item. Raises NoNamedSource if the ledger has
    no copy or no nameable source (a legality error, never shown as '?')."""
    const = item_const(item)
    if option is not None and option.fixed_mon and option.fixed_mon.get("held_item") == const:
        return f"Held by the NPC-trade Pokemon on arrival ({option.detail})", list(option.fixed_mon.get("src", []))[:2]
    copies = led.item_copies(const)
    srcs = item_sources(const, led)
    if copies == 0 or not srcs:
        raise NoNamedSource(f"{const}: no named pre-Champion source in the availability ledger (copies: {copies}); "
                            "this is a legality error (FR-006), not a display issue")
    if copies == UNLIMITED and srcs[0].quantity == UNLIMITED:
        return srcs[0].label, list(srcs[0].src)
    if copies == UNLIMITED:  # finite berry copies, replanted at a reachable berry patch (ledger.item_copies)
        patch = led.pre(kind="berry_tree")[0].entry
        return ("; ".join(s.label for s in srcs) + " - replanted for unlimited copies",
                [r for s in srcs for r in s.src] + list(patch.src[-1:]))
    return "; ".join(s.label for s in srcs), [r for s in srcs for r in s.src]


__all__ = ["SourceOption", "Stage", "options_of", "source_options", "min_level", "sources", "explain", "uses_of",
           "relearner_available", "daycare_available", "find_father", "refs", "egg_groups", "gender_ratio",
           "BREED", "OPTION_RANK", "MOVE_KIND_ORDER", "option_class", "option_sort_key", "move_source_key", "move_cost",
           "consumes_limited", "resource_copies", "NoNamedSource", "ItemSource", "item_sources", "held_item_source"]
