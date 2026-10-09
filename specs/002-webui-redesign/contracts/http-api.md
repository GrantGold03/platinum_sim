# Contract: HTTP API changes

The server binds to 127.0.0.1 only (unchanged). Every endpoint not listed here is unchanged,
and so is the shape of every existing field this page does not stop using. This file lists only
the changes.

## `POST /api/jobs` (unchanged shape)

- `budget` (`quick | standard | thorough`, default `standard`) is already accepted. The page now
  sends it (FR-005). An unknown budget → 422 (existing behaviour).

## `GET /api/jobs` (existing, now used by the page)

- Newest first, up to 50 jobs. Each item is a JobView ([data-model](../data-model.md)) and adds
  `label` (species and verdict or status, with no time), `elapsed_s`, `eta_s` (running only)
  and `platsim_version`. `created` is already in the view as UTC ISO time, and the page formats
  it in local time.
- Items never include `summary`, `team` or `per_trainer`. The page fetches those one job at a
  time.

## `GET /api/jobs/{id}` (extended)

- `status` may now be `cancelled`.
- When `status == done`, the response includes `summary`, `per_trainer`, `team` and
  `downloads` as defined in the [data model](../data-model.md) ResultView.
- **Breaking change**: `summary` loses the keys the page no longer shows, and `table` is
  removed. The only client is `static/app.js`, and both are changed together. The downloadable
  files still carry everything.

## `POST /api/jobs/{id}/cancel` (new)

| Job state | Response |
|---|---|
| queued | 200 `{"id", "status": "cancelled"}`. It never starts |
| running | 202 `{"id", "status": "running", "cancel_requested": "<time>"}`. The final status follows within 10 s (SC-004): `cancelled`, or `done` if the job had already finished |
| done / failed / cancelled | 409 `{"detail": "job <id> is <status>"}` |
| unknown id | 404 |

## `GET /api/sprites/{species}/{kind}.png` (new)

- `kind ∈ {front, icon}`. Responds 200 `image/png` with `Cache-Control: max-age=86400`.
- Unknown species, unknown kind or a missing file → 404 with a JSON `detail`. The page shows its
  placeholder.
- Works offline: the image is read from the vendored decomp.

## `GET /api/species` (one field added)

- Each item gains `sprite_icon`, the URL of its icon, so team slots can show it (FR-004).
