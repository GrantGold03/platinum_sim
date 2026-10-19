# Research: Ledger Item Sources

Observed 2026-10-19 on branch `008-ledger-item-sources` (from `main` at `f88cdd0`).

## R1. The 007 commit applies to `main` unchanged

- Decision: cherry-pick `a8b529b` (src and tests only).
- Evidence: `git diff main a8b529b -- <3 files>` applies with `git apply --check` (all three "Checking patch"
  lines, no error). The three files are identical on `main` and on `a8b529b^` (`git diff --stat` empty), and
  only `a8b529b` touches them between `main` and the 007 branch (`git log main..007-status-moves-items`).
  The one new import, `platsim.decomp.scripts.walk`, exists on `main` (`scripts.py:562`), and
  `src/platsim/decomp` is identical on both branches.
- Alternatives: re-implementing on `main` (rejected: the spec says re-verify, not rewrite).

## R2. Item counts before and after

- `main`, rebuilt with `uv run platsim extract` (41.8 s): **66 unlimited, 37 finite, 55 unavailable**
  (158 items). `main`'s tests pin 66 and 55 (`test_availability_controls.py:522, 526`), a built-in
  positive control. Snapshot: `runs/008-evidence/availability-main-f88cdd0.json`.
- 007 (recorded 2026-10-15): **74 / 40 / 44** (158). Expected change: 11 items leave "unavailable",
  8 become unlimited (Pastoria/Amity berries), 3 become finite (Route 221: Black Belt, Expert Belt,
  Focus Sash, 1 each). To be confirmed item by item in implementation.

## R3. Optimizer impact

- `main`'s `held_item_candidates` (`optimizer/candidates.py:422-449`) offers the best HP berry, a type
  booster for the strongest attack, and Leftovers when team-gated.
  - Type boosters sort unlimited first (`:442`), so Black Belt (1 copy) does not displace Fist Plate
    (unlimited). Expert Belt and Focus Sash are not offered by this rule.
  - HP berries sort by `effect_param`: a new berry changes the pick only if it is an HP berry ranked
    above Sitrus. Unverified until the 11-item diff is known; checked in implementation step 4.
- Expected: no candidate change, so optimizer results identical. Verified by SC-005.
