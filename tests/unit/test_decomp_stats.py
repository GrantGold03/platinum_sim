"""Stat formula port (src/pokemon.c:564 Pokemon_CalcStats, :2593 Pokemon_GetNatureStatValue).

Hand-worked cases; base stats copied from data.json, nature rows from sNatureStatAffinities.
HP    = (2*B + IV + EV/4) * L / 100 + L + 10
other = (2*B + IV + EV/4) * L / 100 + 5, then *110/100 (+) or *90/100 (-), integer division.
"""

from platsim.decomp.stats import calc_stats, nature_affinities, nature_name

# res/pokemon/garchomp/data.json:2-9 (hp 108, attack 130, defense 95, speed 102, spa 80, spd 85)
GARCHOMP = {"hp": 108, "atk": 130, "def": 95, "spa": 80, "spd": 85, "spe": 102}
# res/pokemon/gible/data.json:2-9 (hp 58, attack 70, defense 45, speed 42, spa 40, spd 45)
GIBLE = {"hp": 58, "atk": 70, "def": 45, "spa": 40, "spd": 45, "spe": 42}
# res/pokemon/shedinja/data.json:2-9 (hp 1, attack 90, defense 45, speed 40, spa 30, spd 30)
SHEDINJA = {"hp": 1, "atk": 90, "def": 45, "spa": 30, "spd": 30, "spe": 40}


def _all(v):
    return dict.fromkeys(("hp", "atk", "def", "spa", "spd", "spe"), v)


def test_garchomp_l62_iv30_quirky():
    # Cynthia's Garchomp shape: L62, IV 30, EV 0, neutral nature (Quirky).
    # hp : (216+30)*62/100 = 15252/100 = 152; +62+10 = 224
    # atk: (260+30)*62/100 = 17980/100 = 179; +5 = 184
    # def: (190+30)*62/100 = 13640/100 = 136; +5 = 141
    # spa: (160+30)*62/100 = 11780/100 = 117; +5 = 122
    # spd: (170+30)*62/100 = 12400/100 = 124; +5 = 129
    # spe: (204+30)*62/100 = 14508/100 = 145; +5 = 150
    got = calc_stats(GARCHOMP, _all(30), _all(0), 62, "NATURE_QUIRKY")
    assert got == {"hp": 224, "atk": 184, "def": 141, "spa": 122, "spd": 129, "spe": 150}


def test_garchomp_l100_jolly_evs():
    # src/pokemon.c:2507-2513 NATURE_JOLLY: speed +1, special attack -1.
    evs = {"hp": 4, "atk": 252, "def": 0, "spa": 0, "spd": 0, "spe": 252}
    # hp : (216+31+1)*100/100 = 248; +100+10 = 358
    # atk: (260+31+63) = 354; +5 = 359 (neutral)
    # def: (190+31) = 221; +5 = 226
    # spa: (160+31) = 191; +5 = 196; *90 = 17640; /100 = 176
    # spd: (170+31) = 201; +5 = 206
    # spe: (204+31+63) = 298; +5 = 303; *110 = 33330; /100 = 333
    got = calc_stats(GARCHOMP, _all(31), evs, 100, "NATURE_JOLLY")
    assert got == {"hp": 358, "atk": 359, "def": 226, "spa": 176, "spd": 206, "spe": 333}


def test_gible_l5_adamant_zero_ivs():
    # src/pokemon.c:2437-2443 NATURE_ADAMANT: attack +1, special attack -1.
    # hp : 116*5/100 = 580/100 = 5; +5+10 = 20
    # atk: 140*5/100 = 7; +5 = 12; *110 = 1320; /100 = 13
    # def: 90*5/100 = 4; +5 = 9
    # spa: 80*5/100 = 4; +5 = 9; *90 = 810; /100 = 8
    # spd: 90*5/100 = 4; +5 = 9
    # spe: 84*5/100 = 4; +5 = 9
    got = calc_stats(GIBLE, _all(0), _all(0), 5, "NATURE_ADAMANT")
    assert got == {"hp": 20, "atk": 13, "def": 9, "spa": 8, "spd": 9, "spe": 9}


def test_shedinja_hp_is_one():
    # src/pokemon.c:597-598: SPECIES_SHEDINJA -> max HP 1.
    # atk: (180+31)*50/100 = 10550/100 = 105; +5 = 110 (Hardy, neutral)
    got = calc_stats(SHEDINJA, _all(31), _all(0), 50, "NATURE_HARDY", species="SPECIES_SHEDINJA")
    assert got["hp"] == 1
    assert got["atk"] == 110


def test_nature_table_parsed():
    t = nature_affinities()
    assert len(t) == 25  # generated/natures.txt: 25 natures + NATURE_COUNT
    assert t["NATURE_ADAMANT"] == {"atk": 1, "def": 0, "spe": 0, "spa": -1, "spd": 0}
    # Pokemon_GetNatureOf (src/pokemon.c:2410): personality % 25; 28 % 25 = 3 = NATURE_ADAMANT
    # (generated/natures.txt:4)
    assert nature_name(28) == "NATURE_ADAMANT"
