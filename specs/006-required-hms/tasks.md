---
description: "Task list for 006 Required HMs"
---

# Tasks: Required HMs on the Team

**Input**: the design documents in `specs/006-required-hms/`: plan.md, spec.md, research.md
(R1–R7), data-model.md (H1–H4), contracts/required-hms.md and quickstart.md (V1–V6).

**Tests**: included. Spec FR-010 lists the regression tests. The constitution requires positive
controls (Principle V).

**Format**: `[ID] [P?] [Story] Description`. `[P]` means the task can run in parallel, because it
touches different files and has no unfinished dependency.

## Ground rules for every task

- **Where**: all work happens in the git worktree `/home/grant/Desktop/platinum_sim-006`, branch
  `006-required-hms`. Never edit the main checkout `/home/grant/Desktop/platinum_sim`, which is
  on branch 005.
  - `pokeplatinum` and `pokemon-showdown` are symlinks; never commit them.
  - Commit on the branch when done. Don't merge until the user has tested it.
- **Defaults**: with no HM required, fingerprints, reports and outputs must be byte-identical
  (FR-009). Every new key is written only when non-empty.
- **Scope**:
  - The validator must not import `platsim.optimizer`.
  - Don't edit `sim/` or anything under `runs/`.
- **HM ↔ move mapping**: always from `decomp.items.tm_moves()`. Never type the HM list by hand.
- **Recording results**: paste the real test output for each checkpoint into
  `specs/006-required-hms/validation-log.md` (created in T001).
- **Temp files** go in the session scratchpad. Run probe scripts with `python -u`.
  - If another test suite is running in the main checkout, run heavy commands with `nice -n 10`.

## Path conventions

- **Code**: `src/platsim/legality/`, `src/platsim/optimizer/`, `src/platsim/report/`,
  `src/platsim/web/`.
- **Tests**: `tests/unit/`, `tests/integration/`, `tests/browser/`.

---

## Phase 1: Setup

- [X] T001 Prepare the worktree and record the baseline in a new
  `specs/006-required-hms/validation-log.md`:
  - `uv sync`, then `uv run platsim extract`, then `uv run platsim extract --check`;
  - `git rev-parse HEAD`;
  - the output of `uv run pytest -q tests/unit/test_validator.py tests/unit/test_source_preference.py tests/unit/test_optimizer_candidates.py tests/integration/test_web.py`;
  - `job_fingerprint(...)` and `default_out_dir(...)` for a default `OptimizeRequest` with six
    species (e.g. the six in `tests/fixtures/legal_team.json`), for the FR-009 comparison;
  - `sha256sum tests/fixtures/web_final_defaults/*`.
- [X] T002 Confirm that no `runs/*/state.json` in the worktree needs resuming. `runs/` is
  git-ignored, so the worktree normally has none. Record the result.

---

## Phase 2: Foundational

- [X] T003 Add `HM_MOVES` to `src/platsim/legality/movesources.py`: an ordered tuple of
  `(hm_item, MOVE_*, key, display name)` built from `decomp.items.tm_moves()` (`HM01`…`HM08`)
  and `load_moves()`. Add `hm_key(name) -> key` to accept keys or display names (e.g.
  "Rock Smash" or `rock_smash`).
  - Unit test in a new `tests/unit/test_required_hms.py`: 8 entries in HM-number order. Cut is
    HM01 and Rock Climb is HM08, read from the decomp, not typed.
- [X] T004 Add `required_hms: tuple[str, ...] = ()` to `OptimizeRequest` in
  `src/platsim/optimizer/api.py`. Normalise the keys through `hm_key`, deduplicate them and order
  them by HM number. Raise `InvalidRequest` on unknown names.

**Checkpoint**: the T001 tests are still green.

---

## Phase 3: User Story 2 — Impossible requirements are refused (P1)

**Goal**: a required HM that no team member can learn stops the run before any battle (H2).

**Independent test**: quickstart V2.

### Tests (write first and see them fail)

