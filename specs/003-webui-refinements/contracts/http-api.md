# Contract: HTTP API changes (003)

This file lists only the changes. Everything else is as in
`specs/002-webui-redesign/contracts/http-api.md`. The server still binds to 127.0.0.1 only and
works offline.

## Rule names (used by every endpoint below)

`allow_egg_moves`, `allow_trade_evolutions`, `allow_post_game_pokemon`, `allow_post_game_items`,
`allow_unobtainable_pokemon`. They are all booleans and all default to false.

## `GET /api/species` (changed)

- **Params**:
  - `q`, `limit`, as before.
  - `trade_evolutions`, `post_game_pokemon`, `post_game_items` and `unobtainable_pokemon`, each `0` or
    `1` (default 0).
  - `excluded` is still accepted, but the page always sends `1`. It is kept for the command line and
    tests.
- **Item fields**: unchanged, except:
  - `reason_code` has the values `trade_evolution`, `trade_evolution_unavailable`, `post_game`,
    `national_dex`, `unavailable`, `pre_evolution_unavailable`. (`excluded`, `unobtainable` and
    `no_source` are gone.)
  - `reason` follows the data model table. It never contains a requirement id or "species".
- **503 while loading**: `detail` reads "Pokémon data is loading…".

## `POST /api/jobs` (changed)

- **Body**: accepts the three new rule keys. Each must be a boolean, or the request gets a 422.
- **Stored rules**: `job.options` holds all five keys.
- **Errors**: 422 `detail` and `reasons` texts use "Pokémon" and contain no requirement ids. An unknown
  name reads "unknown Pokémon".

## `GET /api/jobs/{id}` (changed)

- `summary.legality_options` holds all five keys for new runs. Old runs have two keys or `null`, and
  the page treats missing keys as off.
- `team[i].moves[j]` gains `type`, the display type name, e.g. "Fire". It is `null` if the move key is
  unknown.
- All shown text fields have been through the display cleaner (research R6): `summary.warnings[]`,
  `team[i].obtained_from`, `moves[j].source`, `error`, and `invalid_reasons` values.

## `GET /api/league` (new)

- Returns 200 with the five first-run trainers in order (data model "League"). The data is static, so
  the response carries `Cache-Control: max-age=86400`.
- Party entries are pokemon keys that `GET /api/sprites/{key}/icon.png` and `front.png` accept.

## `GET /api/trainer-sprites/{trainer}.png` (new)

- `trainer` is one of `aaron`, `bertha`, `flint`, `lucian`, `cynthia`. Anything else → 404 with a JSON
  `detail`. The path is never built from raw input.
- The response is 200 `image/png`: `res/trainers/classes/<class>/front_scan.png` (160×80, two frames)
  with index 0 made transparent. It is cached in memory and sent with `Cache-Control: max-age=86400`.
