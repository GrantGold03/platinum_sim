"""`platsim explain SUBJECT` (T073, User Story 3): trace a legality fact or opponent detail back to
the decomp.

Subjects: `tmNN`, `hmNN`, `species:<key>`, `item:<key>`, `move:<key>`, `trainer:<key>`,
`divergence:<id>`. Keys accept the decomp constant (`SPECIES_ABRA`), its stem (`abra`,
`poke_radar`) or the display name (`Poké Radar`); matching ignores case, accents and punctuation.

`explain(subject)` returns an `Explanation`: `data` (JSON-ready) and `lines` (human output). Every
content line ends with `[refs]`: decomp `path:line` (relative to pokeplatinum/), the divergence
ledger's own refs, or - for project rules (National Dex / Munchlax exclusions) - the spec clause
and the line of the rule in src/platsim/availability/ledger.py. Nothing here restates a game value:
everything is read from the availability ledger and the decomp readers.

An unknown subject raises `UnknownSubject` with close-match suggestions (CLI exit 2).
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from platsim.pins import DECOMP_COMMIT, DECOMP_ROOT, REPO_ROOT

LEDGER_PY = Path(__file__).resolve().parent / "availability" / "ledger.py"
DIVERGENCES_JSON = REPO_ROOT / "data" / "divergences.json"
POKEMON_C = DECOMP_ROOT / "src" / "pokemon.c"
KINDS = ("tm", "hm", "species", "item", "move", "trainer", "divergence")
DOUBLE = '"double_battle"'
ACQUIRE_KINDS = ("wild_slot", "gift", "egg", "static", "roamer", "npc_trade")


class UnknownSubject(ValueError):
    def __init__(self, subject: str, why: str, suggestions: list[str]):
        self.subject = subject
        self.suggestions = suggestions
        msg = f"unknown subject {subject!r}: {why}"
        if suggestions:
            msg += "; closest matches: " + ", ".join(suggestions)
        super().__init__(msg)


@dataclass
class Explanation:
    subject: str
    kind: str
    data: dict[str, Any]
    lines: list[str] = field(default_factory=list)

    def text(self) -> str:
        return "\n".join(self.lines)

    def to_json(self) -> dict[str, Any]:
        return {"subject": self.subject, "kind": self.kind, "decomp_commit": DECOMP_COMMIT, **self.data}


# ---------------------------------------------------------------------------------------------
# helpers


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z0-9]", "", s.encode("ascii", "ignore").decode().lower())


def _line(text: str, *refs: str) -> str:
    refs_ = [r for r in dict.fromkeys(refs) if r]
    return f"{text}  [{', '.join(refs_)}]" if refs_ else text


def _project_ref(needle: str) -> str:
    rel_ = LEDGER_PY.relative_to(REPO_ROOT)
    for i, line in enumerate(LEDGER_PY.read_text().splitlines(), start=1):
        if needle in line:
            return f"{rel_}:{i}"
    raise ValueError(f"{rel_}: {needle!r} not found")


def _qty(q: Any) -> str:
    return "unlimited" if q == "unlimited" else str(q)


def _resolve(kind: str, key: str, table: dict[str, str], subject: str) -> str:
    """`table`: normalised alias -> canonical constant."""
    hit = table.get(_norm(key))
    if hit:
        return hit
    close = difflib.get_close_matches(_norm(key), list(table), n=5, cutoff=0.6)
    sugg = list(dict.fromkeys(f"{kind}:{_display_key(kind, table[c])}" for c in close))
    raise UnknownSubject(subject, f"no {kind} named {key!r}", sugg)


def _display_key(kind: str, const: str) -> str:
    if kind in ("tm", "hm"):
        return const.removeprefix("ITEM_").lower()
    if kind == "divergence":
        return const
    return re.sub(r"^(SPECIES|ITEM|MOVE|TRAINER)_", "", const).lower()


@cache
def _species_table() -> dict[str, str]:
    from platsim.decomp.species import by_constant

    t: dict[str, str] = {}
    for const, s in by_constant().items():
        t.setdefault(_norm(s.name), const)
        t[_norm(const.removeprefix("SPECIES_"))] = const
        t[_norm(const)] = const
    return t


@cache
def _item_table() -> dict[str, str]:
    from platsim.decomp.items import load_items

    t: dict[str, str] = {}
    for const, it in load_items().items():
        if const == "ITEM_NONE":
            continue
        t.setdefault(_norm(it.name), const)
        t[_norm(it.key)] = const
        t[_norm(const)] = const
    return t


@cache
def _move_table() -> dict[str, str]:
    from platsim.decomp.moves import load_moves

    t: dict[str, str] = {}
    for const, mv in load_moves().items():
        if const == "MOVE_NONE":
            continue
        t.setdefault(_norm(mv.name), const)
        t[_norm(mv.key)] = const
        t[_norm(const)] = const
    return t


@cache
def _trainer_table() -> dict[str, str]:
    """Trainer data file stems (res/trainers/data/<stem>.json). A key also matches a stem it ends
    with after an underscore (`cynthia` -> champion_cynthia) when that suffix is unique."""
    from platsim.decomp.constants import load_enum
    from platsim.decomp.trainers import TRAINERS_DIR

    enum = load_enum("trainers")
    stems = sorted(p.stem for p in TRAINERS_DIR.glob("*.json") if f"TRAINER_{p.stem.upper()}" in enum.values)
    t = {_norm(s): f"TRAINER_{s.upper()}" for s in stems}
    t.update({_norm(f"TRAINER_{s}"): f"TRAINER_{s.upper()}" for s in stems})
    by_suffix: dict[str, set[str]] = {}
    for s in stems:
        parts = s.split("_")
        for i in range(1, len(parts)):
            by_suffix.setdefault(_norm("_".join(parts[i:])), set()).add(s)
    for suf, ss in by_suffix.items():
        if len(ss) == 1 and suf not in t:
            t[suf] = f"TRAINER_{next(iter(ss)).upper()}"
    return t


@cache
def _divergences() -> dict[str, tuple[dict, str]]:
    text = DIVERGENCES_JSON.read_text()
    lines = text.splitlines()
    out = {}
    for e in json.loads(text)["entries"]:
        ln = next((i for i, l in enumerate(lines, start=1) if f'"id": "{e["id"]}"' in l), 1)
        out[e["id"]] = (e, f"{DIVERGENCES_JSON.relative_to(REPO_ROOT)}:{ln}")
    return out


# ---------------------------------------------------------------------------------------------
# availability entries


def _header(text: str, *refs: str) -> list[str]:
    return [_line(text, *refs), _line(f"  decomp: pokeplatinum @ {DECOMP_COMMIT} (refs relative to pokeplatinum/)")]


def _exclusion_notes(c, led) -> list[str]:
    """Project-rule exclusions, stated in the spec's words."""
    from platsim.availability import ledger as Lg

    out = []
    if c.needs_national_dex and c.phase != Lg.PRE:
        v = led.national_dex
        out.append(_line(
            f"excluded: National Dex (spec FR-003a; project rule ALLOW_NATIONAL_DEX={Lg.ALLOW_NATIONAL_DEX}; "
            f"decomp verdict national_dex.pre_champion={v['pre_champion']}, grant {v['grant']['ref']})",
            _project_ref("ALLOW_NATIONAL_DEX = "), v["grant"]["ref"], *v["condition"]["src"]))
    if any(r.startswith("project_rule:") for r in c.reasons):
        e = c.entry
        sp = e.subject if e.kind in ACQUIRE_KINDS else e.via_species
        out.append(_line(f"excluded: {_species_title(sp)} (spec FR-006a; project rule EXCLUDED_SPECIES)",
                         _project_ref("EXCLUDED_SPECIES = ")))
    return out


