"""Ability choice per member (T060; spec FR-008c; research.md R8 "Policy per stage": ability screening
uses `greedy-v1` against the decomp trainer AI; run count = the budget preset's `ability_screen`).

1. Battle-effect classification (generated data: data/generated/abilities_battle.json, `platsim extract`)
--------------------------------------------------------------------------------------------------
An ability HAS a battle effect iff its `ABILITY_*` constant appears in code (comments stripped) of the
battle ENGINE, which in the decomp is:

  - C: `src/battle/**/*.c|.h` EXCEPT `src/battle/trainer_ai/**`; `include/battle/**/*.h`;
    `include/constants/battle/**/*.h`;
  - battle scripts: `res/battle/scripts/**/*.s` (effect scripts and subscripts). Several abilities are
    implemented ONLY there (e.g. Rock Head, Leaf Guard, Reckless; `CheckAbility` commands), so a
    C-only scan would wrongly call them "no battle effect" (validation-log lesson: mechanics also live
    in battle scripts).

Excluded on purpose:
  - `src/battle/trainer_ai/**` (AI script + interpreter): the opponent AI *reading* an ability changes
    the AI's choices, not what the ability does. (ABILITY_STENCH is referenced only there and in the
    overworld encounter code, so it is the control for this exclusion.)
  - everything else in `src/` (overworld encounter rates, daycare, Battle Arcade, summary screens,
    easy-chat words, string tables): effects outside battle.

Raw numbers: no battle script passes an ability as a number (`CheckAbility`/`CheckIgnorableAbility`
and `CompareMonDataToValue ... BATTLEMON_ABILITY, <x>` all use names) and no battle C file compares an
ability to an integer literal; `raw_number_scan` re-checks this at extract time and stores the result
so a decomp change that introduces raw numbers fails loudly (see `battle_effect_table`).

The rule is conservative: any reference in battle code counts, even where the effect cannot matter in
the Champion gauntlet (e.g. Run Away: fleeing only; Pickup/Honey Gather: item generated after a WON
battle, `BtlCmd_GenerateEndOfBattleItem`, run from subscript_battle_won.s). Those are screened by
battle test like any other ability; a test that finds no difference keeps slot 1 (tie_default).

2. choose_ability(pool, team_builds, slot, *, seed, budget) -> AbilityChoice(ability, reason, stats)
--------------------------------------------------------------------------------------------------
In order (reason codes = data-model Build.ability_reason):
  - species has one distinct ability                            -> single_ability (no runs)
  - source is an NPC trade: personality fixes the slot          -> fixed_by_trade (no runs)
      (odd personality -> slot 2, availability/sources.py npc_trade_fixed_mon; same rule the validator uses)
  - one ability has no battle effect                            -> the other one, other_no_battle_effect
    (neither has one: slot 1, other_no_battle_effect)           (no runs)
  - else: N = preset.ability_screen paired gauntlets per ability (same seeds i = 0..N-1 for both),
    player `greedy-v1`, opponent `decomp-ai`, stop_on_loss; McNemar exact (stats.mcnemar_exact, alpha
    0.05) on "cleared". Significant -> the winner, tested_better; otherwise slot 1, tie_default.
Seeds: run i of the screen for member `slot` uses derive_seed(f"{seed}|ability-screen|slot{slot}", i, 0);
the worker derives battle b's seed from it. Same inputs -> same seeds -> same result.
"""

from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from functools import cache
from pathlib import Path
from typing import Any, NamedTuple

from platsim.pins import DECOMP_COMMIT, DECOMP_ROOT

SCREEN_PLAYER_POLICY = "greedy-v1"  # research.md R8 "Policy per stage"
OPPONENT_POLICY = "decomp-ai"  # FR-010
ALPHA = 0.05

# --- 1. classification ------------------------------------------------------------------------------

# (glob relative to DECOMP_ROOT, kind) -- the battle engine.
BATTLE_SCOPE: tuple[tuple[str, str], ...] = (
    ("src/battle/**/*.c", "c"),
    ("src/battle/**/*.h", "c"),
    ("include/battle/**/*.h", "c"),
    ("include/constants/battle/**/*.h", "c"),
    ("res/battle/scripts/**/*.s", "script"),
)
EXCLUDED_FROM_BATTLE = ("src/battle/trainer_ai/",)  # opponent AI reads abilities; not an ability effect
# Everything else that is searched (for the `other_refs` record only).
OTHER_SCOPE: tuple[tuple[str, str], ...] = (
    ("src/**/*.c", "c"),
    ("src/**/*.s", "script"),  # src/battle/trainer_ai/script.s
    ("include/**/*.h", "c"),
)

