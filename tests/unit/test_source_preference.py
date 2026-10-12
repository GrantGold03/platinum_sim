"""Source preference (legality/movesources.py "Source preference") and held-item source text.

Facts are computed from the ledger / decomp data, never typed: each test asserts its own positive
control (e.g. that a single-copy TM *is* a legal source before checking it is not chosen).

Fixture tests/fixtures/t076_v8_team.json is the team of the real V8 optimize result
(runs/t076/v8/result.json), whose report printed "? (unlimited)" for Sitrus Berry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from platsim.legality import movesources as MS
from platsim.legality.models import TeamCandidate
from platsim.legality.validator import validate
from platsim.optimizer import resources as R
from platsim.pins import DECOMP_ROOT, REPO_ROOT
from platsim.report.sources import team_sources

V8_TEAM = REPO_ROOT / "tests" / "fixtures" / "t076_v8_team.json"
V8_RUN = REPO_ROOT / "runs" / "t076" / "v8"


@pytest.fixture(scope="module")
def led():
    from platsim.availability.ledger import build_ledger

    return build_ledger()


@pytest.fixture(scope="module")
def egg_led(led):
    """Egg moves allowed (LegalityOptions; off by default since 2026-10-08). The V8 result and the
    Luxray egg-move test were made with egg moves legal."""
    from platsim.legality.models import LegalityOptions

    return led.with_options(LegalityOptions(allow_egg_moves=True))


def _opt(real, slot=0):
    return real.options[slot]


# --- species source ---------------------------------------------------------------------------


def _story(o) -> int:
    return MS.story_key(o)[0]


def test_earliest_catch_beats_breeding_across_stages(led):
    """003 FR-017 (user decision 2026-10-11): the earliest location wins across evolution stages, and
    a Day Care egg is named only when no catch qualifies."""
    opts = MS.source_options("SPECIES_STARAVIA", led)
    kinds = {MS.option_class(o) for o in opts}
    assert {"own", "pre_evolution", MS.BREED} <= kinds, kinds  # positive control: all three are legal
    spec = R.MemberSpec("SPECIES_STARAVIA", "own", ("MOVE_WING_ATTACK", "MOVE_QUICK_ATTACK"))
    real = R.realize((spec,), [30], led)
    assert not isinstance(real, R.Refusal)
    chosen = _opt(real)
    assert chosen.kind == "wild_slot" and MS.option_class(chosen) != MS.BREED
    catches = [o for o in opts if o.kind == "wild_slot" and o.min_level <= 30]
    assert _story(chosen) == min(_story(o) for o in catches), (chosen.detail, [(o.detail, _story(o)) for o in catches])


def test_pre_evolution_catch_beats_breeding_when_no_egg_move(led):
    # Staraptor has no wild slot of its own pre-Champion (computed), so: catch a pre-evolution, evolve.
    classes = {MS.option_class(o) for o in MS.source_options("SPECIES_STARAPTOR", led)}
    assert "own" not in classes and {"pre_evolution", MS.BREED} <= classes
    spec = R.MemberSpec("SPECIES_STARAPTOR", "own", ("MOVE_BRAVE_BIRD", "MOVE_CLOSE_COMBAT"))
    real = R.realize((spec,), [54], led)
    assert MS.option_class(_opt(real)) == "pre_evolution"
    pre = [o for o in MS.source_options("SPECIES_STARAPTOR", led) if MS.option_class(o) == "pre_evolution"]
    assert _story(_opt(real)) == min(_story(o) for o in pre)


def test_garchomp_is_named_from_gible_in_wayward_cave(led):
    """The quickstart V5 case: Gible (Wayward Cave B1F) beats Gabite (Victory Road 1F)."""
    spec = R.MemberSpec("SPECIES_GARCHOMP", "own", ("MOVE_EARTHQUAKE",))
    real = R.realize((spec,), [48], led)
    assert not isinstance(real, R.Refusal), real
    o = _opt(real)
    assert o.acquired == "SPECIES_GIBLE" and o.map_header == "MAP_HEADER_WAYWARD_CAVE_B1F", o.detail
    assert o.detail.startswith("Wild - Wayward Cave B1F (Gible, grass) -> Gabite at level"), o.detail
    gabite = [x for x in MS.source_options("SPECIES_GARCHOMP", led) if x.acquired == "SPECIES_GABITE" and x.kind == "wild_slot"]
    assert gabite and all(_story(x) > _story(o) for x in gabite)  # positive control: the later option exists


def test_one_percent_only_location_is_skipped_unless_it_is_the_only_one(led):
    one = [o for c in ("SPECIES_GABITE", "SPECIES_MUNCHLAX") for o in MS.source_options(c, led)
           if o.kind == "wild_slot" and o.rate_percent is not None]
    assert any(o.rate_percent <= MS.ONE_PERCENT for o in one), "positive control: a 1% option exists (Munchlax)"
    k1 = MS.option_sort_key(next(o for o in one if o.rate_percent <= MS.ONE_PERCENT))
    k2 = MS.option_sort_key(next(o for o in one if o.rate_percent > MS.ONE_PERCENT))
    assert k1[2] is True and k2[2] is False
    mun = R.realize((R.MemberSpec("SPECIES_MUNCHLAX", "own", ("MOVE_TACKLE",)),), [15], led)
    assert not isinstance(mun, R.Refusal) and "honey tree" in _opt(mun).detail  # the only catch: still named


def test_min_level_is_only_a_feasibility_filter(led):
    spec = R.MemberSpec("SPECIES_GABITE", "own", ("MOVE_DRAGON_RAGE",))
    real = R.realize((spec,), [24], led)
    assert not isinstance(real, R.Refusal) and _opt(real).min_level <= 24


def test_floors_unchanged_for_the_reference_species(led):
    """003 T001 baseline: the optimizer's level floors do not depend on which source is named."""
    base = json.loads((REPO_ROOT / "specs/003-webui-refinements/baseline/t001-baseline.json").read_text())
    res = json.loads((REPO_ROOT / "tests/fixtures/web_final_defaults/result.json").read_text())
    for b in res["team"]["builds"]:
        spec = R.MemberSpec("SPECIES_" + b["species"].upper(), "own",
                            tuple("MOVE_" + m["move"].upper() for m in b["moves"]), b.get("held_item"), b.get("ability"))
        assert R.member_floor(spec, led) == base["floors_final_defaults_specs"][b["species"]], b["species"]


