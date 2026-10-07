"""`platsim extract` (T019): run every decomp reader and write data/generated/*.json.

Outputs (one file per table, plus manifest.json):
    species.json   {"decomp_commit", "species": {key: Species}}       (platsim.decomp.species)
    moves.json     {"decomp_commit", "moves": {key: Move}}            (platsim.decomp.moves)
    items.json     {"decomp_commit", "items": {key: Item}}            (platsim.decomp.items)
    tutors.json    {"decomp_commit", "tutors": [Tutor, ...]}          (platsim.decomp.tutors)
    trainers.json  {"decomp_commit", "trainers": [OpponentTrainer]}   (platsim.decomp.trainers, gauntlet order)
    exp.json       {"decomp_commit", "max_level", "tables": {EXP_RATE_*: [exp at level 0..max]}, "src"}
    constants.json {"decomp_commit", "gender_ratios", "natures", "abilities", "nature_affinities", "src"}
    manifest.json  {"decomp_commit", "showdown_commit", "files": {name: sha256}}

Determinism: every file is `json.dumps(..., sort_keys=True, indent=1)` + "\n", lists keep the
reader's order (which follows decomp file order), so two runs give identical bytes.

Pluggable outputs: OUTPUTS maps file stem -> zero-arg builder returning a JSON-able object.
T024 adds `availability` with `register_output("availability", builder)` (or by adding it to
OUTPUTS below); nothing else changes. Generated data must not be hand-edited (constitution).
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from platsim.pins import DECOMP_COMMIT, REPO_ROOT, SHOWDOWN_COMMIT, check_pins

DEFAULT_OUT = REPO_ROOT / "data" / "generated"
MANIFEST = "manifest.json"

Builder = Callable[[], Any]


def _keyed(records: dict[str, Any], what: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rec in records.values():
        if rec.key in out:
            raise ValueError(f"{what}: duplicate key {rec.key!r}")
        out[rec.key] = rec.to_json()
    return out


def _species() -> dict[str, Any]:
    from platsim.decomp.species import load_species

    return {"decomp_commit": DECOMP_COMMIT, "species": _keyed(load_species(), "species")}


def _moves() -> dict[str, Any]:
    from platsim.decomp.moves import load_moves

    return {"decomp_commit": DECOMP_COMMIT, "moves": _keyed(load_moves(), "moves")}


def _items() -> dict[str, Any]:
    from platsim.decomp.items import load_items

    return {"decomp_commit": DECOMP_COMMIT, "items": _keyed(load_items(), "items")}


def _tutors() -> dict[str, Any]:
    from platsim.decomp.tutors import load_tutors

    return {"decomp_commit": DECOMP_COMMIT, "tutors": [t.to_json() for t in load_tutors()]}


def _trainers() -> dict[str, Any]:
    from platsim.decomp.trainers import load_league

    return {"decomp_commit": DECOMP_COMMIT, "trainers": [t.to_json() for t in load_league()]}


def _exp() -> dict[str, Any]:
    from platsim.decomp.exp import load_exp_tables, max_level

    t = load_exp_tables()
    return {
        "decomp_commit": DECOMP_COMMIT,
        "max_level": max_level(),
        "tables": {rate: list(v) for rate, v in t.tables.items()},
        "src": list(t.src),
    }


def _constants() -> dict[str, Any]:
    """Enum values the Node game layer needs (gender from personality, natures for stats)."""
    from platsim.decomp.constants import load_enum
    from platsim.decomp.stats import POKEMON_C, nature_affinities
    from platsim.decomp._util import ref

    out: dict[str, Any] = {"decomp_commit": DECOMP_COMMIT, "src": {}}
    for name in ("gender_ratios", "natures", "abilities"):
        e = load_enum(name)
        out[name] = dict(e.values)
        out["src"][name] = str(e.refs[next(iter(e.values))])
    # {NATURE_*: {stat: +1/0/-1}} from sNatureStatAffinities (src/pokemon.c)
    out["nature_affinities"] = nature_affinities()
    out["src"]["nature_affinities"] = ref(POKEMON_C, "static const s8 sNatureStatAffinities[][5] = {")
    return out


OUTPUTS: dict[str, Builder] = {
    "constants": _constants,
    "species": _species,
    "moves": _moves,
    "items": _items,
    "tutors": _tutors,
    "trainers": _trainers,
    "exp": _exp,
}


def register_output(name: str, builder: Builder) -> None:
    """Add a generated table (e.g. T024's `availability`)."""
    if name == MANIFEST.removesuffix(".json"):
        raise ValueError("'manifest' is reserved")
    OUTPUTS[name] = builder


def dumps(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate() -> dict[str, bytes]:
    """All output files (name -> bytes), manifest last. Pure: writes nothing."""
    files = {f"{name}.json": dumps(builder()) for name, builder in sorted(OUTPUTS.items())}
    manifest = {
        "decomp_commit": DECOMP_COMMIT,
        "showdown_commit": SHOWDOWN_COMMIT,
        "generator": "platsim extract (src/platsim/extract.py)",
        "files": {name: sha256(data) for name, data in files.items()},
    }
    files[MANIFEST] = dumps(manifest)
    return files


def write(out_dir: Path = DEFAULT_OUT) -> dict[str, bytes]:
    check_pins()
    files = generate()
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        tmp = out_dir / f".{name}.partial"
        tmp.write_bytes(data)
        tmp.replace(out_dir / name)
    return files


def check(out_dir: Path = DEFAULT_OUT) -> list[str]:
    """Regenerate in memory; return a list of differences against out_dir (empty = up to date)."""
    check_pins()
    files = generate()
    problems = []
    for name, data in files.items():
        path = out_dir / name
        if not path.exists():
            problems.append(f"{path}: missing")
        elif path.read_bytes() != data:
            problems.append(f"{path}: differs (expected sha256 {sha256(data)}, got {sha256(path.read_bytes())})")
    for path in sorted(out_dir.glob("*.json")) if out_dir.exists() else []:
        if path.name not in files:
            problems.append(f"{path}: not produced by extract (stale or hand-made)")
    return problems


def main(check_only: bool = False, out_dir: Path = DEFAULT_OUT) -> int:
    if check_only:
        problems = check(out_dir)
        for p in problems:
            print(f"platsim extract --check: {p}", file=sys.stderr)
        if problems:
            return 1
        print(f"platsim extract --check: {out_dir} is up to date ({len(generate())} files)")
        return 0
    files = write(out_dir)
    for name, data in files.items():
        print(f"{out_dir / name}  {len(data)} bytes  sha256 {sha256(data)[:16]}")
    return 0
