# Validation log: feature 026 Candidate sets by marginal coverage

Branch `026-marginal-coverage-sets` from `main` 7c466ae, main checkout. Times US Eastern.

## T001 Setup (about 5:25 PM EST)

`git diff --stat main -- src sim tests pyproject.toml` lines: 0 (the branch's code equals `main`, so the pre-feature side can
run here). Before-values (only `platsim_code_hash` is expected to change; `sim/` must not change at all):

```
sim_code_hash platsim_code_hash: sha256:e968ff0f403539460e6c0260db6253ad971d1a3eb7c02feaa8c9fbe393e74b7d sha256:047562351ac92cdec4042061850daaea072437bdc2bc5dffd2c21c4eda867142
divergence_ledger_version: sha256:feb2a48ef2e1dd08
```

Scripts under `scripts/`: `acceptance.py` (025's: evidence `runs/026-evidence`, identity seed `026-ident`; the snapshot records
dead moves per set, `one_apart`, `no_live_reason` and the candidate-generation time for the six B2 species (SC-006); the
branch side adds the dead-moves table, the allocation record, the baseline-repair and screen-repair counts, and the pass rule
also requires 0 baseline repairs and 0 dead moves outside no-live-move members), `attribution.py` (025's plus `coverage`,
`marginal`, `dead_moves_of`, `dead_table`, and the cause `marginal_pool` verified by recomputation: an entrant's gain to the
pool before it must be positive, a leaver must add no more than the smallest entrant gain, a set change among the new pool's
moves that removed a dead move or was accepted one apart), `equal_levels.py` (master `026-equal|B2`), `hand_check.py` (025's
plus dead moves per set, `one_apart`, `no_live_reason`, the generation time, the allocation record when the code has it).
Smoke on today's code: the helper lists Flamethrower and Fire Punch as dead in Infernape's second set.

## T002 Pre-feature side (5:32:25 to 5:42:10 PM EST, alone, exit 0; code identical to `main` 7c466ae)

`acceptance.py --side main --workers 16` (evidence `runs/026-evidence/`, copies in `evidence/pre/`):

- B2 quick on today's code (`b2-main`): levels [51, 52, 52, 52, 53, 53], clear 0.9380 [0.9133, 0.956] (n 500, 2 attempts),
  wall 429.0 s: the same winner as feature 025's branch run (same code). Its Infernape carries Fire Blast / Flamethrower /
  Close Combat / Fire Punch.
- Candidate generation, six B2 species at level 48: **0.9 s** (SC-006 baseline; the unit tests' 38 s include the ledger build).
- Identity evaluations `ident-main/{ref,b2main}` (200 runs, quick, seed 026-ident).
- Snapshot `evidence/candidates-main.json`: 36 member variants with the dead moves per set computed by the helper:
  **335 dead-move entries** across the 36 members' offered sets (base and extras); Infernape's second set lists Flamethrower
  and Fire Punch, as the spec's evidence says.

## T003 to T010 Code and controls (5:45 to 6:20 PM EST)

`candidates.py`: `marginal`, `dead_moves` (tie-aware: of two moves with equal values the one first by name is live, the
other dead), `live_moves`, `takeover`, `cost_tier`, `prefer_cost_free`, `pool_by_marginal`, `rank_sets`, `_repaired`,
`choose_sets`, `filler_reason`; `member_candidates(..., unavailable=frozenset())` with one value table over attacks and the
offered variable moves, the marginal pool, the 024 and 025 extras over the same pool and ranking; `MemberCandidates.dead_moves`,
`no_live_reason`, `one_apart`, `unavailable` in `summary()`.

Three design corrections found at implementation, each by a real-member control (recorded for the docs task, T018):

1. **The cost class splits into two tiers for pool entry.** The single rule (a cost move refused wherever a cost-free move
   already hits the opponent) locked Close Combat out of Staraptor's pool (its self stat drop is a "cost") while a candidate-only
   rule let Fly in over Aerial Ace. Turn costs (charge turn, recharge, lock-in, delayed hit, first-turn-only, sleep-only,
   fails-when-hit, the user faints: `TURN_COST_EFFECTS`) enter only for an opponent no cost-free move hits at all; damage costs
   (recoil, self stat drops, crash damage) are compared with cost-free candidates only. Dominance keeps the single class.
2. **A set is never dropped for a lower-coverage all-live set.** With a hard all-live rule, Staraptor's Return / Close Combat /
   Aerial Ace (which cover every League opponent, so any fourth move is dead) lost to today's weaker set without Return. Now
   the ranked sets have their dead moves replaced where a live legal move exists, are re-ranked by coverage, and a set keeps a
   dead move only when no live replacement exists (the filler, listed with the reason). FR-004a (option B) is applied as
   stated: a one-apart all-live set replaces a two-apart set only when that set carries a dead move and the all-live set is at
   least as good as its live part; a two-apart all-live set is kept (Garchomp's sets 2 and 3 stay today's).
3. **The marginal-sum tie-break is dropped** (FR-003): a filler that backs nothing up maximises the other moves' marginals, so
   it preferred the weakest filler (Quick Attack over Pluck); the key is today's (coverage, standalone sum, name).

Also found: "live" is set-relative, so the spec's premise that Infernape has five live moves was wrong (Flamethrower is live in
a set without Fire Blast); Infernape gets three all-live sets two apart with Grass Knot in each, no one-apart set needed. And
Staraptor's lists change (the spec's SC-002 expected "unchanged"): Return is a same-type 102-power move on a Normal type, so
it enters the pool and the first set; Fly and Giga Impact (turn costs) stay out.

