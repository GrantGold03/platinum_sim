# Contract: Python ↔ Node sim worker

- **Process**: `node sim/worker.mjs`. It runs as one long-lived process per worker slot.
- **Transport**: newline-delimited JSON over stdin/stdout; stderr carries logs only.
- **Matching**: every request has an `id`, and the response echoes it.

## Requests
```json
{"id": 1, "op": "hello"}
→ {"id": 1, "ok": true, "showdown_commit": "...", "sim_code_hash": "sha256:...", "node_version": "v22.22.1",
   "decomp_commit": "...", "decomp_data_hash": "sha256:...", "divergence_ledger_version": "...",
   "divergence_patches_applied": 5, "policies": ["greedy-v1", "expectimax2-v2", ...],
   "opponent_policies": ["decomp-ai", ...], "pp_restore_between_battles": false}

{"id": 2, "op": "gauntlet",
 "team": [ /* 6 Build objects incl. start_level, moves, ability, item, nature, ivs, evs, is_traded */ ],
 "seed": "sodium,0123...", "player_policy": "expectimax2-v1",
 "trainers": ["aaron","bertha","flint","lucian","cynthia"],
 "stop_on_loss": true, "log": "none" | "summary" | "full"}
→ {"id": 2, "ok": true, "cleared": false,
   "battles": [{"trainer":"aaron","won":true,"turns":14,"log_hash":"..."}, ...],
   "final_levels": [..6], "exp_events": [...], "log": null}

{"id": 3, "op": "damage_check", "attacker": {...}, "defender": {...}, "move": "earthquake", "field": {...}}
→ {"id": 3, "ok": true, "decomp_rolls": [16 ints], "showdown_rolls": [16 ints]}

{"id": 4, "op": "gauntlet", "team": [...], "seed": "...", "player_policy": "expectimax2-v1",
 "trainers": ["cynthia"],
 "start_state": {"levels": [..6], "exp": [..6], "pp": [[..4] ×6], "items": [..6]}}
→ same response shape as op 2. This is used for the Cynthia top-up (research R8). Without
  `start_state`, the team starts at its build values.
```

Every `gauntlet` response with `"log": "summary"` or `"full"` also includes `state_before` per battle (the
`start_state` shape), so Cynthia top-ups can resume from a recorded post-Lucian state.

`hello` code version (sim/version.mjs, computed once at worker start):
- `sim_code_hash` = `"sha256:"` + sha256 over every `*.mjs` and `package.json` under `sim/`, excluding
  `sim/test/**`, `sim/spikes/**` and `node_modules/**`. Files are taken in ascending order of their
  repo-relative POSIX path (`sim/ai/adapter.mjs`, ...), each contributing
  `<path utf-8> 0x00 <byte length, decimal> 0x00 <file bytes>`. `src/platsim/version.py` computes the
  same hash in Python.
- `node_version` = `process.version`.

The pool (`src/platsim/sim/pool.py`) requires `showdown_commit` / `decomp_commit` to equal the pins,
refuses a hello without `sim_code_hash`, and requires every worker (including a restarted one) to
report the same `sim_code_hash`, `node_version`, data hash, ledger version and policies.

## Guarantees
- **Determinism**: the same request with the same seed gives byte-identical output, apart from
  `log_hash` for logs that contain timestamps (timestamps are stripped before hashing).
- **Between battles**: HP, status and fainted members are restored and PP is carried over
  (FR-012). Levels and exp persist.
- **Errors**: `{"id": n, "ok": false, "error": {"kind": "invalid_team" | "ai_unimplemented" | "internal", "detail": "..."}}`.
  `ai_unimplemented` names the AI command that was reached; it is never silently skipped.