- [X] T005 [P] [US2] Add refusal tests to `tests/unit/test_required_hms.py`:
  - `MS.unlearnable_moves([GARCHOMP]*6, ["fly"], ledger) == ["fly"]`;
  - with Staraptor swapped in → `[]` (positive control);
  - several missing HMs are all returned, in HM order.
  - Then `run.run_optimization(OptimizeRequest(species=("garchomp",)*6, required_hms=("fly",), budget="quick"))`
    raises `InvalidRequest` with `reasons == {"fly": "No team member can learn Fly"}`.
    Monkeypatch `WorkerPool` to fail if constructed, so the test proves no pool starts.
  - Legality-option side: use a probe to find an HM learnable only with
    `allow_post_game_items` (or another option) for some species. If one exists, assert the
    refusal with the option off and no refusal with it on. If none exists under the current data,
    record that in `validation-log.md` and test the option path with a monkeypatched
    `MS.sources`.
- [X] T006 [P] [US2] Add a web refusal test to `tests/integration/test_web.py`. `POST /api/jobs`
  with Garchomp ×6 and `"required_hms": ["fly"]` returns 422 with `reasons == {"fly": "No team
  member can learn Fly"}`, and no job is created. Also: an unknown key (`"required_hms": ["dig"]`)
  → 422; a non-list → 422.

### Implementation

- [X] T007 [US2] Add `unlearnable_moves(consts, moves, led) -> list[str]` to
  `src/platsim/legality/movesources.py` (research R3). It returns the keys of required HMs with no
  legal source at level 100 for any member.
- [X] T008 [US2] In `run_optimization` in `src/platsim/optimizer/run.py`, right after
  `C.resolve_species` (~:269) and before `WorkerPool`, raise `InvalidRequest` naming each
  unlearnable HM (data-model messages).
- [X] T009 [US2] Wire the web refusal:
  - `src/platsim/web/app.py` `_options`: parse and validate `required_hms`, a list of HM keys,
    default `[]`. Store it in job options only when non-empty.
  - `SpeciesCatalog.resolve_team` in `src/platsim/web/species_catalog.py`: add an optional
    `required_hms` argument and an `hm_check` callback built in `build_catalog`, like 004's
    `conflicts`. Raise `InvalidRequest("some Pokémon cannot be used: …", reasons keyed by HM)`.
  - In `POST /api/jobs`, pass `required_hms` to `resolve_team`.
- [X] T010 [US2] Run T005–T006. Record the output.

---

## Phase 4: User Story 1 — Required HMs are carried (P1) 🎯 MVP together with US2

**Goal**: every result carries each required HM in a final moveset (H1, H3), and the validator
checks it independently.

**Independent test**: quickstart V1, V3 and V4.

### Tests (write first and see them fail)

- [X] T011 [P] [US1] Add validator tests to `tests/unit/test_validator.py`:
  - `validate(legal_team, led, required_hms=("fly",))` →
    `["REQUIRED_HM_MISSING"]`, with "Fly" in the message and a `src` ref;
  - `required_hms=("waterfall",)` → `[]` (Gyarados carries Waterfall; positive control);
  - the default call is unchanged.
- [X] T012 [P] [US1] Add placement tests to `tests/unit/test_required_hms.py`, building
  `MemberSpec`/`TeamSpec` with `candidates.member_candidates` for a small team at fixed levels:
  - required Surf, not in any moveset → after `realize(..., required_hms=("surf",))` exactly one
    member carries `surf`, and it is the member and slot with the lowest-scored replaced move
    (check against `MemberCandidates.scores`);
  - required Surf + Waterfall on a team with one learner of both → that member carries both;
  - required Defog (a status move, never in the pool) on a team with a Defog learner → placed;
  - a learner that can't learn the HM at its level → `Refusal` naming the HM;
  - `realize` without `required_hms` returns exactly the same team as before (positive
    control);
  - the realized team passes `validate(..., required_hms=...)`.
- [X] T013 [P] [US1] Add fingerprint and provenance tests to `tests/unit/test_required_hms.py`:
  - `job_fingerprint` of a default request equals the T001 record;
  - with `required_hms=("surf",)` it contains `"required_hms": ["surf"]` and a different
    `default_out_dir`;
  - `_optimizer_provenance` includes `required_hms` only when non-empty.

### Implementation

- [X] T014 [US1] Add the validator rule in `src/platsim/legality/validator.py`:
  - `validate(..., *, required_hms=())` adds `REQUIRED_HM_MISSING` per missing HM after the
    LEVEL_GAP block;
  - `src` refs: the HM's `tm_moves` decomp ref and 006 spec FR-002;
  - document the code in the module docstring.
