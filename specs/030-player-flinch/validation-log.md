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

## Diagnosis of the B2 loss (owner's choice: diagnose; 4:40 to 5:14 PM EST; scripts in `evidence/diagnosis/`)

1. **Where** (`diag030.py`, the 146 discordant gauntlets replayed, all reproduced): the differences sit in the Cynthia battle in both
   directions (model lost 85 there that the reference won; won 54 there that the reference lost).
2. **What changed in play** (`diag030b.py`, full logs, Cynthia battle, 146 gauntlets): Garchomp Rock Slide 220 uses vs 27, Crunch 11
   vs 156; Floatzel Waterfall 360 vs 130, Crunch 40 vs 185; Cynthia's Pokemon flinched 106 times vs 25; in the 87 model losses more
   switches (1,976 vs 1,454) and longer battles (1,727 vs 1,310 turns). The realized flinch rate (106 in 580 uses of the two flinch
   moves) is close to what the model expects: the rule is right.
3. **Which half** (owner approved a diagnosis knob `flinch=attack|defend`, default play unchanged; B2, 2,000 pairs each against
   `flinch=0`): attack only 0.9375 vs 0.9465 (53 / 71, p 0.13); defence only 0.9490 vs 0.9465 (18 / 13, p 0.47). The harm is in valuing
   the player's own flinch chances.
