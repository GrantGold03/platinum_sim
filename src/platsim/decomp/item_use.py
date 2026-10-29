"""Single-use held items (feature 013): which held items the battle code uses up when they trigger.

An item is single-use when its own hold effect, on triggering, runs a battle script that reaches the command
`RemoveItem` on the holder (pokeplatinum/src/battle/battle_script.c BtlCmd_RemoveItem: the item is saved for
Recycle and the battler's heldItem set to ITEM_NONE). A berry is an item whose data puts it in the berries
pocket (`"fieldPocket": "POCKET_BERRIES"` in res/items/data/<item>.json).

Every `RemoveItem` in res/battle/scripts/ is tied to the hold effects that reach it:
  1. C trigger switches: in src/battle/battle_lib.c, the holder's own item triggers (BattleSystem_TriggerHeldItem,
     _TriggerLeftovers, _TriggerHeldItemOnStatus, _TriggerDetrimentalHeldItem, _TriggerHeldItemOnHit) map
     `case HOLD_EFFECT_X:` to the subscript they load. BattleSystem_PluckBerry and _FlingItem are moves, not read.
  2-4. Guards inside the scripts, followed path by path: `CheckItemHoldEffect CHECK_HAVE / CHECK_NOT_HAVE`,
     `GetItemHoldEffect` followed by `CompareVarToValue` on that variable, and `CompareMonDataToValue` on a
     battle-mon flag that C sets only for one hold effect (custapBerry, battle_lib.c).
A site no hold effect reaches must be reachable from a move effect script (res/battle/scripts/effects/, directly or
through include/data/move_side_effect_subscripts.h): those are moves spending an item (Natural Gift, Fling, Pluck).
Any other site, an unresolved subscript name or an empty result raises ItemUseReadError, so a broken reader cannot
report "nothing is single-use".

Subscript names: BATTLE_SUBSCRIPT_<NAME> (generated/battle_subscripts.txt) and the C symbol subscript_<name> both
name res/battle/scripts/subscripts/subscript_<name>.s; the decomp lists the files in the same order in
res/battle/scripts/subscripts/sub_seq.order, which is checked here.
"""

import json
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from platsim.decomp.constants import Ref, load_enum, rel
from platsim.decomp.items import ITEMS_DIR, load_items
from platsim.optimizer.abilities import strip_comments
from platsim.pins import DECOMP_ROOT

SCRIPTS_DIR = DECOMP_ROOT / "res" / "battle" / "scripts"
BATTLE_LIB = DECOMP_ROOT / "src" / "battle" / "battle_lib.c"
MOVE_SUBSCRIPT_TABLE = DECOMP_ROOT / "include" / "data" / "move_side_effect_subscripts.h"
TRIGGER_FUNCS = ("BattleSystem_TriggerHeldItem", "BattleSystem_TriggerLeftovers", "BattleSystem_TriggerHeldItemOnStatus",
                 "BattleSystem_TriggerDetrimentalHeldItem", "BattleSystem_TriggerHeldItemOnHit")
ANY = "*"  # the holder, for an entry from a C trigger (the script names it ATTACKER / DEFENDER / MSG_TEMP)
_LABEL = re.compile(r"^(_\d+):$")


class ItemUseReadError(RuntimeError):
    """The decomp could not be read completely; the classification would be unreliable."""


@dataclass
class ItemUse:
    const: str
    hold_effect: str
    berry: bool
    single_use: bool
    evidence: list[str] = field(default_factory=list)  # decomp file:line refs: trigger/guard, then RemoveItem


@dataclass
class _Cmd:
    ref: str
    op: str
    args: list[str]


@dataclass
class _Script:
    name: str  # file stem, e.g. subscript_pluck_check / effect_script_0039
    cmds: list[_Cmd]
    labels: dict[str, int]