RULE = ("has_battle_effect iff the ABILITY_* constant appears (comments stripped) in the battle engine: "
        "src/battle/**/*.{c,h} except src/battle/trainer_ai/**, include/battle/**/*.h, "
        "include/constants/battle/**/*.h, res/battle/scripts/**/*.s. Trainer-AI references (opponent "
        "decision-making) and all other src/ references (overworld, daycare, menus, Battle Arcade) do not "
        "count. Conservative: any engine reference counts, even if the effect cannot occur in a trainer "
        "battle (e.g. fleeing).")

_TOKEN = re.compile(r"\bABILITY_[A-Z0-9_]+\b")
# Raw-number checks (must stay empty). Positive controls for the same shapes live in the tests.
_RAW_SCRIPT = re.compile(r"^\s*(?:CheckAbility|CheckIgnorableAbility)\b[^/]*,\s*(-?\d|0x)", re.M)
_RAW_SCRIPT_MONDATA = re.compile(r"BATTLEMON_ABILITY,\s*(-?\d|0x)")
_RAW_C = re.compile(r"[aA]bility\w*(?:\[[^\]]*\])?(?:\.\w+|->\w+)*\s*[!=]=\s*(\d|0x)")
_FUNC_DEF = re.compile(r"^(?:static\s+|inline\s+)*[A-Za-z_][\w\s\*]*?\b(\w+)\s*\([^;]*$")


def _rel(p: Path) -> str:
    return str(p.relative_to(DECOMP_ROOT))


def strip_comments(text: str, kind: str) -> list[str]:
    """Lines of `text` with comments blanked (line count kept, so refs keep their line numbers).
    C: `//` and `/* */`. Battle scripts (preprocessed by cpp): the same."""
    out: list[str] = []
    in_block = False
    for line in text.splitlines():
        res = []
        i = 0
        while i < len(line):
            if in_block:
                j = line.find("*/", i)
                if j < 0:
                    i = len(line)
                else:
                    in_block = False
                    i = j + 2
                continue
            if line.startswith("//", i):
                break
            if line.startswith("/*", i):
                in_block = True
                i += 2
                continue
            if line[i] == '"':  # string literal: copy through
                j = i + 1
                while j < len(line) and line[j] != '"':
                    j += 2 if line[j] == "\\" else 1
                res.append(line[i:j + 1])
                i = j + 1
                continue
            res.append(line[i])
            i += 1
        out.append("".join(res))
    return out


def _context(lines: list[str], idx: int, kind: str, path: Path) -> str:
    """Enclosing C function (nearest preceding definition at column 0) or the script file stem."""
    if kind == "script":
        return path.stem
    for j in range(idx, -1, -1):
        m = _FUNC_DEF.match(lines[j])
        if m and not lines[j].startswith((" ", "\t", "#")):
            return m.group(1)
    return "<file scope>"


def _files(scope) -> list[tuple[Path, str]]:
    seen: dict[Path, str] = {}
    for pattern, kind in scope:
        for p in sorted(DECOMP_ROOT.glob(pattern)):
            if p.is_file():
                seen.setdefault(p, kind)
    return sorted(seen.items())


def _is_battle(path: Path) -> bool:
    rel = _rel(path)
    if any(rel.startswith(x) for x in EXCLUDED_FROM_BATTLE):
        return False
    return rel.startswith(_BATTLE_DIRS) and path.suffix in (".c", ".h", ".s")


_BATTLE_DIRS = tuple(p.split("**")[0] for p, _ in BATTLE_SCOPE)


def scan_refs(names: frozenset[str]) -> tuple[dict[str, list[dict]], dict[str, list[str]], list[str]]:
    """(battle refs per name [{ref, context}], other refs per name [path:line], raw-number hits)."""
    battle: dict[str, list[dict]] = {n: [] for n in names}
    other: dict[str, list[str]] = {n: [] for n in names}
    raw: list[str] = []
    files = dict(_files(BATTLE_SCOPE))
    for p, k in _files(OTHER_SCOPE):
        files.setdefault(p, k)
    for path, kind in sorted(files.items()):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "ABILITY_" not in text and "bility" not in text:
            continue
        lines = strip_comments(text, kind)
        in_battle = _is_battle(path)
        rel = _rel(path)
        for i, line in enumerate(lines):
            for tok in _TOKEN.findall(line):
                if tok not in names:
                    continue  # e.g. TAG_NICKNAME_ABILITY, MON_DATA_ABILITY_RIBBON: not ability constants
                if in_battle:
                    battle[tok].append({"ref": f"{rel}:{i + 1}", "context": _context(lines, i, kind, path)})
                else:
                    other[tok].append(f"{rel}:{i + 1}")
            if in_battle:
                rx = (_RAW_SCRIPT, _RAW_SCRIPT_MONDATA) if kind == "script" else (_RAW_C,)
                if any(r.search(line) for r in rx):
                    raw.append(f"{rel}:{i + 1}: {line.strip()}")
    return battle, other, raw