def _species_title(const: str | None) -> str:
    if not const:
        return "?"
    from platsim.decomp.species import by_constant

    s = by_constant().get(const)
    return s.name.title() if s else const


def _entry_lines(c, led, indent: str = "  ") -> list[str]:
    from platsim.legality.movesources import human_map

    e = c.entry
    lvl = ""
    if e.level:
        lvl = f", Lv {e.level[0]}" + (f"-{e.level[1]}" if e.level[1] != e.level[0] else "")
    via = f", held by wild {_species_title(e.via_species)}" if e.via_species else ""
    head = (f"{indent}- [{c.phase}] {e.kind} at {human_map(e.map_header)} ({e.map_header or '-'}), "
            f"quantity {_qty(e.quantity)}{lvl}{via}" + (f": {e.detail}" if e.detail else ""))
    out = [_line(head, *e.src)]
    ind = indent + "    "
    for g in e.gates:
        pg = "post-game" if g["post_game"] else "pre-game"
        req = f", requires {g['requires']}" if g.get("requires") else ""
        out.append(_line(f"{ind}gate {g['kind']} ({pg}{req}): {g['detail']}", g["ref"]))
    if e.requires_items:
        out.append(_line(f"{ind}requires item(s): {', '.join(e.requires_items)}", *e.src))
    if e.requires_any:
        out.append(_line(f"{ind}requires any of: {', '.join(e.requires_any)}", *e.src))
    if e.exclusive_group:
        out.append(_line(f"{ind}exclusive group: {e.exclusive_group} (only one of the group can be taken)", *e.src))
    if getattr(e, "once_flag", None):
        out.append(_line(f"{ind}one-time flag: {e.once_flag} (entries sharing it are one acquisition)", *(e.once_flag_src or e.src)))
    for r in c.reasons:
        out.append(_line(f"{ind}reason: {r}", *e.src))
    if c.uncertain:
        out.append(_line(f"{ind}uncertain: a gate could not be resolved; treated as not pre-Champion", *e.src))
    out += [ind + x for x in _exclusion_notes(c, led)]
    if e.fixed_mon:
        out += _fixed_mon_lines(e.fixed_mon, ind)
    return out


