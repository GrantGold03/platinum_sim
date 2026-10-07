"""Field-script parser for pokeplatinum/res/field/scripts/*.s (T018).

What it reads, and from where:
- Command and macro shapes come from `asm/macros/scrcmd.inc` (and `asm/macros/movement.inc`, which
  scrcmd.inc includes). Every source command is expanded, recursively, to its primitive
  `.short SCRCMD_*` ops. Control flow is decided from those primitives, never from command
  names: SCRCMD_END / SCRCMD_RETURN / SCRCMD_RETURNCOMMONSCRIPT stop, SCRCMD_GOTO jumps,
  SCRCMD_GOTOIF / SCRCMD_GOTOIFTARGETTRAINERDEFEATED branch, SCRCMD_CALL / SCRCMD_CALLIF call a
  local label, SCRCMD_CALLCOMMONSCRIPT calls a script by ID (so every `Common_*` alias resolves
  through its `CallCommonScript 0x7xx` body).
- A `ScriptEntry` line's index is its position (0-based) in the file's ScriptEntry block; each
  entry is a `.long label-.-4` jump-table slot (scrcmd.inc `ScriptEntry`).
- Script IDs resolve as `ScriptContext_LoadAndOffsetID` does (src/script_manager.c:228-254):
  the first `SCRIPT_RANGE_TABLE` threshold (src/script_manager.c:32-62, offsets from
  include/script_manager.h:89-119) that the ID reaches picks the file and is subtracted; IDs
  1..1999 are local to the current map's scripts file (ID-1); ID 0 loads `scripts_unk_0402`.
  The remainder indexes the 4-byte jump table (`ScriptContext_JumpToOffsetID`,
  src/script_manager.c:412-416), i.e. the ScriptEntry index.

Assembler details handled: `#define` in a script file (whole-word substitution), comments
(`//`, `/* */`, `@`), labels with no commands (they address the next command, so control falls
through), `.if` inside macros (see `_if_holds`), and `.balign` / `.long` data lines (ignored).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from platsim.decomp.constants import Ref, rel
from platsim.pins import DECOMP_ROOT

SCRIPTS_DIR = DECOMP_ROOT / "res" / "field" / "scripts"
SCRCMD_INC = DECOMP_ROOT / "asm" / "macros" / "scrcmd.inc"
MOVEMENT_INC = DECOMP_ROOT / "asm" / "macros" / "movement.inc"
SCRIPT_MANAGER_H = DECOMP_ROOT / "include" / "script_manager.h"
SCRIPT_MANAGER_C = DECOMP_ROOT / "src" / "script_manager.c"

# Primitive ops with control-flow meaning (names from asm/macros/scrcmd.inc).
OP_END = "SCRCMD_END"
OP_RETURN = "SCRCMD_RETURN"
OP_RETURN_COMMON = "SCRCMD_RETURNCOMMONSCRIPT"
OP_GOTO = "SCRCMD_GOTO"
OP_GOTOIF = "SCRCMD_GOTOIF"
OP_GOTOIF_TRAINER = "SCRCMD_GOTOIFTARGETTRAINERDEFEATED"
OP_CALL = "SCRCMD_CALL"
OP_CALLIF = "SCRCMD_CALLIF"
OP_CALL_COMMON = "SCRCMD_CALLCOMMONSCRIPT"
TERMINAL_OPS = frozenset({OP_END, OP_RETURN, OP_RETURN_COMMON})
# Ops whose label operand is code in this file. Other label operands (ApplyMovement) are data.
CODE_LABEL_OPS = frozenset({OP_GOTO, OP_GOTOIF, OP_GOTOIF_TRAINER, OP_CALL, OP_CALLIF})

_COMMENT_BLOCK = re.compile(r"/\*.*?\*/")
_LABEL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*$")
_DEFINE_RE = re.compile(r"^#define\s+(\w+)\s+(.+?)\s*$")
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _strip_comments(line: str) -> str:
    line = _COMMENT_BLOCK.sub("", line)
    for marker in ("//", "@"):
        i = line.find(marker)
        if i >= 0:
            line = line[:i]
    return line.rstrip()


def _split_args(text: str) -> list[str]:
    """Split on top-level commas (parentheses respected)."""
    out, depth, cur = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    tail = "".join(cur).strip()
    if tail or out:
        out.append(tail)
    return [a for a in out if a != ""]


# ---------------------------------------------------------------------------------------------
# Macro table


@dataclass(frozen=True)
class Operand:
    kind: str  # "expr" | "label"
    text: str


@dataclass(frozen=True)
class Prim:
    op: str
    operands: tuple[Operand, ...]

    def label(self) -> str | None:
        for o in self.operands:
            if o.kind == "label":
                return o.text
        return None


@dataclass(frozen=True)
class Macro:
    name: str
    params: tuple[str, ...]
    defaults: tuple[tuple[str, str], ...]
    body: tuple[str, ...]
    ref: Ref
    movement: bool


def _parse_macros(path: Path, movement: bool) -> dict[str, Macro]:
    macros: dict[str, Macro] = {}
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        s = _strip_comments(lines[i]).strip()
        if s.startswith(".macro"):
            head = s[len(".macro"):].strip()
            parts = head.split(None, 1)
            name = parts[0]
            params, defaults = [], []
            if len(parts) > 1:
                for p in re.split(r"[,\s]+", parts[1].strip()):
                    if not p:
                        continue
                    if "=" in p:
                        k, v = p.split("=", 1)
                        params.append(k)
                        defaults.append((k, v))
                    else:
                        params.append(p)
            start = i + 1  # 1-based line of the .macro directive
            body = []
            i += 1
            while not _strip_comments(lines[i]).strip().startswith(".endm"):
                body.append(_strip_comments(lines[i]).strip())
                i += 1
            macros[name] = Macro(
                name, tuple(params), tuple(defaults), tuple(body), Ref(rel(path), start), movement
            )
        i += 1
    return macros


@cache
def macro_table() -> dict[str, Macro]:
    table = _parse_macros(MOVEMENT_INC, movement=True)
    table.update(_parse_macros(SCRCMD_INC, movement=False))
    return table


def _is_var(token: str) -> bool:
    return token.strip().startswith("VAR_")


def _if_holds(cond: str, bound_vars: dict[str, str]) -> bool:
    """Evaluate a macro `.if`. Only the forms that matter are evaluated; others take the `.if` arm.

    - `(\\x >= VARS_START && ...)` (CompareVar, SetVar): true when the argument is a VAR_* name.
    - `F_ACCEPT_SCRIPT_ENTRIES == TRUE` / frame-table flags: assembler bookkeeping, true.
    - `\\lower < \\upper` (GoToIfInRange recursion): integer comparison, so the recursion emits
      one compare+branch per value in the range.
    """
    if "VARS_START" in cond:
        m = re.search(r"\\(\w+)\s*>=\s*VARS_START", cond)
        return bool(m and _is_var(bound_vars.get(m.group(1), "")))
    m = re.fullmatch(r"\s*\\(\w+)\s*<\s*\\(\w+)\s*", cond)
    if m:
        a, b = _int_expr(bound_vars.get(m.group(1), "")), _int_expr(bound_vars.get(m.group(2), ""))
        if a is None or b is None:
            raise ValueError(f"cannot evaluate .if {cond!r} with {bound_vars}")
        return a < b
    return True


def _int_expr(text: str) -> int | None:
    """Integer value of `N` or `N + M + ...` (what GoToIfInRange's recursion produces)."""
    total = 0
    for part in text.split("+"):
        v = parse_int(part)
        if v is None:
            v = generated_constants().get(part.strip())
        if v is None:
            return None
        total += v
    return total


@cache
def generated_constants() -> dict[str, int]:
    """Every name in the non-mask enums of pokeplatinum/generated/*.txt (C-enum semantics).

    Names defined with different values in two files are dropped (ambiguous)."""
    from platsim.decomp.constants import GENERATED, load_enum, mask_names

    out: dict[str, int] = {}
    clash: set[str] = set()
    masks = mask_names()
    for path in sorted(GENERATED.glob("*.txt")):
        if path.stem in masks:
            continue
        try:
            enum = load_enum(path.stem)
        except ValueError:
            continue
        for k, v in enum.values.items():
            if k in out and out[k] != v:
                clash.add(k)
            out[k] = v
    for k in clash:
        del out[k]
    return out


def _subst(text: str, bound: dict[str, str]) -> str:
    return re.sub(r"\\(\w+)", lambda m: bound.get(m.group(1), m.group(0)), text)


def expand(name: str, args: tuple[str, ...], _stack: tuple = ()) -> tuple[Prim, ...]:
    """Expand a macro call to primitive ops, operands substituted with the call's arguments."""
    table = macro_table()
    macro = table.get(name)
    if macro is None:
        raise KeyError(f"unknown script macro {name!r}")
    if (name, args) in _stack:
        raise ValueError(f"recursive expansion of {name}{args}")
    bound = dict(macro.defaults)
    for p, a in zip(macro.params, args):
        bound[p] = a
    prims: list[Prim] = []
    cur_op: str | None = None
    cur_operands: list[Operand] = []

    def flush() -> None:
        nonlocal cur_op, cur_operands
        if cur_op is not None:
            prims.append(Prim(cur_op, tuple(cur_operands)))
        cur_op, cur_operands = None, []

    # if-stack entries: (taking_this_arm, any_arm_taken)
    if_stack: list[list[bool]] = []

    def active() -> bool:
        return all(x[0] for x in if_stack)

    for line in macro.body:
        if not line:
            continue
        if line.startswith(".if"):
            holds = _if_holds(line[3:], bound) if active() else False
            if_stack.append([holds, holds])
            continue
        if line.startswith(".else"):
            top = if_stack[-1]
            top[0] = not top[1]
            continue
        if line.startswith(".endif"):
            if_stack.pop()
            continue
        if not active():
            continue
        if line.startswith((".error", ".set", ".balign")):
            continue
        if line.startswith((".short", ".byte", ".long", ".word", ".hword")):
            directive, _, rest = line.partition(" ")
            for item in _split_args(rest):
                item_s = _subst(item, bound)
                if directive == ".short" and item.startswith("SCRCMD_"):
                    flush()
                    cur_op = item
                    continue
                if item_s.endswith("-.-4"):
                    cur_operands.append(Operand("label", item_s[: -len("-.-4")].strip()))
                else:
                    cur_operands.append(Operand("expr", item_s.strip()))
            continue
        # nested macro call
        parts = line.split(None, 1)
        sub_name = parts[0]
        sub_args = tuple(_subst(a, bound) for a in _split_args(parts[1])) if len(parts) > 1 else ()
        flush()
        prims.extend(expand(sub_name, sub_args, _stack + ((name, args),)))
    flush()
    return tuple(prims)


@cache
def _expand_cached(name: str, args: tuple[str, ...]) -> tuple[Prim, ...]:
    return expand(name, args)


# ---------------------------------------------------------------------------------------------
# Script IDs


@dataclass(frozen=True)
class ScriptRange:
    threshold: int
    file: str
    ref: Ref


@cache
def script_ranges() -> tuple[ScriptRange, ...]:
    """SCRIPT_RANGE_TABLE in src/script_manager.c, in table (descending) order."""
    offsets: dict[str, int] = {}
    for line in SCRIPT_MANAGER_H.read_text().splitlines():
        m = re.match(r"#define\s+(SCRIPT_ID_OFFSET_\w+)\s+(\d+)", line)
        if m:
            offsets[m.group(1)] = int(m.group(2))
    out = []
    lines = SCRIPT_MANAGER_C.read_text().splitlines()
    for lineno, line in enumerate(lines, start=1):
        m = re.match(r"\s*Entry\((SCRIPT_ID_OFFSET_\w+),\s*(\w+),", line)
        if m:
            out.append(ScriptRange(offsets[m.group(1)], m.group(2), Ref(rel(SCRIPT_MANAGER_C), lineno)))
    if not out:
        raise ValueError("SCRIPT_RANGE_TABLE not found in src/script_manager.c")
    return tuple(out)


@cache
def _fallback_zero_file() -> str:
    text = SCRIPT_MANAGER_C.read_text()
    m = re.search(r"else\s*\{\s*ScriptContext_Load\(fieldSystem, ctx, (\w+),", text)
    if not m:
        raise ValueError("script ID 0 fallback not found in src/script_manager.c")
    return m.group(1)


def resolve_script_id(script_id: int, local_file: str | None) -> tuple[str, int]:
    """script ID -> (scripts file stem, ScriptEntry index), per ScriptContext_LoadAndOffsetID."""
    for r in script_ranges():
        if script_id >= r.threshold:
            return r.file, script_id - r.threshold
    if script_id >= 1:
        if local_file is None:
            raise ValueError(f"script ID {script_id} is map-local but no local file was given")
        return local_file, script_id - 1
    return _fallback_zero_file(), 0


def parse_int(token: str) -> int | None:
    try:
        return int(token.strip(), 0)
    except ValueError:
        return None


# ---------------------------------------------------------------------------------------------
# Script files


@dataclass(frozen=True)
class Command:
    file: str
    index: int
    name: str
    args: tuple[str, ...]  # after #define substitution
    raw_args: tuple[str, ...]
    label: str | None  # nearest preceding label
    ref: Ref
    prims: tuple[Prim, ...]
    movement: bool

    @property
    def ops(self) -> tuple[str, ...]:
        return tuple(p.op for p in self.prims)

    def __str__(self) -> str:
        return f"{self.ref} {self.name} {', '.join(self.args)}"


@dataclass(frozen=True)
class Successor:
    kind: str  # "next" | "goto" | "branch" | "call" | "call_common"
    file: str
    index: int  # command index in `file`; for calls, the callee's first command
    prim: Prim | None = None  # the branching/calling primitive (for conditions)


@dataclass
class ScriptFile:
    stem: str
    path: str
    entries: list[tuple[str, Ref]] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)  # label -> index of next command
    label_refs: dict[str, Ref] = field(default_factory=dict)
    commands: list[Command] = field(default_factory=list)
    defines: dict[str, str] = field(default_factory=dict)
    init_entries: list[tuple[str, tuple[str, ...], Ref]] = field(default_factory=list)

    @property
    def is_init(self) -> bool:
        return bool(self.init_entries) or self.stem.startswith("scripts_init_")

    def entry_label(self, index: int) -> str:
        return self.entries[index][0]

    def entry_index(self, label: str) -> int:
        for i, (lab, _) in enumerate(self.entries):
            if lab == label:
                return i
        raise KeyError(f"{self.stem}: {label} is not a ScriptEntry")

    def label_at(self, label: str) -> int:
        return self.labels[label]

    def command_for_entry(self, index: int) -> int:
        return self.labels[self.entries[index][0]]


