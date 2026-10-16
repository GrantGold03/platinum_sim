"""Optional legality rules (legality/models.LegalityOptions; user decisions 2026-10-08): egg moves and
trade evolutions, both off by default.

Game facts used below are computed from the decomp / ledger, never typed, except these citations
(each re-read by `_line`):
- EVO_CLASS_BY_TRADE: src/pokemon.c (Pokemon_GetEvolutionTargetSpecies), EVO_TRADE /
  EVO_TRADE_WITH_HELD_ITEM.
- The held item is removed on a trade-with-item evolution: src/evolution.c:782-786.
- Trading never rewrites OT: the trade room calls UpdateMonStatusAndTrainerInfo(..., 5, ...)
  (src/applications/trade_room/application.c:2452), and mode 5 only touches an egg's met data
  (src/unk_02092494.c:816-822); AssignTrainerInfoToBoxPokemon is not called. The traded exp boost
  needs BattleSystem_PokemonIsOT == FALSE (src/battle/battle_script.c:9757,
  src/battle/battle_lib.c:6286-6301 compares OT id, gender and name).
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from platsim import cli
from platsim.legality import movesources as MS
from platsim.legality.models import LegalityOptions, TeamCandidate
from platsim.legality.validator import validate
from platsim.pins import DECOMP_ROOT, REPO_ROOT

FIX = REPO_ROOT / "tests" / "fixtures"
V8_TEAM = FIX / "t076_v8_team.json"
TRADE = LegalityOptions(allow_trade_evolutions=True)
EGG = LegalityOptions(allow_egg_moves=True)
POST_MON = LegalityOptions(allow_post_game_pokemon=True)
POST_ITEMS = LegalityOptions(allow_post_game_items=True)
OUTSIDE = LegalityOptions(allow_unobtainable_pokemon=True)
NEW_RULES = ("allow_post_game_pokemon", "allow_post_game_items", "allow_unobtainable_pokemon")
# 003 T001 baseline (specs/003-webui-refinements/baseline/t001-baseline.json): the default fingerprint
# of the test_optimize_small.py request must not move when the new rules are added.
T001_FINGERPRINT = {"species": ["SPECIES_INFERNAPE", "SPECIES_STARAPTOR", "SPECIES_LUXRAY", "SPECIES_GARCHOMP",
                                "SPECIES_GYARADOS", "SPECIES_GARDEVOIR"], "min_clear": 0.75, "seed": "t058",
                    "budget": "quick", "legality_options": {"allow_egg_moves": False, "allow_trade_evolutions": False},
                    "state_version": 4, "candidates": "off"}  # 007: state version 4 + the candidates mode (default off)
TRADE_TAIL = "(trade evolution; needs a second cartridge for the trade)"


def _line(path: str, line: int, needle: str) -> None:
    text = (DECOMP_ROOT / path).read_text().splitlines()[line - 1]
    assert needle in text, f"{path}:{line} is {text!r}, expected {needle!r}"


@pytest.fixture(scope="module")
def led():
    from platsim.availability.ledger import build_ledger

    return build_ledger()


@pytest.fixture(scope="module")
def tr(led):
    return led.with_options(TRADE)


def _legal() -> dict:
    return json.loads((FIX / "legal_team.json").read_text())


# --- the options object -------------------------------------------------------------------------


def test_options_default_off_and_round_trip():
    o = LegalityOptions()
    assert o.to_dict() == {"allow_egg_moves": False, "allow_trade_evolutions": False,
                           "allow_post_game_pokemon": False, "allow_post_game_items": False,
                           "allow_unobtainable_pokemon": False}
    assert o.to_dict(compact=True) == {"allow_egg_moves": False, "allow_trade_evolutions": False}
    assert POST_ITEMS.to_dict(compact=True) == {"allow_egg_moves": False, "allow_trade_evolutions": False,
                                                "allow_post_game_items": True}
    old = {"allow_egg_moves": True, "allow_trade_evolutions": False}  # a report written before 003
    assert LegalityOptions.from_dict(old) == LegalityOptions(allow_egg_moves=True)
    for o2 in (POST_MON, POST_ITEMS, OUTSIDE):
        assert LegalityOptions.from_dict(o2.to_dict()) == o2
    assert LegalityOptions.from_dict(TRADE.to_dict()) == TRADE and LegalityOptions.from_dict(None) == o
    with pytest.raises(ValueError):
        LegalityOptions.from_dict({"allow_egg_moves": "yes"})
    with pytest.raises(ValueError):
        LegalityOptions.from_dict({"allow_eggs": True})


def test_egg_option_never_changes_species_sources(led):
    egg = led.with_options(EGG)
    for sp in ("SPECIES_GARCHOMP", "SPECIES_LUXRAY", "SPECIES_STARAPTOR", "SPECIES_ALAKAZAM"):
        assert [o.id for o in MS.source_options(sp, led)] == [o.id for o in MS.source_options(sp, egg)], sp


# --- egg moves: the real V8 result -------------------------------------------------------------


def test_v8_team_needs_the_egg_move_flag(led):
    """tests/fixtures/t076_v8_team.json (V8 optimize result) has Luxray with the egg moves Ice Fang
    and Fire Fang: illegal by default, legal with allow_egg_moves."""
    vs = validate(str(V8_TEAM), led)
    assert sorted(v.code for v in vs) == ["EGG_MOVE_NOT_ALLOWED", "EGG_MOVE_NOT_ALLOWED"], [v.message for v in vs]
    assert {m for v in vs for m in ("MOVE_ICE_FANG", "MOVE_FIRE_FANG") if m in v.message} == {"MOVE_ICE_FANG", "MOVE_FIRE_FANG"}
    assert all("luxray" in v.message for v in vs)
    assert validate(str(V8_TEAM), led, options=EGG) == []


def test_cli_validate_egg_flag(capsys):
    assert cli.main(["validate", str(V8_TEAM)]) == 2
    out = capsys.readouterr().out
    assert "EGG_MOVE_NOT_ALLOWED" in out and "allow_egg_moves=off" in out
    assert cli.main(["validate", str(V8_TEAM), "--allow-egg-moves"]) == 0
    assert "legal (no violations)" in capsys.readouterr().out
    assert cli.main(["validate", str(V8_TEAM), "--allow-egg-moves", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["legal"] and d["legality_options"] == LegalityOptions(allow_egg_moves=True).to_dict()  # all five rules


# --- trade evolutions --------------------------------------------------------------------------


def test_trade_evolution_cited_lines():
    _line("src/evolution.c", 782, "case EVO_TRADE_WITH_HELD_ITEM:")
    _line("src/evolution.c", 786, "Pokemon_SetValue(evolutionData->mon, MON_DATA_HELD_ITEM, &i);")
    _line("src/applications/trade_room/application.c", 2452, "UpdateMonStatusAndTrainerInfo(receivingMon")
    _line("src/applications/trade_room/application.c", 2452, ", 5, 0,")
    _line("src/unk_02092494.c", 816, "case 5:")
    body = "\n".join((DECOMP_ROOT / "src/unk_02092494.c").read_text().splitlines()[815:822])
    assert "AssignTrainerInfoToBoxPokemon" not in body and "break;" in body
    _line("src/battle/battle_script.c", 9757, "BattleSystem_PokemonIsOT(data->battleSys, mon) == FALSE")
    _line("src/battle/battle_lib.c", 6286, "BOOL BattleSystem_PokemonIsOT(")


@pytest.mark.parametrize("pre", ["SPECIES_KADABRA", "SPECIES_HAUNTER", "SPECIES_MACHOKE", "SPECIES_GRAVELER"])
def test_trade_pre_evolutions_obtainable(led, pre):
    kinds = {o.kind for o in MS.source_options(pre, led)}
    assert "wild_slot" in kinds or "npc_trade" in kinds, (pre, kinds)


def test_trade_evolution_species_only_with_the_flag(led, tr):
    for sp in ("SPECIES_ALAKAZAM", "SPECIES_GENGAR", "SPECIES_MACHAMP", "SPECIES_GOLEM"):
        assert MS.source_options(sp, led) == [], sp  # FR-005 default
        opts = MS.source_options(sp, tr)
        assert opts, sp
        assert all(TRADE_TAIL in o.detail for o in opts), sp
        assert all(o.consumes == () for o in opts)  # plain EVO_TRADE uses no item
    # requested text form: "Wild - <map> (Kadabra) -> Alakazam (trade evolution; ...)"
    wild = [o for o in MS.source_options("SPECIES_ALAKAZAM", tr) if o.kind == "wild_slot" and o.acquired == "SPECIES_KADABRA"]
    assert wild and wild[0].detail.startswith("Wild - ") and "(Kadabra" in wild[0].detail
    assert wild[0].detail.endswith(f") -> Alakazam {TRADE_TAIL}"), wild[0].detail
    # no level-up is needed: the evolved stage exists at the pre-evolution's level
    assert wild[0].stages[-1].enter == wild[0].stages[-2].enter


def test_item_trade_evolution_needs_an_obtainable_item_and_uses_it(led, tr):
    # Positive: Rhydon -> Rhyperior holding a Protector (single pre-Champion copy per the ledger).
    assert led.item_copies("ITEM_PROTECTOR") == 1
    opts = MS.source_options("SPECIES_RHYPERIOR", tr)
    assert opts and all(dict(o.consumes).get("ITEM_PROTECTOR") == 1 for o in opts)
    assert all("holding Protector" in o.detail for o in opts)
    # Negative: Kingdra needs a Dragon Scale, which has no pre-Champion copy (and Seadra no source).
    assert led.item_copies("ITEM_DRAGON_SCALE") == 0
    assert MS.source_options("SPECIES_KINGDRA", tr) == []
    d = _legal()
    d["builds"][5]["species"] = "kingdra"
    (v,) = [v for v in validate(d, tr) if v.code == "SPECIES_TRADE_EVOLUTION"]
    assert "trade evolutions are allowed" in v.message and "ITEM_DRAGON_SCALE has no pre-Champion copy" in v.message


def _member(species: str, moves: tuple[str, ...], level: int, led) -> dict:
    """A legal Build dict made by the optimizer's realize (first variant, documented preferences)."""
    from platsim.optimizer import resources as R

    real = R.realize((R.MemberSpec(species, "own", moves),), [level], led)
    assert not isinstance(real, R.Refusal), real.reason
    return real.team.builds[0].to_dict()


