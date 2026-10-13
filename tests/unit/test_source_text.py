"""003 T032 (spec FR-014–FR-016, SC-005; research R7): "obtained from" text in plain words.

Levels, items, moves and species named below are read from the decomp evolution data in each test
(platsim.decomp.species), never typed, except the display names checked against load_items /
load_moves / species_name.
"""

from __future__ import annotations

import itertools
import re

import pytest

from platsim.decomp.species import by_constant
from platsim.legality import movesources as MS
from platsim.legality.models import LegalityOptions

LEAK = re.compile(r"[A-Z]{2,}_[A-Z_]{2,}|EVO|Start[A-Z]|GivePokemon|GiveEgg|ROAMING|NPC_TRADE")


@pytest.fixture(scope="module")
def led():
    from platsim.availability.ledger import build_ledger

    return build_ledger()


def _evo(pre: str, target: str):
    return next(e for e in by_constant()[pre].evolutions if e.target == target)


def _details(species: str, view) -> list[str]:
    return [o.detail for o in MS.source_options(species, view)]


def test_no_internal_code_in_any_source_text(led):
    """Every option of every pokemon under all 16 combinations of the four availability rules."""
    names = ("allow_trade_evolutions", "allow_post_game_pokemon", "allow_post_game_items", "allow_unobtainable_pokemon")
    assert LEAK.search("Gift - Route 201 (Chimchar, starter choice (one of three)) -> Monferno (EVO_LEVEL)"), \
        "positive control: the 002 text is caught"
    bad = []
    n = 0
    for values in itertools.product((False, True), repeat=len(names)):
        view = led.with_options(LegalityOptions(**dict(zip(names, values))))
        for const, sp in by_constant().items():
            if sp.form is not None:
                continue
            for d in _details(const, view):
                n += 1
                if LEAK.search(d):
                    bad.append(d)
    assert n > 1000, "positive control: options were checked"
    assert not bad, sorted(set(bad))[:10]


def test_starter_and_level_evolutions(led):
    a, b = _evo("SPECIES_CHIMCHAR", "SPECIES_MONFERNO"), _evo("SPECIES_MONFERNO", "SPECIES_INFERNAPE")
    want = f"Gift - Route 201 (Chimchar, starter) -> Monferno at level {a.param} -> Infernape at level {b.param}"
    assert want in _details("SPECIES_INFERNAPE", led), _details("SPECIES_INFERNAPE", led)


def test_held_item_evolution_names_item_and_time(led):
    from platsim.decomp.items import load_items

    ev = _evo("SPECIES_SNEASEL", "SPECIES_WEAVILE")
    item = load_items()[ev.param].name
    ds = _details("SPECIES_WEAVILE", led)
    assert ds and all(d.endswith(f"-> Weavile by leveling up holding {item} at night") for d in ds if "Day Care" not in d), ds


def test_static_encounter_has_no_parenthetical(led):
    ds = [d for d in _details("SPECIES_ROTOM", led) if d.startswith("Static encounter")]
    assert ds and all("(" not in d for d in ds), ds


def test_npc_trade_names_nickname_and_requested_pokemon(led):
    ds = [d for d in _details("SPECIES_ABRA", led) if d.startswith("NPC trade")]
    assert ds == [ds[0]] and ds[0].endswith("(Kazza, give Machop)"), ds  # res/npc_trades/kazza_abra.json "name"


def test_fossil_names_its_item(led):
    ds = [d for d in _details("SPECIES_SHIELDON", led) if d.startswith("Fossil")]
    assert ds and all("Armor Fossil" in d for d in ds), ds


def test_other_evolution_methods(led):
    from platsim.decomp.moves import load_moves

    know = _evo("SPECIES_LICKITUNG", "SPECIES_LICKILICKY")
    assert any(d.endswith(f"-> Lickilicky by leveling up knowing {load_moves()[know.param].name}")
               for d in _details("SPECIES_LICKILICKY", led)), _details("SPECIES_LICKILICKY", led)
    assert any(d.endswith("-> Mantine by leveling up with Remoraid in the party")
               for d in _details("SPECIES_MANTINE", led)), _details("SPECIES_MANTINE", led)
    mz = _details("SPECIES_MAGNEZONE", led)
    assert mz and all(re.search(r"-> Magnezone by leveling up at [A-Z]", d) for d in mz if "Day Care" not in d), mz


def test_wild_methods_are_plain(led):
    fl = [d for d in _details("SPECIES_FLOATZEL", led) if d.startswith("Wild")]
    assert fl and not any("NIGHT" in d or "DAY" in d for d in fl), fl
    gy = _details("SPECIES_GYARADOS", led)
    assert any("Old Rod" in d for d in gy), gy


# --- 004: breed and fossil text names the parent's source ----------------------------------------

def _breed_detail(species: str, view) -> str:
    return next(o.detail for o in MS.source_options(species, view) if o.kind == MS.BREED)


def test_breed_text_names_the_parent(led):
    assert _breed_detail("SPECIES_INFERNAPE", led).startswith("Day Care egg from your starter Chimchar")
    assert _breed_detail("SPECIES_RAMPARDOS", led).startswith("Day Care egg from a revived Skull Fossil (odd Trainer ID)")
    assert "Gift egg - Iron Island" in _breed_detail("SPECIES_LUCARIO", led)
    assert "Hearthome City" in _breed_detail("SPECIES_VAPOREON", led)
    garchomp = _breed_detail("SPECIES_GARCHOMP", led)
    assert garchomp.startswith("Day Care egg (mother: ") and "Ditto" not in garchomp
    rev = next(o.detail for o in MS.source_options("SPECIES_RAMPARDOS", led) if o.kind == "gift")
    assert rev.startswith("Fossil - Mining Museum (Skull Fossil, odd Trainer ID)")


def test_every_breed_source_names_a_parent(led):
    """SC-005: every breed option names its group's parent source or at least one mother."""
    bm = MS.breed_mothers(led)
    names = {MS.species_name(c) for mothers, _ in bm.values() for c in mothers}
    seen = 0
    for egg in bm:
        for o in MS.source_options(egg, led):
            if o.kind != MS.BREED or o.acquired != egg:  # count each egg once, not via a pre-evolution's egg
                continue
            seen += 1
            assert o.detail.startswith("Day Care egg"), o.detail
            assert ("starter" in o.detail or "Fossil" in o.detail or "one-time parent" in o.detail
                    or any(n in o.detail for n in names)), o.detail
    assert seen == len(bm) == 86
