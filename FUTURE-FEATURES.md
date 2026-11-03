# Future features

Planned work, plus a record of items already built (marked **Done**). Each item becomes its own small Spec Kit feature and branch, merged
after the user's hands-on testing (keep features small: about 3 stories / 30 tasks at most, one major
layer, short acceptance runs). Ordered roughly by priority; the order is a proposal, not a decision.

## 0. Held items, redone in small slices (user, 2026-10-26)

Built from the decomp and `main`, not from the 007-010 archive.

- **H1 Held-item sources** (feature 011, branch `011-held-item-sources`): the ledger's gift reader finds the
  Route 221 house, the Pastoria City SW house and Amity Square. Merged to `main` 2026-10-26 after the user's test.
- **H2** (revised by the user 2026-10-29) The optimizer never offers single-use held items (consumed when they
  trigger: Focus Sash, herbs, ...); berries stay allowed. Today it already offers none (HP berry, unlimited
  type boosts, Leftovers), so H2 makes the rule explicit and tested. The earlier plan (offer Focus Sash; Life
  Orb, which has 0 pre-Champion copies) is dropped. Feature 013, branch `013-no-single-use-items`: built and checked
  2026-10-29; **merged to `main` 2026-10-29** (user's go). For H3+: every candidate passes through the filter in
  `held_item_candidates` automatically (decomp reader `platsim.decomp.item_use`; excluded today: Focus Sash, White
  Herb, Mental Herb, Power Herb, Berry Juice).
- **H3** (feature 014, branch `014-damage-boost-items`, built and checked 2026-10-29; **merged to `main` 2026-10-29**):
  the optimizer offers the damage boosters chosen by hold effect (Expert Belt, Wise Glasses; Muscle Band has no
  pre-Champion copy). B2 at equal levels: branch team clears 0.8195 vs 0.7650 (McNemar p 1.0e-5).
- **H4+** One item group per feature, with the player learning each group where needed. Remaining groups
  (out of scope in H3): Choice Band / Specs / Scarf (the player must model choice lock first), Metronome, Wide
  Lens, King's Rock / Razor Fang, Razor Claw, Shell Bell, then Lum Berry and the resist berries. Life Orb has no
  pre-Champion copy. Reusable checks: `specs/014-damage-boost-items/scripts/` (B1-B5 candidate snapshot, B2
  equal-levels comparison). Items tied to status moves (Light Clay, weather
  rocks, Chesto Berry) wait for the status-move work (007's version was reverted; not on `main`, no item yet).
- Follow-up found in H1: objects hidden when a map loads and shown only by a gated script (Amity Square's
  walking partner) are treated as always visible; the partner condition is therefore not stated with the
  Amity sources. It never changes availability today (every starter qualifies).

## 1. Re-slice 007 onto main (user decision 2026-10-19; **stopped and reverted 2026-10-20**)

> **Reverted 2026-10-20 (user):** `main` was set back to the state before 007 was first implemented
> (code = `f88cdd0`, 007 spec/plan/tasks as of `2fa6059`). Slices 1-2 (features 008, 009, merged) are
> undone on `main`; slice 3 (010) was never merged. All branches (`007-status-moves-items`,
> `008-ledger-item-sources`, `009-move-item-classes`, `010-variable-power`) are kept on GitHub as an archive,
> and their specs and findings are kept under `specs/`. The text below is the record as it stood.

007 (`007-status-moves-items`) is not merged as one piece. Proposal: land it as small slices, each
benchmarked against main, so a regression points at one change. Triggered by the 2026-10-19 B2 run
(average final level 55.27 vs 53.49 on Oct 8; cause: the team's movesets, not the player; see the 007 validation-log).

1. Ledger item sources (Route 221, Pastoria, Amity Square). **Feature 008, merged 2026-10-19; reverted on `main` 2026-10-20 (branch kept).**
2. Move and item classification (no optimizer behaviour change). **Feature 009, merged 2026-10-19; reverted on `main` 2026-10-20 (branch kept).** Item pairings move to slice 5 (only the alternatives stage uses them).
3. Variable-power attacks (Return, Grass Knot, Low Kick, ...; **not Hidden Power**, user 2026-10-19: IVs are a uniform 15 by assumption): feature 010, paired runs on B1-B5. **Known regression
   (2026-10-19):** on B2 the 007 team clears 8-10 points less than the Oct 8 team under the same player and
   levels; 4 of 6 moveset changes add a variable-power move and drop coverage (Ice Beam, Close Combat). Find
   and fix the cause (candidate ranking and/or the greedy-v1 screen) before this slice lands.
4. expectimax2-v3 as the default player: paired v3 vs v2 on B1-B5. B2 check 2026-10-19: v3 >= v2 (p 0.025 on
   the Oct 8 team; tie on the 007 team).
5. Alternatives stage, off by default, with the item pairings.

## 2. Alternatives acceptance (moved out of 007 on 2026-10-16; was called "008", renumbered when the re-slice took 008)

> **Blocked (2026-10-27):** depends on 007's alternatives stage and expectimax2-v3, which were reverted on
> 2026-10-20 and are not on `main`. The budget below is the 007-era record.

Split into three, per the size rule:
- **(a) Reference benchmark.** Reference runs on B4, B5, B3 (about 31 h); checks of the structured-set and
  weakest-two-slots rules (old T066, T066b, T067). Records per-seed outcomes.
- **(b) Prefilter.** Cheaper versions compared offline against (a)'s recorded outcomes, then one live
  acceptance: SC-002 (no team worse) and SC-006 (at most 2.0x baseline time). Old T068, T069, FR-019.
- **(c) Default switch.** Make the prefilter the default if accepted; docs.

Budget: about 110 h of one-time runs in total for 007 + this work, 32.2 h used. Raw 007 evidence:
`runs/007-evidence/`.

## 3. Shift battle style (added 2026-10-19)

- **Gap.** Battles run in Pokemon Showdown, where only the side whose Pokemon fainted sends a
  replacement. So the simulator plays the game's **Set** style. Platinum's default is **Shift**: after the
  player KOs a foe, the game shows the trainer's next Pokemon and offers the player a free switch first.
  Probably makes results slightly pessimistic (unmeasured). Not yet in the divergence ledger (found by
  code search of `sim/` and the ledger, 2026-10-19; not confirmed by a battle trace).
- **Scope.**
  1. Divergence entry with the decomp's Shift-prompt code reference; user option Shift (game default) or
     Set (current behaviour), recorded in the fingerprint and provenance.
  2. Battle worker: after a foe faints, reveal the incoming foe to the player and offer a free switch
     before it enters.
  3. Player policies (greedy-v1, expectimax2-*) decide switch or stay with their existing matchup scoring;
     golden v1/v2 logs stay byte-identical under Set.
  4. Acceptance: paired Shift vs Set runs on a few benchmark teams, then the user decides the default.
- **Order.** Independent of the 007 work (reverted 2026-10-20); it can land on `main` as is. Land it alone, so a level change is attributable to Shift alone. It changes
  every result, so it lands on its own.

## 4. Plain-language user-facing output (added 2026-10-19)

- **Gap.** User-facing text carries internal labels and developer jargon. Found in user testing of slice 1:
  `platsim explain item:<x>` source lines ended with "(007 dataflow: Return-aware calls / GetRandom+AddVar /
  save-var literals / C table)". That label came with the slice 1 code, now reverted on `main`.
  Confirmed on `main` (user test of 011, 2026-10-26): `platsim explain item:occa_berry` shows five Iron Island
  Mawile lines, each with "needs a GBA ruby cartridge in slot 2 (FR-005) and the National Dex" twice (gate and
  reason) and a reason prefix "other_cartridge @src/overlay006/dual_slot_encounters.c:13:". "(FR-005)" is a spec
  requirement id and "other_cartridge" an internal gate name; the file:line citation stays. Other surfaces are
  not yet searched.
- **Scope.**
  1. Inventory every user-facing text surface: CLI output (`explain`, `validate`, `evaluate`, `optimize`
     progress), report files (xlsx, csv, `team.txt`, result.json `warnings`), and the web UI.
  2. Remove or rewrite feature numbers, task ids, internal function/rule names and implementation terms
     in plain language. Keep decomp file:line references (Constitution I: every claim cites its source).
  3. A test that fails if user-facing text contains internal labels (e.g. feature or task ids, "dataflow").
- **Size.** Text-only; no behaviour change. Result files differ only in wording, so same-seed runs must
  match apart from changed strings.

## 5. Fast test mode without the battle simulations (added 2026-10-26)

> **Done: feature 012, merged to `main` 2026-10-27.** Fast mode `uv run pytest -q -m "not battle_sim"`: 504 passed, 4 xfailed in 10 min; 26 battle tests;
> the split is checked in every run. See `specs/012-fast-test-mode/validation-log.md`. The scope below is history.

- **Gap (as of 2026-10-26; the full suite took 1 h 05 min on 2026-11-01 after features 015 and 016, and per-test
  timings are now recorded with `--durations=25` in their validation logs).** The full suite takes about 2.5 h,
  almost all of it in roughly 45 integration tests that run real Node / Showdown battles. The ~477 other tests (unit, ledger, explain, extract, web, browser) finish in about 10-12 min
  (measured: `tests/unit` 474 tests in 109 s, 010 log; unit + ledger/web/explain/extract 400 tests in 10 min, 003
  log). There is no single command that runs only those. Per-test timings have never been recorded; the split
  below is from file contents and earlier logs (estimates marked).
- **Battle-simulation files** (the slow set): `test_optimize_small.py` (two quick optimizations, est. 50-70 min),
  `test_policy_strength.py` (2,000 paired runs × 3 policies, est. 30-40 min), `test_evaluate.py` (2,000-run
  evaluations twice, est. 25-30 min), `test_final_levels.py`, `test_champion_topup.py`, `test_pool.py`,
  `test_ability_screen.py`, `test_worker.py` (est. 15-25 min together).
- **Scope.**
  1. A pytest marker (e.g. `battle_sim`) on every test that starts `sim/worker.mjs` or the optimizer, and one
     documented command for the fast mode (e.g. `uv run pytest -m "not battle_sim"`). The full suite stays the
     acceptance gate for merges.
  2. A guard test so a new battle-simulation test cannot be left unmarked (positive control: one known
     battle test must carry the marker; negative: the fast set starts no Node worker).
  3. Record per-test times once with `--durations=0` on a full run, to confirm the split and the fast mode's
     run time.
- **Size.** Test infrastructure only; no behaviour change. Small (one story).

## 6. Smaller follow-ups

- Magnitude, Wring Out, Crush Grip, Punishment: offer them once the strong player computes their power
  (neither expectimax2-v2 nor 007's v3 does; found in feature 010, research R5). On `main` no variable-power
  move is offered at all (`optimizer/candidates.py`: power 1 excluded; 010 was reverted).

- Pickup ability as an item source (Leftovers, King's Rock), proposed after 007; after-battle Pickup/Honey
  Gather items are an accepted divergence.
- Payoffs past the 2-ply horizon (weather, Wish, Taunt, Substitute, Damp Rock): no helps-position at the
  2-ply reference (007 SC-008 partly met, on the reverted 007 branch); needs a deeper reference.
- Carried over from 001 (2026-10-08, not rechecked since):
  - with `--allow-trade-evolutions`, NPC-trade pre-evolutions (e.g. Gaspar's Haunter) as sources for the
    trade evolution;
  - the "? (unlimited)" item-source text;
  - an optimize resume test;
  - a cartridge or emulator comparison.

## 7. expectimax2 speedups after 015 (added 2026-10-31)

Feature 015 (exact: memoised damage-formula inputs, constants resolved once) gave 2.02x single process on the
fixed set with byte-identical decisions. Evidence: `runs/015-evidence/scratchpad/prof/REPORT.md` (profile on
`main` c751fb2), `specs/015-exact-ai-speedups/validation-log.md`, research R2 and R7. Every item below must keep the
replay test (`sim/test/replay.test.mjs`) green if exact, or be a new policy name if not.

- **Done in feature 016 (2026-11-01, exact, 1.45x single process on top of 015; `specs/016-exact-damage-speedups/`).**
  From the post-015 re-profile (`runs/015-evidence/scratchpad/prof2/REPORT2.md`): the type-chart walk repeated per
  damage roll (12.9% + 4.8% prepare) → one plan per matchup replayed per roll (`damage.mjs` `typeChartPlan` /
  `replayTypeChart`, reference kept as `applyTypeChartDirect`); the AI's pre-variance damage recomputed per sample
  → memoised per decision in the adapter (`ai.preVariance`, with the `PLATSIM_AI_CHECK=1` control mode); the id
  mappers rebuilt cold per shadow adapter (3.8%) → one shared set per dex. Attribution 1.08x / 1.31x / 1.44x.
- **Done in feature 017 (2026-11-02, exact, 1.23x single process on top of 016; `specs/017-exact-dispatch-speedups/`).**
  From the post-016 re-profile (`runs/016-evidence/scratchpad/prof3/REPORT3.md`): (A) the trainer-AI interpreter
  executed 143 M instructions per bench run, 128 M of them `IfCurrentMoveEffectEqualTo` in two contiguous runs of 178
  and 152 checks → each run is answered by one parse-time table (`parse.mjs` `indexInstructions`, split at entry
  points; `ins.a` / `ins.jt` argument index; one interpreter loop with an `onStep` hook): 15.9 M steps after, 9.0x
  fewer, attribution 1.076x; (B) the policy's `damageTable` rebuilt its inputs from the live battle per miss (677 k
  conversions) → it reads the root adapter's 015 memo and copies before `fix()`, with `PLATSIM_AI_CHECK=1` now
  covering the structs: 1.087x; (C) `speedValuesNow` per sample and `speedInfo` per `resolveTurn` → one speed pair per
  adapter per decision (`ai.speedPair`, reference kept as `compareBattlerSpeedDirect`) and `speedInfo` once per state
  (247 k → 60 k calls): 1.037x. v2 1.014 → 1.244 gauntlets/s, v1 1.22x, pool 1.12x; `node sim/bench.mjs` reports
  `interp_steps`.
- **Exact, next in line (measured 2026-11-02 on `main` 6ab83b5 after 017, `runs/017-evidence/scratchpad/prof4/REPORT4.md`;
  shares of sampled time, block a).** (D) `Constants.get` 5.9% self over ~320 sites: the `calcDamage` switch re-resolves
  every case label per call (1.6%), `battlerAbility` three names per read (1.0%); resolve once per module into a frozen
  field table (est. 4-5%). (F, revised) the end-state merge in `resolveTurn` computes a ~200-char signature for every
  branch (1.05 M per run, 87% of signature calls, 3.5% self plus the Map lookups inside `resolveTurn`'s 6.7% self)
  while collapsing 0.5% of branches; a cheap pre-key (both actives' hp, status, idx + turn) repeats for only 3.6% of
  branches, so bucketing by pre-key and computing the full signature only inside a repeated bucket is exact and skips
  96% of them (est. 4-6%). (E) `damageOutcomes` memo per decision on (table entry, t.hp, t.maxhp, effect): 66% of
  620 k calls repeat, 3.6% self (est. 2%). (G) generalised compare-and-jump dispatch for `IfLoadedEqualTo` (407 checks
  in 294 runs, longest 7) and `IfMoveEqualTo` (49 in 16 runs, longest 11): at most about 2.5 M of the remaining 15.9 M
  steps, interpreter+cmds is 7.7% of time, est. under 1%: low value, deferred. (H, new) adapter per-battler read memos:
  `moveEffectsMask` 2.3% self, `battlerAbility` 1.6%, `sideOfBattler` 1.7%, `moveEffectsData` 1.1% recomputed on every
  read from an immutable shadow state; a per-decision memo per battler with the 015-017 lifecycle, freeze guard and
  CHECK would be exact (est. 4-5%), the round after this one. Specify draft for the next feature (D, F, E):
  `runs/017-evidence/scratchpad/prof4/specify_018.txt` (written before the user chose v4 first; it becomes 019 or later).
- **Exact, cross-decision.** Caches that persist across decisions: `damageTable` (10.1% category after 015, 77% hit
  rate within a decision), `matchupScore`. Need a cache key that proves the inputs are unchanged.
- **Exact, mechanical.** Hoist the remaining ~320 `K()` / `C.get` name lookups in `sim/ai` to pre-resolved fields
  (user decision 2026-10-31: out of 015, which made each a single memo read). `Constants.get` was 4.9% after 015 and
  6.3% after 016 (adapter 87 sites, cmds/battler 75, switch 53, calcdamage 47, misc 17, cmds/damage 13, moves 9, items 7,
  choose 6, opponent 4); `createAdapter` rebuilds its `K()` tables for each of the 54,779 shadow adapters per run.
- **Killed by the 015 profile (do not retry without new evidence).** Cloning / copy-on-write (0.7% of time);
  better prediction-cache keys (0.35% hit rate; coarse-key bound 11.6% of ply-2 calls); the end-state merge
  (collapses 0.5% of branches).
- **Feature 018 = `expectimax2-v4` (done 2026-11-02/03; `specs/018-expectimax2-v4/`).** The ladder (each knob alone,
  then the combination; 2,000 paired gauntlets vs v2 on four fixed teams, McNemar exact): switch beam 1 worse on the 014
  B2 main team (p 0.0065), dropped; kRoot 4, kPly2 1, floor 0.02 and 0.05 passed alone; the combination 4 / 1 / 2 / 0.05
  passed on all four teams (deficits 0.3 to 1.05 points, p 0.33 to 0.71). Speed 1.64x single process, 1.35x on the pool,
  B2 quick optimize 407 → 350 s. **Caveat on record**: near the 0.75 threshold (the v2 B2 team at its own levels) v4 is
  2 to 3 points weaker with p 0.006 (pooled p 0.007 over 4,000 pairs) and the quick B2 optimization settled one level
  higher on five of six members; the user adopted v4 as the default on the gate's letter with that cost documented;
  `--player-policy expectimax2-v2` keeps the reference. **Follow-ups**: (a) a milder set near the threshold (kRoot 4 +
  floor 0.05 without the second-ply cut, or kRoot 4 alone: both had no measurable deficit alone) tested on the
  near-threshold team with `paired_policies.py --teams file:<team.json>`; (b) the exact items D, F, E, H (above) are
  019+; (c) the ladder's four teams sat at 0.80 to 0.95 clear rate, so any future player comparison should include a
  team at the qualification threshold.

## 8. Ideas under assessment (user, 2026-11-03)

Raw ideas, not yet decided. Each goes through the Spec Kit `assess` extension (`.specify/assessments/<slug>/`: intake →
research → define → shape → decide) before any `/speckit-specify`. First-glance facts from the code and reports, to be
confirmed by the research stage:

- **E4 scope** (ideas 1 and 3; assessed 2026-11-03, `.specify/assessments/e4-scope/`, verdict **go** for a reshaped
  version). Research (stored 2,000-run reports, `scan_results.py`; one read-only timing run, `e4_time.mjs`): the four
  Elite Four battles are **70% of player decision time** (Cynthia 30%, though hers is the longest battle at 18.6 turns);
  Aaron, Bertha and Flint are at 0.996 or better in every stored run; **Lucian is the only Elite Four member who decides
  runs**, and on teams at 0.77 to 0.81 clear rate he decides 7 to 46% of the losses (bench-010 B3: Lucian 0.8945,
  gauntlet 0.7715, Cynthia conditional 0.8625, so a Cynthia-only rate would pass a failing team). Members arrive at
  Cynthia 0 to 2 levels above their start levels with PP spent and berries eaten. **Closed**: "drop the Elite Four,
  Cynthia only from the start levels" (wrong statistic, wrong state) and "ignore Elite Four exp" (no measurable time
  saving, lower fidelity; a Principle I divergence). **Going forward as Option C**: adaptive Elite Four sampling that
  generalises the Cynthia top-up: full gauntlets run until each Elite Four member's pass rate is proven (Wilson
  lower-bound floor), banking real post-Lucian states; the remaining runs are Cynthia-only from banked states; the
  gauntlet clear rate becomes Elite Four pass rate × Cynthia conditional rate with a conservative combined interval;
  Lucian-heavy teams degrade to the full gauntlet by construction. Ceiling 2 to 3x on strong teams against a 1.5x bar
  (baselines: `evaluate` reference 2,000 runs 769 s; B2 quick optimize 350 s). Three small features in order:
  (1) **spike, no behaviour change**: replay the composite estimate offline against the ten stored 2,000-run evaluations
  (must reproduce clear rate within the interval and the qualified / borderline verdict on every team, B3 included) and
  measure the Elite Four share inside one real level-search stage; kill criteria written in `decision.md`;
  (2) `evaluate` with adaptive sampling, paired against the full gauntlet on the four 018 ladder teams plus one
  Lucian-heavy team, full gauntlet kept behind a flag as the reference; (3) the optimizer stages on the same estimator,
  B2 quick end to end at equal levels. Fallbacks if the spike fails: a cheaper player for Aaron / Bertha / Flint only
  (ceiling about 1.6x, needs greedy-v1's per-trainer rates measured first), else nothing, with the numbers recorded.
  Two product questions left for `/speckit-clarify`: wall time the only goal; a team-dependent saving acceptable.
  **Feature 019 spike result (2026-11-03, `specs/019-e4-sampling-spike/`, no behaviour change): no-go as specified, conditional go.**
  (1) Estimator vs the ten stored evaluations: point estimates agree within 0.004 on all ten and every interval contains the stored
  rate, but the plan's Bonferroni product interval (two 97.5% Wilson factors; 1.3 to 1.6x wider than the binomial) makes the four
  teams within two points of 0.75 (bench-010 B2, B3, t076/v8, job-2d8f18) borderline where the stored verdict is above: FAIL on the
  threshold verdict; the standard delta-method interval agrees on all ten. (2) Replay on two fresh 2,000-run recordings: on the
  reference team the rule switches to Cynthia-only in every order at every floor (share 0.91 / 0.81 / 0.43 at floors 0.98 / 0.99 /
  0.995 after 189 / 381 / 1,131 full runs) with the verdict unchanged in 100% of orders; on B3 Lucian never clears any floor: PASS.
  (3) In-stage share on the pool (stop-on-loss, batches 50 to 200, harness proven by identical digests): Elite Four 0.72 to 0.75 of
  battle time: PASS. Projection: 2.63 to 2.87x at floor 0.98, 1.85 to 2.40x at 0.99 on a reference-team evaluation (model baseline
  255 s with v4); B2 quick bracket 1.00 to 1.38x. **Decision needed**: amend 021's interval to the delta method (then go: every
  criterion met) or keep Bonferroni (then threshold teams need 2,700 to 5,600 full runs to resolve, and the method is not built).
  **User decision 2026-11-03: adopt the delta-method interval for feature 021 → go.** 021 (adaptive sampling in `evaluate`) is
  specified with the delta interval as the method's interval; its paired acceptance against the full gauntlet checks it on real runs.
- **Lead per fight** (idea 2; assessed 2026-11-03, `.specify/assessments/lead-per-fight/`, verdict **go** for a reshaped
  version). Game rule confirmed in the decomp: the start menu opens on any map but the Mystery Zone (`src/start_menu.c:261`),
  the Elite Four room scripts release control after each win, the party menu's Switch reorders, and the battle lead is
  the first living non-egg slot (`battle_controller_player.c:4097`). Today the lead is the first species in the optimize
  request (`OptimizeRequest.species` order = team order) and nothing reports it. Measured (100 paired gauntlets per lead,
  v4, `measurement/`): the six fixed leads span **12, 8 and 15 points of clear rate** on the bench, reference and 018 B2
  teams, almost all at Cynthia (Aaron and Flint 100/100 under every lead); best fixed lead vs slot 1: +6, +2, 0 (not
  significant at n 100; B2's first-listed Garchomp was already best). **A per-fight lead adds under one point over the
  best fixed lead** on all three teams (per-trainer best-lead product 0.921 / 0.980 / 0.830 vs best fixed 0.92 / 0.98 /
  0.83), so the idea as stated is closed with its numbers (reopen only on a team with a per-trainer lead conflict).
  **Going forward as "choose and report the lead"**, small features in order: (1) spike: six leads × 2,000 paired
  gauntlets on the two optimizer-built 014 B2 teams, McNemar best vs first-listed, plus a 400-pair subset to size a
  screening check; (2) the lead named in every output (team.txt, result.json, xlsx/csv, web) and the rule documented,
  no behaviour change; (3) only if the spike shows a supported gain: a paired six-lead check in the optimizer's
  confirmation stage (screening-sized, best lead confirmed at full size, team written with it first), `evaluate
  --lead-check`, the no-check path kept as the reference; B2 quick at equal levels with the lead's own exp gain (0.7 to
  1.4 levels) reported separately. Cheapest after e4-scope's Cynthia-only phase exists, but independent of it.
  **Feature 020 spike result (2026-11-03, `specs/020-lead-spike/`, no behaviour change): no-go for the confirmation-stage check;
  the reporting follow-on stands.** Six leads × 2,000 paired gauntlets (v4) on three optimizer-built teams: spreads 9.2 / 10.2 / 8.7
  points (b2main, b2branch, 018 v2 B2), almost all at Cynthia (up to 8 points) with Lucian up to 3.5. Best lead chosen on the first
  1,000 pairs and tested on the second 1,000 (McNemar exact, so the best-of-six selection never touches the test): b2main chose
  Staraptor, held-out +2.0 points, only-chosen 85 / only-first 65, p 0.121 (naive 2,000-pair p 0.0695, selection-biased); b2branch and
  b2v2: the first-listed Garchomp was already best (0 discordant). Pairing control 0 discordant on all three. Screening: 200 pairs
  picked the 1,000-pair lead on all three teams, 400 pairs missed on b2main. Exp coupling: the lead gains 0.9 to 2.0 levels, Garchomp
  leading the most (+0.85 over the others' mean). **Follow-ons**: (a) the lead named in every output and the rule documented (go,
  small); (b) no confirmation-stage lead check now; reopen if a future optimizer-built team shows a held-out gain, e.g. by adding a
  cheap first-half-of-confirmation lead screen as a report-only column.