def test_trade_evolution_item_copies_counted_team_wide(led, tr):
    rh = MS.by_constant()["SPECIES_RHYPERIOR"]
    move = next(mv for n, mv in rh.learnset_level if n <= 30)  # a level-up move it knows by default
    one = _member("SPECIES_RHYPERIOR", (move,), 60, tr)
    d = _legal()
    d["builds"][5] = one
    assert validate(d, tr) == []  # positive control: one Rhyperior is legal with the flag
    assert sorted(v.code for v in validate(d, led)) == ["SPECIES_TRADE_EVOLUTION"]  # and not without it
    d["builds"][2] = dict(one)
    codes = [v.code for v in validate(d, tr)]
    assert "ITEM_COPIES" in codes and any("ITEM_PROTECTOR" in v.message for v in validate(d, tr))
    # the optimizer's resource assignment never builds the second one
    from platsim.optimizer import resources as R

    spec = R.MemberSpec("SPECIES_RHYPERIOR", "own", (move,))
    assert isinstance(R.realize((spec, spec), [60, 60], tr), R.Refusal)


def test_trade_evolved_member_gets_no_traded_exp_boost(tr):
    """Own Pokemon traded away and back keep the player as OT (module doc): no boost. An NPC-trade
    Pokemon that is then trade-evolved keeps the NPC's OT: boosted (FR-008a)."""
    from platsim.evaluate import worker_team

    opts = MS.source_options("SPECIES_ALAKAZAM", tr)
    own = next(o for o in opts if o.kind == "wild_slot")
    npc = next(o for o in opts if o.kind == "npc_trade")
    builds = []
    for o in (own, npc):
        b = _member("SPECIES_ALAKAZAM", ("MOVE_CONFUSION",), 40, tr)
        b["source"] = o.id
        builds.append(b)
    team = TeamCandidate.from_dict({"builds": builds})
    flags = [w["is_traded"] for w in worker_team(team, tr)]
    assert flags == [False, True], flags
    # The worker's own derivation (sim/team.mjs tradeOrigin) agrees: only an npc_trade: source is traded.
    probe = ("import { tradeOrigin } from %s;\n"
             "console.log(JSON.stringify(process.argv.slice(1).map((s) => tradeOrigin(s).traded)));") % json.dumps(
        (REPO_ROOT / "sim" / "team.mjs").as_uri())
    r = subprocess.run(["node", "--input-type=module", "-e", probe, own.id, npc.id], capture_output=True, text=True,
                       check=True, cwd=REPO_ROOT)
    assert json.loads(r.stdout) == [False, True]