_INIT_PREFIX = "InitScript"


@cache
def load_script_file(stem: str) -> ScriptFile:
    path = SCRIPTS_DIR / f"{stem}.s"
    sf = ScriptFile(stem=stem, path=rel(path))
    table = macro_table()
    pending_labels: list[str] = []
    current_label: str | None = None
    in_entries = True
    raw_lines = path.read_text().splitlines()
    for lineno, raw in enumerate(raw_lines, start=1):
        ref = Ref(sf.path, lineno)
        stripped = raw.strip()
        m = _DEFINE_RE.match(stripped)
        if m:
            sf.defines[m.group(1)] = _strip_comments(m.group(2)).strip()
            continue
        if stripped.startswith("#"):
            continue
        line = _strip_comments(raw).strip()
        if not line:
            continue
        m = _LABEL_RE.match(line)
        if m:
            pending_labels.append(m.group(1))
            sf.label_refs[m.group(1)] = ref
            current_label = m.group(1)
            continue
        if line.startswith("."):
            continue  # .balign / .long data
        name, _, rest = line.partition(" ")
        raw_args = tuple(_split_args(rest))
        if name == "ScriptEntry":
            if not in_entries:
                raise ValueError(f"{ref}: ScriptEntry after ScriptEntryEnd")
            sf.entries.append((raw_args[0], ref))
            continue
        if name == "ScriptEntryEnd":
            in_entries = False
            continue
        if name.startswith(_INIT_PREFIX) and name not in ("InitScriptGoToIfEqual",):
            if name.startswith("InitScriptEntry_"):
                sf.init_entries.append((name, raw_args, ref))
            if name == "InitScriptEntry_OnFrameTable":
                pass
            continue
        macro = table.get(name)
        if macro is None:
            raise ValueError(f"{ref}: unknown command {name!r}")
        if len(raw_args) < len(macro.params) - len(macro.defaults) and len(raw_args) == 1:
            raw_args = tuple(raw_args[0].split())
        args = tuple(_apply_defines(a, sf.defines) for a in raw_args)
        if name == "InitScriptGoToIfEqual":
            prims: tuple[Prim, ...] = ()
        else:
            prims = _expand_cached(name, args)
        idx = len(sf.commands)
        for lab in pending_labels:
            sf.labels[lab] = idx
        pending_labels = []
        sf.commands.append(
            Command(stem, idx, name, args, raw_args, current_label, ref, prims, macro.movement)
        )
    for lab in pending_labels:  # trailing labels address the end of the file
        sf.labels[lab] = len(sf.commands)
    return sf


