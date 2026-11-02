# Validation log: feature 018 (expectimax2-v4, reference-first approximations)

Times are US Eastern. Evidence files (pairs cache, optimizer outputs, bench JSON, suite logs) live in
`runs/018-evidence/` (git-ignored, local). Branch `018-expectimax2-v4` from `main` 7a88ae6 (2026-11-02). Every
measurement and ladder run is alone on the machine (`pgrep -a -x node; pgrep -a pytest` empty first). Commit hashes are
recorded as they land.

## T001 Setup (3:24 PM EST)

- `git diff --stat main HEAD -- sim src tests`: empty (the Spec Kit 1.2.6 upgrade commit `875080a` touched no `sim/`, `src/` or `tests/` file; exit 0).
- `mkdir -p runs/018-evidence/pairs` done.

## T002 The four fixed teams (present, loaded)

| Team | Source | Members (species, start level, held item) |
|---|---|---|
| bench | `tests/fixtures/policy_benchmark_team.json` `.team` | infernape 57, staraptor 57, luxray 57, garchomp 57, gyarados 57, alakazam 57; no items |
| ref | `tests/fixtures/reference_team.json` `.builds` | infernape 60, staraptor 60, luxray 60, garchomp 60, gyarados 60, gardevoir 60; no items |
| b2main | `runs/014-evidence/b2-main/result.json` `.team.builds` | garchomp 52 sitrus_berry, infernape 54 sitrus_berry, staraptor 53 sitrus_berry, rotom 55 zap_plate, floatzel 55 sitrus_berry, weavile 53 sitrus_berry |
| b2branch | `runs/014-evidence/b2-branch/result.json` `.team.builds` | garchomp 51 earth_plate, infernape 53 sitrus_berry, staraptor 53 sitrus_berry, rotom 53 expert_belt, floatzel 53 sitrus_berry, weavile 54 sitrus_berry |

No regeneration needed.

## T003 Replay gate on unchanged code, branch at bbe3bbe (3:24:39 to 3:25:00 PM EST)

`(cd sim && node --test test/replay.test.mjs)`: 3 tests, 3 pass, exit 0; `replay: 80 gauntlets, 6144 player decisions,
16 workers, 20.2 s` (`runs/018-evidence/t003-replay.log`). The 015 fixture is the v1/v2 reference for this base.

## T004-T010 US1: expectimax2-v4, per-version search budget, candidate names (3:26 to 3:34:23 PM EST)

- Tests first: the new `expectimax2.test.mjs` and `gauntlet.test.mjs` tests failed on the missing exports
  (`EXPECTIMAX2_V4`, `V4_OPTS`) before T007/T008. One test assumption corrected after implementation: on the Spiritomb
  position v4 floors no branch (every first-ply weight is above 0.02 there), so the floor check now runs one Aaron
  battle (v4 floors > 0 branches, v2 floors 0). Not a behaviour issue.
- After T007/T008: `expectimax2 + gauntlet + determinism + replay + ai_golden`: **45 pass, 0 fail**: v1/v2 options
  unchanged, `V4_OPTS` provisional `{ kRoot 4, kPly2 1, beam 1, floor 0.02 }`, beam and root-sample bounds hold on the
  Spiritomb position; candidate names resolve, cache, reject nine malformed forms with `invalid_policy`, and a candidate
  spelling out `V4_OPTS` equals `expectimax2-v4` byte for byte on two Aaron gauntlets (shared seeding) while a
  different knob changes the result (positive control); determinism holds for v4 (200 gauntlets); **replay for v1/v2
  unchanged** (digests `db6d20cf…` / `1273b694…`, every choice and draw count).
- Full Node suite 3:32:01 to 3:34:23 PM EST: **351 pass, 0 fail, exit 0**, 142.0 s (`runs/018-evidence/node-suite-c1.log`).

## T011-T015 US3 code half: one default constant, `optimize --player-policy` (3:35 to 4:13:38 PM EST)

- Tests first: `tests/unit/test_default_policy.py` (new) and the resume test addition failed before T013 (4 failures);
  after: 17 passed. Two corrections while gating, both test-side or precedent: (1) the first fingerprint version added
  `player_policy` unconditionally and broke the two tests that pin the recorded default fingerprint
  (`test_required_hms`, `test_legality_options`); changed to the feature-006 `required_hms` rule (the key joins the
  fingerprint only when the policy differs from the default), contract and data model updated; (2) a missing
  module-level import in `run.py` (my guard mistook a comment for the import) made the first fast-mode rerun fail 14
  tests with `NameError`; fixed. Deviation from T017's wording: the script's unit test lives in its own file
  `tests/unit/test_paired_policies.py` (the existing `test_scripts.py` covers the decomp field-script parser, not the
  014 scripts).
- Smoke (3:37 PM EST): `optimize … --player-policy expectimax2-v9` exits 1 at once with `worker does not offer
  'expectimax2-v9' (policies: [... 'expectimax2-v4'])`; `--player-policy expectimax2-v4` runs (stopped after 75 s in the
  calibrate stage) and `state.json` records `fingerprint.player_policy = expectimax2-v4` (`runs/018-evidence/smoke-*`).
- Gates: targeted unit files **47 passed** (45.8 s); fast mode 4:03:23 to 4:13:38 PM EST: **535 passed, 28 deselected,
  4 xfailed, exit 0**, 612.4 s (`runs/018-evidence/fast-c2.log`; 528 + 7 new).