def test_combee_is_named_from_the_honey_tree(led):
    """Analysis H3: Combee was only a level-1 Day Care egg; with honey-tree levels it is caught."""
    real = R.realize((R.MemberSpec("SPECIES_COMBEE", "own", ("MOVE_GUST",)),), [15], led)
    assert not isinstance(real, R.Refusal) and "honey tree" in _opt(real).detail, _opt(real).detail
    assert R.member_floor(R.MemberSpec("SPECIES_COMBEE", "own", ("MOVE_GUST",)), led) == 1  # breeding stays legal


def test_luxray_with_egg_moves_is_bred_without_them_is_caught(led, egg_led):
    eggs = R.MemberSpec("SPECIES_LUXRAY", "own", ("MOVE_THUNDERBOLT", "MOVE_ICE_FANG", "MOVE_CRUNCH", "MOVE_FIRE_FANG"))
    assert isinstance(R.realize((eggs,), [55], led), R.Refusal)  # default: egg moves off, never built
    led = egg_led
    real = R.realize((eggs,), [55], led)
    assert not isinstance(real, R.Refusal)
    assert _opt(real).kind == MS.BREED
    kinds = {m.move: m.source_kind for m in real.team.builds[0].moves}
    assert kinds["ice_fang"] == "egg" and kinds["fire_fang"] == "egg"
    assert kinds["crunch"] == "level_up"  # egg is the last resort per move too
    plain = R.MemberSpec("SPECIES_LUXRAY", "own", ("MOVE_THUNDERBOLT", "MOVE_CRUNCH"))
    real2 = R.realize((plain,), [55], led)
    assert _opt(real2).kind == "wild_slot", _opt(real2).id


