# Data Model: expectimax2-v4

## Version options (`sim/policy/expectimax2.mjs`)

```text
VersionOpts {
  koStop: boolean, wAlive?: number, wFR?: number     // as today (v1 / v2)
  kRoot?: number    // trainer-AI samples at the root (default PARAMS.K_ROOT = 8)
  kPly2?: number    // samples per second-ply state (default PARAMS.K_PLY2 = 2)
  beam?: number     // switch targets searched at the root (default PARAMS.SWITCH_BEAM = 2)
  floor?: number    // first-ply branch weight p(opponent action) x p(branch) below which the branch is leaf-valued (default 0)
  seedName?: string // name used to seed the private trainer-AI streams (default: the policy name); candidates pass 'expectimax2-v4'
}
V1_OPTS, V2_OPTS unchanged; V4_OPTS = { ...V2_OPTS, kRoot, kPly2, beam, floor } (provisional 4 / 1 / 1 / 0.02; final = the ladder's passing set)
```

## Candidate name (`sim/gauntlet.mjs`)

```text
'expectimax2-v4?' key '=' value ('&' key '=' value)*
key   ∈ { kRoot, kPly2, beam, floor }, each at most once
kRoot, kPly2 ∈ 1..32 (integer); beam ∈ 1..5 (integer); floor ∈ [0, 0.5] (decimal)
```

Resolves to `makeExpectimax2(fullName, { ...V4_OPTS, ...parsed, seedName: 'expectimax2-v4' })`, cached under the full
name; invalid → `RequestError('invalid_policy')`. Results carry the full name as `player_policy`.

## Policy counters

`STATS.floored`: first-ply branches valued by the leaf because of the floor (diagnostics; 0 for v1 and v2).

## Ladder row (validation log and `runs/018-evidence/pairs/summary.json`)

```text
{ candidate, team, n, a_cleared, b_cleared, a_rate, b_rate, a_only, b_only, p_value, verdict ('A' | 'B' | 'indistinguishable'),
  a_gauntlets_per_s, b_gauntlets_per_s, master }
```

A candidate passes when no team has verdict `B` (b = v2 better). The pairing control row has `a == b`, `a_only == b_only == 0`.

## Pairs cache (`runs/018-evidence/pairs/<team>__<policy-file-safe>__<n>.json`)

```text
{ team, policy, master, n, cleared: boolean[n], battles_seed_0: string[n] (positive control of pairing), wall_s, gauntlets_per_s, sim_code_hash, hello: { decomp_commit, showdown_commit, node } }
```

The v2 side is computed once per team and reused for every candidate; a cache entry whose `sim_code_hash` differs
from the current worker's is not reused (recomputed, noted in the log).

## Optimizer request and result (`src/platsim/optimizer/api.py`, `result.json`)

`OptimizeRequest.player_policy: str = DEFAULT_PLAYER_POLICY` (new field; the web leaves it at the default);
`result.json.player_policy` (already present) now reflects the request. `evaluate` and `bench` keep their explicit
arguments, defaulting to the same constant.

## Replay fixture (`sim/test/replay_prof_a.json`)

`policies['expectimax2-v4']` added by `node sim/bench.mjs --policy expectimax2-v4 --record …` with the final options:
`digest_full`, `digest_logs`, 40 gauntlet records (choices, per-decision draw counts). v1 and v2 entries byte-identical
to today's.

## Relationships

- A candidate name → `VersionOpts` (over `V4_OPTS`) → one `makeExpectimax2` instance, seeded from the base name.
- A ladder row ties one candidate, one team and one master to two cached pair files (candidate side, v2 side).
- The final `V4_OPTS` is chosen from the rows (FR-005); the fixture entry and the default switch depend on it.
