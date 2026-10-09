# Data Model: Web UI Redesign

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

These entities are web-layer only. The optimizer's `OptimizeRequest`, `Progress` and report
files do not change (FR-030).

## Job (`runs/<id>/job.json`, extended)

Existing fields are kept: `id`, `species[6]`, `options`, `status`, `created`, `started`,
`finished`, `progress`, `result_paths`, `qualified`, `error`, `invalid_reasons`, `traceback`.

| Field | Type | New? | Notes |
|---|---|---|---|
| `status` | `queued \| running \| done \| failed \| cancelled` | `cancelled` new | terminal: done, failed, cancelled |
| `platsim_version` | str \| absent | new | `importlib.metadata.version("platsim")` stored when the job starts running, not at creation (R5, analysis N5). Absent on older jobs |
| `cancel_requested` | ISO time \| absent | new | set by the cancel endpoint; used to settle the cancel/finish race |
| `progress.stage_started` | ISO time | new | reset whenever `progress.stage` changes, and carried forward on same-stage updates (needed for ETA, R2) |
| `progress.seen_stages` | list[str] | new | stages seen so far, carried forward; used by the ETA (P4-09) |
| `verdict` | `qualified \| borderline \| not_qualified` \| absent | new | written when a job finishes `done`, from its result.json. Used for `label` |
| `progress.best_so_far` | dict \| null | kept | still stored, but no longer displayed (FR-013) |

**State transitions**

```text
queued ──run_one──▶ running ──child exits, result present──▶ done
   │                   │──child exits with error / dies──▶ failed
   │                   └──cancel (killpg) and no result───▶ cancelled
   └──cancel──────────────────────────────────────────────▶ cancelled
server restart: running ──▶ failed (unchanged); queued ──▶ resubmitted (unchanged)
```

**Rules**:
- Cancel on `done`, `failed` or `cancelled` → 409.
- If the child finished and wrote `result.json` before the kill landed, the status becomes
  `done` and the cancel is ignored. One status always wins (spec edge case).
- A cancelled job keeps any files the child wrote under `runs/<id>/`. They are not shown and not
  resumed.

## JobView (`GET /api/jobs/{id}` and list items, computed, not stored)

These fields are added to today's view:

| Field | Type | When |
|---|---|---|
| `elapsed_s` | float | running: now − `started`; finished: `finished` − `started` |
| `eta_s` | float \| null | running only; null = "estimating…" (R2) |
| `label` | str | e.g. "Infernape, Staraptor, … · qualified". It has no time; the page adds the `created` time in the browser's local time (FR-015, analysis A1) |
| `platsim_version` | str \| null | null → page shows "platsim version not recorded" |

## ResultView (`GET /api/jobs/{id}` when `status == done`)

This replaces today's `summary` and `table`.

**summary**
- `verdict` (`qualified \| borderline \| not_qualified`)
- `clear_rate`
- `clear_ci95` and `n_runs` (shown in the clear-rate tooltip only, FR-017)
- `avg_final_level`
- `level_gap`
- `threshold`
- `budget`
- `legality_options`
- `warnings[]`
- `no_qualifying`
- `platsim_version`

It drops these fields from the screen: `champion_*`, policies,
`objective`, and all commit hashes (FR-017–FR-021).

**per_trainer[]**: `{trainer, label, rate, ci95[2], battles}`, in battle order. Empty when the
run has no `per_battle`.

**team[]**, one entry per slot:

| Field | Source | Notes |
|---|---|---|
| `slot` | CSV `Slot` | |
| `species_key` | `result.json team.builds[].species` | used for the sprite URL |
| `species` | CSV `Species` | display name |
| `sprite` | — | `/api/sprites/<species_key>/front.png` |
| `start_level` | CSV | |
| `final_level` | CSV `Final level (expected)` | |
| `ability` | build `ability` + `ability_reason` + decomp `data.json` | `"A/B (no significant difference)"` for `tie_default` (R4), else the display name |
| `held_item` | CSV `Held item` | the source is not sent |
| `obtained_from` | CSV `Obtained from` | |
| `moves[4]` | CSV `Move n` + `Move n source` | `{name, source}`. The source is shown on hover or focus only (FR-026) |

These are not sent: nature, IVs, EVs, `Ability choice`, `Held item source` (FR-024).

**downloads**: unchanged (FR-022).

## SpriteRequest

- `species`: must match a folder name under `pokeplatinum/res/pokemon/` (allowlist built at
  startup). Anything else → 404. The value never reaches the filesystem as a raw path.
- `kind`: `front` (from `male_front.png`, falling back to `female_front.png`) or `icon` (from
  `icon.png`).
- Response: the PNG bytes with an added `tRNS` chunk (index 0 transparent), cached in memory.

## StageTimingHistory (in memory, computed)

- Built from every `runs/*/state.json`: for each budget and stage, the list of `timing[stage]`
  seconds. It uses the median.
- Refreshed when a job ends.
- The data is a few kilobytes.
