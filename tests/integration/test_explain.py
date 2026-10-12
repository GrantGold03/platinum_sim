"""T074: `platsim explain` (User Story 3, quickstart V3/V4).

Expected game values are copied from the decomp files cited next to them (pokeplatinum @ pinned
commit). The CLI runs in-process (`platsim.cli.main`) so the availability ledger is built once per
test session; one test also runs the real console script as a subprocess (V3 command line).

Positive controls: every "excluded"/"post_game"/"unlimited" assertion is paired with a subject
that must show the opposite (a pre-Champion trade, a finite TM count), so an explain that printed
nothing, or the same thing for everything, fails.
"""

import json
import re
import subprocess

import pytest

from platsim.cli import main
from platsim.pins import REPO_ROOT

REF = re.compile(r"\[[^\]]*\S+:\d+[^\]]*\]$")  # line ends with [.., path:line, ..]


def run(capsys, *args: str) -> tuple[int, str, str]:
    rc = main(["explain", *args])
    out, err = capsys.readouterr()
    return rc, out, err


def run_json(capsys, subject: str) -> dict:
    rc, out, err = run(capsys, subject, "--json")
    assert rc == 0, err
    return json.loads(out)


@pytest.fixture(scope="module")
def ledger():
    from platsim.availability.ledger import build_ledger

    return build_ledger()


def content_lines(out: str) -> list[str]:
    """Lines that state a game fact. Section headers ('  party:') and the provenance line
    ('decomp: pokeplatinum @ <commit>') carry no path:line."""
    return [l for l in out.splitlines()
            if l.strip() and not l.rstrip().endswith(":") and not l.strip().startswith("decomp: pokeplatinum @")]


# ---------------------------------------------------------------------------------------------
# V3: trainer:cynthia


# res/trainers/data/champion_cynthia.json: species :18/:32/:46/:60/:74/:88, levels :20/:34/:48/:62/:76/:90,
# items :21/:35/:49/:63/:77/:91 (only Garchomp holds ITEM_SITRUS_BERRY, :91).
CYNTHIA_PARTY = [
    ("SPECIES_SPIRITOMB", 58, "ITEM_NONE"),
    ("SPECIES_ROSERADE", 58, "ITEM_NONE"),
    ("SPECIES_TOGEKISS", 60, "ITEM_NONE"),
    ("SPECIES_LUCARIO", 60, "ITEM_NONE"),
    ("SPECIES_MILOTIC", 58, "ITEM_NONE"),
    ("SPECIES_GARCHOMP", 62, "ITEM_SITRUS_BERRY"),
]
# champion_cynthia.json:93-96 Garchomp's moves
GARCHOMP_MOVES = ["MOVE_DRAGON_RUSH", "MOVE_EARTHQUAKE", "MOVE_FLAMETHROWER", "MOVE_GIGA_IMPACT"]
# champion_cynthia.json:5-8 (four ITEM_FULL_RESTORE), :11-13 (AI flags)
CYNTHIA_BAG = ["ITEM_FULL_RESTORE"] * 4
CYNTHIA_AI = ["AI_FLAG_BASIC", "AI_FLAG_EVAL_ATTACK", "AI_FLAG_EXPERT"]
CYN = "res/trainers/data/champion_cynthia.json"


def test_cynthia_v3(capsys):
    rc, out, err = run(capsys, "trainer:cynthia")
    assert rc == 0, err
    for sp, lvl, item in CYNTHIA_PARTY:
        line = next(l for l in out.splitlines() if l.strip().startswith(f"- {sp} "))
        assert f"Lv {lvl} @ {item}" in line
        assert CYN in line
    assert out.count("bag item: ITEM_FULL_RESTORE") == 4
    for i in range(4):
        assert f"{CYN}:{5 + i}" in out
    ai = next(l for l in out.splitlines() if "AI flags:" in l)
    assert all(f in ai for f in CYNTHIA_AI) and f"{CYN}:11" in ai and f"{CYN}:13" in ai
    for j, mv in enumerate(GARCHOMP_MOVES):
        assert f"move {mv}  [{CYN}:{93 + j}]" in out
    # computed nature/ability lines cite the BuildParty port and pokemon.c
    assert out.count("computed: personality") == 6 and out.count("computed: ability") == 6
    assert "src/trainer_data.c:" in out and "src/pokemon.c:" in out
    facts = content_lines(out)
    assert len(facts) >= 6 * 7  # control: the check covers every party line (6 mons x 7 lines)
    for l in facts:
        assert REF.search(l), f"line without a src ref: {l!r}"