def test_cli_validate_trade_flag(capsys, tmp_path):
    from platsim.availability.ledger import build_ledger

    d = _legal()
    d["builds"][5] = _member("SPECIES_GENGAR", ("MOVE_SHADOW_BALL",), 57, build_ledger().with_options(TRADE))
    p = tmp_path / "gengar_team.json"
    p.write_text(json.dumps(d))
    assert cli.main(["validate", str(p)]) == 2
    assert "SPECIES_TRADE_EVOLUTION" in capsys.readouterr().out
    assert cli.main(["validate", str(p), "--allow-trade-evolutions"]) == 0


def test_cli_flags_on_evaluate_and_optimize():
    p = cli.build_parser()
    for argv in (["evaluate", "t.json"], ["optimize", *["garchomp"] * 6], ["validate", "t.json"]):
        a = p.parse_args(argv)
        assert (a.allow_egg_moves, a.allow_trade_evolutions) == (False, False)
        assert cli._legality(a) == LegalityOptions()
        a = p.parse_args(argv + ["--allow-egg-moves", "--allow-trade-evolutions"])
        assert cli._legality(a) == LegalityOptions(True, True)
        a = p.parse_args(argv + ["--allow-post-game-pokemon", "--allow-post-game-items", "--allow-unobtainable-pokemon"])
        assert cli._legality(a) == LegalityOptions(**{k: True for k in NEW_RULES})