def test_npc_trade_is_never_mixed_into_the_own_variant(led):
    from platsim.optimizer import candidates as C

    for const in ("SPECIES_STARAPTOR", "SPECIES_LUXRAY", "SPECIES_GARCHOMP"):
        own = next(v for v in C.variants(const, led) if v.key == "own")
        assert all(o.kind != "npc_trade" for o in own.options(led))
    trades = [c.entry.subject for c in led.pre(kind="npc_trade")]
    assert trades  # positive control: NPC trades exist in the ledger
    for const in trades:
        vs = C.variants(const, led)
        assert any(v.key != "own" and all(o.kind == "npc_trade" for o in v.options(led)) for v in vs)


# --- move source ------------------------------------------------------------------------------


def test_move_kind_order_is_documented_order():
    o = MS.MOVE_KIND_ORDER
    assert o["level_up"] == o["pre_evo_level_up"] < o["tm"] == o["hm"] < o["tutor"] < o["relearner"] < o["egg"]


def test_single_copy_tm_only_when_no_unlimited_source(led):
    marker = "TM18"
    assert led.tm_copies(marker) == 1  # positive control (ledger)
    lvl_up = [n for n, mv in MS.by_constant()["SPECIES_GYARADOS"].learnset_level if mv == "MOVE_RAIN_DANCE"]
    assert lvl_up  # Gyarados learns Rain Dance by level-up (decomp learnset)
    hi, lo = max(lvl_up[0], 50), lvl_up[0] - 1
    # at a level above the level-up move: TM18 is legal but the level-up wins
    cs = MS.sources("SPECIES_GYARADOS", "MOVE_RAIN_DANCE", hi, led)
    assert any(c.source_kind == "tm" and MS.consumes_limited(c, led) for c in cs)
    spec = R.MemberSpec("SPECIES_GYARADOS", "own", ("MOVE_RAIN_DANCE", "MOVE_WATERFALL"))
    real = R.realize((spec,), [hi], led)
    assert real.team.builds[0].moves[0].source_kind == "level_up" and "TM18" not in real.uses
    # below it no unlimited source exists, so the single copy is used (and counted)
    cs_lo = MS.sources("SPECIES_GYARADOS", "MOVE_RAIN_DANCE", lo, led)
    assert cs_lo and all(MS.consumes_limited(c, led) for c in cs_lo), [c.detail for c in cs_lo]
    real_lo = R.realize((spec,), [lo], led)
    assert real_lo.team.builds[0].moves[0].source_kind == "tm" and real_lo.uses.get("TM18") == 1


def test_validator_from_showdown_prefers_simplest_source(egg_led):
    led = egg_led
    team = TeamCandidate.from_dict(json.loads(V8_TEAM.read_text()))
    from platsim.legality.models import export_team
    from platsim.legality.validator import load_team, showdown_name

    sd = export_team(team, showdown_name)
    parsed, _, _ = load_team(sd, led)
    by = {b.species: b for b in parsed.builds}
    assert by["SPECIES_LUXRAY"].source.startswith("breed:")  # needs its egg moves
    for sp in ("SPECIES_INFERNAPE", "SPECIES_STARAPTOR", "SPECIES_GARCHOMP", "SPECIES_GYARADOS", "SPECIES_GARDEVOIR"):
        assert not by[sp].source.startswith(("breed:", "npc_trade:")), (sp, by[sp].source)
    assert validate(parsed, led) == []


# --- held-item source -------------------------------------------------------------------------


