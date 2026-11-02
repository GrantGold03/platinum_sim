# Research: expectimax2-v4 (reference-first approximations)

Read on 2026-11-02 on `018-expectimax2-v4` = `main` 7a88ae6 + spec commits. Evidence: the post-017 profile and the
v4 sizing runs in `runs/017-evidence/scratchpad/prof4/REPORT4.md` (appendix), made by patching the search parameters
in memory on the fixed set (digests differ from v2's by design; clear counts over 40 gauntlets are noise-level).

## R1. The four knobs become version options (`sim/policy/expectimax2.mjs`)

**Facts**. `PARAMS = { K_ROOT: 8, K_PLY2: 2, SWITCH_BEAM: 2, W_ALIVE, W_FR, WIN }` is module-level; `valuePly2` reads
`PARAMS.K_PLY2` (line 1125), `scoreActions` reads `PARAMS.SWITCH_BEAM` (1227) and `PARAMS.K_ROOT` (1231); `qValue`
(1143-1148) sums `p * br.p * (koStop && fainted ? leaf : valuePly2)` over every first-ply branch. Versions are
`makeExpectimax2(name, opts)` with `V1_OPTS = { koStop: false }`, `V2_OPTS = { koStop: true, wAlive: 0.25, wFR: 0.1 }`;
`X.opts` is the version's options inside the search. The policy name seeds the private trainer-AI streams
(`mirrorFor(battle, trainer, name)` → `seedBase` from `sha256(prngSeed|name)`).

**Decision**. Four optional fields on the version options, read through `X.opts` with today's values as defaults:
`kRoot` (default `PARAMS.K_ROOT`), `kPly2` (`PARAMS.K_PLY2`), `beam` (`PARAMS.SWITCH_BEAM`), `floor` (0). `V1_OPTS` and
`V2_OPTS` are unchanged objects (they do not name the knobs, so they take the defaults). `qValue` becomes:
`const w = p * br.p; const ko = X.opts.koStop && activeFainted(br.S); if (!ko && w < floor) { STATS.floored++; q += w *
leafValue(X, br.S); } else q += w * (ko ? leafValue(X, br.S) : valuePly2(X, br.S));` with `floor = X.opts.floor ?? 0`.
`V4_OPTS = Object.freeze({ ...V2_OPTS, kRoot: 4, kPly2: 1, beam: 1, floor: 0.02 })` provisionally; commit 4 sets the
passing set. `EXPECTIMAX2_V4 = 'expectimax2-v4'`, `expectimax2v4 = makeExpectimax2(EXPECTIMAX2_V4, V4_OPTS)`,
registered in `gauntlet.mjs` after v2. `STATS.floored` counts leaf-valued branches (0 for v1/v2 by construction).

**Why v1 and v2 are unchanged**: with `floor` 0 the new branch is never taken (`w < 0` is false for w >= 0); the other
three reads return the same numbers as before; the replay fixture is the proof after every commit.

**Alternatives rejected**: a second `PARAMS` object per version (two sources of truth for the same knob); a global
override through the environment (invisible in the result's provenance, see R2).

## R2. Candidate names for the ladder (`sim/gauntlet.mjs`)

**Decision**. `playerPolicyFor(name)` in `gauntlet.mjs` (used by `runGauntlet`): a registered name returns the
registered policy; a name matching `^expectimax2-v4\?(.+)$` is parsed as `key=value&…` with keys `kRoot`, `kPly2`
(integers 1..32), `beam` (integer 1..5), `floor` (decimal in [0, 0.5]); anything else (unknown key, repeated key,
bad value, empty query) throws `RequestError('invalid_policy', …)`. A valid candidate is built once with
`makeExpectimax2(name, { ...V4_OPTS, ...parsed, seedName: EXPECTIMAX2_V4 })`, cached in `PLAYER_POLICIES` under the full
name, and the result's `player_policy` is the full name. `makeExpectimax2` passes `opts.seedName ?? name` to
`mirrorFor` and the seed hash, so a candidate whose knobs equal the shipped `V4_OPTS` produces byte-identical results to
`expectimax2-v4` (test: two gauntlets, equal digests). The worker's hello still lists only registered base names;
the Python callers that assert `player_policy` equality compare the requested string with the returned one, which is
the full candidate name on both sides.

**Why**: Principle IV wants the policy named in every result; a candidate name carries its parameters, so the ladder's
evidence files are self-describing and the pool needs no environment plumbing. Seeding from the base name keeps the
ladder's measurement of the final set identical to the shipped policy.

**Alternatives rejected**: environment overrides (results would all say `expectimax2-v4` with different behaviour);
registering fixed candidate names in code (the ladder decides the set at run time).

## R3. The paired-comparison script and the ladder (`specs/018-expectimax2-v4/scripts/paired_policies.py`)

**Decision**. A script in the feature's `scripts/` directory (the 014 precedent), run with `uv run python`:

```
paired_policies.py --a <policy> --b <policy> [--teams bench,ref,b2main,b2branch] [--runs 2000] [--workers 16]
                   [--out runs/018-evidence/pairs] [--self]
```

Teams: `bench` = `tests/fixtures/policy_benchmark_team.json` `.team` (worker shape, Lv 57); `ref` =
`tests/fixtures/reference_team.json` `.builds` through `load_and_validate` + `worker_team` (Lv 60); `b2main` /
`b2branch` = `runs/014-evidence/b2-{main,branch}/result.json` `.team` through the same loader (their own start
levels). Seeds: `derive_seed(f"018-pairs|{team}", i, 0)` for `i < runs`. Requests: `{ op: 'gauntlet', team, seed,
player_policy, opponent_policy: 'decomp-ai', stop_on_loss: true, log: 'none' }` through `WorkerPool(workers).map`,
checked as `run_full_gauntlets` checks them (ok, policies echoed). Outcomes: `cleared` per seed; `mcnemar_exact(a, b)`
(A = `--a`, B = `--b`), Wilson intervals, wall and gauntlets/s per side. Cache: `<out>/<team>__<policy-as-filename>__
<runs>.json` holds the outcome list and timing for one (team, policy); a cached side is reused, so v2 is played once
per team over the whole ladder. `--self` runs `--a` against itself on the first team (pairing control: 0 discordant).
Output: one text block per team plus a `summary.json` row with team, a, b, n, clear rates, a_only, b_only, p,
verdict, speeds.

**Ladder** (FR-005, clarification 1: full protocol for every candidate). Candidates as names:
`expectimax2-v4?kRoot=8&kPly2=1&beam=2&floor=0` (second-ply 1 alone), `…?kRoot=8&kPly2=2&beam=1&floor=0` (beam 1),
`…?kRoot=4&kPly2=2&beam=2&floor=0` (root 4), `…?kRoot=8&kPly2=2&beam=2&floor=0.02`, `…floor=0.05`. Then the
combinations in descending measured speed: all passing singles together (with the larger passing floor), then that
set minus one knob each (fastest first), then pairs; stop at the first combination that passes on all four teams.
A single knob that fails on any team is excluded from every combination. Every row goes in the validation log.

## R4. Python plumbing: one default, `optimize --player-policy`

**Facts**. The default strong player is spelled out in five places: `cli.py:140` (`evaluate --player-policy`),
`cli.py:301` (`bench --policy`), `bench.py:30` (`DEFAULT_POLICY`), `evaluate.py:54` (`DEFAULT_PLAYER_POLICY`),
`optimizer/levels.py:55` and `optimizer/run.py:77` (`POLICY`, used for the level search, the confirmation runs and the
result's provenance). `optimize` has no policy argument; `OptimizeRequest` (`optimizer/api.py`) carries the run's
inputs and the web passes one through.

**Decision**. `platsim.evaluate.DEFAULT_PLAYER_POLICY` is the single source: `cli.py` defaults reference it (help text
shows the value), `bench.DEFAULT_POLICY = DEFAULT_PLAYER_POLICY`, `OptimizeRequest.player_policy: str =
DEFAULT_PLAYER_POLICY`, `run.py` uses `req.player_policy` for the level search (`LevelSearch(..., policy=…)`), the
setup check, the confirmation runs and the result provenance, and `levels.POLICY` goes (or becomes an alias kept for
`__all__`). `optimize --player-policy NAME` sets the request field; the web keeps the default. Tests: a unit test that
every default equals the constant and that `optimize --player-policy x` lands in the request.

**Why**: the B2 end-to-end run with v4 (FR-007) must happen before any default changes, so the optimizer needs an
explicit policy; and the switch (FR-008) then is one constant.

## R5. B2 end to end (FR-007)

`uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2
--player-policy expectimax2-v2 --out runs/018-evidence/b2-v2` and the same with `expectimax2-v4` → `b2-v4`
(both re-run on today's code so the wall times are comparable; 015-017 were exact, so the v2 result should equal the
014 branch result apart from provenance, which is a free consistency check). Then the 014 equal-levels script, copied
to this feature's `scripts/equal_levels.py` with the v4 result as A and the v2 result as B (both at the v4 team's
start levels, 2,000 paired, master `018-equal|B2`, player v2 for both sides? No: the spec compares the TEAMS at equal
levels, so both teams are played by the same player, the reference v2, as 014 did). Verdict: not "B", and mean final
level of A not higher. Wall times from the optimizer logs.

## R6. Default switch and tests (FR-008, FR-010)

Flip `DEFAULT_PLAYER_POLICY = "expectimax2-v4"` only after R3's ladder and R5 pass; `README.md` (the default-player
sentence, the command table, the speed table), `FUTURE-FEATURES.md` section 7, `RUN-STATE.md`, the policy header
(VERSIONS entry for v4 with the ladder's numbers). Tests: `test_policy_strength.py` `POLICIES` gains v4 and `pairs`
gains `(v4, greedy)` (must be "A") and `(v4, v2)` (must not be "B"), both under the existing `PLATSIM_STRENGTH_N`;
`determinism.test.mjs` runs v4; `replay.test.mjs` expects three policies once the fixture has the v4 entry;
`expectimax2.test.mjs` covers options, candidates and the floor.

## R7. Measurement (FR-006)

Same session, alone: `node sim/bench.mjs --policy expectimax2-v2 --json` and `--policy expectimax2-v4 --json`, then
`uv run platsim bench --policy expectimax2-v4 --workers 16 --json` (and v2), digests agreeing; the fixture entry
`node sim/bench.mjs --policy expectimax2-v4 --record sim/test/replay_prof_a.json` after the final parameters.

## R8. Compute budget (local pool, 16 workers)

| Step | Runs | Estimate |
|---|---|---|
| Pairing control (v2 vs v2, one team) | 2 x 200 | 2 min |
| v2 side, four teams (cached) | 4 x 2,000 at about 4.5 gauntlets/s | 30 min |
| Five single knobs | 5 x 4 x 2,000 at 5 to 8 gauntlets/s | 1 h 40 min |
| Combinations until one passes | 1 to 4 x 4 x 2,000 | 20 to 80 min |
| B2 optimize v2 and v4 (quick) | | 15 + 10 min |
| Equal-levels replay | 2 x 2,000 | 15 min |
| Bench, fixture record | | 5 min |
| Total | | about 4 to 5 hours, in the background, nothing else running |

## R9. Out of scope

The exact items D, F, E and H (FUTURE-FEATURES section 7, 019+); model, leaf, horizon or trainer-AI changes; the
README headline re-run; a web option to choose the policy (the web uses the default).