B2 at level 48 on the branch (`evidence/b2-candidates-branch.txt`, generation 1.4 s for six, SC-006 vs 0.9 s before):
Garchomp's three sets unchanged; Infernape Fire Blast / Close Combat / Earthquake / Grass Knot, Flamethrower / Close Combat /
Stone Edge / Grass Knot, Fire Blast / Focus Blast / Stone Edge / Grass Knot (no Fire Punch, no dead move); Staraptor Return /
Aerial Ace / Close Combat + Pluck (filler, listed), Return / Wing Attack / Close Combat + Secret Power (filler), then today's
first set; Rotom unchanged, listed ("its two strongest moves cover every League opponent"); Floatzel Waterfall / Ice Beam /
Crunch / Brick Break and two Return sets; Weavile Ice Punch / Night Slash / Aerial Ace / Brick Break and two more, all live.

Attributed diff over the 36 snapshot members (the helper recomputes the pool gains): marginal_pool 7781, appended 166,
crit_term 34, **defects 0**. Dead moves in base sets: 92 before (335 over all sets), **0 after outside the 9 listed members**
(Staraptor ×4, Rotom ×2, Chatot, Milotic, Magnezone); the appended sets (024 variable-power, 025 item-conditioned) keep 215
dead-move entries: FR-007 applies only the pool and ranking rule to them (recorded; a candidate refinement for a later feature).

```
uv run pytest -q tests/unit/test_marginal_coverage.py tests/unit/test_optimizer_candidates.py tests/unit/test_variable_power.py tests/unit/test_h4_items.py -m "not battle_sim"
  → 48 passed + (after the helper's filler-tail rule) 20 passed, exit 0 (15 new tests)
```

Fast suite (`runs/026-evidence/fast.log`, 6:03:10 to 6:13:07 PM EST): `617 passed, 32 deselected, 4 xfailed, 1 warning in
594.96s`, exit 0.

## T011, T012 The filler-move note (6:25 to 6:40 PM EST)

`EvaluationReport.member_notes` (default empty; pre-026 files read with none); `team_txt.team_text` appends a `Notes:` block
after the Showdown export and `legality.models.import_team` skips it (round trip tested); `evaluate.summary_text` prints
`note: ...` lines; the xlsx **Evaluation** sheet gets one "Member note" row per note (the plan's Team-sheet column was dropped:
the Team headers are the published spreadsheet contract of feature 001 and two tests pin them); `csv_report.member_note`
matches a member by key or display name. `run._member_notes` builds the lines from the prune stage's candidate summaries
(`dead_moves` of the chosen set and `no_live_reason`): "Rotom: Thunder, Ominous Wind are filler: no better option: its two
strongest moves cover every League opponent".

```
uv run pytest -q tests/unit/test_reports.py tests/unit/test_marginal_coverage.py tests/unit/test_optimizer_resume.py tests/unit/test_required_hms.py -m "not battle_sim"   → 59 passed, exit 0
```

## T013 to T015 Team-level allocation (6:45 to 7:25 PM EST)

`src/platsim/optimizer/allocation.py`: `needs` (the cheapest source per move, memoised per ledger: the source lookup was
32.8 s uncached for the B2 team, 5.9 s cached), `contested`, `remaining`, `allocate` (step 1 first-set contention by
coverage gained, ties by slot; step 2 resources with no copy left after the first sets are charged become unavailable to the
other members; rebuild; loop until no first set changes, bounded). `run._build_cands` returns `(cands, record)`; the prune
stage and the optimizer provenance carry `allocation`. On the B2 team at level 48 (`evidence/b2-candidates-branch.txt`):

| Resource | Contenders (gain) | Given to | Rebuilt |
|---|---|---|---|
| TM26 Earthquake | Garchomp 262486, Infernape 8769 | Garchomp | Infernape |
| TM71 Stone Edge | Garchomp 28519, Infernape 7254 | Garchomp | Infernape |
| TM31 Brick Break | Weavile 13388, Floatzel 1785 | Weavile | Floatzel; Garchomp, Infernape (no copy left) |
| TM40 Aerial Ace | Weavile 18394, Garchomp 1849 | Weavile | Garchomp, Infernape (no copy left) |
| TM30 Shadow Ball | (Rotom's first set holds the copy) | | Weavile (no copy left) |

Infernape without Earthquake and Stone Edge: Fire Blast / Flamethrower / Close Combat / Grass Knot (Flamethrower the filler,
listed), Fire Blast / Focus Blast / Grass Knot / Rock Slide, Close Combat / Fire Punch / Grass Knot / Shadow Claw. Garchomp's
first set becomes Earthquake / Dragon Claw / Stone Edge / Fire Blast (Aerial Ace to Weavile, where it gains ten times more).
Baseline repair notes: 0; every offered set of every member (today's, the extras, the setup set) realizes beside the others'
first sets at level 48 with no repair note (test). Coverage memoised over move subsets (`_cov`).

**SC-006 as written fails**: candidate generation for the six B2 species is 1.2 s without the allocation (0.9 s on main; the
dead-move repair of every ranked combination) and **4.8 s with it** (about a dozen rebuilds at 0.3 s each), 5.3× today's,
against "at most twice". The allocation is the owner's story 3 (chosen after the criterion was written); 4.8 s is a few
seconds of a seven-minute quick optimize. Recorded for the report; the docs task proposes an absolute bound instead.

```
uv run pytest -q tests/unit/test_marginal_coverage.py -m "not battle_sim"   → 20 passed, exit 0 (4 allocation tests)
uv run pytest -q tests/unit/test_optimizer_resume.py tests/unit/test_required_hms.py tests/unit/test_reports.py tests/unit/test_optimizer_candidates.py -m "not battle_sim"   → see below
```
60 passed in 46.38s