def _ref_exists(r: str) -> bool:
    path = r.rsplit(":", 1)[0]
    return (DECOMP_ROOT / path).is_file()


def test_every_held_item_of_the_real_v8_result_has_a_named_source(egg_led):
    led = egg_led
    d = json.loads(V8_TEAM.read_text())
    team = TeamCandidate.from_dict(d)
    assert validate(team, led) == []  # positive control: the recorded team is legal
    items = [b.held_item for b in team.builds]
    assert "sitrus_berry" in items and all(items)
    _, held, refs = team_sources(team, led)
    for item, text, src in zip(items, held, refs):
        assert text and "?" not in text and "not recorded" not in text, (item, text)
        assert text.endswith(("(unlimited)", "copy)", "copies)")), text
        assert src and all(_ref_exists(r) for r in src), (item, src)
    sitrus = [t for i, t in zip(items, held) if i == "sitrus_berry"]
    assert sitrus and all(t.startswith("Berry patch - ") and t.endswith("(unlimited)") for t in sitrus), sitrus


def test_item_without_a_source_is_an_error_not_a_question_mark(led):
    from platsim.decomp.items import load_items

    none = next(c for c, it in sorted(load_items().items())
                if it.hold_effect != "HOLD_EFFECT_NONE" and led.item_copies(c) == 0)
    with pytest.raises(MS.NoNamedSource):
        MS.held_item_source(none, led)
    # positive controls: each source kind the contract names produces its label
    texts = {k: MS.item_sources(c, led)[0].label for k, c in (("berry", "ITEM_SITRUS_BERRY"), ("tm", "ITEM_TM26"))}
    assert texts["berry"].startswith("Berry patch - ")
    assert texts["tm"].startswith("Item ball - ") and texts["tm"].endswith("(1 copy)")
    wild = next(c.entry.subject for c in led.pre(kind="wild_held_item"))
    assert any(s.text.startswith("Wild held item - ") and " at " in s.text for s in MS.item_sources(wild, led))


# --- re-render ---------------------------------------------------------------------------------


@pytest.mark.skipif(not (V8_RUN / "result.json").is_file(), reason="runs/t076/v8 not present (runs/ is not versioned)")
def test_rerender_keeps_numbers_and_names_sources(tmp_path):
    from platsim.report.rerender import RerenderError, rerender

    before = {p.name: p.read_bytes() for p in V8_RUN.iterdir() if p.is_file()}
    rep, paths, _changes = rerender(V8_RUN, tmp_path / "out")
    assert {p.name: p.read_bytes() for p in V8_RUN.iterdir() if p.is_file()} == before  # source run untouched
    old = json.loads(before["result.json"])
    new = json.loads(paths["json"].read_text())
    for k in ("n_runs", "clear_rate", "clear_ci95", "per_battle", "champion_rate", "champion_ci95", "expected_final_levels",
              "loss_causes", "seeds", "decomp_commit", "showdown_commit", "platsim_code_hash", "sim_code_hash"):
        assert new.get(k) == old.get(k), k  # code hashes: None in reports written before versioning
    assert [[m["move"] for m in b["moves"]] for b in new["team"]["builds"]] == \
        [[m["move"] for m in b["moves"]] for b in old["team"]["builds"]]
    assert (tmp_path / "out" / "team.txt").read_text() == before["team.txt"].decode()
    assert "?" not in " ".join(new["held_item_sources"]) and all(new["held_item_source_refs"])
    assert new["provenance"]["rerender"]["rerendered_by"]["platsim_code_hash"].startswith("sha256:")
    assert sum(s.startswith("Day Care egg") for s in new["obtained_from"]) == 1  # only Luxray (egg moves)
    with pytest.raises(RerenderError):  # never overwrites
        rerender(V8_RUN, V8_RUN)
    with pytest.raises(RerenderError):
        rerender(V8_RUN, tmp_path / "out")
    assert Path(paths["csv"]).is_file()
