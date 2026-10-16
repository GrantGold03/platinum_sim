# Contract: candidate records, mode option and report additions (007)

This contract amends `specs/001-champion-team-optimizer/contracts/cli.md`, `http-api.md` and `spreadsheet.md`. Existing fields keep their meaning.

## CLI

`platsim optimize … [--candidates off|reference]` (007; `prefilter` comes with feature 008)

- Default: `off` (no alternatives stage; the result records `candidate_mode: off` and no candidate_tests). `reference` plays every alternative (about 8-10 h per standard run). Feature 008 adds `prefilter` and makes it the default once accepted.
- The value is recorded in `provenance.optimizer.candidate_mode` and in the job fingerprint, so a run in a different mode never resumes another mode's state.
- Test-only request fields (not on the CLI or the web): `alternatives_round` (the reference's first-round size r) and `alternatives_members` (limit the stage to the first N members). Both are recorded in provenance when set.
- `--player-policy` (evaluate) accepts `expectimax2-v3`. After acceptance (research R4.6), the default becomes `expectimax2-v3`. `expectimax2-v1` and `-v2` stay available.

## HTTP

- The optimize request body accepts an optional `"candidates": "off" | "reference"`. If it's absent, the default `off` applies.
- No UI control is added. The web uses the default.

## result.json

```json
"provenance": { "optimizer": {
  "candidate_mode": "reference",
  "item_tie_rule": "more copies; higher effect_param; classic STRENGTHEN_* before ARCEUS_*; item key",
  "assumptions": {"friendship": 255, "ivs": 15, "hidden_power": "Dark 70"},
  "excluded_moves": {"1": {"MOVE_SCREECH": "foe_drop: stages reset when the foe faints or switches (battle_lib.c:97-100, 2156-2162)",
                          "MOVE_TRICK": "not offered: not modelled by expectimax2-v3"}},
  "candidate_tests": [
    {"slot": 4, "species": "SPECIES_MILOTIC", "kind": "status+item", "round_reached": "final",
     "moves": ["MOVE_SURF", "MOVE_ICE_BEAM", "MOVE_RECOVER", "MOVE_TOXIC"], "item": "leftovers",
     "levels": [54, 54, 54, 54, 54, 54], "mode": "reference",
     "n_paired": 200, "rate_alt": 0.79, "rate_current": 0.71, "alt_only": 22, "current_only": 6,
     "p_value": 0.003, "p_holm": 0.012, "verdict": "alternative better", "confirmed": true,
     "adopted": true, "not_modelled": []}
  ],
  "policy_per_stage": {"alternatives": "expectimax2-v3"},
  "seeds": {"alternatives": "<seed>|alternatives"}
}}
```

- Every offered alternative appears exactly once. `kind` is one of `status`, `status+item`, `structured`, `structured+item` and `item`.
- An alternative dropped in a successive-halving round has `round_reached` (e.g. `"round 2 of 4"`), its round's clear count and run count, and `verdict: "dropped in screening"`.
- The full test of a finalist uses a fresh seed block (`alternatives_final_seeds`); `confirmed` is null (no separate confirmation since 2026-10-16). Each alternative's per-seed screening outcomes are in the run's state.json (`screening_outcomes`), not in result.json.
- One that wasn't tested at all has `verdict: "not tested: <reason>"` and null statistics (SC-003).
- The numbers are those of the recorded battles. `n_paired` equals the number of runs actually played.

## Warnings

Unmodelled moves and items are not offered (spec FR-001, FR-009). The one remaining case is a **required HM** whose effect the player doesn't model (e.g. Defog), which is still carried (FR-014). Then `warnings` gets:

`"<Species> carries <Move/Item>, which <policy> does not model; its in-battle effect is applied by the engine but the player does not plan around it."`

## Spreadsheet

- New sheet **"Candidates"**, after "Resources". One row per `candidate_tests` entry, with the columns in the order above.
- `SHEET_NAMES` and its test are updated.
- The CSV is unchanged.

## Web results view

- Shows the warnings, as today.
- Optional: a per-member count, "offered N / tested M / adopted K", with a link to the report files (Constitution IV: a shorter view is allowed).

## ETA

`web/eta.py` `STAGE_ORDER` gains `alternatives` between `level_search` bisection and descent. The old `setup_check` key maps to it for old state files.