4. **Why, in one position** (`probe030.mjs`, `probe030b.mjs`; Garchomp Lv 52 against Cynthia's Spiritomb): Rock Slide's score rises
   from 0.058 to 0.144 with flinch (Earthquake 0.201 is still chosen there). A flinched end state is worth 0.59 against 0.24 for its
   twin with the same HP for both Pokemon. The twin and the flinched state differ only in Spiritomb's last move, PP, "last move worked"
   flag and the move-hit record; changing any one of them changes the trainer-AI prediction at the second ply, which v4 takes from
   **one** sample (`kPly2=1`) seeded by the state: the flinched state's single draw predicted a switch. Each flinch outcome adds new
   distinct states with their own one-draw predictions, and the player takes the best estimate, so moves that spread into more noisy
   states win by luck (the optimizer's curse). This is the reading of one position, not a proof.
5. **Test of that reading** (B2, 2,000 pairs, 4 samples at the second ply in both arms): attack only 0.9485 vs 0.9545 (40 / 52, p 0.25).
   The deficit shrinks (-0.90 to -0.60 points) but does not vanish: sampling noise explains part of it. Side note: with 4 samples the
   reference arm itself clears 0.9545 against 0.9465 with one sample on the same seeds (not a paired test of that change).

## Diagnosis, continued (owner away; instruction: keep digging so King's Rock is chosen when best; 5:20 to 6:00 PM EST)

All on today's B2 winner, 2,000 pairs, the same seeds as T007 unless stated.

| Variant (A) | Reference (B) | A | B | only A / only B | p |
|---|---|---|---|---|---|
| attack, common random numbers below the root (`crn=1`) | `flinch=0&crn=1` | 0.9340 | 0.9510 | 47 / 81 | 0.003 |
| full, `crn=1` | `flinch=0&crn=1` | 0.9305 | 0.9510 | 49 / 90 | 0.0006 |
| `flinch=0&crn=1` (crn alone) | `flinch=0` | 0.9510 | 0.9465 | 75 / 66 | 0.50 |
| **full, move-hit fix** | `flinch=0` | 0.9335 | 0.9465 | 57 / 83 | 0.034 |
| attack, move-hit fix | `flinch=0` | 0.9385 | 0.9465 | 50 / 66 | 0.16 |
| full, own flinch odds at half weight (`flinchAtk=0.5`) | `flinch=0` | 0.9400 | 0.9465 | 33 / 46 | 0.18 |
| full, `kPly2=4` | `flinch=0&kPly2=4` | 0.9475 | 0.9545 | 45 / 59 | 0.20 |

- Common random numbers made it worse, so sampling noise is not the main cause; the bias is systematic.
- **A model bug found and fixed** (`flinchStop`): in the game a flinched Pokemon's turn still ends through `ClearFlags`, which clears
  its move-hit record (`battle_controller_player.c:4389`; the live AI tracker clears it on `|cant|`, `sim/ai/opponent.mjs:152`). The
  model did not, so the trainer-AI prediction after a flinch saw a hit the game had cleared, and predicted switches (31% in the
  Spiritomb probe, against none for the twin) that the game never makes. After the fix, flinched states are worth exactly their
  HP-equal twins (Garchomp/Spiritomb and Floatzel/Milotic probes); Rock Slide's flinch bonus in the Spiritomb position fell from
  +0.085 to +0.040 (below Crunch). Test added (11 flinch tests pass). The fix changed the B2 result little (0.9335 vs 0.9465).
- **Pre-existing gap, not fixed (would change today's v4)**: the model does not clear the move-hit record for the model's other
  "cannot move" turns either (sleep, full paralysis, freeze), while the game and the live tracker do. Recorded for a later feature.
- Replays of the new discordant games: Cynthia's Lucario (Steadfast) is rarely flinched (Speed boosts 4 vs 0), so Steadfast is not the
  cause. The model still prefers Rock Slide (140 vs 11) and Waterfall (169 vs 76) over Crunch (7 vs 93; 32 vs 110), e.g. Waterfall into
  a resisting Milotic, and switches more in the games it loses (1,870 vs 1,400). In the Floatzel/Milotic probe, the flinch is worth
  surviving a Dragon Pulse that otherwise knocks Floatzel out, a real gain within the two-turn view.
- Reading so far: every variant that values the player's own flinch odds comes out 0.6 to 1.3 points behind on these seeds; valuing
  only the foe's flinches is neutral to slightly better. Next: the same comparisons on fresh seeds (`--master-suffix fresh1`).

## Fresh seeds (6:05 PM EST)

On fresh B2 seeds (`--master-suffix fresh1`, 2,000 pairs): the fixed full model 0.9395 vs 0.9395 without flinch (70 / 70, p 1);
defence only 0.9410 vs 0.9395 (13 / 10, p 0.68). The deficit seen on the T007 seeds after the move-hit fix does not replicate.

**Re-check declared before running** (the T007 seeds were examined many times during the diagnosis, so the stop-rule re-check uses
a new seed set): the fixed full model (`expectimax2-v4`) against `expectimax2-v4?flinch=0`, 029's paired script with
`--master-suffix fresh2`, the reference team, the benchmark team and today's B2 winner, 2,000 pairs each, plus the `--self` pairing
control; the FR-008 rule applies unchanged (a supported loss on any team stops the feature).

## Declared re-check on fresh seeds `fresh2` (6:05:45 to 6:21:47 PM EST, alone, all exit 0)

| Check | n | With flinch (fixed) | Without | only with / only without | p | verdict |
|---|---|---|---|---|---|---|
| pairing control (`--self`, ref) | 200 | | | 0 / 0 | 1 | OK |
| reference team | 2,000 | 0.9715 | 0.9750 | 28 / 35 | 0.45 | indistinguishable |
| benchmark team | 2,000 | 0.9400 | 0.9495 | 66 / 85 | 0.14 | indistinguishable |
| **today's B2 winner** | 2,000 | **0.9375** | **0.9585** | **41 / 83** | **0.0002** | **supported loss** |

**FR-008: the fixed full model stops again.** Over B2's three seed sets with the fix: 57/83, 70/70, 41/83.

Move order and realized flinches (`diag030c.py`, 300 fresh2 gauntlets, Cynthia battles): the player's Rock Slide and Waterfall went
first every time (988 of 988); Cynthia's Pokemon flinched on 227 of those turns (23%: Waterfall 20%, Rock Slide 27% x hit), as modelled.
Targets: Milotic 613, Spiritomb 299, Togekiss 72. So the model's flinch values are internally right and are realized, yet trading
damage for flinch chances (e.g. Waterfall into a resisting Milotic instead of Crunch) loses over the Cynthia fight: the two-turn
search's leaf evaluation weighs avoiding one hit above the damage given up. Fixing that is a retune of v4's evaluation (all play),
not this feature.

For King's Rock (031): the optimizer measures a team by playing simulated battles, where the engine applies the item's flinches
whatever the player believes; a King's Rock team (multi-hit moves included) is credited with its flinches in the measurement even if
the player does not value its own flinch odds. What the player cannot do without the attack side is steer toward flinches.

**Next candidate declared before running**: defence only (`expectimax2-v4?flinch=defend`: the foe's flinches on the player, the
move-hit fix, Fake Out rule) against `flinch=0`, on new seeds `fresh3`, the three teams, 2,000 pairs each; FR-008 unchanged.

## Declared defence-only candidate on fresh seeds `fresh3` (6:28 to 6:38:29 PM EST, alone, all exit 0)

| Team | n | Defence only | Without flinch | only with / only without | p | verdict |
|---|---|---|---|---|---|---|
| reference team | 2,000 | 0.9815 | 0.9785 | 26 / 20 | 0.46 | indistinguishable |
| benchmark team | 2,000 | 0.9535 | 0.9480 | 35 / 24 | 0.19 | indistinguishable |
| today's B2 winner | 2,000 | 0.9435 | 0.9485 | 7 / 17 | 0.064 | indistinguishable |

**No supported loss: defence only passes FR-008.** Over B2's three seed sets defence only is even (18/13, 13/10, 7/17: 38 / 40).
Speed in these runs (order-confounded): 14.79 vs 15.98, 13.88 vs 14.88, 15.35 vs 16.42 gauntlets/s (about 7% slower), within the
25% bound. Status: stopped for the owner's decision between defence only (measured, shippable) and further work on the attack side
(the leaf evaluation's trade of damage against a flinch, a v4 retune).

## Owner's decision (committed 10:29 PM EST): ship defence only

v4's default becomes `flinch: 'defend'`. The 018 options pin and the flinch tests updated (the model's both-sides cases run with
`flinch: true`; a new test checks the default values only the foe's flinches); 12 flinch tests pass. The replay fixture's v4 entry
re-recorded for the new default (v1 and v2 entries unchanged). Node suite **414 pass, 0 fail**, exit 0. The defence-only player was
measured on fresh seeds `fresh3` (previous section); the T007 table above is the both-sides model's and stays as the record of why.

## T009 and T010 Branch acceptance (10:29:12 to 10:47:23 PM EST, alone, exit 0) and the merge gate

| Measure | main | branch (defence only) |
|---|---|---|
| B2 quick winner | levels [52, 50, 50, 50, 51, 53], clear 0.9440 | the same six with the same moves and items, levels [52, 50, 51, 50, 50, 53] (Staraptor +1, Floatzel -1), clear 0.9280; same average |
| Equal levels, 2,000 pairs | 0.9375 | 0.9375 (0 / 0, p 1); expected average final level 51.69 on both, diff +0.00 |
| Candidate snapshot, 36 members | | all identical (`snapshot_members_changed` 0) |
| Teams screened | 269 | 269, overlap 269 |
| Identity (ref, b2main) | | differ as expected (flinch changes play): ref in rates, per-battle and levels; b2main in expected final levels |
| Generation | 1.6 s / 7.0 s | 1.6 s / 7.0 s |

**Gate (FR-011): pass** for the shipped defence-only player: no supported loss on fresh seeds (previous sections), speed within the
bound, snapshot identical, equal-level comparison passes. The quick search's winner differs only in how one level is split between
Staraptor and Floatzel (the search's own noise between two codes whose players differ).

## T012 Gates (10:48:14 PM to 12:25:27 AM EST, alone)

Vendored engine diff against `main`: empty. `src` diff: empty (no ledger entry needed). `sim` diff: the player (`expectimax2.mjs`), the
knobs (`gauntlet.mjs`), the bench's v4-candidate support (`bench.mjs`), the tests (`flinch.test.mjs` new, the 018 options pin) and the
replay fixture's v4 entry. Hashes: sim sha256:d305a555… (changed, as expected), platsim sha256:f3271a01… (unchanged); ledger version
unchanged at sha256:821f33356f6a61bb. Node suite: **414 pass, 0 fail**, exit 0. Full pytest: **675 passed, 4 xfailed**, exit 0 (1:34:34).
