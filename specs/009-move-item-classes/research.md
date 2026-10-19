# Research: Move and Item Classification

Observed 2026-10-19 on `009-move-item-classes` (from `main` at `de102fa`).

## R1. The commit applies to `main` unchanged

`git diff main 9e1f065 -- <the 8 src/test files> | git apply --check -v`: all 8 "Checking patch" lines, no
error. The three changed optimizer files are identical on `main` and `9e1f065^`. Decision: cherry-pick
src/tests only (the commit's 007 `tasks.md` edit is dropped).

## R2. The modelled-move reader is dormant

`9e1f065`'s `move_classes.modelled_table()` returns `{}` when `sim/policy/expectimax2.mjs` has no
`export const MODELLED = {` table. `main`'s player has only a comment heading "MODELLED MOVE EFFECTS"
(line 110), not the table; the table arrives with the player slice (007 `279e820`). Nothing calls
`modelled()` in this slice.

## R3. HM-placement tiers

Old `_slot_cost` key: `(1 if self-boost else 0, attack coverage value or 0)`. New: status 0 < attack
(by value) 1 < self-boost 2 < adopted 3.
- No attack has a self-boost effect (`expectimax_self_boosts()` has 16 effects; 0 damaging moves use
  them; checked 2026-10-19), so the old "boosting attack" case never occurs.
- Remaining difference: an attack with coverage value exactly 0 tied with status moves before (slot order
  broke the tie) and now gives way after them. Checked empirically in T005 over every candidate moveset of
  B1-B5 and every HM.

## R4. `MemberSpec.adopted`

New field, default `()`. `to_dict` writes it only when non-empty, `from_dict` reads it with default `()`,
so state.json / result files of every run without adopted moves are byte-identical. `repair` keeps only
adopted moves still in the moveset. Nothing marks moves adopted until the alternatives slice.

## R5. Derived exp/EV list vs the old list

Old `EXP_HOLD_EFFECTS`: EXP_UP, EXP_SHARE, LVLUP_SPEED_DOWN (the last does not exist in the decomp).
The derived list adds EVS_UP_SPEED_DOWN (Macho Brace) and the LVLUP_*_EV_UP power items. It is used only to
exclude items from the type-boost choice, and no type-boost item has those effects, so the choice cannot
change. Checked by T004 (candidates identical).