def test_optimizer_fingerprint_and_resolve_use_options(led):
    from platsim.optimizer.api import InvalidRequest, OptimizeRequest
    from platsim.optimizer.candidates import resolve_species
    from platsim.optimizer.run import job_fingerprint

    names = ["alakazam", "staraptor", "luxray", "garchomp", "gyarados", "gardevoir"]
    with pytest.raises(InvalidRequest) as e:
        resolve_species(names, led)
    assert "--allow-trade-evolutions" in e.value.reasons["alakazam"]
    consts = resolve_species(names, led.with_options(TRADE))
    assert consts[0] == "SPECIES_ALAKAZAM"
    a = job_fingerprint(consts, OptimizeRequest(tuple(names)))
    b = job_fingerprint(consts, OptimizeRequest(tuple(names), legality=TRADE))
    assert a["legality_options"] == LegalityOptions().to_dict(compact=True) and a != b
    t058 = ["infernape", "staraptor", "luxray", "garchomp", "gyarados", "gardevoir"]
    req = OptimizeRequest(tuple(t058), budget="quick", seed="t058")
    assert job_fingerprint([f"SPECIES_{s.upper()}" for s in t058], req) == T001_FINGERPRINT
    for o in (POST_MON, POST_ITEMS, OUTSIDE):  # each new rule changes the fingerprint
        assert job_fingerprint(consts, OptimizeRequest(tuple(names), legality=o)) != a


