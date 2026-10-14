# Quickstart: validating 006

Each scenario says how to check one part of the feature. See the contract
([required-hms](contracts/required-hms.md)) and the entities ([data-model](data-model.md)).

## Prerequisites

- **Location**: the worktree `../platinum_sim-006`, branch `006-required-hms`. `pokeplatinum`
  and `pokemon-showdown` are symlinks to the main checkout.
- **Setup**: run `uv sync`, then `uv run platsim extract`. `data/generated/` is not shared, so it
  must be built in the worktree. Then `uv run platsim extract --check` must pass.

## Fast checks

```bash
uv run pytest -q tests/unit/test_required_hms.py tests/unit/test_validator.py \
  tests/unit/test_source_preference.py tests/unit/test_optimizer_candidates.py tests/integration/test_web.py
```

## V1. Placement (US1)

- **Do**: run `realize` on a TeamSpec whose movesets have no Surf, with `required_hms=("surf",)`.
- **Expect**:
  - exactly one member's moves contain `surf`, on the carrier with the cheapest replaced move;
  - the team validates with `required_hms=("surf",)`.
- **Several HMs**: require Surf and Waterfall on a team where only one member learns both.
  - **Expect**: that member carries both.
- **Positive control**: the same TeamSpec without `required_hms` is unchanged.

## V2. Refusal (US2)

- **Do**: `run_optimization` with six species that can't learn Fly (e.g. Garchomp ×6), with
  `required_hms=("fly",)`.
- **Expect**: `InvalidRequest`, with `reasons == {"fly": "No team member can learn Fly"}`, and no
  `WorkerPool` started.
- **Web**: the same request returns 422, and no job is created.
- **Positive control**: replace one member with Staraptor and the request passes the check.
- **Options**: an HM learnable only through a rule (if one exists, found with the
  `unlearnable_moves` probe) is refused with the rule off and passes with it on.

## V3. Validator (FR-004)

- **Do**: `legal_team.json` validated with `required_hms=("fly",)`.
  - **Expect**: `REQUIRED_HM_MISSING`.
- **Do**: the same team with `required_hms=("waterfall",)`. Gyarados knows Waterfall in that
  fixture.
  - **Expect**: no violation.

## V4. Default unchanged (FR-009)

- `job_fingerprint` of a default request equals the value recorded at T001 (`validation-log.md`).
- `test_web_final_defaults` re-render fixtures are unchanged.

## V5. Web page (US3)

- The headings read 1–4 in the contract order, and step 3 has 8 unchecked HM boxes.
- The legality-rule checkbox count test is scoped to its own 5 ids.
- Checking Surf and starting a stub job puts `required_hms: ["surf"]` in job.json and the
  summary.

## V6. Small real run (end to end)

- **Do**: `uv run platsim optimize <six species> --budget quick --require-hm surf --require-hm waterfall`.
  Running locally costs nothing.
- **Expect**: the report's team carries both HMs, `provenance.required_hms ==
  ["surf", "waterfall"]`, and `platsim validate --require-hm surf --require-hm waterfall` on the
  output passes.

## Full suite before merge

The full suite (`uv run pytest -q`) must be green before merge. Record the output in
`validation-log.md`.
