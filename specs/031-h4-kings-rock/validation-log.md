# Validation log: feature 031 H4, King's Rock / Razor Fang

Branch `031-h4-kings-rock` from `main` 5d8650d, main checkout. Times US Eastern, read from the clock.

## T001 Setup (9:59 AM EST, 2026-11-24)

`git diff --stat main -- src sim tests pyproject.toml`: 0 lines. Before-values:

```
sim_code_hash platsim_code_hash: sha256:d305a55582d8a59722f853216eb8e82489d7cf924f3a14c218656671425f7e4a sha256:f3271a011f8a55146cccdac95b0b5baeecb638885f83dd0d4b4f493c16f2b974
divergence_ledger_version: sha256:821f33356f6a61bb
```

Scripts under `scripts/`: `acceptance.py` (029's; `runs/031-evidence`, seed `031-ident`, flinch-item holders reported),
`attribution.py` (appended items may gain `kings_rock` at the end; the pre-feature extras unchanged; new extras only of kind
`flinch_item`, held with `kings_rock`; anything else a defect), `equal_levels.py` (master `031-equal|B2`), `hand_check.py`
(appended flinch item and `flinch_item` extras per B2 member), `paired_policies.py` (030's, with `--master-suffix`).

## T002 Pre-feature side (9:59:40 to 10:12:35 AM EST, alone, exit 0; code identical to `main` 5d8650d)

B2 quick: levels [52, 50, 51, 50, 50, 53], clear 0.9280 [0.9019, 0.9475], wall 600.6 s: the same team as 030's branch winner
(030 shipped the defence-only player). Identity evaluations (seed 031-ident). Snapshot `evidence/candidates-main.json` (36 records).
Generation 1.7 s for six members, 7.2 s with the allocation.

## T003 and T004 Engine against the game (10:15 to 10:30 AM EST)

`sim/test/kings_rock.test.mjs` (Level-80 Crobat holding King's Rock, faster than Flint's Houndoom, which answers with Sunny Day; a
use counts when it damaged the target and the target survived; 400 seeds per rate):

| Case | Flinched | Rate | Game | 99% interval holds |
|---|---|---|---|---|
| Tackle (single hit) | 37 / 373 | 9.9% | 10% | yes |
| Double Kick (two hits, Lv-45 holder) | 68 / 400 | 17.0% | 19% (1 - 0.9^2) | yes; above the one-roll rate's interval |
| Air Slash (its own 30% plus the item) | 130 / 353 | 36.8% | 37% (1 - 0.7 x 0.9) | yes |
| Shield Dust, Inner Focus, substitute (set on the target by the test), slower holder | 0 / 100 each | 0 | 0 | yes |
| No item (control) | 0 / 100 | 0 | 0 | yes |

First run: the Double Kick case read 0/400 because a Lv-80 Crobat's super-effective Double Kick knocked Houndoom out (a fainted
target cannot flinch); the test now counts only surviving targets and uses a Lv-45 holder. No difference from the game: no ledger
entry, ledger version unchanged. Node suite in the next line of this log.
Node suite: # tests 418 # pass 417 # fail 1 
The one failure is `seeds.test.mjs` 'Showdown accepts a derived seed and replays identically': its two runs differ only in the `|t:|` timestamp line (a second boundary crossed, as in 030); rerun alone it passes (see the next commit). It does not touch the item.

## T005 to T009 The optimizer offers the flinch item (10:30 to 11:08 AM EST)

`candidates.py`: `KINGS_ROCK_FLAG`, `FLINCH_ITEM` (`kings_rock`), `EQUIVALENT_ITEMS = {kings_rock: (kings_rock, razor_fang)}`,
`kings_rock_affected`, `kings_rock_multi_hit` (15 moves); `extra_item_candidates` appends `kings_rock` last for a set with an affected
move; a `flinch_item` extra set per member variant (the best affected multi-hit move from the full legal list, since pruning may
drop it as dominated; swapped in for a same-type move, else the lowest-scoring move; 027's dead-move rule decides). `resources.py`:
`realize` gives a holder whose group item's copies are taken the next affordable item of the group (the report shows it).

**Finding at implementation, owner's decision**: with the planned swap (the lowest-scoring move) every multi-hit move came out dead
(Bone Rush, Fury Swipes, Fury Attack, Bullet Seed, Double Slap always do less than the member's other moves). The battle player picks
moves by damage only (030), so a dead multi-hit move would never be used and its flinches never happen. The owner chose the same-type
swap and keeping the dead-move rule: on the snapshot teams only Torterra (B5) gets a set: Earthquake, Stone Edge, Crunch, Bullet Seed
held with King's Rock (Bullet Seed in place of Wood Hammer); every other learner records "<move> is dead in the League". Multi-hit
King's Rock sets in general wait on the v4 retune (FUTURE-FEATURES). The FR-007 measurement therefore uses B5 and Torterra.

Tests: `tests/unit/test_kings_rock.py` (7: affected and multi-hit moves; appended last only with an affected move; Torterra's extra
and Clefable's reason; two holders realize as King's Rock and Razor Fang, a third refused; with Gliscor only one fits; the 36
snapshot members change only by `appended` items and `appended_extra` sets). The 028 and 029 snapshot tests ignore 031's additions
(`_without_031`); four whole-list pins updated. Item tests 28 passed. Hand check: every B2 set has an affected move and gets King's
Rock appended; no B2 member has a live multi-hit move. Fast suite **649 passed, 32 deselected, 4 xfailed**, exit 0.

## T010 and T011 Branch acceptance (11:09:06 to 11:26:53 AM EST, alone, exit 0) and the merge gate

| Measure | main | branch |
|---|---|---|
| B2 quick winner | levels [52, 50, 51, 50, 50, 53], clear 0.9280 | identical; flinch-item holders: none |
| Teams screened | 269 | 301 (item deviations 142 → 174: King's Rock) |
| Identity (ref, b2main) | | identical |
| Equal levels, 2,000 pairs | 0.9410 | 0.9410 (0 / 0, p 1); level diff +0.00 |
| Attribution, 36 members | | `appended` items on every member; Torterra (B5) also one `appended_extra`; 0 defects |
| Extras | 271 | 272 (Torterra's flinch_item set); dead moves in extras 56 → 56, all with reasons |
| Generation | 1.7 s / 7.2 s | 1.6 s / 7.0 s |

**Gate (FR-009): pass.**

**Bug found by T012's B5 quick search** (11:29 AM EST): `KeyError: 'flinch_item'` in the screen's per-kind count
(`run.EXTRA_KINDS` listed the 024/025 kinds only). B2 has no flinch_item extra, so acceptance did not reach it. Fixed (the kind added);
a guard test checks that every extra kind the candidates produce on B5 is known to the screen (fails without the fix, passes with
it). The fix only adds a counter key, so the B2 acceptance above is unaffected.
