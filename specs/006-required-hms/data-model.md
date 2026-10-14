# Data Model: Required HMs (006)

## Required HMs (new input)

| Where | Field | Type / values | Default |
|---|---|---|---|
| `OptimizeRequest` | `required_hms` | `tuple[str, ...]` of move keys from {`cut`, `fly`, `surf`, `strength`, `defog`, `rock_smash`, `waterfall`, `rock_climb`}, deduplicated, in HM-number order | `()` |
| Web job `options` (job.json) | `required_hms` | list of the same keys | absent or `[]` = none |
| `job_fingerprint` | `required_hms` | sorted list | **omitted when empty** |
| Report `provenance` | `required_hms` | list of keys | **omitted when empty** |
| Report `provenance.optimizer.request` | `required_hms` | list of keys | **omitted when empty** |
| CLI | `--require-hm NAME` (repeatable) | the same eight names | none |

- The keys are data/generated move keys, as used in `Build.moves`.
- The HM ↔ move mapping comes from `decomp.items.tm_moves()` (`HM01`…`HM08`).

## Rules

- **H1 (carried)**: a required HM is satisfied iff some build's `moves` contains its move key.
  The validator code is `REQUIRED_HM_MISSING`, one per missing HM.
- **H2 (learnable)**: a request is impossible iff, for some required HM, no member species has a
  legal source for the move at level 100 under the request's legality options. The request is
  refused before any battle (`InvalidRequest` / 422), with one reason per HM.
- **H3 (placement)**: `realize` places each missing required HM on the member with the cheapest
  legal slot (research R2). It is deterministic. If no carrier exists at the member levels, the
  team is refused (`Refusal`) and dropped like any other refused team.
- **H4 (default)**: with `required_hms == ()`, nothing above runs. Fingerprints, reports and
  outputs are byte-identical to before.

## Validation messages

| Case | Text |
|---|---|
| Refusal (H2) | `No team member can learn <Move>` (per HM, keyed by HM key) |
| Validator (H1) | `required HM <Move> is not in any member's moveset` |
| Placement failure (H3) | `no member can carry required HM <Move> at these levels` |
