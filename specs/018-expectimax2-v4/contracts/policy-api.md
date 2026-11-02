# Contract: policy additions (`sim/policy/expectimax2.mjs`, `sim/gauntlet.mjs`)

## Exports (`expectimax2.mjs`)

- `EXPECTIMAX2_V4 = 'expectimax2-v4'`; `V4_OPTS` (frozen; provisional `{ ...V2_OPTS, kRoot: 4, kPly2: 1, beam: 1, floor:
  0.02 }`, final = the ladder's passing set, stated in the header's VERSIONS entry with the numbers);
  `expectimax2v4 = makeExpectimax2(EXPECTIMAX2_V4, V4_OPTS)`.
- `makeExpectimax2(name, opts)`: unchanged signature; `opts.seedName ?? name` seeds the private trainer-AI streams and
  keys the per-battle mirror; `opts.kRoot / kPly2 / beam / floor` are read inside the search with the defaults
  `PARAMS.K_ROOT / K_PLY2 / SWITCH_BEAM / 0`.
- `STATS.floored` (new counter).
- `V1_OPTS`, `V2_OPTS`, `PARAMS`, `expectimax2`, `expectimax2v2`, `scoreActions`, `makeContext`, `_internal`: unchanged.

## Search semantics per knob

- `kRoot`: `predictOpponent(X, S, 'root', kRoot)` at the root (today 8).
- `kPly2`: `predictOpponent(X, S, 'p2', kPly2)` in `valuePly2` (today 2).
- `beam`: the number of best switch targets (by `matchupScore`) searched at the root; the others score `-Infinity`
  (today 2). Forced switches are unaffected (every replacement is searched, as today).
- `floor`: in `qValue`, a first-ply branch with weight `w = p(opp action) * p(branch) < floor` that is not already
  leaf-valued by `koStop` is valued by `leafValue` instead of `valuePly2`; its weight is kept (the expectation's mass is
  unchanged); `STATS.floored++`. `floor` 0 disables it.

## Results for v1 and v2

Byte-identical to `main` 7a88ae6: the 015 replay fixture entries (`db6d20cf…`, `1273b694…`, choices, draw counts)
match after every commit (FR-002).

## `playerPolicyFor(name)` (`gauntlet.mjs`, used by `runGauntlet`; exported for tests)

- A registered name → the registered policy (as today).
- `expectimax2-v4?<query>` → parsed per data-model.md; valid → a cached candidate instance whose `name` is the full
  string and whose streams are seeded from `'expectimax2-v4'`; invalid → `RequestError('invalid_policy', <reason>)`
  (surfaces as `ok: false` from the worker like other request errors).
- Anything else → `RequestError('internal', 'unknown player_policy …')` as today.

Guarantee (tested): `expectimax2-v4?<final V4_OPTS values>` and `expectimax2-v4` give equal `digest_full` on the same
requests.

## Replay fixture

`node sim/bench.mjs --policy expectimax2-v4 --record sim/test/replay_prof_a.json` adds the v4 entry (015 contract,
merge by policy key); `replay.test.mjs` then expects `['expectimax2-v1', 'expectimax2-v2', 'expectimax2-v4']` and
checks all three.