def _parse_script(path: Path, root: Path) -> _Script:
    """Refs read `res/battle/scripts/<sub>/<file>:<line>` whatever the root (tests read a copied tree)."""
    where = str(Path(rel(SCRIPTS_DIR)) / path.relative_to(root))
    cmds: list[_Cmd] = []
    labels: dict[str, int] = {}
    for lineno, line in enumerate(strip_comments(path.read_text(), "script"), start=1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if m := _LABEL.match(s):
            labels[m.group(1)] = len(cmds)
            continue
        op, _, rest = s.partition(" ")
        args = [a.strip() for a in rest.split(",")] if rest.strip() else []
        cmds.append(_Cmd(str(Ref(where, lineno)), op, args))
    return _Script(path.stem, cmds, labels)


@cache
def _scripts(root: Path) -> dict[str, _Script]:
    out = {}
    for sub in ("effects", "subscripts"):
        for path in sorted((root / sub).glob("*.s")):
            out[path.stem] = _parse_script(path, root)
    order = [s.strip() for s in (root / "subscripts" / "sub_seq.order").read_text().splitlines() if s.strip()]
    enum = [s.strip() for s in (DECOMP_ROOT / "generated" / "battle_subscripts.txt").read_text().splitlines()
            if s.strip()]
    if [e.removeprefix("BATTLE_").lower() for e in enum] != order:
        raise ItemUseReadError("generated/battle_subscripts.txt and subscripts/sub_seq.order disagree")
    missing = [n for n in order if n not in out]
    if missing:
        raise ItemUseReadError(f"subscripts listed in sub_seq.order without a file: {missing[:5]}")
    return out


def _subscript(name: str, scripts: dict[str, _Script], ref: str) -> str:
    """BATTLE_SUBSCRIPT_X or subscript_x -> 'subscript_x' (a file stem)."""
    stem = name.removeprefix("BATTLE_").lower() if name.startswith("BATTLE_SUBSCRIPT_") else name
    if stem not in scripts:
        raise ItemUseReadError(f"{ref}: subscript {name} does not resolve to a file")
    return stem


def _function_body(lines: list[str], name: str) -> list[tuple[int, str]]:
    start = next((i for i, ln in enumerate(lines) if re.match(rf"^\S.*\b{name}\(", ln)), None)
    if start is None:
        raise ItemUseReadError(f"{rel(BATTLE_LIB)}: function {name} not found")
    body = []
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("}"):
            return body
        body.append((i + 1, lines[i]))
    raise ItemUseReadError(f"{rel(BATTLE_LIB)}: end of {name} not found")


@cache
def _c_entries() -> list[tuple[str, str, str]]:
    """(HOLD_EFFECT_X, subscript stem name, ref of the case line) from the trigger switches (rule 1)."""
    lines = strip_comments(BATTLE_LIB.read_text(), "c")
    out = []
    for func in TRIGGER_FUNCS:
        group: list[tuple[str, str]] = []
        last_was_case = False
        for lineno, ln in _function_body(lines, func):
            if m := re.search(r"\bcase (HOLD_EFFECT_\w+):", ln):
                if not last_was_case:
                    group = []
                group.append((m.group(1), str(Ref(rel(BATTLE_LIB), lineno))))
                last_was_case = True
                continue
            if ln.strip():
                last_was_case = False
            for m in re.finditer(r"\bsubscript\s*=\s*(subscript_\w+)", ln):
                out.extend((eff, m.group(1), ref) for eff, ref in group)
    if not out:
        raise ItemUseReadError(f"{rel(BATTLE_LIB)}: no held-item trigger case found")
    return out


@cache
def _flag_effects() -> dict[str, tuple[frozenset[str], str]]:
    """BATTLEMON_<FLAG> -> (hold effects that set it, ref): battle-mon flags C sets only under an item check."""
    lines = strip_comments(BATTLE_LIB.read_text(), "c")
    getters = {}
    for i, ln in enumerate(lines):
        if m := re.search(r"case (BATTLEMON_\w+):", ln):
            if i + 1 < len(lines) and (g := re.search(r"return battleMon->moveEffectsData\.(\w+);", lines[i + 1])):
                getters[m.group(1)] = g.group(1)
    out = {}
    for flag, fld in getters.items():
        effs, refs = set(), []
        for i, ln in enumerate(lines):
            if re.search(rf"moveEffectsData\.{fld}\s*=\s*1;", ln):
                for j in range(i - 1, max(i - 15, 0), -1):
                    if m := re.search(r"ItemEffect\s*==\s*(HOLD_EFFECT_\w+)", lines[j]):
                        effs.add(m.group(1))
                        refs.append(str(Ref(rel(BATTLE_LIB), j + 1)))
                        break
                else:
                    effs = None
                    break
        if effs:
            out[flag] = (frozenset(effs), refs[0])
    return out


# A constraint on one battler's held-item effect: ("in", S) = one of S; ("not", S) = none of S.
def _narrow(c, effs: frozenset[str], keep: bool):
    kind, s = c
    if keep:
        return ("in", s & effs) if kind == "in" else ("in", effs - s)
    return ("in", s - effs) if kind == "in" else ("not", s | effs)


class _Walker:
    def __init__(self, scripts: dict[str, _Script]):
        self.scripts = scripts
        self.effect_names = {v: k for k, v in load_enum("item_hold_effects").values.items()}
        self.flags = _flag_effects()
        self.sites: dict[str, set[str]] = {}  # RemoveItem ref -> hold effects attributed
        self.evidence: dict[str, set[tuple[str, ...]]] = {}  # hold effect -> evidence ref tuples
        self.seen: set = set()

    def walk(self, name: str, idx: int, cons: tuple, why: tuple, varmap: tuple, depth: int = 0) -> None:
        if depth > 64:
            raise ItemUseReadError(f"{name}: call depth over 64")
        script = self.scripts[name]
        while idx < len(script.cmds):
            key = (name, idx, cons, varmap)
            if key in self.seen:
                return
            self.seen.add(key)
            cmd = script.cmds[idx]
            op, a = cmd.op, cmd.args
            if op == "End":
                return
            if op == "GoTo":
                idx = script.labels[a[0]]
                continue
            if op == "GoToSubscript":
                self.walk(_subscript(a[0], self.scripts, cmd.ref), 0, cons, why, (), depth + 1)
                return
            if op == "Call":
                self.walk(_subscript(a[0], self.scripts, cmd.ref), 0, cons, why, (), depth + 1)
                idx += 1
                continue
            if op == "RemoveItem":
                self._remove(cmd, a[0], cons, why)
                idx += 1
                continue
            if op == "GetItemHoldEffect":
                varmap = tuple(sorted(dict(varmap, **{a[1]: a[0]}).items()))
                idx += 1
                continue
            branch = self._guard(cmd, cons, why, varmap)
            if branch is not None:
                (jcons, jwhy), (fcons, fwhy) = branch
                if jcons is not None:
                    self.walk(name, script.labels[a[-1]], jcons, jwhy, varmap, depth)
                if fcons is None:
                    return
                cons, why = fcons, fwhy
                idx += 1
                continue
            for arg in a:  # any other jump: both ways, nothing learnt
                if arg in script.labels:
                    self.walk(name, script.labels[arg], cons, why, varmap, depth)
            if varmap and op != "CompareVarToValue":  # a variable written by another command no longer holds the effect
                varmap = tuple((k, v) for k, v in varmap if k not in a)
            idx += 1

    def _get(self, cons: tuple, battler: str):
        d = dict(cons)
        return d.get(battler, d.get(ANY, ("not", frozenset())))

    def _set(self, cons: tuple, battler: str, c) -> tuple | None:
        if c[0] == "in" and not c[1]:
            return None  # impossible path
        return tuple(sorted(dict(cons, **{battler: c}).items()))

    def _split(self, cons, why, battler, effs, jump_keeps, ref):
        c = self._get(cons, battler)
        j = self._set(cons, battler, _narrow(c, effs, jump_keeps))
        f = self._set(cons, battler, _narrow(c, effs, not jump_keeps))
        jw = why + ((battler, ref),) if jump_keeps else why
        fw = why if jump_keeps else why + ((battler, ref),)
        return (j, jw), (f, fw)

    def _guard(self, cmd: _Cmd, cons, why, varmap):
        op, a = cmd.op, cmd.args
        if op == "CheckItemHoldEffect" and len(a) == 4:
            return self._split(cons, why, a[1], frozenset([a[2]]), a[0] == "CHECK_HAVE", cmd.ref)
        if op == "CompareVarToValue" and len(a) == 4 and a[1] in dict(varmap) and a[0] in ("OPCODE_EQU", "OPCODE_NEQ"):
            try:
                eff = self.effect_names[int(a[2], 0)]
            except (ValueError, KeyError):
                eff = a[2] if a[2].startswith("HOLD_EFFECT_") else None
            if eff is None:
                raise ItemUseReadError(f"{cmd.ref}: held-item effect compared with {a[2]!r}, not a hold effect")
            return self._split(cons, why, dict(varmap)[a[1]], frozenset([eff]), a[0] == "OPCODE_EQU", cmd.ref)
        if op == "CompareMonDataToValue" and len(a) == 5 and a[2] in self.flags and a[0] == "OPCODE_EQU":
            effs, cref = self.flags[a[2]]
            c = self._get(cons, a[1])
            narrowed = self._set(cons, a[1], _narrow(c, effs, True))
            w = why + ((a[1], cmd.ref), (a[1], cref))
            if a[3] == "0":  # jump when the flag is clear (no info); fall through when set
                return (cons, why), (narrowed, w)
            return (narrowed, w), (cons, why)
        return None

    def _remove(self, cmd: _Cmd, battler: str, cons, why) -> None:
        self.sites.setdefault(cmd.ref, set())
        c = self._get(cons, battler)
        if c[0] != "in":
            return  # not tied to a hold effect on this path
        refs = tuple(r for b, r in why if b in (battler, ANY)) + (cmd.ref,)
        for eff in c[1]:
            self.sites[cmd.ref].add(eff)
            self.evidence.setdefault(eff, set()).add(refs)


@cache
def _move_reachable(root: Path) -> frozenset[str]:
    """Scripts reachable from move effect scripts: Call / GoToSubscript and MOVE_SUBSCRIPT_PTR_* (the C table)."""
    scripts = _scripts(root)
    table = {}
    for lineno, ln in enumerate(strip_comments(MOVE_SUBSCRIPT_TABLE.read_text(), "c"), start=1):
        if m := re.search(r"\[(MOVE_SUBSCRIPT_PTR_\w+)\]\s*=\s*(subscript_\w+)", ln):
            table[m.group(1)] = m.group(2)
    if not table:
        raise ItemUseReadError(f"{rel(MOVE_SUBSCRIPT_TABLE)}: no entries read")
    todo = [n for n in scripts if n.startswith("effect_script_")]
    seen = set(todo)
    while todo:
        for cmd in scripts[todo.pop()].cmds:
            targets = []
            if cmd.op in ("Call", "GoToSubscript"):
                targets.append(_subscript(cmd.args[0], scripts, cmd.ref))
            for arg in cmd.args:
                for ptr in re.findall(r"MOVE_SUBSCRIPT_PTR_\w+", arg):
                    if ptr in table:
                        targets.append(_subscript(table[ptr], scripts, cmd.ref))
            for t in targets:
                if t not in seen:
                    seen.add(t)
                    todo.append(t)
    return frozenset(seen)


def remove_sites(root: Path = SCRIPTS_DIR) -> tuple[dict[str, set[str]], dict[str, set[tuple[str, ...]]], set[str]]:
    """(RemoveItem ref -> hold effects, hold effect -> evidence, move-driven refs). Raises ItemUseReadError."""
    scripts = _scripts(root)
    w = _Walker(scripts)
    for eff, sub, ref in _c_entries():
        w.walk(_subscript(sub, scripts, ref), 0, ((ANY, ("in", frozenset([eff]))),), ((ANY, ref),), ())
    for name in scripts:  # every script as an entry: C and other scripts load them directly
        w.walk(name, 0, (), (), ())
    all_sites = {c.ref for s in scripts.values() for c in s.cmds if c.op == "RemoveItem"}
    if not all_sites:
        raise ItemUseReadError(f"{root}: no RemoveItem found")
    moves = _move_reachable(root)
    move_driven = set()
    for ref in sorted(all_sites):
        if w.sites.get(ref):
            continue
        stem = Path(ref.split(":")[0]).stem
        if stem not in moves:
            raise ItemUseReadError(f"{ref}: RemoveItem not tied to any hold effect and not reachable from a move")
        move_driven.add(ref)
    if not w.evidence:
        raise ItemUseReadError("no hold effect reaches RemoveItem")
    return w.sites, w.evidence, move_driven


@cache
def item_uses() -> dict[str, ItemUse]:
    """ITEM_* -> ItemUse for every item load_items() returns."""
    _, evidence, _ = remove_sites()
    out = {}
    for const, it in load_items().items():
        data = json.loads((ITEMS_DIR / f"{it.key}.json").read_text())
        ev = sorted({r for refs in evidence.get(it.hold_effect, ()) for r in refs}) \
            if it.hold_effect != "HOLD_EFFECT_NONE" else []
        out[const] = ItemUse(const, it.hold_effect, data.get("fieldPocket") == "POCKET_BERRIES", bool(ev), ev)
    return out


def is_excluded_single_use(item: str | None) -> bool:
    """True when the item (ITEM_* or key) is single-use and not a berry: never a held-item candidate."""
    if not item:
        return False
    u = item_uses().get(item if item.startswith("ITEM_") else f"ITEM_{item.upper()}")
    return bool(u and u.single_use and not u.berry)


__all__ = ["ItemUse", "ItemUseReadError", "is_excluded_single_use", "item_uses", "remove_sites"]
