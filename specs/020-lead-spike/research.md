# Research: Lead Spike

## R1. Rotation rule

- **Decision**: lead i's party is `[team[i]] + [m for j, m in enumerate(team) if j != i]`: the chosen member first, the
  others in their existing relative order. Lead 0 is the first-listed order itself (Garchomp first on all three
  teams), so its recording is the reference row and no duplicate run is made.
- **Rationale**: the game's party Switch swaps two slots; moving one member to the front and keeping the rest in
  order is what a player does to set a lead, and it is what the assessment measured.
- **Alternatives considered**: swapping member i with slot 1 (changes a second member's position too; rejected).

## R2. Choosing the best lead on the first half

- **Decision**: on pairs 0..999 (run indices), the lead with the highest clear count; ties go to the lowest member
  index and are reported. The first-listed lead (index 0) may win, in which case the held-out comparison is the lead
  against itself and the team counts as "no supported gain" with the note "first-listed already best".
- **Rationale**: the clear rate is the qualification statistic; the lowest-index tie rule is deterministic and
  favours today's order.

## R3. The held-out test

- **Decision**: `platsim.stats.mcnemar_exact(a=chosen_lead_cleared[1000:2000], b=first_listed_cleared[1000:2000],
  alpha=0.05)`; "supported gain" means verdict `A` (p < 0.05 with the chosen lead winning more discordant pairs).
  Pairs are matched by run index after checking that the two recordings' seed lists are identical.
- **Rationale**: the same exact test and alpha as every paired comparison in the project (014, 018); the held-out
  half removes the optimism of selecting the best of six on the runs it is tested on.
- **Alternatives considered**: Bonferroni over five comparisons on the full sample (keeps all 2,000 pairs but tests a
  different hypothesis and is still biased by selection on the same runs); a permutation test (more machinery).

## R4. The naive test and the pairing control

- **Decision**: the naive figure is the same McNemar on all 2,000 pairs of the chosen lead against the first-listed
  lead, printed beside the held-out one and labelled "selection-biased". The control is the first-listed recording
  paired against itself: 0 discordant pairs by construction, printed as proof that pairing by run index is sound.
- **Rationale**: the naive figure is what a reader would compute first; showing it beside the honest one documents
  the size of the bias. The control is the 018 pairing control.

## R5. Screening-sized check

- **Decision**: the lead chosen (R2 rule) on pairs 0..199 and on pairs 0..399, each compared with the choice on
  0..999; agreement reported per team.
- **Rationale**: sizes the follow-on's confirmation-stage check (the quick preset's confirmation is 500 runs; a
  200- or 400-pair screen would cost a fraction of it).

## R6. Level gain

- **Decision**: expected final levels per member = mean over cleared runs of that member's final level (the report's
  definition); the lead's own gain = its mean final level minus its start level; reported per lead row, and for the
  chosen lead versus the other five in the record (the exp coupling the follow-on must separate at equal levels).

## R7. Reuse of the feature-019 scripts

- **Decision**: `lead_runs.py` inserts `specs/019-e4-sampling-spike/scripts` on `sys.path` and imports
  `common.assert_idle`, `eastern_now`, `code_hashes`; it writes the 019 JSON-lines layout (header line, then one line
  per run with `run`, `seed`, `cleared`, `battles` [trainer, won, end, turns, log_hash], `final_levels`) with
  `lead_index`, `lead_species` and `order` added to the header. The Cynthia `state_before` is not kept (not needed).
- **Rationale**: one helper set, one recording format; the 019 replay tooling stays usable on these recordings.

## R8. Layout, order and cost

- **Decision**: one file per team and lead, `runs/020-evidence/<team>-lead<i>.jsonl`, teams `b2main` (014 b2-main),
  `b2branch` (014 b2-branch), `b2v2` (018 v2 B2); master seeds `020-lead-<team>`; the recorder runs one team's six
  leads back to back (lead 0 first) and may be invoked per team so a failure costs one team. Expected cost about 36,000
  gauntlets at about 12 per second with stop-on-loss on: about 50 minutes, split as three runs of about 17 minutes.
  The analysis writes `runs/020-evidence/lead_analysis.json` and `.txt`; the small files are copied to `evidence/`.
