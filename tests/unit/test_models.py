"""T027: run-data models, JSON round trip and Showdown export/import.

No game facts are needed: species/move/item/ability keys below are synthetic placeholders
("species_a", "move_a1", ...), so nothing here claims a value from the decomp.
"""

import json
import subprocess

import pytest

from platsim.legality.models import (
    DEFAULT_EV,
    DEFAULT_IV,
    DEFAULT_NATURE,
    STAT_KEYS,
    Build,
    MoveChoice,
    ShowdownSet,
    TeamCandidate,
    Violation,
    export_team,
    import_team,
)
from platsim.pins import REPO_ROOT


def _build(i: int, item: str | None = "item_x", nmoves: int = 4) -> Build:
    return Build(
        species=f"species_{i}",
        source=f"avail:wild_slot:map_{i}",
        start_level=40 + i,
        moves=[
            MoveChoice(f"move_{i}_{j}", "level_up", f"Lv {10 + j}", None) for j in range(nmoves)
        ],
        ability=f"ability_{i}",
        ability_reason="single_ability",
        held_item=item,
    )


def _team() -> TeamCandidate:
    builds = [_build(i, item=None if i == 3 else f"item_{i}", nmoves=1 + i % 4) for i in range(6)]
    builds[2].moves[0] = MoveChoice("move_tm", "tm", "TM99 – shop (unlimited)", "avail:shop:7")
    builds[5].ivs = {"hp": 31, "atk": 0, "def": 7, "spa": 15, "spd": 22, "spe": 30}
    builds[5].nature = "Adamant"
    builds[5].ability_reason = "fixed_by_trade"
    return TeamCandidate(builds=builds, resource_use={"tm99": 1, "item_1": 1})


def test_defaults_follow_fr008():
    b = _build(0)
    assert b.ivs == {k: 15 for k in STAT_KEYS} and DEFAULT_IV == 15
    assert b.evs == {k: 85 for k in STAT_KEYS} and DEFAULT_EV == 85
    assert sum(b.evs.values()) == 510
    assert b.nature == DEFAULT_NATURE == "Hardy"


def test_json_round_trip():
    team = _team()
    text = team.to_json()
    again = TeamCandidate.from_json(text)
    assert again == team
    assert again.to_json() == text
    # Plain JSON, keys exactly as data-model.md
    d = json.loads(text)
    assert set(d) == {"builds", "resource_use"}
    assert set(d["builds"][0]) == {
        "species", "source", "start_level", "moves", "ability", "ability_reason",
        "held_item", "nature", "ivs", "evs",
    }
    assert set(d["builds"][0]["moves"][0]) == {"move", "source_kind", "detail", "availability_ref"}


def test_violation_round_trip():
    v = Violation("TM_COPIES", "two members use a single-copy TM", ["include/x.h:12"])
    assert Violation.from_dict(json.loads(json.dumps(v.to_dict()))) == v
    assert Violation("X", "y").src == []


def test_schema_errors_fail_loudly():
    with pytest.raises(ValueError, match="source_kind"):
        MoveChoice("m", "trade", "x")
    with pytest.raises(ValueError, match="ability_reason"):
        Build("s", "src", 5, [], "a", "because")
    with pytest.raises(ValueError, match="ivs"):
        Build("s", "src", 5, [], "a", "single_ability", ivs={"hp": 15})
    # Out-of-range but well-formed values load: legality is the validator's job (T029).
    b = Build("s", "src", 5, [], "a", "single_ability", ivs={k: 31 for k in STAT_KEYS})
    assert b.ivs["hp"] == 31


def test_export_text_shape():
    text = export_team(_team())
    first = text.split("\n\n")[0].splitlines()
    assert first == [
        "species_0 @ item_0",
        "Ability: ability_0",
        "Level: 40",
        "EVs: 85 HP / 85 Atk / 85 Def / 85 SpA / 85 SpD / 85 Spe",
        "Hardy Nature",
        "IVs: 15 HP / 15 Atk / 15 Def / 15 SpA / 15 SpD / 15 Spe",
        "- move_0_0",
    ]
    assert "species_3\n" in text  # no item -> no " @ "


def test_export_import_round_trip():
    team = _team()
    assert import_team(export_team(team)) == [b.showdown_set() for b in team.builds]


def test_export_import_with_name_mapping():
    team = _team()
    name_of = lambda kind, key: f"{kind.upper()}:{key.replace('_', ' ')}"  # noqa: E731
    key_of = lambda kind, name: name.split(":", 1)[1].replace(" ", "_")  # noqa: E731
    text = export_team(team, name_of)
    assert "SPECIES:species 0 @ ITEM:item 0" in text
    assert "NATURE:Hardy Nature" in text
    assert import_team(text, key_of) == [b.showdown_set() for b in team.builds]


def test_import_applies_showdown_defaults_and_rejects_junk():
    (s,) = import_team("Foo (Bar) (M) @ Baz\n- Tackle\n")
    assert s == ShowdownSet(
        species="Bar", level=100, ability="", item="Baz", nature="",
        ivs=tuple((k, 31) for k in STAT_KEYS), evs=tuple((k, 0) for k in STAT_KEYS),
        moves=("Tackle",),
    )
    with pytest.raises(ValueError, match="unrecognised"):
        import_team("Foo\nShiny: Maybe\n")


def test_showdown_own_parser_reads_our_export():
    """Cross-check against Showdown's Teams.import (pokemon-showdown/sim/teams.ts:556)."""
    team = _team()
    script = (
        "import { Teams } from './sim/showdown.mjs';"
        "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>"
        "console.log(JSON.stringify(Teams.import(s))));"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=export_team(team), capture_output=True, text=True, cwd=REPO_ROOT, check=False,
    )
    assert out.returncode == 0, out.stderr
    sets = json.loads(out.stdout)
    assert len(sets) == 6
    for ps, b in zip(sets, team.builds, strict=True):
        assert ps["level"] == b.start_level
        assert ps["ability"] == b.ability
        assert ps["item"] == (b.held_item or "")
        assert ps["nature"] == b.nature
        assert ps["ivs"] == b.ivs and ps["evs"] == b.evs
        assert ps["moves"] == [m.move for m in b.moves]
