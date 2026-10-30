# Data Model: Exact AI-Prediction Speedups

No persisted game data changes. The entities are in-memory caches, one committed test fixture and one report.

## Decision cache (per adapter instance)

| Field | Type | Meaning |
|---|---|---|
| `battlers` | `Map<Pokemon, BattlerStruct>` | `battlerFromShowdown(p)` result for each Showdown Pokemon asked about since the last `beginDecision()` (active or benched; live or shadow object) |
| `fields` | `Map<Side, FieldStruct>` | the `field` block of `fromShowdown` for a given defender side: `weather`, `abilitiesOnField`, `defenderSide` screens, `gravity`, `mudSport`, `waterSport` (the `*SideAbilities` members depend on attacker and defender and are built per call from their cached structs) |
| `cacheStats` | `{ builds, hits, decisions }` | diagnostics: structs built, cache hits, `beginDecision()` calls. Never read by the AI |

Lifecycle: created empty with the adapter; cleared by `beginDecision()`; the adapter owner calls it at every
decision boundary (research R3). Shadow-view adapters are created per state and discarded with the decision
context. Validation: a struct is a pure function of the battle state at the time it is built; with
`PLATSIM_AI_FREEZE=1` it is deep-frozen when built.

`BattlerStruct` and `FieldStruct` are the existing shapes documented in `sim/damage.mjs` (`battlerFromShowdown`,
`fromShowdown`); they do not change.

## Resolved effect table (per parsed table, per constants instance)

| Field | Type | Meaning |
|---|---|---|
| `names` | `string[]` | decomp constant names, as parsed from `trainer_ai.c` (unchanged) |
| `line` | number | source line (unchanged) |
| resolved | `WeakMap<Constants, Set<number>>` | the names resolved through that constants instance, built on first use |

Rule: `effectIn(ai, table, x)` ≡ `x ∈ resolved(table, ai.constants)` ≡ `table.names.some((n) => ai.constants.get(n) === x)`.

## Replay fixture (`sim/test/replay_prof_a.json`)

```json
{
  "recorded": { "commit": "<sha>", "date": "2026-10-30", "node": "v22.22.1", "sim_code_hash": "sha256:..." },
  "set": { "block": "a", "n": 20, "teams": ["bench", "ref"], "trainers": ["aaron","bertha","flint","lucian","cynthia"], "stop_on_loss": false, "opponent_policy": "decomp-ai" },
  "policies": {
    "expectimax2-v2": {
      "digest_full": "db6d20cf…", "digest_logs": "<sha256>",
      "gauntlets": [
        { "seed": "prof-a-bench-0", "team": "bench", "cleared": true, "final_levels": [..],
          "battles": [["aaron", "win", 23, "sha256:…"], ...],
          "choices": ["move 2", "switch 3", ...],
          "policy_ai_draws": 12345, "live_ai_draws": [410, 388, ...] }
      ]
    },
    "expectimax2-v1": { ... }
  }
}
```

Identity: `(policy, seed)`. The team fixtures are referenced by name (`bench` = `tests/fixtures/policy_benchmark_team.json`
`.team`; `ref` = `tests/fixtures/reference_team.json` `.builds`), not copied; a change to those files changes the
results and the test says so.

## Bench report (output of `sim/bench.mjs --json` and `platsim bench --json`)

See `contracts/bench-tool.md` for the fields. Identity: `(policy, block, n, teams, trainers, sim_code_hash)`.
Numbers recorded in `validation-log.md` always carry the commit hash, the time (Eastern) and whether the machine
was otherwise idle.