def _trade_file(src: list[str]) -> Path | None:
    for s in src:
        if s.startswith("res/npc_trades/"):
            return DECOMP_ROOT / s.split(":")[0]
    return None


def _key_ref(path: Path | None, key: str, fallback: list[str]) -> list[str]:
    """`path:line` of `"key":` in a decomp JSON file (the line the value is read from)."""
    if path is None:
        return fallback[:1]
    from platsim.decomp._util import ref

    try:
        return [ref(path, f'"{key}"')]
    except ValueError:
        return fallback[:1]


def _fixed_mon_lines(fm: dict, ind: str) -> list[str]:
    """NPC trade mon. IVs are listed in the trade file's order (hp, atk, def, speed, spAtk, spDef)."""
    from platsim.decomp.exp import exp_formula

    src = fm.get("src", [])
    tf = _trade_file(src)
    ivs = fm["ivs"]
    iv_refs = [r for k in ("hpIV", "atkIV", "defIV", "speedIV", "spAtkIV", "spDefIV") for r in _key_ref(tf, k, src)]
    out = [
        _line(f"{ind}fixed IVs HP/Atk/Def/Spe/SpA/SpD: "
              f"{ivs['hp']}/{ivs['atk']}/{ivs['def']}/{ivs['spe']}/{ivs['spa']}/{ivs['spd']}", *iv_refs),
        _line(f"{ind}nature {fm['nature']} (personality {fm['personality']} % NATURE_COUNT)",
              *_key_ref(tf, "personality", src), *src[2:3]),
        _line(f"{ind}ability {fm['ability']} (slot {fm['ability_slot']}), held item {fm['held_item']}",
              *_key_ref(tf, "heldItem", src), *src[1:2]),
    ]
    if fm.get("requested_species"):
        out.append(_line(f"{ind}you give: {fm['requested_species']}", *_key_ref(tf, "requestedSpecies", src)))
    if fm.get("is_traded"):
        f = exp_formula()
        lang = json.loads(tf.read_text()).get("language") if tf else None
        foreign = lang not in (None, "LANGUAGE_ENGLISH")
        mul, div = f.traded_foreign if foreign else f.traded
        key = "traded_foreign" if foreign else "traded"
        out.append(_line(f"{ind}traded (not OT, language {lang}): boosted battle exp x{mul}/{div}",
                         f.src[key], *_key_ref(tf, "language", src)))
    return out


