# Tasks: H4, Shell Bell

**Input**: `specs/028-h4-shell-bell/` (spec.md, plan.md, research.md R1 to R6, data-model.md, contracts/, quickstart.md)

**Branch**: `028-h4-shell-bell` from `main` 634e270, main checkout. Times US Eastern. Measurements alone (`pgrep -a -x node;
pgrep -a pytest` empty); never pipe a gating command into `tail`; never amend or force-push; never edit `src/` or `sim/` while an
acceptance, check or suite runs; never key a cache on `id()` alone; evidence under `runs/028-evidence/` (local) with copies under
`specs/028-h4-shell-bell/evidence/`.

**Tests**: requested by the spec (heal cases, replay, engine checks, item lists, the one copy).

## Phase 1: Setup (pre-feature evidence, before any code change)

- [x] T001 Start `specs/028-h4-shell-bell/validation-log.md` (before-values: `sim_code_hash`, `platsim_code_hash`, the ledger
      version; `git diff --stat main -- src sim tests pyproject.toml` empty) and adapt 027's scripts into
      `specs/028-h4-shell-bell/scripts/`: `acceptance.py` (`runs/028-evidence`, identity seed `028-ident`, `NEW_ITEMS = {"shell_bell"}`
      reported per winner as 025 did; the 027 snapshot plus each record's `items_extra`; branch side: the attributed diff where
      base sets, extras and existing items unchanged and `shell_bell` appended is `appended`, anything else `defect`),
      `attribution.py` (027's plus the items_extra rule), `equal_levels.py` (master `028-equal|B2`), `hand_check.py` (each B2
      member's `items_extra` per set), `make_check_team.py` (writes `runs/028-evidence/teams/b2-shellbell.json`: the 027 B2 winner's
      team with Garchomp's item replaced by `shell_bell`, validated by `load_and_validate`)
- [x] T002 Run the pre-feature side alone (about 10 min): `uv run python specs/028-h4-shell-bell/scripts/acceptance.py --side main --workers 16 > runs/028-evidence/acceptance-main.txt 2> runs/028-evidence/acceptance-main.err; echo exit=$?`;
      copy outputs and the snapshot to `evidence/pre/`; log; Commit 1 `docs(028): pre-feature evidence and scripts`; push

---

## Phase 2: Foundational

- [x] T003 Engine-versus-game checks (FR-003, R2) in `sim/test/shell_bell.test.mjs` part 1, against the vendored engine on
      constructed battles built the way `sim/test/switch_reset.test.mjs` and `sim/test/expectimax2.test.mjs` build them (the
      worker's battle setup on fixed teams with the needed moves: Substitute, U-turn, a multi-hit move, a recoil move;
      expected values: U-turn heals like the game): (a) a hit into a substitute: does the holder heal floor(damage to the substitute / 8)? (b) a multi-hit
      move: heal from the total; (c) U-turn: heal before the switch; (d) a holder fainted by its own recoil: no heal; (e) rounding: 7
      damage heals 1; record each result in the log against the decomp (`battle_controller_player.c:3361-3430, 4738`,
      `battle_lib.c:3599, 7345`); add a divergence ledger entry for each confirmed difference with its impact; run and record

---

## Phase 3: User Story 1 - The battle player knows Shell Bell heals (Priority: P1) 🎯 MVP

- [x] T004 [US1] `sim/policy/expectimax2.mjs` `applyHit`: after the Life Orb line and before `afterHpLoss(X, u)`, `if (opts.shellBell && dmg > 0 && u.item && holdEffect(X, u.item) === 'HOLD_EFFECT_HP_RESTORE_ON_DMG' && u.hp > 0 && u.hp < u.maxhp) u.hp = Math.min(u.maxhp, u.hp + Math.max(1, Math.floor(dmg / 8)))`
      with `shellBell` an option of the v4 policy (default on), reachable from `applyHit`; the header comment's held-items list
      gains Shell Bell with its decomp citation
- [x] T005 [US1] `sim/gauntlet.mjs` v4 candidate knobs: `shellBell=0|1` (any other value an `invalid_policy` error); the reference
      arm `expectimax2-v4?shellBell=0`
- [x] T006 [US1] `sim/test/shell_bell.test.mjs` part 2 (contract): on constructed player states, holder at 50% HP dealing 80 heals
      10; at full HP 0; 7 damage heals 1; fainted by recoil 0; the knob off 0; an invalid knob value refused; then the Node suite
      `(cd sim && node --test test/*.test.mjs)` with `replay.test.mjs` byte-identical; record; confirm greedy-v1 needs no change
      (FR-004: it scores moves, not HP; cite the function) and record
- [x] T007 [US1] Player check, alone (FR-008, about 15 min): `make_check_team.py`, then `uv run python specs/018-expectimax2-v4/scripts/paired_policies.py`
      `--a expectimax2-v4 --b 'expectimax2-v4?shellBell=0' --teams file:runs/028-evidence/teams/b2-shellbell.json --runs 2000 --workers 16 --out runs/028-evidence/pairs`,
      preceded by the pairing control `--self` on the same team (0 discordant pairs required); record clear rates, discordant
      pairs, exact McNemar p; **a supported loss stops the feature** (report to the user); Commit 2 `feat(028): the player models Shell Bell; v4 knob shellBell; engine checks; player check`; push

---

## Phase 4: User Story 2 - The optimizer offers Shell Bell (Priority: P2)

- [x] T008 [US2] `src/platsim/optimizer/candidates.py` `extra_item_candidates`: after the Razor Claw entry, append
      `_item_for_effect("HOLD_EFFECT_HP_RESTORE_ON_DMG", led)` when the set has an attack and the item has a copy; docstring updated
- [x] T009 [US2] `tests/unit/test_shell_bell.py`: Shell Bell last in `items_extra` for every B2 set with an attack (level 48);
      existing entries unchanged against T002's snapshot; base sets and extras unchanged (the 027 helper, 0 defects over 36 members);
      `resources.realize` refuses a second Shell Bell on a team; run with the candidate tests (exit code kept) and record
- [x] T010 [US2] Hand check and the fast suite `uv run pytest -q -m "not battle_sim" > runs/028-evidence/fast.log 2>&1; echo exit=$?`; log;
      Commit 3 `feat(028): Shell Bell offered by hold effect, appended after each set's items`; push

---

## Phase 5: User Story 3 - Measured on both codes (Priority: P3)

- [x] T011 [US3] Branch side alone (about 20 min): `uv run python specs/028-h4-shell-bell/scripts/acceptance.py --side branch --workers 16 --runs 2000 > runs/028-evidence/acceptance.txt 2> runs/028-evidence/acceptance.err; echo exit=$?`; copy evidence
- [x] T012 [US3] Merge gate (FR-010): a supported loss, a level diff above 1.0, a defect, or a non-identical identity row: no merge,
      record and stop at the report; else continue
- [x] T013 [US3] Docs: validation log (the player check and the acceptance table with which member took Shell Bell); `README.md`
      (H4 block: Shell Bell modelled and offered, the engine checks, the remaining groups and why they wait; the player-change note
      on `expectimax2-v4` stating its measurement cost (Principle VII): no change for teams without Shell Bell, shown by the replay
      and identity evaluations; for a holder, the clear-rate difference measured by the player check); `FUTURE-FEATURES.md`
      section 0; the spec's U-turn statements finalised from T003's result; `RUN-STATE.md`; Commit 4
      `feat(028): acceptance and player check; docs`; push

---

## Phase 6: Gates and close

- [ ] T014 Gates, nothing else running: `git diff --stat main -- pokemon-showdown` empty; `sim_code_hash` changed (the player),
      ledger version changed only if T003 added an entry; Node suite green; `uv run pytest -q --durations=25 > runs/028-evidence/full.log 2>&1; echo full exit=$?` green; log and `evidence/gates.txt`
- [ ] T015 Closing commit `docs(028): gates recorded; feature closed on its branch`; push; report with the merge command; merge only on the user's go

## Dependencies

- T001 → T002 (**before any code change**) → T003 → US1 (T004 → T005 → T006 → T007) → US2 (T008 → T009 → T010) → US3 (T011 → T012
  → T013) → T014 → T015. T007 must finish before T008 (reference-first). No commit during T002, T007, T011 or T014's measured steps.

## Parallel opportunities

- T001's scripts are independent files; T003 (engine tests) beside T004-T005 (player code) once T002 is done.

## Implementation strategy

- MVP = US1 (the player knows the item, measured). US2 is a one-function change. 15 tasks, three stories, two layers.
