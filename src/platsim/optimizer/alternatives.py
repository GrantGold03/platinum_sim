"""Alternatives stage (007 T031/T032; spec FR-005, FR-007, FR-008, FR-017; research R5).

Replaces the old setup check. For each member of the level-search winner, in slot order, every
offered alternative (status moves swapped into its moveset; held items come with US2) is played by
the strong player that can use status moves (`move_classes.ALT_POLICY`) on paired seeds. It is
never eliminated by greedy-v1, which scores status moves as worth nothing (FR-007).

Generation (deterministic, sorted; spec FR-005):
- every replacement of the member's weakest attack, its second-weakest attack, or both, by offered
  status moves (user 2026-10-15; `all_slots=True` gives every slot, used by the feature 008 check);
- structured 3-4-status sets: for every choice of 3 or 4 categories the member can fill (inflict
  status, protection, recovery, Leech Seed, self-boost, screen), each category's first move in
  `_category_order` and, for a 3-status set, the member's best current attack in the 4th slot.
  The structured rule is a shortcut, validated against full 3-4-slot generation (moved to feature 008).
Every alternative is checked buildable at the comparison levels with the copies left (resources
.realize, required HMs included); one that is not is recorded with the refusal, never silently dropped.
The status moves of the alternative under test are marked `adopted`, so required-HM placement does
not displace the moves being measured (research R6).

Comparison levels: the current team's first failing neighbour of the uniform bisection (U - 1), where
a gain matters for the objective; the bisection levels when U - 1 is below the search bound.

Statistics (`mode="reference"`, the expensive version; Constitution VI):
1. Successive halving over all of the member's alternatives, rounds of r, 2r, 4r, 8r new paired runs
   (cumulative 15r; seeds derive_seed(f"{seed}|alternatives", i, 0), the same for every alternative),
   keeping the top third (at least 3) each round; ranking by gauntlets cleared, then battles won,
   then generation order.
2. The last round's top 3 are compared with the current team on a FRESH seed block that the screening
   never used (f"{seed}|alternatives-final|<slot>", `n_full` paired runs per arm: FINAL_RUNS = 800 in a
   qualifying budget), McNemar exact, Holm's correction over the three (FR-008, 2026-10-16).
3. The best significant one is adopted. (Before 2026-10-16 finalists were tested on the screening seeds,
   which selected them, and a confirm block followed; the T067 B4 run showed the inflation: Blissey
   91.5% vs 79.5% on the screening seeds, 82% vs 77.5% on fresh seeds.)
Every alternative's per-seed screening outcomes are kept as a bit string (`screening_bits`, seed order)
in state.json, for offline prefilter comparison (feature 008); result.json leaves them out.
Every alternative appears in the records with how far it got (spec FR-013, SC-003). The `confirmed`
field stays in each record (always null) so older reports and the Candidates sheet keep their columns.

The stage runs only with `candidates="reference"`; the default is `"off"` (Clarifications 2026-10-16).
Feature 008 takes over the reference benchmark, the 3-4-slot check of the structured rule, the
cheaper prefilter (accepted against this reference by Constitution VI) and FR-017 step 2.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, replace

from platsim.optimizer import candidates as C
from platsim.optimizer import item_classes as IC
from platsim.optimizer import move_classes as MC
from platsim.optimizer import resources as R
from platsim.sim.seeds import derive_seed
from platsim.stats import mcnemar_exact

OPPONENT = "decomp-ai"
ALPHA = 0.05
FINALISTS = 3
FINAL_RUNS = 800  # paired runs per arm for the finalist test in a qualifying budget (about 80% power for +5 points)
DEFAULT_ROUND = 25  # reference first-round size r (research R5: the 25-run minimum fits the 10 h share)
STRUCTURED_CATEGORIES = (MC.INFLICT_STATUS, MC.PROTECTION, MC.RECOVERY, MC.LEECH_SEED, MC.SELF_BOOST, MC.SCREEN)


@dataclass(frozen=True)
class Alternative:
    slot: int
    kind: str  # status | structured | status+item | structured+item | item
    moves: tuple[str, ...]
    item: str | None
    added: tuple[str, ...]  # the status moves this alternative brings in

    def key(self) -> tuple:
        return (self.kind, tuple(sorted(self.moves)), self.item or "")


# Preference within a category for structured sets (policy heuristic, not game data; to be validated in feature 008).
# Effects not listed rank after the listed ones. Within an effect: self-boosts by boost_score, others by
# accuracy (0 = never misses first), then key.
EFFECT_RANK = {
    MC.PROTECTION: ("BATTLE_EFFECT_PROTECT", "BATTLE_EFFECT_SET_SUBSTITUTE", "BATTLE_EFFECT_SURVIVE_WITH_1_HP"),
    MC.RECOVERY: ("BATTLE_EFFECT_RESTORE_HALF_HP", "BATTLE_EFFECT_HEAL_HALF_REMOVE_FLYING_TYPE",
                  "BATTLE_EFFECT_HEAL_HALF_MORE_IN_SUN", "BATTLE_EFFECT_HEAL_IN_3_TURNS", "BATTLE_EFFECT_REST",
                  "BATTLE_EFFECT_RESTORE_HP_EVERY_TURN", "BATTLE_EFFECT_GROUND_TRAP_USER_CONTINUOUS_HEAL"),
    MC.INFLICT_STATUS: ("BATTLE_EFFECT_STATUS_BADLY_POISON", "BATTLE_EFFECT_STATUS_SLEEP", "BATTLE_EFFECT_STATUS_PARALYZE",
                        "BATTLE_EFFECT_STATUS_BURN", "BATTLE_EFFECT_STATUS_SLEEP_NEXT_TURN", "BATTLE_EFFECT_STATUS_POISON"),
    MC.SCREEN: ("BATTLE_EFFECT_SET_REFLECT", "BATTLE_EFFECT_SET_LIGHT_SCREEN", "BATTLE_EFFECT_PREVENT_STATUS"),
}


def _category_order(const: str, moves: list[str]) -> list[str]:
    """Deterministic per-category preference for structured sets (EFFECT_RANK; to be validated in feature 008)."""
    from platsim.decomp.moves import load_moves

    mv = load_moves()

    def k(m):
        c = MC.move_class(m)
        ranks = EFFECT_RANK.get(c.category, ())
        r = ranks.index(c.effect) if c.effect in ranks else len(ranks)
        if c.category == MC.SELF_BOOST:
            return (r, -(C.boost_score(const, m) or 0.0), m)
        acc = mv[m].accuracy
        return (r, -(101 if acc == 0 else acc), m)
    return sorted(moves, key=k)


def generate(spec: R.MemberSpec, mc: C.MemberCandidates, slot: int, *, structured: bool = True,
             all_slots: bool = False, items=None) -> list[Alternative]:
    """`items(moves) -> [item key]`: the items offered with a moveset (item_classes.items_for); None = no item
    alternatives (US1 only)."""
    cur = tuple(spec.moves)
    status = [m for m in mc.legal_status if m not in cur]
    seen, out = set(), []

    def add(kind, moves, added, item=spec.item):
        a = Alternative(slot, kind, tuple(moves), item, tuple(sorted(added)))
        if (sorted(a.moves) == sorted(cur) and a.item == spec.item) or a.key() in seen:
            return
        seen.add(a.key())
        out.append(a)

    # the member's two weakest current moves by League value (status moves count 0), ties by slot
    # (user 2026-10-15: weakest two slots; to be checked against all slots in feature 008)
    slots = sorted(range(len(cur)), key=lambda j: (mc.scores.get(cur[j], 0.0), j))[:2] if all_slots is False else list(range(len(cur)))
    for j in slots:
        for m in status:
            mv = list(cur); mv[j] = m
            add("status", mv, [m])
    if len(slots) >= 2:
        for j, k in itertools.combinations(slots, 2):
            for a, b in itertools.combinations(status, 2):
                mv = list(cur); mv[j], mv[k] = a, b
                add("status", mv, [a, b])
    if structured:
        by_cat = {}
        for m in mc.legal_status:
            by_cat.setdefault(MC.move_class(m).category, []).append(m)
        cats = [c for c in STRUCTURED_CATEGORIES if c in by_cat]
        best_attack = max(cur, key=lambda m: (mc.scores.get(m, 0.0), m)) if cur else None
        for size in (3, 4):
            for combo in itertools.combinations(cats, size):
                picks = [_category_order(spec.species, by_cat[c])[0] for c in combo]
                mv = picks + ([best_attack] if size == 3 and best_attack and best_attack not in picks else [])
                add("structured", mv[:4], picks)
    if items is not None:
        from platsim.optimizer import item_classes as IC

        base_items = set(items(cur))
        for key in sorted(base_items - {spec.item}):  # item-only swaps on the current set
            add("item", cur, [], key)
        for a in [x for x in out if x.kind in ("status", "structured")]:  # move-item pairs (FR-006)
            for key in items(a.moves):
                if key in base_items or key == spec.item:
                    continue  # not made relevant by the added moves
                he = IC._by_key()[key].hold_effect
                if he in IC.PAIRED_EFFECTS or any(he in hs for hs in IC.effect_script_items().values()):
                    add(f"{a.kind}+item", a.moves, a.added, key)
    return sorted(out, key=lambda a: a.key())


def _requests(team, master, lo, hi, policy):
    return [{"op": "gauntlet", "team": team, "seed": derive_seed(master, i, 0), "player_policy": policy,
             "opponent_policy": OPPONENT, "stop_on_loss": True, "log": "none"} for i in range(lo, hi)]


def _check(rs, policy):
    for r in rs:
        if not r.get("ok"):
            raise RuntimeError(f"alternatives gauntlet failed: {r.get('error')}")
        if (r["player_policy"], r["opponent_policy"]) != (policy, OPPONENT):
            raise RuntimeError(f"worker ran {r['player_policy']}/{r['opponent_policy']}")


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, in the input order."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


def run_stage(*, pool, specs, cands, levels, led, seed: str, n_full: int, round_size: int,
              wteam, policy: str = MC.ALT_POLICY, members: int | None = None, progress=None, save=None,
              done: list | None = None, items: bool = True) -> tuple[tuple, list[dict]]:
    """Returns (specs after adoptions, records). `done`: records of members already finished (resume)."""
    records = list(done or [])
    specs = tuple(specs)
    finished = {r["slot"] for r in records if r.get("member_done")}
    master = f"{seed}|alternatives"
    rounds = [round_size * 2 ** k for k in range(4)]
    for slot in range(len(specs) if members is None else min(members, len(specs))):
        if slot in finished:
            adopted = next((r for r in records if r.get("member_done") and r["slot"] == slot), None)
            if adopted and adopted.get("adopted_spec"):
                specs = tuple(R.MemberSpec.from_dict(adopted["adopted_spec"]) if i == slot else s for i, s in enumerate(specs))
            continue
        spec = specs[slot]
        mc = cands[slot].get(spec.variant)
        team_species = tuple(s.species for s in specs)
        item_fn = (lambda moves, sp=spec.species: IC.items_for(sp, moves, team_species, led, policy)) if items else None
        alts = generate(spec, mc, slot, items=item_fn) if mc else []
        base = {"slot": slot + 1, "species": spec.species, "levels": list(levels), "mode": "reference"}
        teams, entries = [], []
        for a in alts:
            alt_spec = replace(spec, moves=a.moves, item=a.item, adopted=tuple(sorted(set(spec.adopted) | set(a.added))))
            alt_specs = tuple(alt_spec if i == slot else s for i, s in enumerate(specs))
            team = wteam(alt_specs, levels)
            e = {**base, "kind": a.kind, "moves": list(a.moves), "item": a.item,
                 "not_modelled": MC.not_modelled(policy, a.moves, a.item)}
            if team is None:
                e.update({"verdict": "not tested: not buildable at these levels with the copies left", "adopted": False})
                entries.append(e)
                continue
            teams.append((a, alt_specs, team, e))
            entries.append(e)
        # successive halving (cumulative paired seeds)
        results = {id(t[3]): [] for t in teams}
        alive = list(range(len(teams)))
        start = 0
        for r, n in enumerate(rounds):
            if not alive:
                break
            reqs = [q for c in alive for q in _requests(teams[c][2], master, start, start + n, policy)]
            res = pool.map(reqs)
            _check(res, policy)
            for k, c in enumerate(alive):
                results[id(teams[c][3])] += res[k * n:(k + 1) * n]
            start += n
            score = {c: (sum(bool(x["cleared"]) for x in results[id(teams[c][3])]),
                         sum(sum(bool(b["won"]) for b in x["battles"]) for x in results[id(teams[c][3])])) for c in alive}
            ranked = sorted(alive, key=lambda c: (-score[c][0], -score[c][1], c))
            last = r == len(rounds) - 1
            keep = ranked[:FINALISTS] if last else ranked[:max(FINALISTS, math.ceil(len(ranked) / 3))]
            for c in alive:
                e = teams[c][3]
                e.update({"round_reached": f"round {r + 1} of {len(rounds)}", "round_cleared": score[c][0],
                          "round_runs": len(results[id(e)]),
                          "screening_bits": "".join("1" if x["cleared"] else "0" for x in results[id(e)])})
                if c not in keep:
                    e.update({"verdict": "dropped in screening", "adopted": False})
            alive = keep
            if progress:
                progress(slot, r + 1, len(alts), len(alive))
        # finalists vs the current team on a fresh seed block (never used by the screening)
        cur_team = wteam(specs, levels)
        if cur_team is None:
            raise RuntimeError(f"alternatives: the current team cannot be built at {levels}")
        fmaster = f"{seed}|alternatives-final|{slot}"
        cur = [bool(x["cleared"]) for x in _run(pool, cur_team, fmaster, 0, n_full, policy)] if alive else []
        comps = []
        for c in alive:
            alt = [bool(x["cleared"]) for x in _run(pool, teams[c][2], fmaster, 0, n_full, policy)]
            comps.append((c, mcnemar_exact(alt, cur, ALPHA)))
        adj = holm([cmp.p_value for _, cmp in comps])
        winner = None
        for (c, cmp), ph in zip(comps, adj):
            e = teams[c][3]
            verdict = ("alternative better" if cmp.a_only > cmp.b_only else "current better") if ph < ALPHA and cmp.a_only != cmp.b_only \
                else "indistinguishable"
            e.update({"round_reached": "final", "n_paired": cmp.n, "rate_alt": cmp.a_rate, "rate_current": cmp.b_rate,
                      "alt_only": cmp.a_only, "current_only": cmp.b_only, "p_value": cmp.p_value, "p_holm": ph,
                      "verdict": verdict, "confirmed": None, "adopted": False})
            if verdict == "alternative better" and (winner is None or cmp.a_rate > winner[1].a_rate):
                winner = (c, cmp)
        member_rec = {**base, "member_done": True, "alternatives": len(alts), "buildable": len(teams), "adopted_spec": None}
        if winner:
            c, _ = winner
            a, alt_specs, team, e = teams[c]
            e["adopted"] = True
            specs = alt_specs
            member_rec["adopted_spec"] = specs[slot].to_dict()
        records.extend(entries)
        records.append(member_rec)
        if save:
            save(records)
    return specs, records


def _run(pool, team, master, lo, hi, policy):
    if hi <= lo:
        return []
    rs = pool.map(_requests(team, master, lo, hi, policy))
    _check(rs, policy)
    return rs


__all__ = ["Alternative", "DEFAULT_ROUND", "FINAL_RUNS", "FINALISTS", "generate", "holm", "run_stage"]
