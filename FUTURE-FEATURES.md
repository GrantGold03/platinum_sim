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
- **H4+** One item group per feature, with the player learning each group (Choice Specs / Expert Belt / Wise
  Glasses and similar, then resist berries / Lum Berry, ...). Items tied to status moves (Light Clay, weather
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

- **Gap.** The full suite takes about 2.5 h, almost all of it in roughly 45 integration tests that run real Node /
  Showdown battles. The ~477 other tests (unit, ledger, explain, extract, web, browser) finish in about 10-12 min
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