def _phase_summary(cs: list, pre_extra: bool = False) -> str:
    from platsim.availability import ledger as Lg

    phases = {c.phase for c in cs}
    if Lg.PRE in phases or pre_extra:
        return Lg.PRE
    if Lg.POST in phases:
        return Lg.POST
    return Lg.NEVER


def _summary_exclusions(cs: list, led) -> list[str]:
    """Project-rule exclusions of the non-pre-Champion entries, once each (for the summary)."""
    return ["  " + x for x in dict.fromkeys(x for c in cs if c.phase != "pre_champion" for x in _exclusion_notes(c, led))]


def _entries_block(cs: list, led) -> list[str]:
    order = {"pre_champion": 0, "post_game": 1, "unobtainable": 2}
    out = []
    for c in sorted(cs, key=lambda c: order.get(c.phase, 3)):
        out += _entry_lines(c, led)
    return out


# ---------------------------------------------------------------------------------------------
# subjects


def _explain_item(const: str, subject: str, kind: str, led) -> Explanation:
    from platsim.decomp.items import load_items

    it = load_items()[const]
    cs = [c for c in led.entries if c.entry.subject == const]
    is_tm = kind in ("tm", "hm")
    copies = led.tm_copies(const) if is_tm else led.item_copies(const)
    lines = _header(f"{const.removeprefix('ITEM_')} - {it.name} ({const})", *it.src[:2])
    if it.teaches_move:
        lines.append(_line(f"  teaches {it.teaches_move}", *it.src[3:4] or it.src[1:2]))
    if it.hold_effect != "HOLD_EFFECT_NONE":
        lines.append(_line(f"  hold effect {it.hold_effect} (param {it.effect_param})", it.src[1]))
    phase = _phase_summary(cs)
    if copies != 0:
        phase = "pre_champion"
    all_refs = [c.entry.src[0] for c in cs][:4] or it.src[1:2]  # what a negative was checked against
    lines.append(_line(f"  phase: {phase}", *[c.entry.src[0] for c in cs if c.phase == phase][:3]))
    if phase != "pre_champion":
        lines += _summary_exclusions(cs, led)
    what = "TM/HM" if is_tm else "item"
    if is_tm and const.startswith("ITEM_HM"):
        note = " (HMs are never consumed: Bag_TryRemoveItem only when !Item_IsHMMove)"
        cref = "src/applications/party_menu/callbacks.c"
        from platsim.availability.ledger import PARTY_CALLBACKS_C
        from platsim.decomp._util import ref

        try:
            cref = ref(PARTY_CALLBACKS_C, "Item_IsHMMove")
        except ValueError:
            pass
        lines.append(_line(f"  copies used by optimizer: {_qty(copies)}{note}", cref))
    else:
        refs = [c.entry.src[0] for c in cs if c.phase == "pre_champion"]
        lines.append(_line(f"  copies used by optimizer ({what} pre-Champion copies): {_qty(copies)}"
                           + (" (no pre-Champion source)" if copies == 0 else ""), *(refs[:6] or all_refs)))
    from platsim.availability.ledger import once_flag_groups

    for flag, grp in once_flag_groups(led, const).items():
        if len(grp) > 1:
            lines.append(_line(f"  shared one-time flag {flag}: {len(grp)} pre-Champion entries, counted once "
                               f"(max quantity {max(int(c.entry.quantity) for c in grp)}, not the sum "
                               f"{sum(int(c.entry.quantity) for c in grp)})",
                               *sorted({r for c in grp for r in c.entry.once_flag_src})))
    purch = [c for c in cs if c.phase == "pre_champion" and c.entry.kind in ("shop", "game_corner")]
    lines.append(_line(f"  purchasable pre-Champion: {'yes' if purch else 'no'}"
                       + (" (" + ", ".join(sorted({c.entry.kind for c in purch})) + ")" if purch else ""),
                       *([c.entry.src[0] for c in purch[:4]] or all_refs)))
    lines.append(_line(f"  availability entries ({len(cs)}):"))
    lines += _entries_block(cs, led)
    data = {"item": const, "name": it.name, "teaches_move": it.teaches_move, "hold_effect": it.hold_effect,
            "phase": phase, "copies": copies, "purchasable": bool(purch), "src": it.src,
            "entries": [c.to_json() for c in cs]}
    return Explanation(subject, kind, data, lines)


