"""T072 (SC-006): final levels recomputed in Python from the battle logs.

For 200 seeded full gauntlets of the reference team (tests/fixtures/reference_team.json) the worker
(sim/gauntlet.mjs, exp layer sim/exp.mjs) reports `final_levels`. This test throws those numbers
away and recomputes them independently:

  - participation (sideGetExpMask) is rebuilt from the Showdown log, following the decomp:
      an enemy mon entering clears the mask and flags the player's active slot
      (BTLSCR_ENEMY / BTLSCR_SWITCHED_MON for an enemy: BattleSystem_ClearSideExpGain then
      BattleSystem_FlagBattlerExpGain, src/battle/battle_script.c:470-478, 512-521, 576-583);
      a player mon entering ORs in its slot (BTLSCR_PLAYER / BTLSCR_SWITCHED_MON for the player,
      :464-466, 512-517), only while the enemy's curHP != 0 (src/battle/battle_lib.c:1466-1468).
      In singles battlersSwitchingMask permanently holds BATTLER_PLAYER_2 and BATTLER_ENEMY_2
      (battle_lib.c:2031-2034), so only selectedPartySlot[0] is ever flagged (battle_lib.c:1465-1477);
  - "alive" is the player mon's HP when the exp is PAID, not when the enemy faints
    (MON_DATA_HP != 0, battle_script.c:2204 and :9740), read from the HP field of the log lines.
    The decomp only flags the payout when a mon faints (BtlCmd_PlayFaintAnimation sets
    SYSCTL_PAYOUT_EXP, battle_script.c:1800); subscript_grant_exp (CalcExpGain + GetExpTask) runs
    from BattleControllerPlayer_AnyExpPayout (src/battle/battle_controller_player.c:4449), whose
    callers are MOVE_END (:3968: after the move's recoil, AFTER_MOVE_MESSAGE :3486-3494, the faint
    loop :3820-3826 and Life Orb, TriggerAfterMoveHitEffects :4715-4775), the field / mon
    condition steps of the end of turn (:940-941, :1295-1296, before every step) and TurnEnd
    (:1846). Mapped onto the Showdown log: an enemy `faint` makes the award pending; it is paid at
    the next line that starts another action (`move`, `cant`, `switch`, `replace`, `turn`,
    `upkeep`, `win`, `tie`, the blank `|` line Showdown writes before the residual phase and
    before each turn loop, `t:`) or at the end of the log. In the residual phase (after the blank
    line, until `upkeep`) Showdown writes the faints of each residual handler right after it, so
    the award is paid at the first line after that run of `faint` lines;
  - each award is `platsim.decomp.exp.exp_gain` (an independent port of BtlCmd_CalcExpGain,
    battle_script.c:2187, and BattleScript_GetExpTask, :9685), with the enemy's base exp and level
    from the Python decomp readers (res/pokemon/<species>/data.json "base_exp_reward",
    src/platsim/decomp/trainers.py), the trainer factor on (every League battle is a trainer
    battle), held Lucky Egg / Exp. Share from the build (an item that the log shows ending is gone
    from then on), and the traded flag from the build (FR-008a, below);
  - levels follow Pokemon_ShouldLevelUp (src/pokemon.c:3501) via `platsim.decomp.exp.apply_exp`,
    starting from the exp table value at `start_level` and carrying over between battles.

Traded (BattleSystem_PokemonIsOT == FALSE, src/battle/battle_lib.c:6286): a build's explicit
`is_traded` / `foreign_language` (the worker's Build fields, sim/team.mjs) win; otherwise a
`source` of `npc_trade:SPECIES_X@...` is traded (FR-008a: in-game NPC trades are not OT) and is
foreign iff that trade's `language` in res/npc_trades/*.json differs from GAME_LANGUAGE
(meson.build `-DGAME_LANGUAGE=...`, used by src/game_version.c:4). Each flag falls back to the
source independently (a build with only `is_traded` still gets its language from the trade).

Assertions: every run's recomputed final levels equal the worker's exactly; the mean final
average level of the worker and of Python differ by <= 1 level (SC-006); final exp is equal too
(stricter: a wrong award can stay below a level-up). Positive control: the same recomputation with
the trainer x1.5 dropped must disagree with the worker. A 50-run variant with Lucky Egg, Exp. Share,
flagged trades and U-turn covers the paths the reference team never reaches.

Payout ordering (tests/fixtures/reference_team_handcalc.md): Showdown logs the enemy's faint before
the attacker's recoil / Life Orb KO; with the pending-award rule above such an attacker gets
nothing, as in the decomp. Known approximation shared with the worker: side-condition residuals
(Future Sight, Perish Song) are paid per Showdown handler, not at TurnEnd.

Player policy: greedy-v1 (expectimax2-v1 is ~20x slower and the policy only changes which moves
are chosen, not the exp rules under test). Opponent: decomp-ai (default). stop_on_loss false, so
all five battles run in every gauntlet. Env: PLATSIM_T072_N (default 200),
PLATSIM_T072_FIXTURE (default tests/fixtures/reference_team.json), PLATSIM_T072_WORKERS.
Run with -s to see the summary.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import cache

import pytest

from platsim import pins
from platsim.decomp.exp import PartyMonExp, apply_exp, exp_at, exp_gain
from platsim.decomp.items import load_items
from platsim.decomp.species import by_constant, load_species
from platsim.decomp.trainers import load_league
from platsim.sim.pool import WorkerPool
from platsim.sim.seeds import derive_seed

FIXTURE = pins.REPO_ROOT / os.environ.get("PLATSIM_T072_FIXTURE", "tests/fixtures/reference_team.json")
N = int(os.environ.get("PLATSIM_T072_N", "200"))
WORKERS = int(os.environ.get("PLATSIM_T072_WORKERS", str(os.cpu_count() or 1)))
MASTER = "t072-final-levels"
POLICY = "greedy-v1"
OPPONENT = "decomp-ai"
TRAINERS = ("aaron", "bertha", "flint", "lucian", "cynthia")
PP = pins.DECOMP_ROOT


def team_of(path) -> list[dict]:
    d = json.loads(path.read_text())
    return d.get("builds", d.get("team"))


# ---- decomp facts -------------------------------------------------------------------------------
@cache
def game_language() -> str:
    m = re.search(r"-DGAME_LANGUAGE=(LANGUAGE_\w+)", (PP / "meson.build").read_text())  # meson.build:74
    assert m, "GAME_LANGUAGE not found in pokeplatinum/meson.build"
    return m.group(1)


@cache
def npc_trade_languages() -> dict[str, str]:
    """SPECIES_* -> language of the NPC trade mon (res/npc_trades/*.json, set by
    NPCTrade_CreateMon, src/overlay006/npc_trade.c:145)."""
    out = {}
    for p in sorted((PP / "res" / "npc_trades").glob("*.json")):
        d = json.loads(p.read_text())
        out[d["species"]] = d["language"]
    return out


def traded_flags(build: dict) -> tuple[bool, bool]:
    src = build.get("source") or ""
    from_src = (False, False)
    if src.startswith("npc_trade:"):
        species = src.removeprefix("npc_trade:").split("@")[0]
        from_src = (True, npc_trade_languages()[species] != game_language())
    explicit = build.get("is_traded", build.get("traded"))
    traded = bool(explicit) if explicit is not None else from_src[0]
    foreign = build.get("foreign_language")
    return traded, bool(foreign) if foreign is not None else from_src[1]


@cache
def hold_effects() -> dict[str, str]:
    return {it.key: it.hold_effect for it in load_items().values()}


@cache
def league() -> dict[str, list[tuple[str, int, int]]]:
    """trainer key -> [(display name, level, base exp)] in party order."""
    consts = by_constant()
    out = {}
    for t in load_league():
        out[t.key.rsplit("_", 1)[-1]] = [(consts[m.species].name, m.level, consts[m.species].base_exp) for m in t.party]
    return out


# ---- recomputation ------------------------------------------------------------------------------
# Log lines that begin a new Showdown action (or phase): a pending award is paid before them.
ACTION_STARTS = frozenset({"move", "cant", "switch", "replace", "turn", "upkeep", "win", "tie", "", "t:"})

@dataclass
class Member:
    name: str  # Showdown nickname = decomp species name (upper case)
    rate: str
    level: int
    exp: int
    item: str | None
    traded: bool
    foreign: bool


@dataclass
class Award:
    battle: int
    turn: int
    fainted: str
    fainted_level: int
    base_exp: int
    mask: list[int]
    alive: list[bool]
    exp: int
    gained: int
    shared: int
    totals: list[int]
    levels_after: list[int] = field(default_factory=list)


def _hp(field_: str) -> int:
    return int(field_.split()[0].split("/")[0])  # "0 fnt" -> 0, "122/174 par" -> 122


def _iter_lines(lines: list[str]):
    """Showdown `|split|pX` is followed by the exact line, then the public copy: keep the first."""
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|split|"):
            yield lines[i + 1]
            i += 3
            continue
        yield line
        i += 1


def recompute(team: list[dict], logs: list[list[str]], trainers=TRAINERS, *, trainer_battle: bool = True,
              pay_at_faint: bool = False):
    """Recompute exp and levels from the logs (a Recomputed: final levels, final exp, awards, problems)."""
    species = load_species()
    effects = hold_effects()
    party = []
    for b in team:
        sp = species[b["species"]]
        traded, foreign = traded_flags(b)
        party.append(Member(sp.name, sp.exp_rate, b["start_level"], exp_at(sp.exp_rate, b["start_level"]),
                            b.get("held_item"), traded, foreign))
    names = [m.name for m in party]
    assert len(set(names)) == len(names), f"duplicate species in team: {names}"
    slot_of = {n: i for i, n in enumerate(names)}
    awards: list[Award] = []
    problems: list[str] = []

    for bi, (trainer, log) in enumerate(zip(trainers, logs)):
        opp = {name: (lvl, base) for name, lvl, base in league()[trainer]}
        hp = [1] * len(party)  # HP is restored between battles (sim/gauntlet.mjs)
        items = [m.item for m in party]
        active = None
        enemy = None
        enemy_hp = 0
        mask: set[int] = set()
        turn = 0
        pending: list[tuple[str, int, int]] = []  # enemies whose SYSCTL_PAYOUT_EXP bit is set
        residual = False

        def pay():
            # AnyExpPayout -> subscript_grant_exp: CalcExpGain (battle_script.c:2187) and
            # GetExpTask (:9685) with the HP and mask as they are now.
            for nick, lvl, base in pending:
                mons = [PartyMonExp(alive=hp[s] > 0, in_mask=s in mask,
                                    exp_share=effects.get(items[s] or "") == "HOLD_EFFECT_EXP_SHARE",
                                    lucky_egg=effects.get(items[s] or "") == "HOLD_EFFECT_EXP_UP",
                                    traded=m.traded, foreign_language=m.foreign, level=m.level)
                        for s, m in enumerate(party)]
                a = exp_gain(base, lvl, mons, trainer_battle=trainer_battle)
                for s, m in enumerate(party):
                    if a.totals[s]:
                        m.level, m.exp = apply_exp(m.rate, m.level, m.exp, a.totals[s])
                awards.append(Award(bi, turn, nick, lvl, base, sorted(mask), [x.alive for x in mons],
                                    a.exp, a.gained, a.shared, list(a.totals), [m.level for m in party]))
            pending.clear()

        for line in _iter_lines(log):
            p = line.split("|")
            if len(p) < 2:
                continue
            kind = p[1]
            if pending and (kind in ACTION_STARTS or ((residual or pay_at_faint) and kind != "faint")):
                pay()  # MOVE_END (:3968) / the next end-of-turn step (:940-941, :1295-1296)
            if kind == "":
                residual = True  # blank line: residual phase (or a turn loop start, ended by `t:`)
            elif kind in ACTION_STARTS:
                residual = False
            if kind == "turn":
                turn = int(p[2])
            elif kind in ("switch", "drag", "replace"):
                side, nick = p[2].split(": ", 1)
                lvl_m = re.search(r", L(\d+)", p[3])
                log_level = int(lvl_m.group(1)) if lvl_m else 100
                if side == "p1a":
                    active = slot_of[nick]
                    hp[active] = _hp(p[4])
                    if log_level != party[active].level:
                        problems.append(f"battle {bi} turn {turn}: {nick} enters at L{log_level}, "
                                        f"Python has L{party[active].level}")
                    if enemy is not None and enemy_hp:  # battle_lib.c:1466-1468
                        mask.add(active)
                else:
                    enemy = nick
                    enemy_hp = _hp(p[4])
                    if log_level != opp[nick][0]:
                        problems.append(f"battle {bi}: enemy {nick} L{log_level} != decomp L{opp[nick][0]}")
                    mask = {active} if active is not None else set()  # clear + flag (battle_lib.c:1456-1471)
            elif kind in ("-damage", "-heal", "-sethp") and len(p) > 3:
                side = p[2].split(": ", 1)[0]
                if side == "p1a":
                    hp[active] = _hp(p[3])
                elif side == "p2a":
                    enemy_hp = _hp(p[3])
            elif kind == "-enditem" and p[2].startswith("p1a: "):
                if "Knock Off" not in line:
                    items[active] = None
            elif kind == "faint":
                side, nick = p[2].split(": ", 1)
                if side == "p1a":
                    hp[slot_of[nick]] = 0
                    continue
                enemy_hp = 0
                lvl, base = opp[nick]
                pending.append((nick, lvl, base))  # only flagged here (battle_script.c:1800)
        pay()  # end of the log: the last action's MOVE_END
        for s, m in enumerate(party):
            m.item = items[s]
    return Recomputed([m.level for m in party], [m.exp for m in party], awards, problems)


@dataclass
class Recomputed:
    levels: list[int]
    exp: list[int]
    awards: list[Award]
    problems: list[str]


# ---- the runs -----------------------------------------------------------------------------------
def requests(team, n, master=MASTER):
    return [{"op": "gauntlet", "id": f"t072-{i}", "team": team, "seed": derive_seed(master, i, 0),
             "player_policy": POLICY, "opponent_policy": OPPONENT, "trainers": list(TRAINERS),
             "stop_on_loss": False, "log": "full"} for i in range(n)]


def run_gauntlets(team, n, master=MASTER):
    with WorkerPool(max(1, min(WORKERS, n))) as pool:
        res = pool.map(requests(team, n, master))
    assert all(r["ok"] for r in res), [r for r in res if not r["ok"]][:2]
    for r in res:
        assert r["player_policy"] == POLICY and r["opponent_policy"] == OPPONENT
        assert len(r["battles"]) == len(TRAINERS) == len(r["log"])  # stop_on_loss false: all five ran
    return res


@pytest.fixture(scope="module")
def runs():
    team = team_of(FIXTURE)
    res = run_gauntlets(team, N)
    return team, res, [recompute(team, r["log"]) for r in res]


def _avg(levels):
    return sum(levels) / len(levels)


def _first_diff(team, r, rc: Recomputed):
    """Diagnostic: the first award whose per-slot exp differs from the worker's exp_events."""
    ev = r["exp_events"]
    for k, a in enumerate(rc.awards):
        if k >= len(ev):
            return f"Python award {k} ({a}) has no worker event"
        w = [0] * len(team)
        for g in ev[k]["gains"]:
            w[g["slot"]] = g["exp"]
        if w != a.totals or ev[k]["fainted_level"] != a.fainted_level:
            return f"award {k}: Python {a} vs worker {ev[k]}"
    if len(ev) != len(rc.awards):
        return f"{len(ev)} worker events vs {len(rc.awards)} Python awards"
    return None


def _compare(team, res, rcs, label):
    lv_match = exp_match = 0
    bad = []
    for i, (r, rc) in enumerate(zip(res, rcs)):
        ok_lv = rc.levels == r["final_levels"] and not rc.problems
        ok_exp = rc.exp == r["final_state"]["exp"]
        lv_match += ok_lv
        exp_match += ok_exp
        if not (ok_lv and ok_exp):
            bad.append((i, rc.levels, r["final_levels"], rc.problems[:2], _first_diff(team, r, rc)))
    py_mean = sum(_avg(rc.levels) for rc in rcs) / len(rcs)
    w_mean = sum(_avg(r["final_levels"]) for r in res) / len(res)
    n_awards = sum(len(rc.awards) for rc in rcs)
    cleared = sum(bool(r["cleared"]) for r in res)
    print(f"\nT072 [{label}]: n={len(res)} policy={POLICY} opponent={OPPONENT} stop_on_loss=false "
          f"cleared={cleared}/{len(res)} exp awards recomputed={n_awards}")
    per_award = sum(_first_diff(team, r, rc) is None for r, rc in zip(res, rcs))
    print(f"T072 [{label}]: exact final-level matches {lv_match}/{len(res)}; "
          f"exact final-exp matches {exp_match}/{len(res)}; "
          f"runs with every award equal to the worker's exp_events {per_award}/{len(res)}")
    print(f"T072 [{label}]: mean final average level worker={w_mean:.4f} python={py_mean:.4f} "
          f"diff={abs(w_mean - py_mean):.4f}")
    for b in bad[:3]:
        print(f"T072 [{label}] MISMATCH:", b)
    return lv_match, exp_match, w_mean, py_mean, n_awards, bad


def test_final_levels_match_worker(runs):
    team, res, rcs = runs
    lv_match, _, w_mean, py_mean, n_awards, bad = _compare(team, res, rcs, FIXTURE.name)
    assert n_awards > 0  # the recomputation actually saw faints
    assert lv_match == len(res), bad[:3]
    assert abs(w_mean - py_mean) <= 1.0  # SC-006


def test_final_exp_match_worker(runs):
    """Stricter than levels: total exp must agree too (a wrong award can stay below a level-up)."""
    team, res, rcs = runs
    _, exp_match, *_, bad = _compare(team, res, rcs, FIXTURE.name + " exp")
    assert exp_match == len(res), bad[:3]


def test_positive_control_trainer_factor(runs):
    """Drop the trainer x1.5 (battle_script.c:9753-9755): the same check must fail."""
    team, res, _ = runs
    match = sum(recompute(team, r["log"], trainer_battle=False).levels == r["final_levels"] for r in res)
    print(f"\nT072 positive control (no trainer x1.5): exact final-level matches {match}/{len(res)}")
    assert match < len(res)


def test_positive_control_payout_ordering(runs):
    """Pay at the enemy's faint (Showdown's event order, the pre-fix rule) instead of at MOVE_END:
    the recoil / Life Orb KOs in these runs must make it disagree with the worker."""
    team, res, rcs = runs
    alt = [recompute(team, r["log"], pay_at_faint=True) for r in res]
    exp_match = sum(a.exp == r["final_state"]["exp"] for a, r in zip(alt, res))
    lv_match = sum(a.levels == r["final_levels"] for a, r in zip(alt, res))
    changed = sum(x.totals != y.totals for a, rc in zip(alt, rcs) for x, y in zip(a.awards, rc.awards))
    alt_mean = sum(_avg(a.levels) for a in alt) / len(alt)
    print(f"\nT072 positive control (pay at faint): exact final-exp matches {exp_match}/{len(res)}, "
          f"final-level matches {lv_match}/{len(res)}, awards changed {changed}, mean final average level {alt_mean:.4f}")
    assert exp_match < len(res) and changed > 0


def test_exp_items_variant():
    """The reference team has no exp items and greedy-v1 almost never switches voluntarily, so a
    50-run variant (not a legal team; only the exp rules matter here) exercises Lucky Egg, Exp. Share,
    explicitly flagged trades (worker Build fields `is_traded` / `foreign_language`, sim/team.mjs) and
    U-turn (a live switch-in joins the mask: several live participants split the exp)."""
    team = [dict(b) for b in team_of(FIXTURE)]
    for i in (0, 1):  # replace the last move with U-turn
        team[i]["moves"] = [*team[i]["moves"][:3], {"move": "u_turn", "source_kind": "tm", "detail": "T072 variant"}]
    team[0]["held_item"] = "lucky_egg"
    team[1]["held_item"] = "exp_share"
    team[2]["held_item"] = "exp_share"
    team[3]["is_traded"] = True
    team[3]["foreign_language"] = True
    team[4]["is_traded"] = True
    team[4]["held_item"] = "lucky_egg"
    n = min(N, 50)
    res = run_gauntlets(team, n, MASTER + "-items")
    rcs = [recompute(team, r["log"]) for r in res]
    lv_match, exp_match, *_, bad = _compare(team, res, rcs, "exp-items variant")
    awards = [a for rc in rcs for a in rc.awards]
    multi = sum(sum(1 for s in a.mask if a.alive[s]) > 1 for a in awards)
    per_award = sum(_first_diff(team, r, rc) is None for r, rc in zip(res, rcs))
    print(f"T072 [exp-items variant]: awards with >1 live participant={multi}; "
          f"with Exp. Share exp={sum(a.shared > 0 for a in awards)}; runs with every award equal to "
          f"the worker's exp_events={per_award}/{n}")
    assert multi > 0 and any(a.shared for a in awards)  # both paths were exercised
    assert lv_match == n and exp_match == n and per_award == n, bad[:3]

def test_log_parser_controls():
    """Participation and HP rules on a hand-made log (no worker): two participants share, a
    fainted participant gets nothing, and a new enemy resets the mask."""
    team = team_of(pins.REPO_ROOT / "tests" / "fixtures" / "legal_team.json")
    names = [load_species()[b["species"]].name for b in team]
    a_name, b_name = names[0], names[1]
    lvl = team[0]["start_level"]
    yan, sci = league()["aaron"][0], league()["aaron"][1]  # YANMEGA L49, SCIZOR L49
    log = [
        f"|switch|p1a: {a_name}|x, L{lvl}|100/100", f"|switch|p2a: {yan[0]}|y, L{yan[1]}|100/100", "|turn|1",
        f"|switch|p1a: {b_name}|x, L{lvl}|100/100", "|turn|2",
        f"|-damage|p2a: {yan[0]}|0 fnt", f"|faint|p2a: {yan[0]}",
        f"|switch|p2a: {sci[0]}|y, L{sci[1]}|100/100", "|turn|3",
        f"|-damage|p2a: {sci[0]}|0 fnt", f"|-damage|p1a: {b_name}|0 fnt", f"|faint|p2a: {sci[0]}",
        f"|faint|p1a: {b_name}",
    ]
    rc = recompute(team, [log], trainers=("aaron",))
    awards = rc.awards
    assert not rc.problems
    # Yanmega: mask {0, 1}, both alive: 198*49//7 = 1386; 1386//2 = 693; *150//100 = 1039
    # (res/pokemon/yanmega/data.json:12 base_exp_reward 198).
    assert awards[0].mask == [0, 1] and awards[0].totals[:2] == [1039, 1039]
    # Scizor: the mask was reset to {1} (the active slot) and slot 1 is at 0 HP -> nobody gains.
    assert awards[1].mask == [1] and awards[1].totals == [0] * len(team)


def test_log_parser_payout_ordering():
    """Decomp payout ordering on hand-made logs (no worker): exp is paid at MOVE_END, after the
    attacker's recoil (battle_controller_player.c:3486-3494, :3968), and in the end-of-turn phase
    after each step (:1295-1296)."""
    team = team_of(pins.REPO_ROOT / "tests" / "fixtures" / "legal_team.json")
    names = [load_species()[b["species"]].name for b in team]
    a_name = names[0]
    lvl = team[0]["start_level"]
    yan = league()["aaron"][0]
    head = [f"|switch|p1a: {a_name}|x, L{lvl}|100/100", f"|switch|p2a: {yan[0]}|y, L{yan[1]}|100/100", "|turn|1",
            "|", "|t:|1"]
    # 1) Recoil KO after the enemy's faint, same move: the attacker has 0 HP at MOVE_END -> nothing.
    log = [*head, f"|move|p1a: {a_name}|Brave Bird|p2a: {yan[0]}", f"|-damage|p2a: {yan[0]}|0 fnt",
           f"|faint|p2a: {yan[0]}", f"|-damage|p1a: {a_name}|0 fnt|[from] Recoil", f"|faint|p1a: {a_name}",
           "|", "|upkeep"]
    rc = recompute(team, [log], trainers=("aaron",))
    assert not rc.problems and len(rc.awards) == 1
    assert rc.awards[0].alive[0] is False and rc.awards[0].totals == [0] * len(team)
    # 2) Recoil that leaves the attacker alive: 198*49//7 = 1386 -> *150//100 = 2079.
    log2 = [l if "Recoil" not in l else f"|-damage|p1a: {a_name}|5/100|[from] Recoil" for l in log]
    log2 = [l for l in log2 if l != f"|faint|p1a: {a_name}"]
    rc2 = recompute(team, [log2], trainers=("aaron",))
    assert rc2.awards[0].totals[0] == 2079
    # 3) Residual: Yanmega's poison KO is paid before the player's poison step KOs slot 0 -> 2079.
    log3 = [*head, f"|move|p1a: {a_name}|Protect|p1a: {a_name}", "|",
            f"|-damage|p2a: {yan[0]}|0 fnt|[from] psn", f"|faint|p2a: {yan[0]}",
            f"|-damage|p1a: {a_name}|0 fnt|[from] psn", f"|faint|p1a: {a_name}", "|upkeep"]
    rc3 = recompute(team, [log3], trainers=("aaron",))
    assert rc3.awards[0].alive[0] is True and rc3.awards[0].totals[0] == 2079
    # 4) Same residual step (one weather handler damages both, faints follow): both at 0 -> nothing.
    log4 = [*head, f"|move|p1a: {a_name}|Protect|p1a: {a_name}", "|", "|-weather|Sandstorm|[upkeep]",
            f"|-damage|p2a: {yan[0]}|0 fnt|[from] Sandstorm", f"|-damage|p1a: {a_name}|0 fnt|[from] Sandstorm",
            f"|faint|p2a: {yan[0]}", f"|faint|p1a: {a_name}", "|upkeep"]
    rc4 = recompute(team, [log4], trainers=("aaron",))
    assert rc4.awards[0].totals == [0] * len(team)


def test_npc_trade_source_is_traded():
    """FR-008a from the team file alone: legal_team.json's Chatot (source npc_trade:SPECIES_CHATOT@...,
    no is_traded field) is traded, same language (res/npc_trades/charap_chatot.json LANGUAGE_ENGLISH,
    meson.build GAME_LANGUAGE=LANGUAGE_ENGLISH) -> x150/100: Yanmega 1386 -> 2079 -> 3118."""
    team = team_of(pins.REPO_ROOT / "tests" / "fixtures" / "legal_team.json")
    chatot = next(b for b in team if b["species"] == "chatot")
    assert "is_traded" not in chatot and traded_flags(chatot) == (True, False)
    assert traded_flags({**chatot, "foreign_language": True}) == (True, True)
    assert traded_flags({"source": "wild_slot:SPECIES_STARAVIA@X"}) == (False, False)
    a = exp_gain(198, 49, [PartyMonExp(alive=True, in_mask=True, traded=True, level=57)])
    assert a.totals == (3118,)