def test_cynthia_json_matches_trainer_reader(capsys):
    from platsim.decomp.trainers import load_trainer

    d = run_json(capsys, "trainer:cynthia")
    t = load_trainer("TRAINER_CHAMPION_CYNTHIA")
    assert d["trainer"] == "TRAINER_CHAMPION_CYNTHIA"
    assert [(m["species"], m["level"], m["held_item"]) for m in d["party"]] == CYNTHIA_PARTY
    assert d["bag_items"] == CYNTHIA_BAG and d["ai_flags"] == CYNTHIA_AI
    assert [m["nature"] for m in d["party"]] == [m.nature for m in t.party]
    assert [m["ability"] for m in d["party"]] == [m.ability for m in t.party]
    assert all(m["refs"]["mon"].startswith(CYN) for m in d["party"])


def test_cli_subprocess_v3():
    """The real console script (quickstart V3 command line)."""
    p = subprocess.run(["uv", "run", "platsim", "explain", "trainer:cynthia"], cwd=REPO_ROOT,
                       capture_output=True, text=True, timeout=300, check=False)
    assert p.returncode == 0, p.stderr
    assert "SPECIES_GARCHOMP Lv 62 @ ITEM_SITRUS_BERRY" in p.stdout


# ---------------------------------------------------------------------------------------------
# V4: NPC trades


def _trade(d: dict, species: str) -> dict:
    return next(e for e in d["entries"] if e["kind"] == "npc_trade" and e["subject"] == species)


def test_abra_trade_pre_champion_v4(capsys):
    rc, out, err = run(capsys, "species:abra")
    assert rc == 0, err
    line = next(l for l in out.splitlines() if "npc_trade" in l)
    assert line.strip().startswith("- [pre_champion] npc_trade")
    assert "res/npc_trades/kazza_abra.json" in line
    # res/npc_trades/kazza_abra.json:5-10 hpIV 15, atkIV 15, defIV 15, speedIV 20, spAtkIV 25, spDefIV 25
    assert "fixed IVs HP/Atk/Def/Spe/SpA/SpD: 15/15/15/20/25/25" in out
    # kazza_abra.json:18 personality 142; 142 % NATURE_COUNT (25) = 17 -> generated/natures.txt:18 NATURE_QUIET
    assert "nature NATURE_QUIET (personality 142" in out
    assert "boosted battle exp" in out  # traded mon (not OT): battle_script.c BattleScript_GetExpTask
    d = run_json(capsys, "species:abra")
    e = _trade(d, "SPECIES_ABRA")
    assert e["phase"] == "pre_champion" and e["fixed_mon"]["nature"] == "NATURE_QUIET"
    assert e["fixed_mon"]["ivs"] == {"hp": 15, "atk": 15, "def": 15, "spe": 20, "spa": 25, "spd": 25}
    assert d["phase"] == "pre_champion"


def test_magikarp_foppa_trade_post_game_v4(capsys):
    # res/field/scripts/scripts_route_226_house.s:44 InitNPCTrade NPC_TRADE_FOPPA_MAGIKARP
    d = run_json(capsys, "species:magikarp")
    e = _trade(d, "SPECIES_MAGIKARP")
    assert e["map_header"] == "MAP_HEADER_ROUTE_226_HOUSE"
    assert e["phase"] == "post_game"
    assert any("not reachable before the Champion" in r for r in e["phase_reasons"])
    rc, out, _ = run(capsys, "species:magikarp")
    assert any(l.strip().startswith("- [post_game] npc_trade at Route 226 House") for l in out.splitlines())
    # control: Magikarp itself is pre-Champion (fishing), only the trade is post-game
    assert d["phase"] == "pre_champion"


# ---------------------------------------------------------------------------------------------
# TMs / items


def test_game_corner_tm_unlimited(capsys, ledger):
    # src/scrcmd_game_corner_prize.c:27 { ITEM_TM90, 2000 } (Veilstone Prize Exchange)
    rc, out, err = run(capsys, "tm90")
    assert rc == 0, err
    assert "copies used by optimizer (TM/HM pre-Champion copies): unlimited" in out
    assert "purchasable pre-Champion: yes (game_corner)" in out
    assert "src/scrcmd_game_corner_prize.c:27" in out
    assert ledger.tm_copies("TM90") == "unlimited"


