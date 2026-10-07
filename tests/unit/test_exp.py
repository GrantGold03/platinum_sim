"""T016 exp table tests. Values copied from pokeplatinum/res/pokemon/.shared/exp_tables.csv."""

import pytest

from platsim.decomp.exp import exp_at, level_from_exp, load_exp_tables

# res/pokemon/.shared/exp_tables.csv:102 (level 100 row):
# 100,1000000,600000,1640000,1059860,800000,1250000,1000000,1000000
LEVEL_100 = {
    "EXP_RATE_MEDIUM_FAST": 1000000,
    "EXP_RATE_ERRATIC": 600000,
    "EXP_RATE_FLUCTUATING": 1640000,
    "EXP_RATE_MEDIUM_SLOW": 1059860,
    "EXP_RATE_FAST": 800000,
    "EXP_RATE_SLOW": 1250000,
    "EXP_RATE_6_UNUSED": 1000000,
    "EXP_RATE_7_UNUSED": 1000000,
}


def test_level_100_matches_csv():
    for rate, exp in LEVEL_100.items():
        assert exp_at(rate, 100) == exp
        assert level_from_exp(rate, exp) == 100
        assert level_from_exp(rate, exp + 12345) == 100  # loop ends at 101 -> 100


def test_level_2_row():
    # res/pokemon/.shared/exp_tables.csv:4  2,8,15,4,9,6,10,8,8
    assert exp_at("EXP_RATE_MEDIUM_FAST", 2) == 8
    assert exp_at("EXP_RATE_SLOW", 2) == 10


@pytest.mark.parametrize("rate", list(LEVEL_100))
def test_boundaries(rate):
    # SpeciesData_GetLevelAt (src/pokemon.c:2378-2391): first i with table[i] > exp, return i-1.
    for n in range(2, 101):
        t = exp_at(rate, n)
        assert level_from_exp(rate, t - 1) == n - 1
        assert level_from_exp(rate, t) == n


def test_zero_exp_is_level_1():
    # csv rows 0 and 1 are both 0, so exp 0 -> level 1 (loop starts at i = 1).
    assert level_from_exp("EXP_RATE_SLOW", 0) == 1


def test_src():
    assert load_exp_tables().src[1] == "src/pokemon.c:2378"


# ---- T072: exp_gain / apply_exp (independent Python port of the decomp exp award) -------------
# Formula refs: BtlCmd_CalcExpGain src/battle/battle_script.c:2187-2248 and BattleScript_GetExpTask
# SEQ_GET_EXP_START :9725-9778. Base exp values are copied from res/pokemon/<species>/data.json:12
# ("base_exp_reward"). Arithmetic is integer division throughout, as in the C.

from platsim.decomp.exp import PartyMonExp, apply_exp, exp_formula, exp_gain  # noqa: E402

YANMEGA, GARCHOMP, SPIRITOMB, MAGIKARP = 198, 218, 168, 20  # data.json:12 of each species


def P(**kw):
    kw.setdefault("alive", True)
    kw.setdefault("in_mask", False)
    kw.setdefault("level", 57)
    return PartyMonExp(**kw)


def test_formula_constants_read_from_c():
    f = exp_formula()
    assert f.level_divisor == 7 and f.src["level_divisor"] == "src/battle/battle_script.c:2217"
    assert f.lucky_egg == (150, 100) and f.src["lucky_egg"] == "src/battle/battle_script.c:9750"
    assert f.trainer == (150, 100) and f.src["trainer"] == "src/battle/battle_script.c:9754"
    assert f.traded_foreign == (170, 100) and f.src["traded_foreign"] == "src/battle/battle_script.c:9759"
    assert f.traded == (150, 100) and f.src["traded"] == "src/battle/battle_script.c:9761"


def test_single_participant_trainer():
    # Aaron's Yanmega L49: 198*49 = 9702; 9702//7 = 1386; one participant -> gained 1386;
    # trainer: 1386*150//100 = 2079.
    a = exp_gain(YANMEGA, 49, [P(in_mask=True)] + [P()] * 5)
    assert (a.exp, a.gained, a.shared, a.n_gaining) == (1386, 1386, 0, 1)
    assert a.totals == (2079, 0, 0, 0, 0, 0)
    # wild (no trainer factor): 1386
    assert exp_gain(YANMEGA, 49, [P(in_mask=True)], trainer_battle=False).totals == (1386,)


def test_lucky_egg_then_trainer():
    # Cynthia's Garchomp L62: 218*62 = 13516; 13516//7 = 1930. Lucky Egg: 1930*150//100 = 2895;
    # trainer: 2895*150//100 = 4342 (4342.5 truncated).
    a = exp_gain(GARCHOMP, 62, [P(in_mask=True, lucky_egg=True), P(in_mask=False, lucky_egg=True)])
    assert a.exp == 1930
    assert a.totals == (4342, 0)  # a Lucky Egg holder outside the mask gets nothing