def _explain_species(const: str, subject: str, led) -> Explanation:
    from platsim.availability import ledger as Lg
    from platsim.decomp.species import by_constant

    spd = by_constant()
    s = spd[const]
    cs = [c for c in led.entries if c.entry.subject == const and c.entry.kind in ACQUIRE_KINDS]
    sources = led.species_sources(const)
    evo_sources = [x for x in sources if x["kind"] == "evolution"]
    lines = _header(f"{s.name.title()} ({const})", *s.src[:2])
    lines.append(_line(f"  types {'/'.join(s.types)}; abilities {', '.join(a for a in s.abilities if a)}", *s.src[1:3]))
    excluded = const in Lg.EXCLUDED_SPECIES
    phase = Lg.PRE if sources else _phase_summary(cs)
    if excluded:
        phase = Lg.NEVER if not sources else phase
    lines.append(_line(f"  phase: {phase} ({len(sources)} pre-Champion way(s) to own it)",
                       *([x["src"][0] for x in sources if x.get("src")][:3] or [c.entry.src[0] for c in cs][:3] or s.src[:2])))
    if excluded:
        lines.append(_line(f"  excluded: {s.name.title()} (spec FR-006a; project rule EXCLUDED_SPECIES): "
                           + Lg.EXCLUDED_SPECIES_REASON.format(sp=const), _project_ref("EXCLUDED_SPECIES = ")))
    elif phase != Lg.PRE:
        lines += _summary_exclusions(cs, led)
    # evolutions into this species (incl. trade ones, FR-005)
    for pre_key, pre in spd.items():
        for ev in pre.evolutions:
            if ev.target != const:
                continue
            if ev.method.startswith("EVO_TRADE"):
                lines.append(_line(f"  evolves from {pre_key} by {ev.method} (param {ev.param}): "
                                   f"excluded: requires trade evolution (FR-005)", *pre.src[:2]))
            else:
                ok = any(x.get("from") == pre_key for x in evo_sources)
                lines.append(_line(f"  evolves from {pre_key} by {ev.method} (param {ev.param}): "
                                   f"{'pre-Champion source' if ok else 'no pre-Champion source for this path'}",
                                   *pre.src[:2]))
    for ev in s.evolutions:
        tag = " - excluded: requires trade evolution (FR-005)" if ev.method.startswith("EVO_TRADE") else ""
        lines.append(_line(f"  evolves into {ev.target} by {ev.method} (param {ev.param}){tag}", *s.src[:2]))
    lines.append(_line(f"  acquisition entries ({len(cs)}):"))
    lines += _entries_block(cs, led)
    data = {"species": const, "name": s.name, "phase": phase, "excluded_project_rule": excluded,
            "src": s.src, "species_sources": sources, "entries": [c.to_json() for c in cs]}
    return Explanation(subject, "species", data, lines)


