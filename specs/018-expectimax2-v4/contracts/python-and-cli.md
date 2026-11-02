# Contract: Python plumbing and the comparison script

## Single default (`platsim.evaluate.DEFAULT_PLAYER_POLICY`)

The one constant naming the default strong player. Read by: `cli.py` (`evaluate --player-policy`, `bench --policy`,
`optimize --player-policy` defaults and help text), `platsim.bench.DEFAULT_POLICY`, `OptimizeRequest.player_policy`.
Value `"expectimax2-v2"` until the gate passes; `"expectimax2-v4"` after (commit 5). A unit test asserts every default
equals it.

## `platsim optimize --player-policy NAME` (new option)

Sets `OptimizeRequest.player_policy`. Used by the optimizer for the level search, the setup check, the confirmation
runs and the result's provenance (`result.json.player_policy`, the summary line "(expectimax2-vN, >= N runs)"). The
screening stages keep `greedy-v1`. The web runner does not set it (default). Unknown names fail at the first worker
request as today ("unknown player_policy"), before any long stage.

Row for the README command table: `--player-policy` (default `DEFAULT_PLAYER_POLICY`'s value).

## `OptimizeRequest.player_policy: str = DEFAULT_PLAYER_POLICY` (`platsim.optimizer.api`)

New dataclass field with a default, so every existing constructor call is unchanged. Recorded in `state.json` with the
other request fields (a resumed run keeps its policy).

## `specs/018-expectimax2-v4/scripts/paired_policies.py`

```
uv run python specs/018-expectimax2-v4/scripts/paired_policies.py --a <policy> --b <policy>
    [--teams bench,ref,b2main,b2branch] [--runs 2000] [--workers N] [--out runs/018-evidence/pairs] [--self]
```

- Loads the teams named in research R3; seeds `derive_seed("018-pairs|<team>", i, 0)`; runs `--a` and `--b` on the
  same seeds through one `WorkerPool`; asserts every result `ok` and echoes the requested policy; asserts the first
  battle's seed per run is identical across the two sides (pairing positive control).
- Caches each (team, policy, runs) outcome list under `--out`; reuses a cache whose `sim_code_hash` matches the pool's.
- Prints, per team: `n, A rate, B rate, A-only, B-only, p, verdict, A gauntlets/s, B gauntlets/s`, and appends the row
  to `<out>/summary.json` (data-model.md "Ladder row"). Exit 0 on completion; exit 1 if any request failed.
- `--self`: runs `--a` against itself on the first team with `--runs` (default 200 for the control) and requires
  0 discordant pairs; exit 1 otherwise.

## `specs/018-expectimax2-v4/scripts/equal_levels.py`

The 014 script with the paths and master (`018-equal|B2`) adjusted: A = the v4 optimizer result, B = the v2 result,
both at A's start levels, played by the reference player (`expectimax2-v2`), 2,000 paired runs, `mcnemar_exact(A, B)`
and mean final levels; `--self` control.
