"""007 T017: the MODELLED table in sim/policy/expectimax2.mjs, as parsed by the optimizer (spec FR-001, FR-009)."""

import re

from platsim.optimizer import move_classes as MC
from platsim.pins import REPO_ROOT


def test_parse_is_non_empty_for_every_version():
    t = MC.modelled_table()
    for name in ("expectimax2-v1", "expectimax2-v2", "expectimax2-v3", "expectimax2-v3-ref"):
        effects, items = t[name]
        assert effects and items, name


def test_v2_contents():
    effects, items = MC.modelled("expectimax2-v2")
    assert {"ATK_UP_2", "STATUS_BADLY_POISON", "PROTECT", "REST"} <= effects
    assert "WEATHER_RAIN" not in effects and "STATUS_LEECH_SEED" not in effects  # no effect in v2 (statusMove)
    assert {"HP_PCT_RESTORE", "HP_RESTORE_GRADUAL", "STRENGTHEN_WATER"} <= items
    assert "CHOICE_SPATK" not in items  # lock not modelled


def test_names_match_gauntlet_registrations():
    text = (REPO_ROOT / "sim" / "gauntlet.mjs").read_text()
    imported = set(re.findall(r"expectimax2v?\w*", text[text.index("from './policy/expectimax2.mjs'") - 120:]))
    assert {"expectimax2v3", "expectimax2v3ref"} <= imported
    pol = (REPO_ROOT / "sim" / "policy" / "expectimax2.mjs").read_text()
    names = set(re.findall(r"export const EXPECTIMAX2\w* = '([\w-]+)'", pol))
    assert names == set(MC.modelled_table())


def test_offered_uses_the_table():
    assert MC.offered("MOVE_TOXIC", "expectimax2-v2") == (True, "")
    ok, why = MC.offered("MOVE_RAIN_DANCE", "expectimax2-v2")
    assert not ok and why == "not offered: not modelled by expectimax2-v2"
    ok, why = MC.offered("MOVE_SCREECH", "expectimax2-v2")
    assert not ok and why.startswith("foe_drop: stat stages reset")
