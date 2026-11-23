# Validation log: feature 030, the battle player models flinch

Branch `030-player-flinch` from `main` 9877958, main checkout. Times US Eastern.

## T001 Setup (3:52 PM EST, 2026-11-23)

`git diff --stat main -- src sim tests pyproject.toml`: 0 lines. Before-values:

```
sim_code_hash platsim_code_hash: sha256:913f9f0c381b70c19212477c76b55c78b72aa48ebd282463315485c29985b048 sha256:f3271a011f8a55146cccdac95b0b5baeecb638885f83dd0d4b4f493c16f2b974
divergence_ledger_version: sha256:821f33356f6a61bb
```

Scripts copied from 029 under `scripts/`: `acceptance.py` (`runs/030-evidence`, identity seed `030-ident`; identity differences
reported, not failures; the pass rule requires every snapshot member identical, `snapshot_members_changed == 0`), `attribution.py`,
`equal_levels.py` (master `030-equal|B2`), `paired_policies.py` (029's, with `--battle-style`).

## T002 Pre-feature side (3:52:29 to 4:07:06 PM EST, alone, all exit 0; code identical to `main` 9877958)

B2 quick: levels [52, 50, 50, 50, 51, 53], clear 0.9440 [0.9203, 0.961], wall 641.3 s: the same winner as 027 to 029. Identity
evaluations (seed 030-ident). Snapshot `evidence/candidates-main.json` (36 records). Generation 1.6 s for six members, 7.0 s with the
allocation. **v4 bench digest on `main`** (`node sim/bench.mjs --policy expectimax2-v4`, 40 gauntlets): digest_full `05fa8cb1…`,
digest_logs `624cbb4c…` (`evidence/pre/v4-main-bench.json`). Today's B2 winner written to `runs/030-evidence/teams/b2-main.json` and
validated by the evaluate loader (analyze U1).

## T003 Engine against the game (between 4:07 and 4:16 PM EST)

`sim/test/flinch.test.mjs` part 1 (Flint's Houndoom, Lv 52, Dark Pulse 20%): (a) a faster Dark Pulse flinches a level-60 Bronzong on
some seed of 40 and the Bronzong does not move; (b) over 30 seeds a slower Dark Pulse never flinches a faster Crobat; (c) Inner Focus
Lucario never flinches over 40 seeds; (e) Steadfast Lucario (Speed forced below Houndoom's) flinches on some seeds and each time logs
`-boost ... spe 1`; (f) Fake Out flinches on its user's first turn and fails on the second. (d) Substitute: by source (the game's
`CheckSubstitute` in `subscript_flinch_mon.s`; the engine applies no secondary effect through a substitute). All agree with the game:
no ledger entry; ledger version unchanged.

## T004 to T006 The player models flinch (4:07 to 4:16 PM EST; the times first written here were estimates, corrected from the T007 start time)

`sim/policy/expectimax2.mjs`: `FLINCH_EFFECTS` (eight effects); `flinchChance` (zero unless the target still moves this turn, the
owner's rule; survived; no substitute; no Inner Focus unless Mold Breaker; chance x2 Serene Grace); in `execMove` each landing outcome
splits into a flinched copy and the rest; in `doMove` a flinched Pokemon loses its move after the sleep and freeze checks and before
paralysis (the game's order), Steadfast +1 Speed; `endOfTurn` clears the mark; Fake Out fails after the first turn out. `V4_OPTS`
gains `flinch: true` (v1 and v2 off). `sim/gauntlet.mjs`: knob `flinch=0|1`. `sim/bench.mjs` now accepts v4 candidate names (it
rejected `expectimax2-v4?flinch=0`; it uses the gauntlet's own resolver).

Two corrections found by the tests:
- The engine counts a Pokemon's turns out at the start of each turn, so a lead's first decision reads 1. The Fake Out rule is
  "fails when activeTurns > 1", not "> 0" as research R3 said.
- Two test setups were wrong, not the model: a Speed tie (Bronzong Lv 100 and Houndoom both 107: flinch mass 0.10 = 0.20 x 0.5), and
  knockouts by a Lv-100 Crobat (a fainted target cannot flinch). Lowered to Lv 60; exact masses then 0.20 and 0.30 x 0.95.

Model tests (part 2, 6 tests): flinch masses exact; **no extra branch and identical probabilities when the flinch move's user moves
second** (FR-012); substitute, Inner Focus, Serene Grace (0.6); Steadfast +1 Speed in exactly the 0.20 flinched mass and no mark left
after the turn; Fake Out first turn only. All 10 tests pass.

**v4 with the switch off equals `main`'s v4** (FR-006, SC-002): the bench of `expectimax2-v4?flinch=0` has the same logs digest
(`624cbb4c…`), decisions (2,853), AI draws (343,327) and interpreter steps (6,526,653) as `main`'s v4; the full digest differs only by
the policy name each result carries. Positive control: v4 with flinch on changes play (36 vs 37 cleared of 40, 348,933 AI draws).

**Correction of analyze finding C1**: the replay fixture holds v1, v2 **and** v4 (I relied on the test file's header comment). v1
and v2 entries are byte-identical; the v4 entry was re-recorded (`node sim/bench.mjs --policy expectimax2-v4 --record`), the
fixture's own rule for an intended decision change; the identity proof for the switch-off player is the bench comparison above.
The 018 options pin gains `flinch: true`. Node suite: **412 pass, 0 fail**, exit 0 (one earlier run failed the seed test on its
`|t:|` timestamp line crossing a second boundary; it passed on rerun and does not touch the player). greedy-v1 untouched (`git diff
main -- sim/policy/greedy.mjs` empty).

## T007 and T008 Player check and speed (4:17:32 to 4:38:57 PM EST, alone, all exit 0)

029's paired script under Shift, model `expectimax2-v4` against reference `expectimax2-v4?flinch=0`, same seeds per pair.

| Control or check | n | Model | Reference | only model / only reference | p | verdict |
|---|---|---|---|---|---|---|
| pairing control (`--self`, ref) | 200 | 0.9600 | 0.9600 | 0 / 0 | 1 | OK |
| reference team | 2,000 | 0.9710 | 0.9745 | 28 / 35 | 0.45 | indistinguishable |
| benchmark team | 2,000 | 0.9550 | 0.9535 | 66 / 63 | 0.86 | indistinguishable |
| **today's B2 winner** | 2,000 | **0.9325** | **0.9465** | **59 / 87** | **0.025** | **supported loss** |

Conditions control: the reference arm on today's B2 winner, 0.9465, lies within the optimizer's 0.944 [0.920, 0.961] for that team.

Speed (SC-004, both orders on ref, 500 pairs each): model 11.61 (first) and 13.21 (second), mean 12.41 gauntlets/s; reference 13.94
(second) and 12.03 (first), mean 12.99. Ratio 0.956: the model is about 4% slower, within the 25% bound.

**Gate (FR-008): a supported loss on today's B2 winner. The feature stops here for the owner's decision**; no acceptance run, no merge.
Notes for that decision: the three teams were each tested at the 0.05 level (with a Bonferroni correction for three tests, 0.0167,
p 0.025 would not be supported; the spec's rule is per team, so the stop stands unless the owner changes the rule). The stored results
keep only cleared or not per gauntlet, so locating the extra losses (which trainer, which decisions) needs a replay of the 87
reference-only seeds with flinch on.
