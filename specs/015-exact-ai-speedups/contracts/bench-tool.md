# Contract: benchmark tool and replay fixture

## `node sim/bench.mjs` (single process)

```
node sim/bench.mjs [--policy expectimax2-v2] [--n 20] [--block a] [--teams bench,ref]
                   [--trainers aaron,bertha,flint,lucian,cynthia] [--json] [--record FILE]
```

Runs the request set in this process with `runGauntlet` and prints a human table (default) or JSON (`--json`).
Exit 0; exit 1 on an unknown policy or team. Loads `data/generated/` like the worker does
(`PLATSIM_GENERATED_DIR` / `PLATSIM_DIVERGENCES` respected).

**Request set** (`benchRequests({ block, n, teams, trainers })`, exported): for each team name in order, for
`i` in `0..n-1`: `{ team, seed: "prof-<block>-<team>-<i>", player_policy, opponent_policy: "decomp-ai",
stop_on_loss: false [, trainers] }`. Team names: `bench` = `tests/fixtures/policy_benchmark_team.json` `.team`,
`ref` = `tests/fixtures/reference_team.json` `.builds`. The default set (block `a`, n 20, both teams, all five
trainers) is the spec's fixed set.

**JSON output**:

| Field | Meaning |
|---|---|
| `policy`, `block`, `n`, `teams`, `trainers` | the set |
| `gauntlets`, `cleared`, `battles`, `turns` | counts |
| `wall_s`, `gauntlets_per_s` | wall time of the loop, throughput |
| `decisions`, `ms_per_decision`, `ai_calls_per_decision`, `ai_draws` | from `STATS` deltas (`expectimax2` policies; `null` for others) |
| `digest_full` | sha256 hex over `JSON.stringify(result)` of each gauntlet in order (the profiling harness's digest; `db6d20cf…` for v2 on `main`) |
| `digest_logs` | sha256 hex over the per-gauntlet lines below |
| `stats` | the raw `STATS` delta object |
| `sim_code_hash`, `node`, `date` | provenance |

**`digest_logs` line**, one per gauntlet in request order, `\n`-terminated, hashed as UTF-8:

```
<seed>|<cleared: 1 or 0>|<final_levels joined by ,>|<battles joined by ;>
battle = <trainer>:<end>:<turns>:<log_hash>
```

**`--record FILE`**: writes the replay fixture (schema in `data-model.md`) for the policy run; merging a second
policy into an existing file is done by running again with the other `--policy` (the file is read, the policy
key replaced, the file rewritten).

**`runRecorded(gd, req)`** (exported): runs one request with wrapped policies and returns `{ result, json,
choices, policy_ai_draws, live_ai_draws }`. The wrappers call through and record only; `result` is byte-identical
to an unwrapped run (checked by `digest_full`).

## `platsim bench`

```
uv run platsim bench [--policy expectimax2-v2] [--n 20] [--block a] [--teams bench,ref] [--trainers ...]
                     [--workers W] [--no-single] [--json]
```

1. Unless `--no-single`: runs `node sim/bench.mjs --json` with the same set and reports its figures.
2. Builds the same requests (`op: "gauntlet"`, same seeds and teams) and times `WorkerPool(W).map(requests)`;
   reports `pool_workers`, `pool_wall_s`, `pool_gauntlets_per_s`, `pool_sim_code_hash` (from the hello) and
   `pool_digest_logs` computed from the returned results with the line format above.
3. Positive control: when both halves ran, `pool_digest_logs` must equal the single-process `digest_logs`;
   otherwise prints both and exits 1.

Output: a table on stdout (`--json` for the merged JSON). Progress to stderr. Exit 0 / 1 as above; 2 on an
invalid option. Row for `specs/001-*/contracts/cli.md` and the README command table:

| `platsim bench` | Time the battle player on the fixed seed set, single process and worker pool | `--policy`, `--n`, `--block`, `--teams`, `--trainers`, `--workers`, `--no-single`, `--json` | gauntlets/s, ms/decision, digests; exit 1 if the pool and single-process digests differ |

## Replay test (`sim/test/replay.test.mjs`)

For each policy in the fixture: runs the fixture's set with `runRecorded` across `min(16, cpus)` worker threads,
reassembles in request order and asserts: `digest_full` and `digest_logs` equal the fixture's; per gauntlet,
`choices`, `policy_ai_draws` and `live_ai_draws` equal. Diagnostic line: gauntlets, decisions, seconds. Positive
control test: a copy of the fixture with one choice altered fails the comparison.