def test_exp_share_split():
    # exp 1930 (above). Slots 0 and 1 in the mask, slot 3 holds Exp. Share and did not take part.
    # gained = (1930//2)//2 = 965//2 = 482; shared = (1930//2)//1 = 965.
    # trainer: slot 0: 482*150//100 = 723; slot 3: 965*150//100 = 1447 (1447.5).
    party = [P(in_mask=True), P(in_mask=True), P(), P(exp_share=True), P(), P()]
    a = exp_gain(GARCHOMP, 62, party)
    assert (a.gained, a.shared, a.n_gaining, a.n_share) == (482, 965, 2, 1)
    assert a.totals == (723, 723, 0, 1447, 0, 0)
    # Slot 1 also holds Exp. Share: nShare = 2 -> shared = 965//2 = 482.
    # slot 1: (482 + 482)*150//100 = 1446; slots 0 and 3: 482*150//100 = 723.
    party[1] = P(in_mask=True, exp_share=True)
    assert exp_gain(GARCHOMP, 62, party).totals == (723, 1446, 0, 723, 0, 0)
    # A fainted Exp. Share holder is not counted and gets nothing (:2204, :9740): back to shared 965.
    party[1] = P(in_mask=True, exp_share=True, alive=False)
    a = exp_gain(GARCHOMP, 62, party)
    assert (a.n_gaining, a.n_share, a.gained, a.shared) == (1, 1, 965, 965)
    assert a.totals == (1447, 0, 0, 1447, 0, 0)


def test_traded_boosts():
    # Cynthia's Spiritomb L58: 168*58 = 9744; 9744//7 = 1392. trainer: 1392*150//100 = 2088.
    # same-language trade: 2088*150//100 = 3132; foreign: 2088*170//100 = 3549 (3549.6).
    # traded Lucky Egg holder: 1392*150//100 = 2088; *150//100 = 3132; *150//100 = 4698.
    one = lambda **kw: exp_gain(SPIRITOMB, 58, [P(in_mask=True, **kw)]).totals[0]  # noqa: E731
    assert one() == 2088
    assert one(traded=True) == 3132
    assert one(traded=True, foreign_language=True) == 3549
    assert one(traded=True, lucky_egg=True) == 4698


def test_minimum_one():
    # Wild Magikarp L1: 20*1//7 = 2. Six live participants: 2//6 = 0 -> raised to 1 (:2234-2236).
    a = exp_gain(MAGIKARP, 1, [P(in_mask=True)] * 6, trainer_battle=False)
    assert (a.exp, a.gained) == (2, 1) and a.totals == (1,) * 6
    # trainer factor on 1: 1*150//100 = 1.
    assert exp_gain(MAGIKARP, 1, [P(in_mask=True)] * 6).totals == (1,) * 6
    # with Exp. Share: (2//2)//6 = 0 -> 1; shared (2//2)//2 = 0 -> 1 (:2222-2229).
    a = exp_gain(MAGIKARP, 1, [P(in_mask=True)] * 4 + [P(in_mask=True, exp_share=True)] * 2, trainer_battle=False)
    assert (a.gained, a.shared) == (1, 1) and a.totals == (1, 1, 1, 1, 2, 2)


def test_u16_truncation():
    # `u16 exp` (:2216): (base*level)//7 is stored in 16 bits. No real species can overflow it
    # (255*100//7 = 3642), so this uses a SYNTHETIC base of 5000: 5000*100 = 500000;
    # 500000//7 = 71428; 71428 - 65536 = 5892.
    a = exp_gain(5000, 100, [P(in_mask=True)], trainer_battle=False)
    assert a.exp == 5892 and a.totals == (5892,)


def test_dead_and_max_level():
    # Dead mask member: not counted, gets nothing. 1392 to the one live member; *1.5 = 2088.
    assert exp_gain(SPIRITOMB, 58, [P(in_mask=True), P(in_mask=True, alive=False)]).totals == (2088, 0)
    # A live level-100 mask member IS counted in nGaining (:2204 checks only species and HP) but
    # gets nothing (:9740): gained = 1392//2 = 696; slot 0: 696*150//100 = 1044.
    a = exp_gain(SPIRITOMB, 58, [P(in_mask=True), P(in_mask=True, level=100)])
    assert a.n_gaining == 2 and a.totals == (1044, 0)


def test_apply_exp_multi_level_and_cap():
    # exp_tables.csv:59-61 medium_fast: L57 185193, L58 195112, L59 205379.
    assert apply_exp("EXP_RATE_MEDIUM_FAST", 57, 185193, 20186) == (59, 205379)
    assert apply_exp("EXP_RATE_MEDIUM_FAST", 57, 185193, 20185) == (58, 205378)
    # exp_tables.csv:101-102: L99 970299, L100 1000000 -> capped at 1000000 (pokemon.c:3507-3512).
    assert apply_exp("EXP_RATE_MEDIUM_FAST", 99, 970299, 100000) == (100, 1000000)