def test_finite_tm_count_matches_ledger(capsys, ledger):
    # TM28 was the ">1" control here (3 copies) until 2026-10-08: its three item-ball entries are one
    # ball shown in three map headers (one hidden_flag), so it is 1 copy now; no TM has more than
    # one finite copy any more, so the non-trivial finite control is PP Up below.
    n = ledger.tm_copies("TM28")
    assert n == 1, n
    d = run_json(capsys, "tm28")
    assert d["copies"] == n
    rc, out, _ = run(capsys, "tm28")
    assert f"copies used by optimizer (TM/HM pre-Champion copies): {n}  [" in out
    assert "purchasable pre-Champion: no" in out
    assert "shared one-time flag FLAG_OBTAINED_RUIN_MANIAC_CAVE_OR_TUNNEL_TM28: 3 pre-Champion entries, counted once" in out
    assert len([e for e in d["entries"] if e["phase"] == "pre_champion"]) == 3
    m = ledger.item_copies("ITEM_PP_UP")
    assert isinstance(m, int) and m > 1, m  # control: a finite, non-trivial count
    assert run_json(capsys, "item:pp_up")["copies"] == m


def test_tm65_explain_counts_shared_flag_once(capsys, ledger):
    assert ledger.tm_copies("TM65") == 1
    rc, out, err = run(capsys, "tm65")
    assert rc == 0, err
    assert "copies used by optimizer (TM/HM pre-Champion copies): 1  [" in out
    assert "shared one-time flag FLAG_RECEIVED_FANTINA_TM65: 2 pre-Champion entries, counted once" in out
    assert "res/field/scripts/scripts_hearthome_city_gym_leader_room.s:93" in out
    assert "res/field/scripts/scripts_hearthome_city_dp_gym_leader_room.s:78" in out


def test_poke_radar_national_dex_exclusion(capsys):
    # res/field/scripts/scripts_sandgem_town_pokemon_research_lab.s:562 SetVar VAR_0x8004, ITEM_POKE_RADAR
    rc, out, err = run(capsys, "item:poke_radar")
    assert rc == 0, err
    assert "phase: post_game" in out
    assert "copies used by optimizer (item pre-Champion copies): 0" in out
    excl = [l for l in out.splitlines() if "excluded: National Dex (spec FR-003a" in l]
    assert excl and all("src/platsim/availability/ledger.py:" in l for l in excl)
    assert "scripts_sandgem_town_pokemon_research_lab.s" in out


def test_munchlax_allowed(capsys):
    """003 FR-008 (supersedes 001 FR-006a): Munchlax is a pre-Champion honey-tree pokemon."""
    rc, out, err = run(capsys, "species:munchlax")
    assert rc == 0, err
    assert "phase: pre_champion" in out
    assert "FR-006a" not in out
    d = run_json(capsys, "species:munchlax")
    assert d.get("excluded_project_rule") is not True and d["species_sources"]
    assert any(e["phase"] == "pre_champion" for e in d["entries"])


def test_move_learners(capsys, ledger):
    from platsim.legality.movesources import sources

    d = run_json(capsys, "move:earthquake")
    assert "SPECIES_GARCHOMP" in d["learners"]
    # control: a learner reported by explain is one movesources accepts at that level
    assert sources("SPECIES_GARCHOMP", "MOVE_EARTHQUAKE", d["level"], ledger)


# ---------------------------------------------------------------------------------------------
# divergences and errors


def test_divergence_shows_resolution(capsys):
    led = json.loads((REPO_ROOT / "data" / "divergences.json").read_text())
    entry = next(e for e in led["entries"] if e["id"] == "data-move-endure-priority")
    rc, out, err = run(capsys, "divergence:data-move-endure-priority")
    assert rc == 0, err
    assert f"resolution: {entry['resolution']}" in out
    assert entry["decomp_ref"] in out and entry["showdown_ref"] in out
    assert "patch:" in out


@pytest.mark.parametrize("subject, suggestion", [
    ("species:abrra", "species:abra"),
    ("trainer:cyntha", "trainer:champion_cynthia"),
    ("tm99", "tm92"),
    ("divergence:mech-rgn", "divergence:mech-rng"),
    ("garchomp", "species:garchomp"),
])
def test_unknown_subject_exit_2(capsys, subject, suggestion):
    rc, out, err = run(capsys, subject)
    assert rc == 2
    assert out == ""
    assert "unknown subject" in err and suggestion in err


@pytest.mark.parametrize("subject", ["tm28", "hm03", "item:poke_radar", "species:munchlax", "species:abra",
                                     "item:leftovers", "move:earthquake", "divergence:mech-rng"])
def test_every_fact_line_has_a_ref(capsys, subject):
    rc, out, err = run(capsys, subject)
    assert rc == 0, err
    facts = content_lines(out)
    assert len(facts) >= 3
    missing = [l for l in facts if not REF.search(l)]
    assert not missing, missing