- [X] T015 [US1] Add `place_required_hms(specs, levels, led, required)` to
  `src/platsim/optimizer/resources.py`, following research R2. Then:
  - `realize(specs, levels, led, *, required_hms=())` calls it first and returns
    `Refusal(slot, "no member can carry required HM <Move> at these levels")` when it gives
    `None`;
  - update the module docstring.
- [X] T016 [US1] Thread `required_hms` through `src/platsim/optimizer/run.py`:
  - every `R.realize(...)` call (~:302, :363, :411, :419, :438, :554) and `R.repair`'s internal
    realize;
  - every `validate(...)` (:412, :657);
  - `job_fingerprint` (only when non-empty), `_optimizer_provenance` `request`, and a top-level
    `provenance["required_hms"]` in `_report` / `_no_qualifying`, both only when non-empty.
- [X] T017 [US1] Thread it through evaluate, rerender and the CLI:
  - `src/platsim/evaluate.py`: `evaluate(..., required_hms=())` → `load_and_validate`; set
    `provenance["required_hms"]` when non-empty.
  - `src/platsim/report/rerender.py`: read `provenance.get("required_hms", [])` and pass it to
    `validate` and `realize`.
  - `src/platsim/cli.py`: add `_add_hm_flags(p)`, a repeatable `--require-hm`, on `validate`,
    `evaluate` and `optimize`, and pass it on. Unknown names → exit 2 (argparse `choices`
    accepting keys and display names via `hm_key`).
- [X] T018 [US1] Run T011–T013 and T001's test set. Record the output, including the default
  fingerprint equal to T001.

**Checkpoint**: US1 + US2 make the backend complete. This is the MVP; the CLI is fully usable.

---

## Phase 5: User Story 3 — Step 3 in the web page (P2)

**Goal**: four steps, eight toggles, and the summary row (FR-006, FR-008).

**Independent test**: quickstart V5.

### Tests

- [X] T019 [P] [US3] Add tests to `tests/integration/test_web.py`:
  - the headings "1. Choose Pokémon", "2. Team", "3. Required HMs", "4. Optimize", in that order;
  - eight `class="hm"` checkboxes, unchecked, in HM order, with ids `require-hm-<key>`;
  - `POST /api/jobs` with `"required_hms": ["surf"]` (StubRunner) stores it in job.json, and the
    `GET` summary has `required_hms == ["surf"]`;
  - **scope fix**: change `test_legality_options_page_search_and_jobs` (:254) so it counts only
    the five legality-rule checkbox ids, not every `type="checkbox"`.
- [X] T020 [P] [US3] In `tests/browser/test_page.py`, extend `test_page_walkthrough` (system
  Chrome):
  - the step 3 card is visible between Team and Optimize;
  - checking Surf and starting a run sends `required_hms`;
  - the results summary shows "Required HMs: Surf".

### Implementation

- [X] T021 [US3] Update `src/platsim/web/static/index.html`:
  - a new card `3. Required HMs` before Optimize, with eight checkboxes generated in HM order;
  - labels like "HM03 Surf", from a small `/api/hms` list or embedded in the page by the server
    from `HM_MOVES` (not typed in the HTML);
  - rename "3. Optimize" to "4. Optimize";
  - styles in `static/style.css` to match the existing check rows.
- [X] T022 [US3] Update `src/platsim/web/static/app.js`:
  - add `required_hms` (the checked keys) to the request body (:216-221);
  - add a "Required HMs" summary row (:382-391), showing the names or "none";
  - show a 422 HM refusal in the existing form error area.
- [X] T023 [US3] Expose `summary.required_hms` in `src/platsim/web/result_view.py` (from
  `provenance.required_hms`, `null` when absent). In `src/platsim/web/app.py`:
  - `run_one` reads `opts.get("required_hms", [])` into `OptimizeRequest`;
  - the module docstring lists the new payload key;
  - if T021 chose an endpoint, serve `/api/hms` from `HM_MOVES`.
- [X] T024 [US3] Run T019–T020: `uv run pytest -q tests/integration/test_web.py` and
  `uv run pytest -q -m browser tests/browser/`. Record the output.

