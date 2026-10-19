# Future features

Planned work, not yet specified. Each item becomes its own small Spec Kit feature and branch, merged
after the user's hands-on testing (keep features small: about 3 stories / 30 tasks at most, one major
layer, short acceptance runs). Ordered roughly by priority; the order is a proposal, not a decision.

## 1. Re-slice 007 onto main (user decision 2026-10-19; in progress)

007 (`007-status-moves-items`) is not merged as one piece. Proposal: land it as small slices, each
benchmarked against main, so a regression points at one change. Triggered by the 2026-10-19 B2 run
(average final level 55.27 vs 53.49 on Oct 8; cause: the team's movesets, not the player; see the 007 validation-log).

1. Ledger item sources (Route 221, Pastoria, Amity Square). **Feature 008, merged 2026-10-19.**
2. Move and item classification (no optimizer behaviour change). **Feature 009, implemented 2026-10-19 from `9e1f065`; awaiting the user's test.** Item pairings move to slice 5 (only the alternatives stage uses them).
3. Variable-power attacks (Return, Grass Knot, Hidden Power, ...): paired runs on B1-B5. **Known regression
   (2026-10-19):** on B2 the 007 team clears 8-10 points less than the Oct 8 team under the same player and
   levels; 4 of 6 moveset changes add a variable-power move and drop coverage (Ice Beam, Close Combat). Find
   and fix the cause (candidate ranking and/or the greedy-v1 screen) before this slice lands.
4. expectimax2-v3 as the default player: paired v3 vs v2 on B1-B5. B2 check 2026-10-19: v3 >= v2 (p 0.025 on
   the Oct 8 team; tie on the 007 team).
5. Alternatives stage, off by default, with the item pairings.

## 2. Alternatives acceptance (moved out of 007 on 2026-10-16; was called "008", renumbered when the re-slice took 008)

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
- **Order.** After re-slice items 3 and 4, so a level change is attributable to Shift alone. It changes
  every result, so it lands on its own.

## 4. Plain-language user-facing output (added 2026-10-19)

- **Gap.** User-facing text carries internal labels and developer jargon. Found in user testing of slice 1:
  `platsim explain item:<x>` source lines end with "(007 dataflow: Return-aware calls / GetRandom+AddVar /
  save-var literals / C table)". Other outputs likely have similar text (unverified; not yet searched).
- **Scope.**
  1. Inventory every user-facing text surface: CLI output (`explain`, `validate`, `evaluate`, `optimize`
     progress), report files (xlsx, csv, `team.txt`, result.json `warnings`), and the web UI.
  2. Remove or rewrite feature numbers, task ids, internal function/rule names and implementation terms
     in plain language. Keep decomp file:line references (Constitution I: every claim cites its source).
  3. A test that fails if user-facing text contains internal labels (e.g. feature or task ids, "dataflow").
- **Size.** Text-only; no behaviour change. Result files differ only in wording, so same-seed runs must
  match apart from changed strings.

## 5. Smaller follow-ups

- Pickup ability as an item source (Leftovers, King's Rock), proposed after 007; after-battle Pickup/Honey
  Gather items are an accepted divergence.
- Payoffs past the 2-ply horizon (weather, Wish, Taunt, Substitute, Damp Rock): no helps-position at the
  2-ply reference (007 SC-008 partly met); needs a deeper reference.
- Carried over from 001 (2026-10-08, not rechecked since):
  - two stale comments in `sim/` (`sim/policy/greedy.mjs:2`, `sim/gauntlet.mjs:41`); fix with the next
    real sim change, because any `sim/` edit changes `sim_code_hash`;
  - with `--allow-trade-evolutions`, NPC-trade pre-evolutions (e.g. Gaspar's Haunter) as sources for the
    trade evolution;
  - `sim/` code hash in provenance;
  - the "? (unlimited)" item-source text;
  - an optimize resume test;
  - a cartridge or emulator comparison.
