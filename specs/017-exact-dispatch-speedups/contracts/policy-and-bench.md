# Contract: policy and benchmark changes (`sim/policy/expectimax2.mjs`, `sim/bench.mjs`, `src/platsim/bench.py`)

## `damageTable(X, S, u, t, rec)` (internal; unchanged result)

Builds its damage inputs from the root adapter's per-decision memo instead of `fromShowdown`:

```
const di = X.rootView.ai.damageInput(u.ref, t.ref, num, { power, type, powerMul: 10 });
const base = { attacker: { ...di.attacker }, defender: { ...di.defender }, move: di.move, field: { ...di.field }, crit: false };
```

then `fix()` and the field overrides as today, on `base` only. The table entry and its key are unchanged;
`fromShowdown` is no longer imported by the policy. The root adapter is the per-battle mirror's (`makeContext`
calls its `beginDecision()` first), so the memo lives exactly one decision.

## `resolveTurn(X, S, pa, oa, speedOf = () => speedInfo(X, S))` (internal; unchanged result)

Uses `speedOf()` where it called `speedInfo(X, S)`. Callers pass one lazy thunk per state: `valuePly2` (after
`replaceFainted`, before its loops), `qValue` (the root state), and through them the forced-switch path.
`variablePower` keeps calling `speedInfo(X, S)` on its (mid-turn) state. `speedInfo(X, S)` itself is unchanged
apart from `STATS.speedInfo++`.

## `STATS` (extended)

`{ decisions, aiCalls, turns, leaves, ms, aiMs, viewMs, aiDraws, speedInfo }`. Diagnostics; the bench reports the
delta object under `stats` as today.

## `node sim/bench.mjs` JSON (015 contract, two fields added)

| Field | Meaning |
|---|---|
| `interp_steps` | `INTERP_STATS.steps` delta over the run (trainer-AI script instructions executed, player predictions and live opponent together) |
| `interp_dispatches` | `INTERP_STATS.dispatches` delta (fused effect-check runs answered in one step; 0 on the instrumentation commit) |

The human table prints both. `digest_full`, `digest_logs`, `ai_draws`, `check_stats` and the rest are unchanged.

## `uv run platsim bench`

Passes the two fields through from the single-process half as rows `single: interpreter steps` and `single:
interpreter dispatches`; the pool half is unchanged (per-worker counters are not aggregated). `digests_agree`
unchanged.

## Required measurements (FR-011, SC-002, SC-003, SC-004)

Validation log, same session, nothing else running: `main` (single v2, v1; pool) and the branch at the final
commit (same), plus single-process v2 after each story commit; `interp_steps` from commit 1 (before) and from the
final commit (after); ratios; digests equal and agreeing.
