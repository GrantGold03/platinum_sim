# Quickstart & Validation Guide: Champion Team Optimizer

This guide proves the feature works end to end. Commands run from the repository root. Details of
inputs and outputs are in [contracts/](./contracts/), and the entities are described in
[data-model.md](./data-model.md).

## Prerequisites (all at once)

1. **Python 3.14** and **uv**. Both are already installed on this machine.
2. **Node ≥ 22.18**. 22.22.1 is installed.
3. **Vendored sources at the pinned commits**:
   - `pokeplatinum` @ `c248fb3f8cc9934ded800e489567c5c0eeee92eb`
   - `pokemon-showdown` @ `c046106cbe075931b1ff8d8b800ff5be47a85f96`
4. **Network access once**, for `npm ci` (Showdown packages) and `uv sync` (Python packages). This
   is free; there are no paid services. After this, everything runs offline.
5. **Disk**: about 1 GB for `node_modules`, `dist` and `.venv`.

The ROM is not needed to run anything. It is only used to confirm the revision hash.

## Setup

```bash
(cd pokemon-showdown && npm ci && node build)   # writes node_modules/ and dist/ only
uv sync                                          # Python deps into .venv/
uv run platsim extract                           # data/generated/ from the decomp
uv run platsim divergences                       # must exit 0 (no unresolved entries)
```

## Validation scenarios

| # | Run | Expected |
|---|---|---|
| V1 | `uv run pytest` and `node --test sim/` | All suites pass. Output pasted into the task log (Constitution V). |
| V2 | `uv run platsim extract --check` | Exit 0: generated data reproduces exactly from the pinned decomp. |
| V3 | `uv run platsim explain trainer:cynthia` | Spiritomb 58, Roserade 58, Togekiss 60, Lucario 60, Milotic 58, Garchomp 62 (Sitrus Berry); 4× Full Restore; AI flags BASIC, EVAL_ATTACK, EXPERT; each with a `champion_cynthia.json` reference. |
| V4 | `uv run platsim explain species:abra` | Lists the Oreburgh NPC trade (fixed IVs 15/15/15/20/25/25, Quiet, boosted exp) as pre-Champion. `explain species:magikarp` lists the Route 226 Foppa trade as **post-game**. |
| V5 | `uv run platsim validate tests/fixtures/illegal_postgame_tutor.json` | Exit 2 and names "Survival Area tutor: post-game (FLAG_GAME_COMPLETED gate, scripts_snowpoint_city.s:178)". |
| V6 | `uv run platsim validate tests/fixtures/illegal_trade_evo.json` (e.g. Gengar) | Exit 2, "requires trade evolution (FR-005)". |
| V7 | `uv run platsim evaluate tests/fixtures/reference_team.json --runs 2000 --seed fixed` twice | Identical JSON both times. Clear rate CI half-width ≤ 2 points. |
| V8 | `uv run platsim optimize <six species> --seed fixed` | Either a qualifying team (clear ≥ 75%, gap ≤ 10, passes `validate`) or a "no qualifying team" report with the best rate found. xlsx has Team / Evaluation / Resources / Provenance / Divergences sheets, and every move has a source. `team.txt` (Showdown export) is written. Cynthia's win rate is reported separately with CI half-width ≤ 2 points. |
| V9 | `uv run platsim serve`, open http://127.0.0.1:8000 | Search "gar" shows Garchomp, add six species, Optimize, progress updates, then the table and xlsx download appear. |

## Benchmarks to record (not pass/fail; feed the plan's budget)

- Gauntlet runs per second per worker for `greedy-v1` and `expectimax2-v1`.
- Wall time of one full optimize on 16 workers.
