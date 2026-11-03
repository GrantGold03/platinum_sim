# Data Model: Lead Spike

## Team

| Field | Notes |
|---|---|
| name | `b2main`, `b2branch`, `b2v2` |
| source | the stored result's `team.builds` path |
| builds | six builds at recorded levels; first-listed (index 0) is Garchomp on all three |
| master | `020-lead-<name>` |

## LeadRecording (`runs/020-evidence/<team>-lead<i>.jsonl`)

| Field | Notes |
|---|---|
| header | team, lead_index, lead_species, order (species list after rotation), master, runs 2000, workers, policies, both code hashes, pool sim hash, Eastern start/end, wall_s |
| run line (×2000) | run index 0..1999 in order, seed `derive_seed(master, i, 0)`, cleared, battles [{trainer, won, end, turns, log_hash}], final_levels (in the rotated order) |

Validation: 2,000 lines in index order; the seed list equals lead 0's seed list for the same team (checked by the
analysis before any pairing); final_levels mapped back to the original member order through `order`.

## LeadRow (per team and lead)

| Field | Notes |
|---|---|
| lead_index, lead_species | |
| cleared, clear_rate, ci95 | Wilson 95% over 2,000 |
| per_trainer | battles faced and rate, conditional on reaching |
| cynthia_rate | conditional |
| expected_final_levels | per member in original order, mean over cleared runs |
| lead_gain | lead's mean final level minus its start level |

Per team: best and worst lead by clear rate, spread in points.

## SplitSampleResult (per team)

| Field | Notes |
|---|---|
| chosen_lead, chosen_on | index chosen on pairs 0..999, with tie note |
| first_listed_already_best | bool |
| held_out | only_chosen, only_first, p, verdict (A / B / indistinguishable), supported_gain (verdict A) |
| naive | same on pairs 0..1999, labelled selection-biased |
| control | first-listed vs itself: discordant 0 |
| chosen_lead_gain_vs_others | lead's gain minus the mean gain of the other five |

## ScreeningResult (per team)

| Field | Notes |
|---|---|
| choice_200, choice_400, choice_1000 | lead indices |
| agree_200, agree_400 | equality with choice_1000 |

## Record

FUTURE-FEATURES section 8 under the lead bullet and the validation log's closing section: the three answers with
numbers per team, go / no-go for the confirmation-stage check (go when any team's held-out verdict is A), the
standing go for the reporting follow-on, the chosen leads' level gains.
