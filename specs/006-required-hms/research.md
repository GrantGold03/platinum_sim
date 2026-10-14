# Research: Required HMs (006)

All findings come from reading `src/platsim` on `006-required-hms`, which is `main` at `dccb3a4`
(2026-10-13). Paths are relative to `src/platsim/`.

## R1. Why a filter is not enough

The optimizer's move pool keeps only attacks. `candidates.member_candidates` (:452-491) works like
this:
- `legal_moves` (:328) keeps every legal move.
- `prune` (:348) keeps only `is_attack` moves: power > 1, not a status move, effect not excluded.
  It also drops dominated ones (R8).
- The pool is the top `POOL = 10` by `move_value` (:458). Movesets are the top 3 coverage combos,
  plus a setup moveset. The top 210 combos (`ranked`) feed `repair`.

So Defog (a status move) never reaches the pool. Fly is weighted 0.5 (`EFFECT_WEIGHT`).
Cut, Rock Smash and Strength usually fall outside the top 10, or are dominated. A search filter
"keep teams that carry the HM" could find no team at all. Moves are also rewritten after the
search in four places, any of which can drop an HM:
- `resources.repair` (:255-285);
- the setup check (`run.py` :478-510);
- the runner-up switch in `_confirm` (`run.py` :587-617);
- the baseline (`run.py` :210).

## R2. Placement in `realize` (decision)

- **Decision**: add `place_required_hms(specs, levels, led, required) -> TeamSpec | None` to
  `optimizer/resources.py`. `realize(specs, levels, led, *, required_hms=())` calls it first when
  `required_hms` is non-empty:
  1. For each required HM, in HM-number order, that no member's `moves` contains yet:
     - **carriers** are members whose variant has a legal source for the HM move at their level:
       `MS.sources(species, move, level, led, o)` over `variant.options(led)`;
     - **cost** for each carrier is the lowest `move_value` among its current moves that are not
       themselves required HMs (using `MemberCandidates.scores`; a move outside the pool scores
       0). A member with fewer than 4 moves gets the HM at no cost;
     - **choice**: the carrier and slot with the lowest cost. Ties go to the lower slot index, then
       the lower move index. The HM replaces that move.
  2. If an HM has no carrier, or every carrier's slots are already taken by required HMs, return
     `None`. `realize` then returns a `Refusal` naming the HM, so the team is dropped like any
     other refused team.
- **Why `realize`**: every team passes through it on the way to battle and to the report. Those
  paths are the baseline, the screen (`run.py` :403-412), finalists, the setup check, `_confirm`,
  `_report` (:652-674) and `report --rerender` (:85). One placement covers them all, so no search
  path can lose an HM.
  - Placement is deterministic: no randomness, fixed tie-breaks. Seeds and reproducibility are
    unchanged (Principle IV).
- **Alternatives rejected**:
  - *Add HM movesets to candidates and filter teams.* The search space may contain no
    combination that carries every HM, and the four rewrite paths can still drop one.
  - *A separate pass after the search.* The battle results would then be for a different moveset
    than the one reported.
- **Effect on win rate**: the HM replaces the member's weakest attack. The evaluation is then run
  with the real moveset, so the reported clear rate is honest.

## R3. Refusing before a run (FR-005)

- **Decision**: a shared function `unlearnable_moves(consts, moves, led) -> list[str]` in
  `legality/movesources.py`. It returns the required HM moves for which no member has any legal
  source at level 100, using `MS.sources(c, m, 100, led)`. Legality only grows with level
  (`resources.py` :31-33), so level 100 is the loosest test. Where it is called:
  - **Optimizer**: `run.run_optimization`, right after `C.resolve_species` (run.py:269) and before
    the `WorkerPool`. It raises `InvalidRequest("required HMs no team member can learn: Fly",
    reasons={"fly": "No team member can learn Fly"})`, and the CLI exits 2.
  - **Web**: `SpeciesCatalog.resolve_team` gets the same check through a callback built in
    `build_catalog`, like 004's `conflicts`. It returns 422 with `reasons` keyed by HM.
  - **evaluate / validate**: the validator's new rule (R5) covers these, because they take a team
    with movesets.
- **Rationale**: the same refusal shape as 004. The message names each HM.

## R4. Where required HMs are carried

- **Request**: `OptimizeRequest.required_hms: tuple[str, ...] = ()`. It holds move keys
  (`"surf"`, …), normalised and ordered by HM number.
  - It is **not** a `LegalityOptions` field. `from_dict` accepts only booleans, and the CLI and
    web loops treat every legality field as a boolean flag (`cli.py` :23-39, `app.py` :538-550).
- **Fingerprint**: `job_fingerprint` (`run.py` :85-87) adds `"required_hms": [...]` only when
  it is non-empty. Default fingerprints, and with them `default_out_dir` and resume, are unchanged
  (FR-009).
- **Reports**:
  - A top-level `provenance["required_hms"]` is added only when non-empty. The xlsx provenance
    sheet writes every top-level key, so it appears there automatically (`report/xlsx.py`
    :152-153).
  - `_optimizer_provenance` `request` gets the same key, also only when non-empty.
  - `report/rerender.py` reads it back and passes it to `validate`.
- **Web**:
  - `_options` (`app.py` :523-545) accepts `required_hms`: a list of HM keys, default `[]`.
    Unknown names → 422.
  - The job stores it, and `run_one` reads `opts.get("required_hms", [])`, so old job.json files
    still load.
  - `result_view` exposes `provenance.required_hms`, and `app.js` adds a "Required HMs" summary
    row.
- **CLI**: a `--require-hm NAME` flag, repeatable, with choices from the eight HM names. It goes
  on `optimize`, `evaluate` and `validate`, as a separate helper from `_add_legality_flags`.

## R5. Validator rule

- **Decision**: `validate(team, ledger=None, final_levels=None, options=None, *,
  required_hms=())`. It adds the code `REQUIRED_HM_MISSING`, one violation per required HM that
  no build's moves contain.
  - Its `src` refs are the HM item's entry in the decomp item table, the same ref
    `decomp.items.tm_moves` reads, and spec 006 FR-002.
  - The validator still never imports `platsim.optimizer` (Principle III independence; it is
    checked by `test_validator.py`).
- **Callers**: `run.py` :412 and :657, `evaluate.load_and_validate` (`evaluate.py` :79-94),
  `cli validate` and `report/rerender.py` :95 pass the request's `required_hms`. Callers that pass
  nothing behave as before.

## R6. HM names and moves

`decomp.items.tm_moves()` maps `HM01`…`HM08` to `MOVE_*` (Principle I: from the decomp). The
order and display names come from there and from `load_moves()`:

| HM | Move |
|---|---|
| HM01 | Cut |
| HM02 | Fly |
| HM03 | Surf |
| HM04 | Strength |
| HM05 | Defog |
| HM06 | Rock Smash |
| HM07 | Waterfall |
| HM08 | Rock Climb |

Nothing is typed by hand.

## R7. Web page

- **Steps**: in `index.html`, the "3. Optimize" heading (:70) becomes "4. Optimize". A new card,
  "3. Required HMs", goes before it, with eight checkboxes (`class="hm"`, ids `require-hm-<key>`),
  all unchecked.
- **Test conflict**: `tests/integration/test_web.py::test_legality_options_page_search_and_jobs`
  (:254) asserts `page.count('type="checkbox"') == 5`. It must count only the legality rule
  checkboxes. Update it to scope the count to those 5 ids; the HM checkboxes are tested separately.
- **app.js**: the request body (:216-221) adds `required_hms: [checked keys]`.