@cache
def battle_effect_table() -> dict[str, Any]:
    """The generated table (data/generated/abilities_battle.json). ABILITY_NONE is not an ability."""
    from platsim.decomp.constants import load_enum

    enum = load_enum("abilities")
    names = frozenset(n for n in enum.values if n != "ABILITY_NONE")
    battle, other, raw = scan_refs(names)
    abilities = {}
    for n in sorted(names, key=lambda x: enum.values[x]):
        refs = battle[n]
        abilities[n] = {
            "id": enum.values[n],
            "src": str(enum.refs[n]),
            "has_battle_effect": bool(refs),
            "battle_refs": [r["ref"] for r in refs],
            "battle_contexts": sorted({r["context"] for r in refs}),
            "other_refs": other[n],  # AI + outside-battle references (do not count)
        }
    if raw:  # the name-only scan would miss these; refuse to produce a table that may be wrong
        raise RuntimeError("raw-number ability comparisons found in battle code; extend the scan:\n" + "\n".join(raw))
    n_eff = sum(a["has_battle_effect"] for a in abilities.values())
    return {
        "decomp_commit": DECOMP_COMMIT,
        "rule": RULE,
        "battle_scope": [p for p, _ in BATTLE_SCOPE],
        "excluded_from_battle": list(EXCLUDED_FROM_BATTLE),
        "raw_number_scan": {"script_patterns": [_RAW_SCRIPT.pattern, _RAW_SCRIPT_MONDATA.pattern],
                            "c_pattern": _RAW_C.pattern, "hits": raw},
        "counts": {"abilities": len(abilities), "has_battle_effect": n_eff, "no_battle_effect": len(abilities) - n_eff},
        "abilities": abilities,
    }


def has_battle_effect(ability: str) -> bool:
    t = battle_effect_table()["abilities"]
    if ability not in t:
        raise KeyError(f"unknown ability {ability!r}")
    return t[ability]["has_battle_effect"]


# --- 2. screening -----------------------------------------------------------------------------------


class AbilityChoice(NamedTuple):
    ability: str
    reason: str  # data-model Build.ability_reason
    stats: dict | None  # None when no runs were spent


def _as_dict(b) -> dict:
    if isinstance(b, dict):
        return dict(b)
    if hasattr(b, "to_dict"):
        return b.to_dict()
    if is_dataclass(b):
        return asdict(b)
    raise TypeError(f"unsupported build type {type(b).__name__}")


def _species(build: dict):
    from platsim.decomp.species import by_constant, load_species

    s = str(build["species"])
    sp = load_species().get(s) or by_constant().get(s) or by_constant().get(f"SPECIES_{s.upper()}")
    if sp is None:
        raise KeyError(f"unknown species {s!r}")
    return sp


def _trade_fixed_mon(build: dict, ledger) -> dict | None:
    """The NPC-trade FixedMon of this build's source, or None. Source ids are '<kind>:<species>@<map>'
    (legality/movesources.py), so only 'npc_trade:' sources need the (slow) availability ledger."""
    src = str(build.get("source") or "")
    if not src.startswith("npc_trade:"):
        return None
    from platsim.legality import movesources as MS

    if ledger is None:
        from platsim.availability.ledger import build_ledger

        ledger = build_ledger()
    const = f"SPECIES_{_species(build).key.upper()}"
    opt = next((o for o in MS.source_options(const, ledger) if o.id == src), None)
    if opt is None:
        raise ValueError(f"source {src!r} is not a legal option for {const}")
    return opt.fixed_mon


def _worker_team(builds: list[dict], ledger) -> list[dict]:
    out = []
    for b in builds:
        d = dict(b)
        if "is_traded" not in d:
            fixed = _trade_fixed_mon(d, ledger)
            d["is_traded"] = bool(fixed and fixed.get("is_traded"))
        out.append(d)
    return out


def screen_master(seed: str, slot: int) -> str:
    return f"{seed}|ability-screen|slot{slot}"


