"""007 T010: held-item classification from decomp battle code (spec FR-009, research R2)."""

import json
import subprocess

import pytest

from platsim.decomp.items import load_items
from platsim.optimizer import item_classes as IC
from platsim.pins import REPO_ROOT

ITEMS = {i.key: i for i in load_items().values()}


def cls(key):
    return IC.item_class(ITEMS[key].const)


RESIST_BERRIES = ["occa_berry", "passho_berry", "wacan_berry", "rindo_berry", "yache_berry", "chople_berry",
                  "kebia_berry", "shuca_berry", "coba_berry", "payapa_berry", "tanga_berry", "charti_berry",
                  "kasib_berry", "haban_berry", "colbur_berry", "babiri_berry", "chilan_berry"]


@pytest.mark.parametrize("key", RESIST_BERRIES)
def test_resist_berries_are_in_battle_by_numeric_reference(key):
    # Positive control for the numeric search: subscript_type_resist_berry.s compares literals 19-35.
    c = cls(key)
    assert c.in_battle and c.excluded_reason is None
    refs = IC.hold_effect_references()[c.hold_effect]
    assert any(r.path.endswith("subscript_type_resist_berry.s") for r in refs)


@pytest.mark.parametrize("key,why", [
    ("everstone", "not_in_battle"), ("cleanse_tag", "not_in_battle"), ("grass_mail", "not_in_battle"),
    ("dragon_scale", "not_in_battle"),
    ("amulet_coin", "no_outcome"), ("smoke_ball", "no_outcome"), ("soothe_bell", "no_outcome"),
    ("lucky_egg", "exp_ev"), ("exp_share", "exp_ev"), ("macho_brace", "exp_ev"), ("power_weight", "exp_ev"),
])
def test_excluded(key, why):
    assert (cls(key).excluded_reason or "").startswith(why), cls(key)


@pytest.mark.parametrize("key", ["sitrus_berry", "leftovers", "light_clay", "choice_specs", "life_orb", "focus_sash",
                                 "lum_berry", "chesto_berry", "damp_rock", "black_sludge", "quick_claw", "shell_bell"])
def test_battle_items_are_candidates_before_copies(key):
    assert cls(key).excluded_reason is None, cls(key)


def test_no_outcome_references_lie_in_their_named_functions():
    for effect, (funcs, _why) in IC.NO_OUTCOME.items():
        allowed = set(funcs.split("|"))
        for r in IC.hold_effect_references()[effect]:
            assert r.function in allowed or r.path.split("/")[-1] in allowed, (effect, r)


def test_species_gates():
    assert cls("light_ball").species == frozenset({"SPECIES_PIKACHU"})
    assert cls("thick_club").species == frozenset({"SPECIES_CUBONE", "SPECIES_MAROWAK"})
    assert cls("sitrus_berry").species is None


@pytest.fixture(scope="module")
def led():
    from platsim.availability.ledger import build_ledger
    from platsim.legality.models import DEFAULT_LEGALITY
    return build_ledger().with_options(DEFAULT_LEGALITY)


B1 = ("SPECIES_INFERNAPE", "SPECIES_STARAPTOR", "SPECIES_LUXRAY", "SPECIES_GARCHOMP", "SPECIES_GYARADOS", "SPECIES_GARDEVOIR")


def test_offerable_items_default_options(led):
    items = IC.offerable_items("SPECIES_GARCHOMP", B1, led)
    assert "sitrus_berry" in items
    assert "choice_band" not in items  # 0 pre-Champion copies (post-game only)
    assert "leftovers" not in items  # team-gated: no Munchlax/Snorlax on B1
    assert "light_ball" not in items  # Pikachu only
    snorlax_team = ("SPECIES_SNORLAX",) + B1[1:]
    assert "leftovers" in IC.offerable_items("SPECIES_SNORLAX", snorlax_team, led)
    every = set()
    for sp in B1:
        every |= set(IC.offerable_items(sp, B1, led))
    print("offerable to some B1 member:", len(every))
    assert len(every) >= 80


def test_every_candidate_item_maps_to_showdown():
    js = ("import('./sim/gamedata.mjs').then(m => { const gd = m.loadGameData(); "
          "console.log(JSON.stringify(gd.unmapped.items)); })")
    out = subprocess.run(["node", "--input-type=module", "-e", js], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    unmapped = set(json.loads(out.stdout.strip().splitlines()[-1]))
    assert "amulet_coin" in unmapped  # positive control: a known unmapped item (data/divergences.json)
    candidates = {k for k, it in ITEMS.items() if IC.item_class(it.const).excluded_reason is None}
    assert not candidates & unmapped, sorted(candidates & unmapped)