def _explain_move(const: str, subject: str, led, level: int) -> Explanation:
    from platsim.decomp.moves import load_moves
    from platsim.legality.movesources import by_constant, source_options, sources

    mv = load_moves()[const]
    lines = _header(f"{mv.name} ({const})", *mv.src[:2])
    lines.append(_line(f"  type {mv.type}, {mv.category}, power {mv.power}, accuracy {mv.accuracy}, pp {mv.pp}",
                       mv.src[1]))
    learners: dict[str, list[dict]] = {}
    for sp in by_constant():
        if not source_options(sp, led):
            continue
        ch = sources(sp, const, level, led)
        if ch:
            learners[sp] = [c.to_dict() for c in ch]
    lines.append(_line(f"  species that can learn it pre-Champion (at level {level}): {len(learners)}", *mv.src[:2]))
    for sp, chs in learners.items():
        kinds = sorted({c["source_kind"] for c in chs})
        first = chs[0]
        more = f" (+{len(chs) - 1} more)" if len(chs) > 1 else ""
        refs = (first.get("availability_ref") or "").split("; ")
        lines.append(_line(f"  - {_species_title(sp)}: {'/'.join(kinds)} - {first['detail']}{more}", *refs))
    data = {"move": const, "name": mv.name, "src": mv.src, "level": level, "learners": learners}
    return Explanation(subject, "move", data, lines)


def _explain_trainer(const: str, subject: str) -> Explanation:
    from platsim.decomp._util import line_of, ref
    from platsim.decomp.constants import rel
    from platsim.decomp.trainers import TRAINERS_DIR, load_trainer

    t = load_trainer(const)
    path = TRAINERS_DIR / f"{t.key}.json"
    r = rel(path)
    lines = _header(f"{t.name} ({const}, class {t.trainer_class}, id {t.trainer_id})", *t.src)
    lines.append(_line(f"  double battle: {t.double_battle}", f"{r}:{line_of(path, DOUBLE)}"))
    items_ln = line_of(path, '"items"')
    for i, it in enumerate(t.bag_items):
        lines.append(_line(f"  bag item: {it}", f"{r}:{items_ln + 1 + i}"))
    ai_ln = line_of(path, '"ai_flags"')
    lines.append(_line(f"  AI flags: {', '.join(t.ai_flags)}", *[f"{r}:{ai_ln + 1 + i}" for i in range(len(t.ai_flags))]))
    nat_ref = ref(POKEMON_C, "% NATURE_COUNT);")
    ab_ref = ref(POKEMON_C, "v2 = SpeciesData_GetSpeciesValue(monSpecies, SPECIES_DATA_ABILITY_2);")
    lines.append(_line("  party:"))
    party = []
    for m in t.party:
        mon_ln = int(m.src[0].rsplit(":", 1)[1])
        lv_ln = line_of(path, '"level"', mon_ln)
        it_ln = line_of(path, '"item"', mon_ln)
        mv_ln = line_of(path, '"moves"', mon_ln)
        ivs_ln = line_of(path, '"iv_scale"', mon_ln)
        lines.append(_line(f"  - {m.species} Lv {m.level} @ {m.held_item}", m.src[0], f"{r}:{lv_ln}", f"{r}:{it_ln}"))
        for j, mvname in enumerate(m.moves):
            lines.append(_line(f"      move {mvname}", f"{r}:{mv_ln + 1 + j}"))
        lines.append(_line(f"      IVs {m.iv} each (iv_scale {m.iv_scale}), EVs 0", f"{r}:{ivs_ln}", m.src[1]))
        lines.append(_line(f"      computed: personality {m.personality}, nature {m.nature}", m.src[1], nat_ref))
        lines.append(_line(f"      computed: ability {m.ability} (slot {m.ability_slot}; base-species data, "
                           f"personality & 1)", m.src[1], ab_ref))
        d = dict(m.__dict__)
        d["refs"] = {"mon": m.src[0], "level": f"{r}:{lv_ln}", "item": f"{r}:{it_ln}", "moves": f"{r}:{mv_ln}",
                     "iv_scale": f"{r}:{ivs_ln}", "build_party": m.src[1], "nature": nat_ref, "ability": ab_ref}
        party.append(d)
    data = {"trainer": const, "name": t.name, "class": t.trainer_class, "trainer_id": t.trainer_id,
            "ai_flags": t.ai_flags, "ai_flags_ref": f"{r}:{ai_ln}", "bag_items": t.bag_items,
            "bag_items_ref": f"{r}:{items_ln}", "double_battle": t.double_battle, "party": party, "src": t.src}
    return Explanation(subject, "trainer", data, lines)


