"""Run-data models for one team (T027): Build, MoveChoice, TeamCandidate, Violation.

Fields follow specs/001-champion-team-optimizer/data-model.md ("Run data") exactly.

Scope of these classes: *schema* only. `__post_init__` rejects malformed records (unknown enum
values, missing stat keys, wrong types) so a bad JSON file fails loudly at load time. It does NOT
check game legality (IV 15 / EV 85, learnable moves, item copies, 6 members, level gap ...): that
is the independent validator's job (T029, Constitution III), and the validator's illegal fixtures
(e.g. IV 31) must still load into these classes.

Showdown text (team.txt, constitution "Interface"): `export_team` / `import_team` use the export
format of pokemon-showdown/sim/TEAMS.md ("Export format") as parsed by
`Teams.parseExportedTeamLine` (pokemon-showdown/sim/teams.ts:458). That format carries only the
battle-relevant part of a Build (species, item, ability, level, EVs, IVs, nature, moves), so the
round trip is defined on `ShowdownSet`:

    import_team(export_team(team)) == [b.showdown_set() for b in team.builds]

Provenance (source, ability_reason, MoveChoice sources, resource_use) lives in the JSON report.

Names: Builds hold keys (species / move / item / ability keys of data/generated). Export takes an
optional `name_of(kind, key) -> display name` and import an optional `key_of(kind, name) -> key`
(kind is "species" | "move" | "item" | "ability" | "nature"); both default to identity. Whoever
writes team.txt for users (T066) should pass the generated-data display names.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

# Stat order and export labels follow Showdown (pokemon-showdown/sim/teams.ts export/import).
STAT_KEYS: tuple[str, ...] = ("hp", "atk", "def", "spa", "spd", "spe")
_STAT_LABEL = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}
_LABEL_STAT = {v.lower(): k for k, v in _STAT_LABEL.items()}

# FR-008 defaults (spec.md FR-008): IV 15, EV 85 per stat, neutral nature. "Hardy" is the
# neutral nature data-model.md names for Build.nature.
DEFAULT_IV = 15
DEFAULT_EV = 85
DEFAULT_NATURE = "Hardy"

SOURCE_KINDS = frozenset(
    {"level_up", "pre_evo_level_up", "tm", "hm", "tutor", "egg", "relearner"}
)
ABILITY_REASONS = frozenset(
    {"tested_better", "tie_default", "other_no_battle_effect", "single_ability", "fixed_by_trade"}
)

Stats = dict[str, int]
NameFn = Callable[[str, str], str]


def _identity(_kind: str, value: str) -> str:
    return value


def default_ivs() -> Stats:
    return {k: DEFAULT_IV for k in STAT_KEYS}


def default_evs() -> Stats:
    return {k: DEFAULT_EV for k in STAT_KEYS}


def _check_stats(name: str, stats: Any) -> Stats:
    if not isinstance(stats, dict) or set(stats) != set(STAT_KEYS):
        raise ValueError(f"{name} must have exactly the keys {STAT_KEYS}, got {stats!r}")
    for k, v in stats.items():
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError(f"{name}.{k} must be an int, got {v!r}")
    return {k: stats[k] for k in STAT_KEYS}


@dataclass(frozen=True)
class Violation:
    """One legality failure. `src` lists the "path:line" decomp refs behind the rule."""

    code: str
    message: str
    src: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "src": list(self.src)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Violation:
        return cls(code=d["code"], message=d["message"], src=list(d.get("src", [])))


@dataclass
class MoveChoice:
    move: str
    source_kind: str
    detail: str
    availability_ref: str | None = None

    def __post_init__(self) -> None:
        if self.source_kind not in SOURCE_KINDS:
            raise ValueError(f"unknown source_kind {self.source_kind!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MoveChoice:
        return cls(
            move=d["move"],
            source_kind=d["source_kind"],
            detail=d["detail"],
            availability_ref=d.get("availability_ref"),
        )


@dataclass(frozen=True)
class ShowdownSet:
    """The battle-relevant view of a Build, i.e. what Showdown export text can carry."""

    species: str
    level: int
    ability: str
    item: str | None
    nature: str
    ivs: tuple[tuple[str, int], ...]
    evs: tuple[tuple[str, int], ...]
    moves: tuple[str, ...]


@dataclass
class Build:
    species: str
    source: str
    start_level: int
    moves: list[MoveChoice]
    ability: str
    ability_reason: str
    held_item: str | None = None
    nature: str = DEFAULT_NATURE
    ivs: Stats = field(default_factory=default_ivs)
    evs: Stats = field(default_factory=default_evs)

    def __post_init__(self) -> None:
        if self.ability_reason not in ABILITY_REASONS:
            raise ValueError(f"unknown ability_reason {self.ability_reason!r}")
        if not isinstance(self.start_level, int) or isinstance(self.start_level, bool):
            raise ValueError(f"start_level must be an int, got {self.start_level!r}")
        if not all(isinstance(m, MoveChoice) for m in self.moves):
            raise ValueError("moves must be MoveChoice instances")
        self.ivs = _check_stats("ivs", self.ivs)
        self.evs = _check_stats("evs", self.evs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "source": self.source,
            "start_level": self.start_level,
            "moves": [m.to_dict() for m in self.moves],
            "ability": self.ability,
            "ability_reason": self.ability_reason,
            "held_item": self.held_item,
            "nature": self.nature,
            "ivs": dict(self.ivs),
            "evs": dict(self.evs),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Build:
        return cls(
            species=d["species"],
            source=d["source"],
            start_level=d["start_level"],
            moves=[MoveChoice.from_dict(m) for m in d["moves"]],
            ability=d["ability"],
            ability_reason=d["ability_reason"],
            held_item=d.get("held_item"),
            nature=d.get("nature", DEFAULT_NATURE),
            ivs=d["ivs"] if "ivs" in d else default_ivs(),
            evs=d["evs"] if "evs" in d else default_evs(),
        )

    def showdown_set(self) -> ShowdownSet:
        return ShowdownSet(
            species=self.species,
            level=self.start_level,
            ability=self.ability,
            item=self.held_item,
            nature=self.nature,
            ivs=tuple((k, self.ivs[k]) for k in STAT_KEYS),
            evs=tuple((k, self.evs[k]) for k in STAT_KEYS),
            moves=tuple(m.move for m in self.moves),
        )


@dataclass
class TeamCandidate:
    builds: list[Build]
    resource_use: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all(isinstance(b, Build) for b in self.builds):
            raise ValueError("builds must be Build instances")

    def to_dict(self) -> dict[str, Any]:
        return {
            "builds": [b.to_dict() for b in self.builds],
            "resource_use": dict(self.resource_use),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TeamCandidate:
        return cls(
            builds=[Build.from_dict(b) for b in d["builds"]],
            resource_use=dict(d.get("resource_use", {})),
        )

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), **kwargs)

    @classmethod
    def from_json(cls, text: str) -> TeamCandidate:
        return cls.from_dict(json.loads(text))


# --- Showdown export format -------------------------------------------------------------------


def _stat_line(label: str, stats: Stats) -> str:
    # Always written in full (Showdown omits IV 31 / EV 0, but ours are 15 / 85; explicit is safer).
    return f"{label}: " + " / ".join(f"{stats[k]} {_STAT_LABEL[k]}" for k in STAT_KEYS)


def export_build(build: Build, name_of: NameFn = _identity) -> str:
    head = name_of("species", build.species)
    if build.held_item:
        head += f" @ {name_of('item', build.held_item)}"
    lines = [
        head,
        f"Ability: {name_of('ability', build.ability)}",
        f"Level: {build.start_level}",
        _stat_line("EVs", build.evs),
        f"{name_of('nature', build.nature)} Nature",
        _stat_line("IVs", build.ivs),
    ]
    lines += [f"- {name_of('move', m.move)}" for m in build.moves]
    return "\n".join(lines)


def export_team(team: TeamCandidate, name_of: NameFn = _identity) -> str:
    return "\n\n".join(export_build(b, name_of) for b in team.builds) + "\n"


def _parse_stats(text: str, fill: int) -> Stats:
    stats = {k: fill for k in STAT_KEYS}
    for part in text.split("/"):
        value, _, label = part.strip().partition(" ")
        stat = _LABEL_STAT.get(label.strip().lower())
        if stat is None:
            raise ValueError(f"unknown stat label in {part!r}")
        stats[stat] = int(value)
    return stats


def import_team(text: str, key_of: NameFn = _identity) -> list[ShowdownSet]:
    """Parse Showdown export text. Missing lines take Showdown's defaults (level 100, IV 31,
    EV 0), as `Teams.import` does; a missing ability or nature becomes ''. Unknown lines raise."""
    sets: list[ShowdownSet] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        name, _, item = lines[0].partition(" @ ")
        for suffix in (" (M)", " (F)"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        if name.endswith(")") and "(" in name:  # "Nickname (Species)"
            name = name[:-1].split("(", 1)[1]
        level, ability, nature, moves = 100, "", "", []
        ivs = {k: 31 for k in STAT_KEYS}
        evs = {k: 0 for k in STAT_KEYS}
        for line in lines[1:]:
            if line.startswith("Ability: "):
                ability = key_of("ability", line[9:].strip())
            elif line.startswith("Level: "):
                level = int(line[7:])
            elif line.startswith("EVs: "):
                evs = _parse_stats(line[5:], 0)
            elif line.startswith("IVs: "):
                ivs = _parse_stats(line[5:], 31)
            elif line.lower().endswith(" nature"):
                nature = key_of("nature", line[: -len(" nature")].strip())
            elif line.startswith(("-", "~")):
                moves.append(key_of("move", line[1:].strip()))
            else:
                raise ValueError(f"unrecognised line in Showdown export: {line!r}")
        sets.append(
            ShowdownSet(
                species=key_of("species", name.strip()),
                level=level,
                ability=ability,
                item=key_of("item", item.strip()) if item.strip() else None,
                nature=nature,
                ivs=tuple((k, ivs[k]) for k in STAT_KEYS),
                evs=tuple((k, evs[k]) for k in STAT_KEYS),
                moves=tuple(moves),
            )
        )
    return sets