def _apply_defines(arg: str, defines: dict[str, str]) -> str:
    if not defines:
        return arg
    for _ in range(4):
        new = _WORD_RE.sub(lambda m: defines.get(m.group(0), m.group(0)), arg)
        if new == arg:
            break
        arg = new
    return arg


@cache
def all_script_stems() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in SCRIPTS_DIR.glob("*.s")))


# ---------------------------------------------------------------------------------------------
# Control flow


def successors(sf: ScriptFile, index: int, local_file: str | None = None) -> list[Successor]:
    """Intra- and inter-file successors of command `index`.

    `local_file` is the map scripts file used to resolve map-local IDs in CallCommonScript
    (only needed when a common script calls an ID below 2000, which does not occur in practice
    but is handled per ScriptContext_LoadAndOffsetID).
    """
    cmd = sf.commands[index]
    if cmd.movement:
        return []
    out: list[Successor] = []
    falls_through = True
    for prim in cmd.prims:
        op = prim.op
        if op in TERMINAL_OPS:
            falls_through = False
            break
        if op in CODE_LABEL_OPS:
            target = sf.labels[prim.label()]
            if op == OP_GOTO:
                out.append(Successor("goto", sf.stem, target, prim))
                falls_through = False
                break
            if op in (OP_GOTOIF, OP_GOTOIF_TRAINER):
                out.append(Successor("branch", sf.stem, target, prim))
            else:
                out.append(Successor("call", sf.stem, target, prim))
        elif op == OP_CALL_COMMON:
            sid = parse_int(prim.operands[0].text)
            if sid is None:
                raise ValueError(f"{cmd.ref}: non-literal CallCommonScript ID {prim.operands[0].text}")
            fstem, entry = resolve_script_id(sid, local_file or sf.stem)
            callee = load_script_file(fstem)
            out.append(Successor("call_common", fstem, callee.command_for_entry(entry), prim))
    if falls_through and index + 1 < len(sf.commands):
        out.append(Successor("next", sf.stem, index + 1, None))
    return out


def ends_procedure(cmd: Command) -> str | None:
    """'end' / 'return' if this command stops its context or returns from a Call."""
    for op in cmd.ops:
        if op == OP_RETURN:
            return "return"
        if op in (OP_END, OP_RETURN_COMMON):
            return "end"
    return None


def walk(sf: ScriptFile, start: int) -> list[Command]:
    """Commands reachable from `start` without leaving the file through returns (calls followed)."""
    seen: set[tuple[str, int]] = set()
    stack = [(sf.stem, start)]
    out = []
    while stack:
        stem, i = stack.pop()
        if (stem, i) in seen:
            continue
        seen.add((stem, i))
        f = load_script_file(stem)
        if i >= len(f.commands):
            continue
        out.append(f.commands[i])
        for s in successors(f, i):
            stack.append((s.file, s.index))
    return out


def find_label(stem: str, label: str) -> Command:
    sf = load_script_file(stem)
    return sf.commands[sf.labels[label]]
