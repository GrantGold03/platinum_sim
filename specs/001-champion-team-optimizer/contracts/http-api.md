# Contract: Web UI and HTTP API

The server is local only (binds to 127.0.0.1). The page is a single static HTML/CSS file with a
small amount of plain JS.

## Page behaviour
1. A search box filters species as you type. Results show only species obtainable before the
   Champion; a toggle shows excluded species greyed out, with the reason (e.g. "post-game",
   "trade evolution").
2. Clicking a result adds it to a 6-slot team; slots can be removed. Duplicates are allowed
   (the game allows them).
3. With 6 species chosen, "Optimize" submits a job. Options: minimum clear rate (default 75%) and
   seed. Two checkboxes, both unchecked by default: "Allow egg moves" and "Allow trade evolutions".
   The trade-evolution box also changes which species the search shows as available (a species
   reachable only by trade evolution is then marked "trade evolution: needs a second cartridge for
   the trade"). Egg moves never change species availability.
4. While the job runs, the page polls and shows the stage, runs done, and the best result so far.
5. When done, the page shows the team table (same columns as the spreadsheet) with a download link
   for `.xlsx` and `.csv`.

> **Superseded by feature 002 (web UI redesign).** Steps 4–5 describe the original page. The
> current page shows progress with elapsed time, an ETA and Cancel, and replaces the table with a
> summary, a per-trainer chart and team cards. The current endpoints, including
> `POST /api/jobs/{id}/cancel` and `GET /api/sprites/...`, are in
> `specs/002-webui-redesign/contracts/http-api.md` and `contracts/ui.md`.

## Endpoints
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/` | | page |
| GET | `/api/species?q=gar&excluded=1&trade_evolutions=0` | `trade_evolutions=1`: availability with trade evolutions allowed | `[{key, name, types, available, reason?, reason_code?, trade_evolution?, note?}]` (≤ 25) |
| POST | `/api/jobs` | `{species: [6 keys], min_clear?: float, seed?: str, budget?: str, allow_egg_moves?: bool, allow_trade_evolutions?: bool}` (flags default `false`; a non-boolean gives `422`) | `201 {id}`; `422` with per-species reasons if invalid (species are checked under `allow_trade_evolutions`) |
| GET | `/api/jobs/{id}` | | `Job` (see data-model) |
| GET | `/api/jobs/{id}/result.json` · `/result.xlsx` · `/result.csv` · `/team.txt` | | file; `409` until done |

Only one job runs at a time (it uses all workers). Later jobs queue.