def choose_ability(pool, team_builds, slot: int, *, seed: str, budget: str = "standard",
                   runs: int | None = None, ledger=None, alpha: float = ALPHA) -> AbilityChoice:
    """Pick the ability of team_builds[slot] (FR-008c). `pool` (sim.pool.WorkerPool) is used only when
    both abilities have a battle effect. `runs` overrides the preset's ability_screen count (tests)."""
    from platsim.budget import get_preset
    from platsim.sim.seeds import SCHEME, derive_seed
    from platsim.stats import mcnemar_exact

    builds = [_as_dict(b) for b in team_builds]
    me = builds[slot]
    sp = _species(me)
    a1, a2 = sp.abilities[0], sp.abilities[1]
    if a2 is None or a2 == a1:
        return AbilityChoice(a1, "single_ability", None)

    fixed = _trade_fixed_mon(me, ledger)
    if fixed is not None:
        s = fixed["ability_slot"]
        return AbilityChoice(sp.abilities[s - 1] or a1, "fixed_by_trade",
                             {"ability_slot": s, "personality": fixed["personality"], "src": list(fixed["src"])})

    e1, e2 = has_battle_effect(a1), has_battle_effect(a2)
    if not (e1 and e2):
        pick = a2 if (e2 and not e1) else a1
        tab = battle_effect_table()["abilities"]
        return AbilityChoice(pick, "other_no_battle_effect", {
            "battle_effect": {a1: e1, a2: e2},
            "battle_refs": {a: tab[a]["battle_refs"][:5] for a in (a1, a2)},
            "rule": RULE,
        })

    if pool is None:
        raise ValueError("both abilities have a battle effect: a WorkerPool is needed for the screen")
    n = runs if runs is not None else get_preset(budget).ability_screen
    if n < 1:
        raise ValueError(f"runs must be >= 1, got {n}")
    master = screen_master(str(seed), slot)
    seeds = [derive_seed(master, i, 0) for i in range(n)]
    hello = getattr(pool, "hello", None) or {}
    for need, key in ((SCREEN_PLAYER_POLICY, "policies"), (OPPONENT_POLICY, "opponent_policies")):
        if key in hello and need not in hello[key]:
            raise RuntimeError(f"worker does not offer {need!r} ({key}: {hello[key]})")

    outcomes: dict[str, list[bool]] = {}
    for ab in (a1, a2):
        team = [dict(b) for b in builds]
        team[slot]["ability"] = ab
        team = _worker_team(team, ledger)
        reqs = [{"op": "gauntlet", "team": team, "seed": s, "player_policy": SCREEN_PLAYER_POLICY,
                 "opponent_policy": OPPONENT_POLICY, "stop_on_loss": True, "log": "none"} for s in seeds]
        res = pool.map(reqs)
        for r in res:
            if not r.get("ok"):
                raise RuntimeError(f"ability screen gauntlet failed: {r.get('error')}")
            if (r.get("player_policy"), r.get("opponent_policy")) != (SCREEN_PLAYER_POLICY, OPPONENT_POLICY):
                raise RuntimeError(f"worker ran {r.get('player_policy')}/{r.get('opponent_policy')}")
        outcomes[ab] = [bool(r["cleared"]) for r in res]

    cmp = mcnemar_exact(outcomes[a1], outcomes[a2], alpha=alpha)
    if cmp.verdict == "A":
        choice, reason = a1, "tested_better"
    elif cmp.verdict == "B":
        choice, reason = a2, "tested_better"
    else:
        choice, reason = a1, "tie_default"
    stats = {
        "abilities": [a1, a2],
        "n_paired": cmp.n,
        "clear_rate": {a1: cmp.a_rate, a2: cmp.b_rate},
        "only_cleared_by": {a1: cmp.a_only, a2: cmp.b_only},
        "p_value": cmp.p_value,
        "alpha": cmp.alpha,
        "test": "McNemar exact (two-sided)",
        "verdict": {"A": a1, "B": a2}.get(cmp.verdict, "indistinguishable"),
        "player_policy": SCREEN_PLAYER_POLICY,
        "opponent_policy": OPPONENT_POLICY,
        "budget": budget,
        "seeds": {"master": master, "scheme": SCHEME, "request_seed": "derive_seed(master, i, 0), i < n_paired"},
        "decomp_commit": hello.get("decomp_commit"),
        "showdown_commit": hello.get("showdown_commit"),
    }
    return AbilityChoice(choice, reason, stats)


__all__ = ["AbilityChoice", "RULE", "battle_effect_table", "choose_ability", "has_battle_effect", "scan_refs",
           "screen_master", "strip_comments"]
