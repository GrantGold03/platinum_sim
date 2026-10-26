# Research: Held-Item Sources (H1)

Observed 2026-10-26 on branch `011-held-item-sources` (from `main` at `73af068`) unless marked as carried
over from 008.

## R1. The archived commit applies unchanged

- Decision: `git cherry-pick -n a8b529b`, keeping `src/` and `tests/` only (its 007 `tasks.md` and
  `validation-log.md` edits are dropped).
- Evidence (2026-10-26): `git diff --stat f88cdd0 HEAD -- src tests sim` is empty, so the code here is
  the same code 008 was verified on. `git diff a8b529b^ a8b529b -- src tests | git apply --check -v`
  reports "Checking patch" for all three files and no error.
- Alternatives: re-implementing (rejected: spec FR-009, reuse).

## R2. Item counts before and after (carried over from 008, re-measured in implementation)

- On this code, 008 measured (2026-10-19) **66 unlimited / 37 finite / 55 unavailable** before and
  **74 / 40 / 44** after (158 held items). 11 items leave "unavailable" (008 validation-log, T003-T007):
  - 1 copy each, Route 221 house: `black_belt`, `expert_belt`, `focus_sash`;
  - unlimited, Pastoria City berry house: `charti_berry`, `chilan_berry`, `coba_berry`, `kebia_berry`,
    `occa_berry`, `passho_berry`, `payapa_berry`, `tanga_berry`.
  The 9 Amity Square berries (Belue, Cornn, Durin, Magost, Nomel, Pamtre, Rabuta, Spelon, Watmel) become
  pre-Champion too, but none is a counted held item, so they do not move the 74/40/44 counts.
- `main`'s tests pin 66 and 55 (`test_availability_controls.py`), a built-in positive control: they must
  fail after step 2 until the pins are updated by the archived test changes.
- The same script reading adds 81 entries in all, including Route 208 house, Solaceon News Press, Flower
  Shop and Amity non-held berries; 008 found none changed a held item's availability. Re-checked here by
  the per-item diff.

## R3. Optimizer impact (carried over from 008, re-measured in implementation)

- `held_item_candidates` offers the best HP berry, one type booster for the strongest attack (unlimited
  copies sort first, so Black Belt never displaces Fist Plate) and Leftovers when the team can get it.
  Expert Belt and Focus Sash are not offered by this rule.
- 008 measured B1-B5 candidates identical (93 entries) and a same-seed quick B2 run identical except the
  two provenance hashes (`runs/008-evidence/sc005-*`). Expected the same here.

## R4. Where the internal labels come from

- The archived code writes the source's reason into `Entry.detail`, which `platsim explain` prints
  verbatim (`src/platsim/explain.py:217-219`). Three pieces of that text are internal, as seen in
  `runs/008-evidence/explain.txt`:
  1. the tag " (007 dataflow: Return-aware calls / GetRandom+AddVar / save-var literals / C table)" on
     every newly found give site;
  2. "repeatable: no once flag guards this give" (Amity Square);
  3. "needs one of 16 species in the party (CheckPartyHasSpecies)" (Amity Square).
  The Route 221 text names the script command `GetDailyRandomLevel` inside the reason.
- Decision: rewrite these per `contracts/explain-text.md`. Decomp file:line references stay
  (Constitution I); script command and flag names move out of the sentence and into the reference list
  the line already carries.
- Out of scope (spec Assumptions; `FUTURE-FEATURES.md` item 4): labels already on `main` in other explain
  lines, such as the source kind (`npc_item_gift`), "mapgraph strict" and "spec FR-003a".

## R5. The sentinel test without the text tag

- The archived test `test_dataflow_sentinel_only_expected_give_sites_change` finds newly found give sites
  by searching for "007" in the detail text. That is the only reason the tag exists.
- Decision: the code that already decides "new site" (comparing the new script reading with the old
  literal-only one) exposes that set through a small helper in `sources.py`; the test reads the helper.
  The ledger's entries and the generated JSON carry no extra field.
- Alternatives: a new field on the ledger entry (rejected: it changes the generated data format for a
  test-only need); dropping the sentinel (rejected: it is the guard that the reading changes only the
  expected sites).
