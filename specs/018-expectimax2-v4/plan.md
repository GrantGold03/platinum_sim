# Implementation Plan: expectimax2-v4, a Cheaper Battle Player, Reference-First

**Branch**: `018-expectimax2-v4` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/018-expectimax2-v4/spec.md` (clarified 2026-11-02: the full 2,000-run,
four-team protocol for every candidate; speed is reported, not gated, so any passing combination faster than v2
becomes the default).

## Summary

One new policy, a candidate-naming scheme for the ladder, a paired-comparison script, Python plumbing so the
optimizer can be told which strong player to use, and the gated default switch:

1. **Per-version search budget** (research R1). `sim/policy/expectimax2.mjs` reads the four knobs from the version
   options instead of the module-level `PARAMS`: `kRoot` (root samples), `kPly2` (second-ply samples), `beam` (root
   switch targets), `floor` (first-ply branch weight below which the branch is valued by the leaf). `V1_OPTS` and
   `V2_OPTS` carry today's values (8, 2, 2, 0), so v1 and v2 are byte-identical (the 015 replay fixture proves it).
   `V4_OPTS = { ...V2_OPTS, kRoot: 4, kPly2: 1, beam: 1, floor: 0.02 }` is the provisional set until the ladder picks
   the final one. `expectimax2-v4` is registered like v2. `STATS.floored` counts leaf-valued branches.
2. **Candidate names** (R2). The gauntlet's policy lookup resolves names of the form
   `expectimax2-v4?kRoot=4&kPly2=1&beam=1&floor=0.02` to a v4 variant with those knobs, seeded from the base name
   `expectimax2-v4` so a candidate with the final knobs is byte-identical to the shipped v4. The result names the full
   candidate string (Principle IV provenance); unknown keys or out-of-range values are a request error.
3. **Paired-comparison script** (R3). `specs/018-expectimax2-v4/scripts/paired_policies.py`: two policy names, the
   four fixed teams, 2,000 seeds per team from a per-team master, both policies on the same seeds through the worker
   pool, McNemar exact, Wilson intervals, throughput; per-(team, policy) result caching so v2 is played once per team;
   `--self` pairing control; JSON and text output under `runs/018-evidence/pairs/`.
4. **Python plumbing** (R4). `DEFAULT_PLAYER_POLICY` in `platsim.evaluate` becomes the single source of the default:
   `cli.py` (`evaluate --player-policy`, `bench --policy`), `bench.DEFAULT_POLICY`, `optimizer/levels.py` and
   `optimizer/run.py` read it. `OptimizeRequest` gains `player_policy` (default that constant) and `optimize
   --player-policy` sets it, so the B2 end-to-end run uses v4 before any default changes; `result.json` already
   records `player_policy`.
5. **Ladder, B2 end to end, default switch** (R5, R6). Runs in the order of the spec; the final `V4_OPTS` is the
   fastest passing combination; the replay fixture gains the v4 entry; the policy-strength tests cover v4; only after
   FR-005 and FR-007 pass does `DEFAULT_PLAYER_POLICY` flip to `expectimax2-v4` and the docs follow.

Proof: the 015 replay test for v1 and v2 after every commit; the ladder table (candidates x teams: clear rates,
discordant counts, p-values, verdicts, speed) in the validation log with the pairing control; the B2 equal-levels
comparison; determinism and the v4 fixture entry; the strength tests. Measurement (R7): the bench tool on `main` and
the branch (v2 and v4, single process and pool), the B2 optimizer wall times.

## Technical Context

**Language/Version**: Node v22.22.1 (ESM, `node:test`, `worker_threads`); Python 3.14 via uv (`platsim` CLI, the
worker pool, the optimizer, pytest)

**Primary Dependencies**: none new. Touches `sim/policy/expectimax2.mjs`, `sim/gauntlet.mjs`; `src/platsim/evaluate.py`,
`cli.py`, `bench.py`, `optimizer/{api,run,levels}.py`; tests under `sim/test/` and `tests/`; a new script under
`specs/018-expectimax2-v4/scripts/`; docs (README, FUTURE-FEATURES, RUN-STATE, the policy header)

**Storage**: the replay fixture `sim/test/replay_prof_a.json` gains an `expectimax2-v4` entry (v1/v2 entries untouched);
evidence JSON under `runs/018-evidence/` (git-ignored); the 014 B2 result teams are read from `runs/014-evidence/`

**Testing**: `(cd sim && node --test test/*.test.mjs)` (347 today + new); `uv run pytest -q -m "not battle_sim"` (528
passed, 4 xfailed today); full `uv run pytest -q` before merge (556 passed, 4 xfailed, 55 min today; the strength test
grows by one policy); the ladder and B2 runs are opt-in evidence runs recorded in the validation log

**Target Platform**: this Linux machine, offline, 16 cores

**Project Type**: simulator library + CLI + web (existing)

**Performance Goals**: v4 faster than v2 single process and on the pool (target 1.5x; sizing 1.5x to 1.75x); the B2
optimization markedly faster end to end

**Constraints**: v1, v2, greedy-v1 and the live opponent unchanged (replay fixture, golden tests); no Showdown edits;
no change to the model, leaf, horizon or the trainer-AI port; `sim_code_hash` changes (checkpoints before 018 will not
resume); compute local only, about 4.5 to 5 hours of pool time for the ladder and the B2 runs (R8)

**Scale/Scope**: about 60 lines in `expectimax2.mjs`, 40 in `gauntlet.mjs`, 60 across the Python modules, a 150-line
script, about 250 lines of tests; 4 stories, 5 commits, about 32 tasks. At the size rule's edge; no split, because
US2 to US4 are evidence and a one-line switch on top of US1's code

## Constitution Check

Constitution v1.4.0.

| Principle | Check | Status |
|---|---|---|
| I. Decomp is ground truth | No game data changes; the search budget is the policy's own parameter | PASS |
| II. Showdown is the battle engine | Vendored tree untouched; the opponent policy is named in every result | PASS |
| III. In-game legality | The B2 v4 result passes the validator like every optimizer output (FR-007) | PASS (planned) |
| IV. Reproducible evaluation | Paired runs on the same seeds and opponents for every comparison; candidate names carry their parameters into the result's provenance; the v4 fixture entry pins its results per seed | PASS (planned) |
| V. Verified claims, positive controls | Pairing control (v2 vs itself: 0 discordant); the replay test proves v1/v2 unchanged; a negative ladder result is recorded with its numbers; candidate == shipped v4 digest test | PASS (planned) |
| VI. Reference-first speed | v2 stays the reference, unchanged and selectable; each knob alone then combinations, adopted only if not worse on paired runs; both run times recorded; the default changes only after the gate | PASS (planned) |

Post-design re-check (after Phase 1): unchanged, PASS. Complexity Tracking: none (the candidate-name scheme is the
experiment harness Principle VI requires and costs one parse per unknown name).

## Project Structure

### Documentation (this feature)

```text
specs/018-expectimax2-v4/
├── spec.md
├── plan.md                     # this file
├── research.md                 # R1 budget options; R2 candidate names; R3 paired script and ladder; R4 Python plumbing; R5 B2 end to end; R6 default switch and tests; R7 measurement; R8 compute budget; R9 out of scope
├── data-model.md               # version options, candidate name, ladder row, pairs cache, request/result fields
├── contracts/policy-api.md     # V4_OPTS, expectimax2v4, candidate names, STATS.floored, fixture entry
├── contracts/python-and-cli.md # DEFAULT_PLAYER_POLICY, optimize --player-policy, OptimizeRequest.player_policy, paired_policies.py CLI
├── scripts/paired_policies.py  # written during implementation (US2)
├── quickstart.md
├── checklists/requirements.md
├── validation-log.md           # written during implementation
└── tasks.md                    # /speckit-tasks
```

### Source Code (repository root)

```text
sim/policy/expectimax2.mjs     opts.kRoot/kPly2/beam/floor read in scoreActions, valuePly2, qValue; V4_OPTS; EXPECTIMAX2_V4; expectimax2v4; makeExpectimax2(name, opts) seeds from opts.seedName ?? name; STATS.floored; header VERSIONS entry
sim/gauntlet.mjs               registerPlayerPolicy(expectimax2v4); playerPolicyFor(name): base names from the registry, `expectimax2-v4?...` parsed, validated, built once and cached
src/platsim/evaluate.py        DEFAULT_PLAYER_POLICY (single source; flips to 'expectimax2-v4' in commit 5 if the gate passes)
src/platsim/cli.py             evaluate --player-policy and bench --policy default to DEFAULT_PLAYER_POLICY; optimize gains --player-policy
src/platsim/bench.py           DEFAULT_POLICY = DEFAULT_PLAYER_POLICY
src/platsim/optimizer/api.py   OptimizeRequest.player_policy (default DEFAULT_PLAYER_POLICY)
src/platsim/optimizer/run.py   POLICY -> req.player_policy everywhere (confirm, level search, result provenance)
src/platsim/optimizer/levels.py  LevelSearch(policy=...) parameter; POLICY constant removed or aliased to the default
specs/018-expectimax2-v4/scripts/paired_policies.py   NEW: the ladder's paired comparison (contracts/python-and-cli.md)
sim/test/expectimax2.test.mjs  V4_OPTS values; knobs read from opts (v1/v2 equal PARAMS); candidate parsing (valid, invalid); candidate == plain v4 digest; floor: leaf-valued branches counted, 0 for v1/v2
sim/test/determinism.test.mjs  POLICIES += 'expectimax2-v4'
sim/test/replay.test.mjs       policy list includes 'expectimax2-v4' (after the fixture entry is recorded)
sim/test/gauntlet.test.mjs     playerPolicyFor: unknown name / bad candidate -> RequestError
tests/integration/test_policy_strength.py   v4 in POLICIES and pairs (v4 vs greedy must be "A"; v4 vs v2 must not be "B")
tests/unit/test_cli*.py, tests/unit/test_optimizer_*.py   optimize --player-policy parsed into OptimizeRequest; DEFAULT_PLAYER_POLICY is the single default
README.md, FUTURE-FEATURES.md, RUN-STATE.md, sim/policy/expectimax2.mjs header   docs
```

**Structure Decision**: the knobs live in the version options because that is where v1 and v2 already differ
(`koStop`, leaf weights), so a version is one options object; candidate parsing lives in the gauntlet's policy
lookup because that is the one place every caller (worker, bench, tests) resolves a name; the Python default lives in
`evaluate.py` because the optimizer already imports its evaluation there and the CLI imports both.

## Commit order

1. **US1 policy**: options-driven knobs, `expectimax2-v4` (provisional `V4_OPTS`), candidate names, `STATS.floored`,
   Node tests (replay for v1/v2 unchanged; determinism for v4; candidate == v4; parsing). Gate: Node suite; replay.
2. **US3 plumbing (code only)**: `DEFAULT_PLAYER_POLICY` single source, `optimize --player-policy`,
   `OptimizeRequest.player_policy`, Python unit tests. Gate: fast mode. No default change.
3. **US2 ladder**: `paired_policies.py`, the pairing control, the v2 sides, five single knobs, then the combinations
   (fastest first) until one passes; every row in the validation log. Gate: the table. Commit the script and the log.
4. **US1 final parameters**: `V4_OPTS` = the passing set; `node sim/bench.mjs --policy expectimax2-v4 --record`
   adds the fixture entry; replay test lists v4; strength tests cover v4; bench v2 vs v4. Gate: Node suite; replay;
   bench digests.
5. **US3 runs + US4 switch + docs**: B2 optimize with v2 and v4 (quick, seed `014-b2`), equal-levels comparison, wall
   ratio; if FR-005 and FR-007 pass, flip `DEFAULT_PLAYER_POLICY`, update docs; fast mode; full suite after the user's
   hands-on testing. If a gate fails: no flip, the negative result in README/FUTURE-FEATURES/RUN-STATE.

## Complexity Tracking

None. Candidate names are the experiment harness Principle VI requires; their parser is small, validated and tested,
and the shipped v4 is a plain registered name. `STATS.floored` follows the existing `STATS` precedent.
