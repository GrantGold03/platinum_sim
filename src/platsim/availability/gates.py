"""Gate conditions on the script paths that reach a script node (T022, research R2 rule 1).

A *gate* is a branch whose direction depends on story progress:
- `FLAG_GAME_COMPLETED` tested with CheckFlag (GoToIfSet / GoToIfUnset / CallIfSet / ...);
- a var written by `CheckGameCompleted` (reads FLAG_GAME_COMPLETED: src/system_flags.c:69-72,
  src/scrcmd_system_flags.c:148-151) and then compared;
- a var written by `GetNationalDexEnabled` (GetSetNationalDexEnabled mode 2:
  src/scrcmd.c:5466-5482) and then compared;
- a var written by `CheckLocalDexCompleted` (the National Dex grant's condition) and then compared:
  kind `national_dex`, like GetNationalDexEnabled;
- a var written by `CheckDistributionEvent`, or by `CheckItem` of a Mystery-Gift-only item
  (event_only_items), and then compared: kind `event_only`, never true on one cartridge;
- a var written by `CheckBadgeAcquired` / `CountBadgesAcquired` and then compared (recorded, never
  post-game: every badge is pre-Champion).

Method. Every branch primitive (SCRCMD_GOTOIF / SCRCMD_CALLIF) consumes the last comparison
result (SCRCMD_CHECKFLAG / SCRCMD_COMPAREVARTO*). The analysis tracks, per path, the pending
comparison and which vars hold a gate value, and explores the script:
1. unconstrained: every gate branch both ways;
2. in the *pre-game world*: FLAG_GAME_COMPLETED = 0 and National Dex = not obtained (R2 rule 1:
   National Dex is granted at scripts_sandgem_town_pokemon_research_lab.s:539). Branches on those
   values are decided with the game's own condition table (src/scrcmd.c:744-752).
A node is post-game when (1) reaches it and (2) does not. The gates reported for a post-game node
are the pruned branch points from which it is still reachable; for a pre-game node, the gate
branch points passed on pre-game paths that can still reach it (badge checks, for example).

Two refinements keep this honest without guessing:
- **Menus** (structural, both explorations): `Init*TextMenu var` + `AddMenuEntry*` + `ShowMenu`
  can only put the added entry indices (or MENU_CANCEL, include/constants/menu.h, when B can
  exit) in `var`, so a compare against an index that was never added on that path is dead.
- **Derived story flags / vars** (`Facts`, a fixpoint): a flag whose every SetFlag (or
  RemoveObject of an object hidden by it) site is itself post-game is unset before the Champion;
  a var whose every write is a literal `SetVar` holds only 0 or the literals written at pre-game
  sites. Flags/vars named anywhere in C (src/, include/) or written any other way are not
  tracked. These gates have kinds `script_flag` / `script_var` and say "derived" in `detail`.
  Site reachability here is script-level (it does not ask whether the site's map is reachable).

Var writes are recognised from the macro parameter names in asm/macros/scrcmd.inc (destVar,
destVarID, result, ...); a write by any other command clears a var's gate meaning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from functools import cache

from platsim.decomp.constants import Ref, rel
from platsim.decomp.scripts import (
    OP_CALL_COMMON,
    OP_CALLIF,
    OP_GOTOIF,
    Command,
    ScriptFile,
    all_script_stems,
    generated_constants,
    load_script_file,
    macro_table,
    parse_int,
    successors,
)
from platsim.pins import DECOMP_ROOT

SCRCMD_C = DECOMP_ROOT / "src" / "scrcmd.c"

GATE_FLAG = "FLAG_GAME_COMPLETED"
# Gate kinds (data-model Gate.kind).
KIND_GAME_COMPLETED = "script_flag"
KIND_NATIONAL_DEX = "national_dex"
KIND_DERIVED_VAR = "script_var"
KIND_BADGE = "badge"
KIND_BADGE_COUNT = "badge_count"
KIND_REGION = "region"
KIND_UNCERTAIN = "uncertain"
# Distribution-event checks (CheckDistributionEvent, or CheckItem of an item only Mystery Gift
# hands out). One cartridge without Mystery Gift never passes them (FR-005); see event_only_items().
KIND_EVENT_ONLY = "event_only"
POST_GAME_KINDS = frozenset({KIND_GAME_COMPLETED, KIND_NATIONAL_DEX, KIND_DERIVED_VAR, KIND_EVENT_ONLY})

# Pre-game world values (R2 rule 1). KIND_EVENT_ONLY is 0 forever on one cartridge.
PREGAME_VALUES = {KIND_GAME_COMPLETED: 0, KIND_NATIONAL_DEX: 0, KIND_EVENT_ONLY: 0}

MYSTERY_GIFT_C = DECOMP_ROOT / "src" / "scrcmd_mystery_gift.c"


@cache
def event_only_items() -> dict[str, Ref]:
    """ITEM_* added to the bag only by a Mystery Gift event handler.

    src/scrcmd_mystery_gift.c: each `Init*Event` handler (dispatched from giftHandlers[] by the
    received gift's type, ScrCmd_MysteryGiftGive) adds a literal ITEM_* with Bag_TryAddItem and sets
    the distribution-event magic. An item counts as event-only when no field script gives it
    (no literal operand of AddItem / a VAR_0x8004 / VAR_0x8008 SetVar, i.e. the item-gift idioms of
    scripts_common.s CommonScript_AddItemQuantity and scripts_visible_items.s) and it is in no mart
    list (include/data/mart_items.h)."""
    text = MYSTERY_GIFT_C.read_text()
    out: dict[str, Ref] = {}
    cur_fn = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = re.match(r"static void (Init\w+Event)\(", line)
        if m:
            cur_fn = m.group(1)
        m = re.search(r"Bag_TryAddItem\(\w+,\s*(ITEM_\w+)", line)
        if m and cur_fn:
            out[m.group(1)] = Ref(rel(MYSTERY_GIFT_C), lineno)
    if not out:
        raise ValueError("no Init*Event item grants found in src/scrcmd_mystery_gift.c")
    given = _script_given_items()
    marts = (DECOMP_ROOT / "include" / "data" / "mart_items.h").read_text()
    return {k: v for k, v in out.items() if k not in given and not re.search(rf"\b{k}\b", marts)}


@cache
def _script_given_items() -> frozenset[str]:
    out: set[str] = set()
    for stem in all_script_stems():
        for c in load_script_file(stem).commands:
            for p in c.prims:
                ops = [o.text for o in p.operands]
                if p.op == "SCRCMD_ADDITEM" and ops[0].startswith("ITEM_"):
                    out.add(ops[0])
                elif p.op == "SCRCMD_SETVARFROMVALUE" and ops[0] in ("VAR_0x8004", "VAR_0x8008") and ops[1].startswith("ITEM_"):
                    out.add(ops[1])
    return frozenset(out)

_WRITE_PARAM = re.compile(r"(?i)^(dest|result|ret$|returnVar|out|successVar|selectedOptionVar)")
_ASM_SETS = {"FALSE": 0, "TRUE": 1}  # asm/macros/scrcmd.inc:67-68
_MENU_INIT = {
    "SCRCMD_INITGLOBALTEXTMENU": (4, 3),  # (selectedOptionVar operand, canExitWithB operand)
    "SCRCMD_INITLOCALTEXTMENU": (4, 3),
    "SCRCMD_INITGLOBALTEXTLISTMENU": (4, 3),
    "SCRCMD_INITLOCALTEXTLISTMENU": (4, 3),
}
_MENU_ADD = {"SCRCMD_ADDMENUENTRYIMM": 1, "SCRCMD_ADDMENUENTRY": 1, "SCRCMD_ADDLISTMENUENTRY": 2}
_MENU_VAR = "__menu__"


@dataclass(frozen=True)
class Gate:
    kind: str
    ref: Ref
    detail: str
    post_game: bool
    requires: str = ""  # for a pruned path: the gate value that path needs, e.g. "FLAG_GAME_COMPLETED=1"

    def __str__(self) -> str:
        req = f" [requires {self.requires}]" if self.requires else ""
        return f"{self.kind}@{self.ref}: {self.detail}{req}"


@cache
def condition_table() -> tuple[tuple[bool, bool, bool], ...]:
    """sConditionTable from src/scrcmd.c: [condition][compare result <,==,>] -> taken."""
    lines = SCRCMD_C.read_text().splitlines()
    for i, line in enumerate(lines):
        if "sConditionTable[6][3]" in line:
            rows = []
            for row in lines[i + 1 : i + 10]:
                m = re.match(r"\s*\{\s*(\w+),\s*(\w+),\s*(\w+)\s*\}", row)
                if m:
                    rows.append(tuple(v == "TRUE" for v in m.groups()))
            if len(rows) != 6:
                raise ValueError("sConditionTable parse failed")
            return tuple(rows)
    raise ValueError("sConditionTable not found in src/scrcmd.c")


def _compare(a: int, b: int) -> int:
    """Compare() in src/scrcmd.c (u16 operands): 0 if a<b, 1 if equal, 2 if a>b."""
    a, b = a & 0xFFFF, b & 0xFFFF
    return 0 if a < b else (1 if a == b else 2)


@cache
def header_defines() -> dict[str, int]:
    """Integer `#define`s in include/constants/**/*.h (e.g. MENU_YES, MENU_CANCEL, DIR_*)."""
    out: dict[str, int] = {}
    for path in sorted((DECOMP_ROOT / "include" / "constants").rglob("*.h")):
        for m in re.finditer(r"^#define\s+(\w+)\s+\(?(-?(?:0x[0-9A-Fa-f]+|\d+))\)?\s*$", path.read_text(errors="replace"), re.M):
            out.setdefault(m.group(1), int(m.group(2), 0))
    return out


def _value(token: str) -> int | None:
    token = token.strip()
    v = parse_int(token)
    if v is not None:
        return v
    if token in _ASM_SETS:
        return _ASM_SETS[token]
    v = generated_constants().get(token)
    if v is not None:
        return v
    return header_defines().get(token)


SCRCMD_TABLE_H = DECOMP_ROOT / "include" / "data" / "scripts" / "scrcmd.h"
_ARG_READ = re.compile(
    r"(FieldSystem_GetVarPointer\([^;]*?ScriptContext_Read(?:HalfWord|Byte|Word)\(ctx\))"
    r"|ScriptContext_(GetVarPointer|GetVar|ReadHalfWord|ReadByte|ReadWord)\(ctx\)"
)


@cache
def prim_write_operands(op: str) -> frozenset[int]:
    """Operand positions of primitive `op` that its C handler writes through a var pointer.

    include/data/scripts/scrcmd.h maps SCRCMD_* to ScrCmd_*; the handler body's operand reads
    (ScriptContext_GetVar / GetVarPointer / ReadHalfWord / ReadByte / ReadWord, in source order)
    give each operand's role; GetVarPointer (or FieldSystem_GetVarPointer of a read id) is a write.
    Complements the macro-parameter-name rule (e.g. GetSpeciesFromFossil `speciesVar`)."""
    if op in _COMPARE_OPS or op in (OP_GOTOIF, OP_CALLIF):
        return frozenset()  # compares read their var through a pointer; they never write it
    return _handler_writes().get(op, frozenset())


@cache
def _handler_writes() -> dict[str, frozenset[int]]:
    handlers = dict(re.findall(r"ScriptCommand\((SCRCMD_\w+),\s*(ScrCmd_\w+)\)", SCRCMD_TABLE_H.read_text()))
    bodies: dict[str, str] = {}
    for path in (DECOMP_ROOT / "src").rglob("*.c"):
        text = path.read_text(errors="replace")
        if "ScrCmd_" not in text:
            continue
        for m in re.finditer(r"^(?:static )?BOOL (ScrCmd_\w+)\(ScriptContext \*ctx\)\s*\{(.*?)^\}", text, re.S | re.M):
            bodies.setdefault(m.group(1), m.group(2))
    out = {}
    for op, fn in handlers.items():
        body = bodies.get(fn)
        if not body:
            continue
        pos = set()
        for i, m in enumerate(_ARG_READ.finditer(body)):
            if m.group(1) or m.group(2) == "GetVarPointer":
                if _pointer_written(body, m.start()):
                    pos.add(i)
        if pos:
            out[op] = frozenset(pos)
    return out


def _pointer_written(body: str, at: int) -> bool:
    """Is the var pointer fetched at `at` written? `u16 *x = ...GetVarPointer(ctx)` counts as a
    write when the body assigns through it (`*x = `, `*x += `, `(*x)++`, ...) or hands `x` to a
    call; a pointer that is only dereferenced for reading (SetVarFromVar's source, a compare) is
    a read. An unnamed pointer is assumed written."""
    line_start = body.rfind("\n", 0, at) + 1
    m = re.search(r"\*\s*(\w+)\s*=\s*$", body[line_start:at]) or re.search(r"(\w+)\s*=\s*$", body[line_start:at])
    if not m:
        return True
    x = re.escape(m.group(1))
    return bool(re.search(rf"\*\s*{x}\s*(=[^=]|\+=|-=|\|=|&=|\+\+|--)|\(\*\s*{x}\)\s*(\+\+|--|=[^=])|[(,]\s*{x}\s*[,)]", body[body.find(";", at) + 1 :]))


@cache
def _write_positions(macro_name: str) -> tuple[int, ...]:
    m = macro_table().get(macro_name)
    if m is None:
        return ()
    return tuple(i for i, p in enumerate(m.params) if _WRITE_PARAM.match(p))


# ---------------------------------------------------------------------------------------------
# Derived story facts


@dataclass(frozen=True)
class Facts:
    """Story flags/vars whose pre-game values are known from the scripts (see module docstring)."""

    post_flags: frozenset[str] = frozenset()  # every set site post-game -> unset pre-game
    var_all: tuple[tuple[str, frozenset[int]], ...] = ()  # every value the var can ever hold
    var_pre: tuple[tuple[str, frozenset[int]], ...] = ()  # values it can hold pre-game

    def all_values(self, var: str) -> frozenset[int] | None:
        return dict(self.var_all).get(var)

    def pre_values(self, var: str) -> frozenset[int] | None:
        return dict(self.var_pre).get(var)


EMPTY_FACTS = Facts()

# A pending comparison: ("flag", name, ref) | ("var", var, taint|None, operand, ref) | ("other",)
Pending = tuple | None
Taints = frozenset  # of (var, kind, detail, ref, values|None)


def _gate_effects(cmd: Command, taints: Taints, pending: Pending):
    """Apply a command's primitives. Returns (taints, pending, branch_prims)."""
    branch_prims = []
    for w in _write_positions(cmd.name):
        if w < len(cmd.args):
            var = cmd.args[w]
            taints = frozenset(t for t in taints if t[0] != var)
    for prim in cmd.prims:
        op = prim.op
        ops = [o.text for o in prim.operands]
        for w in prim_write_operands(op):
            if w < len(ops) and op not in _MENU_INIT:
                taints = frozenset(t for t in taints if t[0] != ops[w])
        if op not in _COMPARE_OPS and op not in _MENU_INIT and op not in _MENU_ADD:
            # A const/menu value is only trusted until the var is handed to any other primitive
            # (a nested macro may write it without a dest-named parameter, e.g.
            # GoToIfNotEnoughMonForCatchingShow -> CheckHasEnoughMonForCatchingShow VAR_RESULT).
            used = set(ops)
            taints = frozenset(t for t in taints if not (t[1] in ("const", "menu") and t[0] in used))
        if op == "SCRCMD_CHECKFLAG":
            pending = ("flag", ops[0], cmd.ref)
        elif op in ("SCRCMD_COMPAREVARTOVALUE", "SCRCMD_COMPAREVARTOVAR"):
            hit = next((t for t in taints if t[0] == ops[0]), None)
            pending = ("var", ops[0], hit, ops[1], cmd.ref)
        elif op == "SCRCMD_SETVARFROMVALUE" and _value(ops[1]) is not None:
            # Path-sensitive constant: a later compare on this var is decided structurally.
            taints = _taint(taints, ops[0], "const", "const", cmd.ref, frozenset({_value(ops[1]) & 0xFFFF}))
        elif op in ("SCRCMD_SETVARFROMVALUE", "SCRCMD_SETVARFROMVAR", "SCRCMD_ADDVAR", "SCRCMD_SUBVAR"):
            taints = frozenset(t for t in taints if t[0] != ops[0])
        elif op == "SCRCMD_CHECKGAMECOMPLETED":
            taints = _taint(taints, ops[0], KIND_GAME_COMPLETED, "CheckGameCompleted", cmd.ref)
        elif op == "SCRCMD_GETSETNATIONALDEXENABLED" and ops[0] == "2":
            taints = _taint(taints, ops[1], KIND_NATIONAL_DEX, "GetNationalDexEnabled", cmd.ref)
        elif op == "SCRCMD_CHECKLOCALDEXCOMPLETED":
            # The National Dex grant's own condition (scripts_sandgem_town_pokemon_research_lab.s);
            # same kind: decided by the ledger's National Dex verdict, not by the scripts.
            taints = _taint(taints, ops[0], KIND_NATIONAL_DEX, "CheckLocalDexCompleted", cmd.ref)
        elif op == "SCRCMD_CHECKDISTRIBUTIONEVENT":
            taints = _taint(taints, ops[1], KIND_EVENT_ONLY, f"CheckDistributionEvent {ops[0]}", cmd.ref)
        elif op == "SCRCMD_CHECKITEM" and ops[0] in event_only_items():
            src = event_only_items()[ops[0]]
            taints = _taint(taints, ops[2], KIND_EVENT_ONLY, f"CheckItem {ops[0]} (Mystery Gift only, {src})", cmd.ref)
        elif op == "SCRCMD_CHECKBADGEACQUIRED":
            taints = _taint(taints, ops[1], KIND_BADGE, f"CheckBadgeAcquired {ops[0]}", cmd.ref)
        elif op == "SCRCMD_COUNTBADGESACQUIRED":
            taints = _taint(taints, ops[0], KIND_BADGE_COUNT, "CountBadgesAcquired", cmd.ref)
        elif op in _MENU_INIT:
            vi, bi = _MENU_INIT[op]
            can_exit = _value(ops[bi]) if bi < len(ops) else 1
            values = frozenset({header_defines()["MENU_CANCEL"] & 0xFFFF}) if can_exit else frozenset()
            taints = _taint(taints, ops[vi], "menu", "menu", cmd.ref, values)
            taints = frozenset(t for t in taints if t[0] != _MENU_VAR) | {(_MENU_VAR, ops[vi], "", cmd.ref, None)}
        elif op in _MENU_ADD:
            cur = next((t[1] for t in taints if t[0] == _MENU_VAR), None)
            v = _value(ops[_MENU_ADD[op]])
            menu = next((t for t in taints if t[0] == cur and t[1] == "menu"), None) if cur else None
            if menu is not None:
                vals = None if (v is None or menu[4] is None) else menu[4] | {v & 0xFFFF}
                taints = frozenset(t for t in taints if t != menu) | {(cur, "menu", "menu", menu[3], vals)}
        elif op in (OP_GOTOIF, OP_CALLIF, "SCRCMD_GOTOIFTARGETTRAINERDEFEATED"):
            branch_prims.append((prim, pending))
        elif op in ("SCRCMD_CHECKTRAINERFLAG", OP_CALL_COMMON):
            pending = ("other",)
    # A comparison result is consumed by the branch that follows it inside the same macro
    # (GoToIfSet = CheckFlag + GoToIf, ...). Keep it across commands only when the command ends
    # with the comparison itself (a bare CheckFlag / CompareVar line).
    if cmd.prims and cmd.prims[-1].op not in _COMPARE_OPS:
        pending = None
    return taints, pending, branch_prims


_COMPARE_OPS = frozenset(
    {"SCRCMD_CHECKFLAG", "SCRCMD_COMPAREVARTOVALUE", "SCRCMD_COMPAREVARTOVAR", "SCRCMD_CHECKTRAINERFLAG"}
)


def _taint(taints: Taints, var: str, kind: str, detail: str, ref: Ref, values=None) -> Taints:
    return frozenset(t for t in taints if t[0] != var) | {(var, kind, detail, ref, values)}


@dataclass(frozen=True)
class Decision:
    """How a branch resolves.

    `taken` applies when the gate's kind is fixed (pre-game world); `base` applies otherwise
    (structural facts: menus, values a var can never hold). True/False/None (= both ways)."""

    taken: bool | None
    gate: Gate | None
    base: bool | None = None
    cond: int | None = None
    rhs: int | None = None
    name: str = ""
    domain: tuple[int, ...] = (0, 1)

    def requirement(self, direction: bool) -> str:
        """Gate value under which the branch goes `direction` (True = taken)."""
        if self.cond is None or self.rhs is None:
            return ""
        table = condition_table()
        vals = [v for v in self.domain if table[self.cond][_compare(v, self.rhs)] == direction]
        if len(vals) == 1:
            return f"{self.name}={vals[0]}"
        return f"{self.name} in {sorted(vals)}" if vals else ""


def _resolve(values, cond: int, rhs: int) -> bool | None:
    outcomes = {condition_table()[cond][_compare(v, rhs)] for v in values}
    return outcomes.pop() if len(outcomes) == 1 else None


def decide(prim, pending: Pending, facts: Facts) -> Decision:
    if prim.op == "SCRCMD_GOTOIFTARGETTRAINERDEFEATED" or pending is None or pending[0] == "other":
        return Decision(None, None)
    cond = parse_int(prim.operands[0].text)
    if cond is None:
        return Decision(None, None)
    if pending[0] == "flag":
        flag, ref = pending[1], pending[2]
        want = "set" if condition_table()[cond][_compare(1, 1)] else "unset"
        if flag == GATE_FLAG:
            taken = _resolve([PREGAME_VALUES[KIND_GAME_COMPLETED]], cond, 1)
            gate = Gate(KIND_GAME_COMPLETED, ref, f"branch taken when {GATE_FLAG} is {want}", True)
            return Decision(taken, gate, None, cond, 1, GATE_FLAG)
        if flag in facts.post_flags:
            taken = _resolve([0], cond, 1)
            detail = f"derived: every SetFlag {flag} site is post-game; branch taken when {flag} is {want}"
            return Decision(taken, Gate(KIND_GAME_COMPLETED, ref, detail, True), None, cond, 1, flag)
        return Decision(None, None)
    _, var, taint, operand, ref = pending
    rhs = _value(operand)
    if rhs is None:
        return Decision(None, None)
    if taint is not None:
        tvar, kind, detail, src, values = taint
        if kind in ("menu", "const"):
            return Decision(None, None, _resolve(values, cond, rhs) if values else None)
        text = f"{detail} at {src} -> {tvar} compared with {operand}, cond {cond}"
        if kind in (KIND_GAME_COMPLETED, KIND_NATIONAL_DEX, KIND_EVENT_ONLY):
            taken = _resolve([PREGAME_VALUES[kind]], cond, rhs)
            return Decision(taken, Gate(kind, ref, text, True), None, cond, rhs, kind)
        return Decision(None, Gate(kind, ref, text, False), None, cond, rhs, kind)
    every = facts.all_values(var)
    if every is None:
        return Decision(None, None)
    base = _resolve(every, cond, rhs)
    pre = _resolve(facts.pre_values(var), cond, rhs)
    if pre is None or pre == base:
        return Decision(None, None, base)
    detail = f"derived: {var} holds only {sorted(facts.pre_values(var))} before the Champion (ever: {sorted(every)}); compared with {operand}, cond {cond}"
    gate = Gate(KIND_DERIVED_VAR, ref, detail, True)
    return Decision(pre, gate, base, cond, rhs, var, tuple(sorted(every)))


# ---------------------------------------------------------------------------------------------
# Exploration

Node = tuple[str, int]  # (script file stem, command index)


@dataclass
class Exploration:
    visited: set[Node] = field(default_factory=set)
    # pruned branch points: (node of branching command, pruned successor node, gate)
    pruned: list[tuple[Node, Node, Gate]] = field(default_factory=list)
    # gate branch points passed: (node, successor node, gate)
    passed: list[tuple[Node, Node, Gate]] = field(default_factory=list)
    widened: set[Node] = field(default_factory=set)  # nodes where the state cap dropped taints


_MAX_STACK = 12
_MAX_STATES_PER_NODE = 24
_COND_OPS = (OP_GOTOIF, OP_CALLIF, "SCRCMD_GOTOIFTARGETTRAINERDEFEATED")


def explore(
    starts: list[Node],
    local_file: str | None,
    fixed: frozenset[str],
    facts: Facts = EMPTY_FACTS,
    avoid: frozenset[Node] = frozenset(),
) -> Exploration:
    """Explore from `starts`. Gate kinds in `fixed` take their pre-game value; others go both ways.
    Nodes in `avoid` are never entered (used to ask "is there a path that skips X?")."""
    ex = Exploration()
    seen: set = set()
    per_node: dict[Node, int] = {}
    work: list = [(n, frozenset(), None, ()) for n in starts]
    while work:
        state = work.pop()
        if state in seen:
            continue
        seen.add(state)
        (stem, idx), taints, pending, stack = state
        if (stem, idx) in avoid:
            continue
        n_states = per_node.get((stem, idx), 0)
        if n_states >= _MAX_STATES_PER_NODE and taints:
            # Widen: forget gate meanings (both branches open). Loses precision toward pre-game.
            ex.widened.add((stem, idx))
            widened = ((stem, idx), frozenset(), pending, stack)
            if widened not in seen:
                work.append(widened)
            continue
        per_node[(stem, idx)] = n_states + 1
        sf = load_script_file(stem)
        if idx >= len(sf.commands):
            continue
        cmd = sf.commands[idx]
        if cmd.movement:
            continue
        ex.visited.add((stem, idx))
        taints2, pending2, branch_prims = _gate_effects(cmd, taints, pending)
        succ = successors(sf, idx, local_file)
        decisions = {id(prim): decide(prim, pend, facts) for prim, pend in branch_prims}
        if "SCRCMD_RETURN" in cmd.ops and stack:
            work.append((stack[-1], taints2, pending2, stack[:-1]))
            continue
        if any(op in ("SCRCMD_END", "SCRCMD_RETURNCOMMONSCRIPT", "SCRCMD_RETURN") for op in cmd.ops):
            continue
        next_node = next(((s.file, s.index) for s in succ if s.kind == "next"), None)
        drop_next = False
        for s in succ:
            node = (s.file, s.index)
            if s.kind in ("branch", "call") and s.prim is not None and s.prim.op in _COND_OPS:
                d = decisions.get(id(s.prim), Decision(None, None))
                taken = d.taken if (d.gate is not None and d.gate.kind in fixed) else d.base
                if d.gate is not None:
                    if taken is False and d.base is not False:
                        ex.pruned.append(((stem, idx), node, _req(d, True)))
                    elif taken is not False:
                        ex.passed.append(((stem, idx), node, d.gate))
                    if s.prim.op == OP_GOTOIF and next_node is not None:
                        if taken is True and d.base is not True:
                            ex.pruned.append(((stem, idx), next_node, _req(d, False)))
                        elif taken is None:
                            ex.passed.append(((stem, idx), next_node, d.gate))
                if taken is False:
                    continue
                if taken is True:
                    # GoToIf: no fall-through. CallIf: fall-through only after the callee returns.
                    drop_next = True
                if s.kind == "call":
                    if len(stack) < _MAX_STACK and next_node is not None:
                        work.append((node, taints2, pending2, stack + (next_node,)))
                    elif next_node is None:
                        work.append((node, taints2, pending2, stack))
                    continue
                work.append((node, taints2, pending2, stack))
            elif s.kind == "call_common":
                # A common script runs in its own context (src/scrcmd.c ScrCmd_CallCommonScript).
                work.append((node, frozenset(), None, ()))
            elif s.kind == "call":
                if len(stack) < _MAX_STACK and next_node is not None:
                    work.append((node, taints2, pending2, stack + (next_node,)))
                    drop_next = True
            elif s.kind == "goto":
                work.append((node, taints2, pending2, stack))
        if next_node is not None and not drop_next:
            work.append((next_node, taints2, pending2, stack))
    return ex


def _req(d: Decision, direction: bool) -> Gate:
    return replace(d.gate, requires=d.requirement(direction))


def _unconstrained_reach(start: Node, local_file: str | None) -> set[Node]:
    seen: set[Node] = set()
    work = [start]
    while work:
        n = work.pop()
        if n in seen:
            continue
        sf = load_script_file(n[0])
        if n[1] >= len(sf.commands) or sf.commands[n[1]].movement:
            continue
        seen.add(n)
        for s in successors(sf, n[1], local_file):
            work.append((s.file, s.index))
    return seen


@dataclass(frozen=True)
class NodeGates:
    node: Node
    ref: Ref
    reachable: bool  # from some start at all (structural facts applied)
    post_game: bool  # every path needs a post-game gate
    gates: tuple[Gate, ...]
    # Post-game even without the R2 premise "National Dex => post-game" (National Dex branches
    # left open, derived facts recomputed the same way). The premise is not derived from scripts.
    post_game_by_flag: bool


def entry_nodes(sf: ScriptFile) -> list[Node]:
    return [(sf.stem, sf.command_for_entry(i)) for i in range(len(sf.entries))]


FIXED_MAIN = POST_GAME_KINDS
FIXED_FLAG_ONLY = frozenset({KIND_GAME_COMPLETED, KIND_DERIVED_VAR, KIND_EVENT_ONLY})


def node_gates(
    stem: str,
    index: int,
    starts: list[Node] | None = None,
    local_file: str | None = None,
    facts: Facts | None = None,
    flag_facts: Facts | None = None,
) -> NodeGates:
    """Gate conditions on every path from `starts` (default: the file's ScriptEntry targets that
    can start before the Champion, `live_entry_nodes`).

    `facts` default to the derived-facts fixpoint (`story_facts()`)."""
    sf = load_script_file(stem)
    if facts is None:
        facts = story_facts(True)
    if starts is None:
        starts = live_entry_nodes(sf, facts)
    if flag_facts is None:
        flag_facts = story_facts(False) if facts is story_facts(True) else facts
    node = (stem, index)
    ref = sf.commands[index].ref
    key = tuple(starts)
    free = _explore_cached(key, local_file, frozenset(), facts)
    if node not in free.visited:
        return NodeGates(node, ref, False, False, (), False)
    pre = _explore_cached(key, local_file, FIXED_MAIN, facts)
    flag_only = _explore_cached(key, local_file, FIXED_FLAG_ONLY, flag_facts)
    by_flag = node not in flag_only.visited
    if node in pre.visited:
        gates = []
        for _src, dst, gate in pre.passed:
            if node in _reach_cached(dst, local_file) and gate not in gates:
                gates.append(gate)
        return NodeGates(node, ref, True, False, tuple(gates), by_flag)
    gates = []
    for _src, dst, gate in pre.pruned:
        if node in _reach_cached(dst, local_file) and gate not in gates:
            gates.append(gate)
    return NodeGates(node, ref, True, True, tuple(gates), by_flag)


@cache
def _explore_cached(
    starts: tuple[Node, ...],
    local_file: str | None,
    fixed: frozenset[str],
    facts: Facts = EMPTY_FACTS,
    avoid: frozenset[Node] = frozenset(),
) -> Exploration:
    return explore(list(starts), local_file, fixed, facts, avoid)


def can_finish_avoiding(starts: list[Node], local_file: str | None, avoid: frozenset[Node], pregame: bool) -> bool:
    """Is there a path from `starts` to an End that never runs a node in `avoid`?"""
    fixed = FIXED_MAIN if pregame else frozenset()
    ex = _explore_cached(tuple(starts), local_file, fixed, story_facts(True), avoid)
    for stem, idx in ex.visited:
        if "SCRCMD_END" in load_script_file(stem).commands[idx].ops:
            return True
    return False


@cache
def _reach_cached(start: Node, local_file: str | None) -> frozenset[Node]:
    return frozenset(_unconstrained_reach(start, local_file))


def label_gates(stem: str, label: str, **kw) -> NodeGates:
    sf = load_script_file(stem)
    return node_gates(stem, sf.labels[label], **kw)


def entry_gates(stem: str, entry_index: int, target: int, local_file: str | None = None) -> NodeGates:
    """Gates on paths from one ScriptEntry (e.g. the script an event triggers) to `target`."""
    sf = load_script_file(stem)
    return node_gates(stem, target, starts=[(stem, sf.command_for_entry(entry_index))], local_file=local_file)


# ---------------------------------------------------------------------------------------------
# Site tables and the derived-facts fixpoint


@cache
def flag_set_sites() -> dict[str, tuple[Node, ...]]:
    """FLAG_* -> every SetFlag site (SCRCMD_SETFLAG) in any script file."""
    out: dict[str, list[Node]] = {}
    for stem in all_script_stems():
        sf = load_script_file(stem)
        for c in sf.commands:
            for p in c.prims:
                if p.op == "SCRCMD_SETFLAG":
                    out.setdefault(p.operands[0].text, []).append((stem, c.index))
    return {k: tuple(v) for k, v in out.items()}


@cache
def _remove_object_flag_sites() -> dict[str, tuple[Node, ...]]:
    """FLAG_* -> RemoveObject sites whose object (in that map's events) has this hidden_flag."""
    from platsim.availability.mapgraph import events_of, map_headers

    out: dict[str, list[Node]] = {}
    for h in map_headers().values():
        objs = {o.data.get("id"): o.data.get("hidden_flag") for o in events_of(h.name)["object"]}
        try:
            sf = load_script_file(h.scripts)
        except FileNotFoundError:
            continue
        for c in sf.commands:
            for p in c.prims:
                if p.op == "SCRCMD_REMOVEOBJECT":
                    flag = objs.get(p.operands[0].text)
                    if flag and flag != "0":
                        out.setdefault(flag, []).append((sf.stem, c.index))
    return {k: tuple(dict.fromkeys(v)) for k, v in out.items()}


@cache
def _c_names() -> frozenset[str]:
    """FLAG_* / VAR_* names used anywhere in C sources or headers (other than the generated list)."""
    names: set[str] = set()
    for root in (DECOMP_ROOT / "src", DECOMP_ROOT / "include"):
        for path in root.rglob("*"):
            if path.suffix in (".c", ".h"):
                names.update(re.findall(r"\b(?:FLAG|VAR)_[A-Z0-9_x]+\b", path.read_text(errors="replace")))
    return frozenset(names)


@cache
def _var_writes() -> tuple[dict[str, list[tuple[Node, int]]], frozenset[str]]:
    """Literal SetVar sites per var, and the vars written any other way (untracked)."""
    literal: dict[str, list[tuple[Node, int]]] = {}
    other: set[str] = set()
    for stem in all_script_stems():
        sf = load_script_file(stem)
        for c in sf.commands:
            written = {c.args[w] for w in _write_positions(c.name) if w < len(c.args)}
            for p in c.prims:
                ops = [o.text for o in p.operands]
                if p.op != "SCRCMD_SETVARFROMVALUE":
                    other.update(ops[w] for w in prim_write_operands(p.op) if w < len(ops) and ops[w].startswith("VAR_"))
                if p.op == "SCRCMD_SETVARFROMVALUE":
                    v = _value(ops[1])
                    written.discard(ops[0])
                    if v is None:
                        other.add(ops[0])
                    else:
                        literal.setdefault(ops[0], []).append(((stem, c.index), v & 0xFFFF))
                elif p.op in ("SCRCMD_SETVARFROMVAR", "SCRCMD_ADDVAR", "SCRCMD_SUBVAR"):
                    written.discard(ops[0])
                    other.add(ops[0])
            other.update(written)
    return literal, frozenset(other)


# A trigger of a map scripts-file entry: (var, value, ref); var None = unconditional.
Trigger = tuple[str | None, int | None, Ref]


@cache
def entry_triggers(stem: str) -> dict[int, tuple[Trigger, ...]]:
    """ScriptEntry index -> what can start it, for every map header whose scriptsArchiveID is `stem`.

    - object / bg event scripts and init-script entries (OnTransition, OnLoad, ...): unconditional;
    - C triggers (mapgraph.c_script_triggers): unconditional;
    - coord events: only while `var == value` (src/unk_0203C954.c:218);
    - frame-table rows `InitScriptGoToIfEqual var, value, id`: only while var == value
      (FieldSystem_GetFrameTableInitScriptID, src/script_manager.c:796).
    Entries with no trigger are absent (callers keep them as starts, over-approximating)."""
    from pathlib import Path

    from platsim.availability.mapgraph import c_script_triggers, events_of, map_headers

    out: dict[int, list[Trigger]] = {}

    def add(sid, trig):
        if isinstance(sid, int) and 1 <= sid < 2000:
            out.setdefault(sid - 1, []).append(trig)

    for h in map_headers().values():
        if h.scripts != stem:
            continue
        ev = events_of(h.name)
        for kind in ("object", "bg"):
            for e in ev[kind]:
                add(e.data.get("script"), (None, None, e.ref))
        for e in ev["coord"]:
            var = e.data.get("var")
            if isinstance(var, str) and var.startswith("VAR_"):
                add(e.data.get("script"), (var, int(e.data.get("value", 0)) & 0xFFFF, e.ref))
            else:
                add(e.data.get("script"), (None, None, e.ref))
        if Path(DECOMP_ROOT / "res/field/scripts" / f"{h.init_scripts}.s").exists():
            init = load_script_file(h.init_scripts)
            for name, args, ref in init.init_entries:
                if name != "InitScriptEntry_OnFrameTable" and args:
                    add(parse_int(args[-1]), (None, None, ref))
            for c in init.commands:
                if c.name == "InitScriptGoToIfEqual":
                    val = _value(c.args[1])
                    trig = (c.args[0], val & 0xFFFF, c.ref) if c.args[0].startswith("VAR_") and val is not None else (None, None, c.ref)
                    add(parse_int(c.args[2]), trig)
        for sid, ref in c_script_triggers().get(h.name, ()):
            add(sid, (None, None, ref))
    return {k: tuple(v) for k, v in out.items()}


def trigger_possible(trig: Trigger, facts: Facts) -> bool:
    var, value, _ = trig
    if var is None:
        return True
    pre = facts.pre_values(var)
    return pre is None or value in pre


def live_entry_nodes(sf: ScriptFile, facts: Facts) -> list[Node]:
    """entry_nodes minus entries whose every trigger is a var condition that cannot hold before
    the Champion (e.g. Harbor Inn's dream, frame-table VAR_DARKRAI_EVENT_STATE == 1)."""
    trig = entry_triggers(sf.stem)
    out = []
    for i in range(len(sf.entries)):
        ts = trig.get(i)
        if ts and not any(trigger_possible(t, facts) for t in ts):
            continue
        out.append((sf.stem, sf.command_for_entry(i)))
    return out


def _site_post_game(node: Node, facts: Facts, fixed: frozenset[str]) -> bool:
    sf = load_script_file(node[0])
    starts = tuple(live_entry_nodes(sf, facts))
    free = _explore_cached(starts, node[0], frozenset(), facts)
    if node not in free.visited:
        return True  # unreachable even structurally: never runs
    return node not in _explore_cached(starts, node[0], fixed, facts).visited


@cache
def story_facts(national_dex_premise: bool = True) -> Facts:
    """Fixpoint of derived flag/var facts (see module docstring)."""
    fixed = FIXED_MAIN if national_dex_premise else FIXED_FLAG_ONLY
    c_names = _c_names()
    flag_sites: dict[str, list[Node]] = {}
    for f, sites in flag_set_sites().items():
        flag_sites.setdefault(f, []).extend(sites)
    for f, sites in _remove_object_flag_sites().items():
        flag_sites.setdefault(f, []).extend(sites)
    flags = {f: s for f, s in flag_sites.items() if f.startswith("FLAG_") and f not in c_names and f != GATE_FLAG}
    literal, other = _var_writes()
    vars_ = {v: s for v, s in literal.items() if v.startswith("VAR_") and v not in other and v not in c_names}
    var_all = tuple(sorted((v, frozenset({0} | {val for _, val in s})) for v, s in vars_.items()))
    # Least fixpoint, like reachability: start from "nothing set before the Champion" (every
    # tracked flag unset, every tracked var 0) and add what a pre-game site can set, until stable.
    # A value only appears pre-game through a chain of pre-game steps.
    facts = Facts(frozenset(flags), var_all, tuple((v, frozenset({0})) for v, _ in var_all))
    for _ in range(50):
        post_flags = frozenset(f for f, sites in flags.items() if all(_site_post_game(n, facts, fixed) for n in sites))
        var_pre = tuple(
            sorted((v, frozenset({0} | {val for n, val in s if not _site_post_game(n, facts, fixed)})) for v, s in vars_.items())
        )
        new = Facts(post_flags, var_all, var_pre)
        if new == facts:
            return facts
        facts = new
    raise RuntimeError("story_facts did not converge in 50 rounds")


__all__ = [
    "Facts",
    "Gate",
    "NodeGates",
    "node_gates",
    "label_gates",
    "entry_gates",
    "entry_nodes",
    "flag_set_sites",
    "event_only_items",
    "entry_triggers",
    "live_entry_nodes",
    "KIND_EVENT_ONLY",
    "story_facts",
    "POST_GAME_KINDS",
    "KIND_REGION",
    "KIND_UNCERTAIN",
    "rel",
]