def _explain_divergence(id_: str, subject: str) -> Explanation:
    e, lref = _divergences()[id_]
    lines = [_line(f"divergence {id_} ({e.get('area', '?')})", lref)]
    lines.append(_line(f"  {e.get('description', '')}", e.get("decomp_ref", ""), e.get("showdown_ref", "")))
    lines.append(_line(f"  decomp: {e.get('decomp_ref', '')}", e.get("decomp_ref", "")))
    lines.append(_line(f"  showdown: {e.get('showdown_ref', '')}", e.get("showdown_ref", "")))
    lines.append(_line(f"  resolution: {e.get('resolution')}", lref))
    if e.get("impact"):
        lines.append(_line(f"  impact: {e['impact']}", lref))
    if e.get("patch"):
        lines.append(_line(f"  patch: {json.dumps(e['patch'], sort_keys=True)}", lref))
    if e.get("test_id"):
        lines.append(_line(f"  test: {e['test_id']}", lref))
    return Explanation(subject, "divergence", {"divergence": e, "ledger_ref": lref}, lines)


def explain(subject: str, level: int = 100) -> Explanation:
    from platsim.availability.ledger import build_ledger

    s = subject.strip()
    m = re.fullmatch(r"(?i)(tm|hm)\s*0*(\d{1,2})", s)
    if m:
        kind = m.group(1).lower()
        const = f"ITEM_{kind.upper()}{int(m.group(2)):02d}"
        from platsim.decomp.items import load_items

        if const not in load_items():
            tms = [k.removeprefix("ITEM_").lower() for k in load_items() if re.fullmatch(r"ITEM_[TH]M\d\d", k)]
            raise UnknownSubject(subject, f"no {kind.upper()} {m.group(2)}",
                                 difflib.get_close_matches(s.lower(), tms, n=5, cutoff=0.5))
        return _explain_item(const, subject, kind, build_ledger())
    if ":" not in s:
        allk = [f"{k}:" for k in KINDS]
        sugg = []
        for k, tab in (("species", _species_table()), ("item", _item_table()), ("move", _move_table())):
            hit = tab.get(_norm(s))
            if hit:
                sugg.append(f"{k}:{_display_key(k, hit)}")
        raise UnknownSubject(subject, "expected tmNN, hmNN or one of " + ", ".join(f"{k}:<key>" for k in KINDS[2:]),
                             sugg or allk)
    kind, key = s.split(":", 1)
    kind = kind.lower().strip()
    key = key.strip()
    if kind not in KINDS[2:]:
        raise UnknownSubject(subject, f"unknown subject kind {kind!r}",
                             [f"{k}:{key}" for k in difflib.get_close_matches(kind, KINDS[2:], n=3, cutoff=0.3)])
    if kind == "species":
        return _explain_species(_resolve(kind, key, _species_table(), subject), subject, build_ledger())
    if kind == "item":
        const = _resolve(kind, key, _item_table(), subject)
        return _explain_item(const, subject, "item", build_ledger())
    if kind == "move":
        return _explain_move(_resolve(kind, key, _move_table(), subject), subject, build_ledger(), level)
    if kind == "trainer":
        return _explain_trainer(_resolve(kind, key, _trainer_table(), subject), subject)
    div = _divergences()
    if key in div:
        return _explain_divergence(key, subject)
    raise UnknownSubject(subject, f"no divergence with id {key!r}",
                         [f"divergence:{k}" for k in difflib.get_close_matches(key, list(div), n=5, cutoff=0.5)])


def main(subject: str, as_json: bool = False, level: int = 100) -> int:
    import sys

    try:
        ex = explain(subject, level=level)
    except UnknownSubject as e:
        print(f"platsim explain: {e}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(ex.to_json(), indent=2, default=str))
    else:
        print(ex.text())
    return 0


__all__ = ["Explanation", "UnknownSubject", "explain", "main"]
