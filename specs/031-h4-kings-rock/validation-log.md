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
