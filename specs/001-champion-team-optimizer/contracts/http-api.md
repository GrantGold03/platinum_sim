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
   seed.
4. While the job runs, the page polls and shows the stage, runs done, and the best result so far.
5. When done, the page shows the team table (same columns as the spreadsheet) with a download link
   for `.xlsx` and `.csv`.

## Endpoints
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/` | | page |
| GET | `/api/species?q=gar` | | `[{key, name, types, available, reason?}]` (≤ 25) |
| POST | `/api/jobs` | `{species: [6 keys], min_clear?: float, seed?: str, budget?: str}` | `201 {id}`; `422` with per-species reasons if invalid |
| GET | `/api/jobs/{id}` | | `Job` (see data-model) |
| GET | `/api/jobs/{id}/result.json` · `/result.xlsx` · `/result.csv` · `/team.txt` | | file; `409` until done |

Only one job runs at a time (it uses all workers). Later jobs queue.