---

## Phase 6: Polish and cross-cutting

- [X] T025 [P] Add a "Required HMs" subsection to `README.md`, next to Legality:
  - what it means (in a final moveset);
  - the refusal;
  - the `--require-hm` flag;
  - the web step 3.
- [X] T026 Run the small end-to-end check (quickstart V6, local, about a few minutes):
  - `uv run platsim optimize <six species incl. Gyarados and Staraptor> --budget quick --require-hm surf --require-hm waterfall --out <scratch dir>`;
  - expect the team to carry both HMs, `provenance.required_hms == ["surf","waterfall"]`, and
    `platsim validate --require-hm surf --require-hm waterfall <out>/team.json` to pass;
  - record the output.
- [X] T027 Run the full suite `uv run pytest -q` in the worktree (about 2.5 h, local only; not at
  the same time as another full suite in the main checkout). Paste the result into
  `validation-log.md`.
- [X] T028 Update the 006 section of `RUN-STATE.md` in the worktree with what's done, the commit,
  how to test (`uv run platsim serve` from the worktree, on a different port if the main
  checkout's server is running) and what isn't committed. Commit on `006-required-hms`. Don't
  merge.

---

## Dependencies

- Setup (T001–T002) → Foundational (T003–T004) → US2 (T005–T010) → US1 (T011–T018) → US3
  (T019–T024) → Polish (T025–T028).
- **US2 before US1**: US1's tests reuse `HM_MOVES` and the request field. US2's refusal is the
  cheapest piece and guards US1's placement from impossible input.
- **US3** needs T004 and T009, for the web payload and refusal. Its tests can be written while US1
  is implemented.
- **T027** waits for the 005 full suite in the main checkout to finish, to avoid two 2.5 h suites
  competing for CPU.

## Parallel opportunities

- **US2 tests:** T005 and T006.
- **US1 tests:** T011, T012 and T013.
- **US3 tests:** T019 and T020.
- **README:** T025 can be done at any time after T017.
- **Implementation:** shares `movesources.py`, `run.py` and `resources.py`, so it runs in order.

## Implementation strategy

1. **MVP**: Setup, Foundational, US2 and US1. The CLI then accepts `--require-hm`, refuses
   impossible requests and returns teams that carry the HMs, which the validator checks.
2. US3 adds the web step.
3. Polish: README, the end-to-end check, the full suite, and a commit. Then the user tests it by
   hand before merging.

---

## Phase 7: Convergence

- [X] T029 Label each step 3 toggle with the move name only (e.g. "Surf", no "HM03"): in
  `src/platsim/web/static/app.js` `loadHms` use `h.name`. Update
  `tests/browser/test_page.py::test_required_hms_step` to assert the eight move names, in HM order,
  with no "HM0" text in `#hm-step`. Per FR-006 / US3/AC1 / Clarification 2026-10-14
  (contradicts).
- [X] T030 Stop step 3 labels overlapping. In `src/platsim/web/static/style.css`, size the
  `#hm-step .hm-list` columns to fit their labels (e.g.
  `repeat(auto-fill, minmax(max-content, …))`), and let the grid wrap to more rows instead of
  shrinking columns below the label width. Steps 1–4 must still fit on a 1080p screen (002 SC-003,
  checked by `test_page_walkthrough`). Add a browser assertion that no two `#hm-list label`
  bounding boxes intersect, at 1920×1080 and at a 390 px phone width. Per FR-006 / contract
  "labels never overlap" (contradicts).

---

## Phase 8: Convergence

- [X] T031 Lay the step 3 toggles out as 4×2 on desktop. In `src/platsim/web/static/style.css`,
  use four columns at 1920×1080 (row 1: Cut, Fly, Surf, Strength; row 2: Defog, Rock Smash,
  Waterfall, Rock Climb). Labels must not overlap, the walkthrough's 1080p fit must hold, and the
  grid may wrap to more rows at 390 px. Extend the browser tests:
  - at 1920×1080, the labels sit in exactly 2 rows of 4, in HM order;
  - the existing no-overlap checks at 1920 and 390 still pass.

  Per FR-006 / contract (4×2) / Clarification 2026-10-14 (contradicts).
