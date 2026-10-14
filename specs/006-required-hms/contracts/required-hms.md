# Contract: Required HMs (006)

Everything not listed here is unchanged. With no HM required, every interface behaves exactly as
before.

## Command line

- **`--require-hm NAME`**, repeatable, on `optimize`, `evaluate` and `validate`.
  - NAME is one of `cut`, `fly`, `surf`, `strength`, `defog`, `rock_smash`, `waterfall`,
    `rock_climb`; display names such as "Rock Smash" are also accepted.
  - An unknown name fails argument parsing with exit 2.
- **`optimize`**: if a required HM can't be learned by any of the six, it prints
  `invalid request: No team member can learn Fly` (one entry per HM) to stderr and exits 2 before
  any battle.
- **`evaluate`**: if the given team's movesets don't carry a required HM, it is refused with
  `REQUIRED_HM_MISSING` (the existing invalid-team path, exit 2).
- **`validate`**: reports `REQUIRED_HM_MISSING` in its violations output.

## HTTP

- **`POST /api/jobs`**:
  - **Body**: an optional `"required_hms": ["surf", "waterfall"]` (list of keys). Absent or `[]`
    means none.
  - **Errors**: a non-list, or an unknown key, returns 422 with `detail`. A required HM that no
    team member can learn returns 422:
    `{"detail": "some Pokémon cannot be used: No team member can learn Fly", "reasons": {"fly": "No team member can learn Fly"}}`.
    No job is created.
- **`GET /api/jobs/{id}`**: `summary.required_hms` is a list of keys, or `null` for runs without
  them.

## Reports

- **JSON**: `provenance.required_hms` and `provenance.optimizer.request.required_hms` are present
  only when non-empty.
- **Spreadsheet**: the provenance sheet gets a `required_hms` row only when non-empty.
- **Validator code**: `REQUIRED_HM_MISSING`, with message
  `required HM <Move> is not in any member's moveset`.

## Web page

- **Step headings**: `1. Choose Pokémon`, `2. Team`, `3. Required HMs`, `4. Optimize`.
- **Step 3**: eight checkboxes in HM-number order, labelled with move names (Cut, Fly, Surf,
  Strength, Defog, Rock Smash, Waterfall, Rock Climb). All are unchecked by default.
  - Each label shows the HM number (e.g. "HM03 Surf").
  - ids are `require-hm-<key>`.
- **Results summary**: a "Required HMs" row lists the move names, or "none".
- **422 refusal**: shown in the same error area as the 004 starter refusal.