def test_resume_with_other_options_is_refused(tmp_path):
    from platsim.optimizer.api import InvalidRequest, OptimizeRequest
    from platsim.optimizer.run import _State, job_fingerprint

    consts = ["SPECIES_GARCHOMP"] * 6
    code = {"sim_code_hash": "x"}
    s = _State(tmp_path / "state.json", job_fingerprint(consts, OptimizeRequest(("garchomp",) * 6)), code)
    s.save()
    with pytest.raises(InvalidRequest, match="different optimize job"):
        _State(tmp_path / "state.json", job_fingerprint(consts, OptimizeRequest(("garchomp",) * 6, legality=EGG)), code)
    with pytest.raises(InvalidRequest, match="different optimize job"):
        _State(tmp_path / "state.json", job_fingerprint(consts, OptimizeRequest(("garchomp",) * 6, legality=POST_MON)), code)


def test_option_dependent_caches_are_keyed_on_options(led):
    """003 T015 (research R2): `species_sources` and `breed_mothers` must give each options view its
    own answer. X is a pokemon whose only acquisition entries are post-game (read from the ledger)."""
    from platsim.availability.ledger import POST, build_ledger

    acq = ("wild_slot", "gift", "egg", "static", "roamer", "npc_trade")
    phases: dict[str, set] = {}
    for c in led.entries:
        if c.entry.kind in acq:
            phases.setdefault(c.entry.subject, set()).add(c.phase)
    post_only = sorted(s for s, p in phases.items() if p == {POST})
    assert post_only, "positive control: the ledger has post-game-only pokemon"
    x = post_only[0]
    fresh = build_ledger.__wrapped__() if hasattr(build_ledger, "__wrapped__") else led
    post = fresh.with_options(POST_MON)
    assert post.species_sources(x), f"{x} has post-game sources once they are allowed"
    assert fresh.species_sources(x) == [], f"{x} has no pre-Champion source by default"
    assert post.species_sources(x), "the default view must not overwrite the post-game view's answer"
    assert MS.source_options(x, post) and not MS.source_options(x, fresh)
    mothers_default, mothers_post = MS.breed_mothers(fresh), MS.breed_mothers(post)
    assert mothers_default != mothers_post, "breed mothers differ once post-game pokemon count"


# --- species catalogue -------------------------------------------------------------------------


def test_catalog_reflects_trade_option(led):
    from platsim.web.species_catalog import build_catalog

    cat = build_catalog(led)
    ala = cat.get("alakazam")
    assert not ala.available and ala.reason_code == "trade_evolution"
    st = cat.status(ala, TRADE)
    assert st.available and st.note
    j = cat.to_json(ala, TRADE)
    assert j["available"] and j["trade_evolution"] and "second cartridge" in j["note"]
    assert not cat.to_json(ala)["available"]
    kd = cat.status(cat.get("kingdra"), TRADE)
    assert not kd.available and kd.reason_code == "trade_evolution" and "Dragon Scale" in kd.reason
    garchomp = cat.get("garchomp")  # positive control: available either way, never marked
    g = cat.status(garchomp, TRADE)
    assert garchomp.available and g.available and not g.note
    assert [s.key for s in cat.search("alaka", include_excluded=False)] == []
    assert [s.key for s in cat.search("alaka", include_excluded=False, options=TRADE)] == ["alakazam"]
    six = ["alakazam", "staraptor", "luxray", "garchomp", "gyarados", "gardevoir"]
    from platsim.optimizer.api import InvalidRequest

    with pytest.raises(InvalidRequest):
        cat.resolve_team(six)
    assert cat.resolve_team(six, TRADE)[0] == "alakazam"


def test_validator_still_independent_of_optimizer():
    probe = ("import sys, platsim.legality.validator, platsim.legality.models, platsim.availability.ledger\n"
             "print('platsim.optimizer' in sys.modules)")
    r = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert r.stdout.strip() == "False"


def test_unobtainable_option_help_names_one_platinum_game(capsys):
    """005 FR-005: the --allow-unobtainable-pokemon help on validate / evaluate / optimize."""
    for cmd in ("validate", "evaluate", "optimize"):
        with pytest.raises(SystemExit):
            cli.main([cmd, "--help"])
        out = " ".join(capsys.readouterr().out.split())  # argparse wraps lines
        assert "unobtainable in one Platinum game" in out and "second starter" in out, cmd
