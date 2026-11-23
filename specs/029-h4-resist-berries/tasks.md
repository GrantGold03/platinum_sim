# Tasks: H4, resist berries

**Input**: `specs/029-h4-resist-berries/` (spec.md, plan.md, research.md R1 to R6, data-model.md, contracts/, quickstart.md)

**Branch**: `029-h4-resist-berries` from `main` 58f1570, main checkout. Times US Eastern. Measurements alone (`pgrep -a -x node;
pgrep -a pytest` empty); never pipe a gating command into `tail`; never amend or force-push; never edit `src/` or `sim/` while an
acceptance, check or suite runs; never key a cache on `id()` alone; paired checks use 028's script with `--battle-style shift` plus a
conditions control; engine tests drop Showdown's duplicate split lines before counting; evidence under `runs/029-evidence/` (local)
with copies under `specs/029-h4-resist-berries/evidence/`.

## Phase 1: Setup (pre-feature evidence, before any code change)

- [x] T001 Start `specs/029-h4-resist-berries/validation-log.md` (before-values: both code hashes, the ledger version; `git diff --stat
      main -- src sim tests pyproject.toml` empty) and adapt 028's scripts into `specs/029-h4-resist-berries/scripts/`: `acceptance.py`
      (`runs/029-evidence`, identity seed `029-ident`, `NEW_ITEMS` = the 17 resist berry keys, holders reported per winner),
      `attribution.py` (028's, the appended rule generalised: an appended-items list may only gain resist berries at its end, after
      `shell_bell`, cause `appended`), `equal_levels.py` (master `029-equal|B2`), `hand_check.py` (each B2 member's berry ranking and
      appended items), `make_check_team.py` (the pre-feature B2 winner with the top-ranked berry on the member whose top berry blocks the
      most, replacing its item; validated; written to `runs/029-evidence/teams/b2-berry.json`; the unmodified team to `b2-plain.json`)
- [x] T002 Run the pre-feature side alone (about 10 min): `uv run python specs/029-h4-resist-berries/scripts/acceptance.py --side main --workers 16 > runs/029-evidence/acceptance-main.txt 2> runs/029-evidence/acceptance-main.err; echo exit=$?`;
      copy outputs and the snapshot to `evidence/pre/`; log; Commit 1 `docs(029): pre-feature evidence and scripts`; push

## Phase 2: Foundational

- [ ] T003 Engine-versus-game checks (FR-004, R4) in `sim/test/resist_berries.test.mjs` part 1 (028's pattern: `leagueBattle`, a player
      member holding the berry, `turn()` with duplicate lines dropped): (a) a super-effective hit of the berry's type: halved (compare
      the HP lost with and without the berry on the same seed) and eaten; (b) a neutral hit: not eaten; (c) a hit on a substitute: eaten
      or not; (d) Chilan on a resisted Normal hit: halved or not; (e) a multi-hit move: first hit only; (f) rounding on an odd damage
      value; record each against the decomp (R1); ledger entries for confirmed differences (`src/platsim/divergence/mechanics.py`, then
      `uv run platsim divergences`)

## Phase 3: User Story 1 - The battle player knows resist berries halve a hit (Priority: P1) 🎯 MVP

- [ ] T004 [US1] `sim/policy/expectimax2.mjs`: `damageOutcomes` adds `se` (super-effective, from the damage calculation's status mask)
      and `hits` (1 or the multi-hit count) to each outcome; `applyHit(X, S, side, rec, e, dmgIn, se = false, hits = 1)` applies, before
      the clamp to the defender's HP and when `X.opts.resistBerries !== false`: defender hold effect `HOLD_EFFECT_WEAKEN_SE_<rec type>`
      with `se`, or `HOLD_EFFECT_WEAKEN_NORMAL` with a Normal move (Normalize: Normal) → single hit `dmg = floor(dmg / 2)`, multi-hit
      `dmg -= floor(floor(dmg / hits) / 2)`; berry removed (`t.item = ''`); header comment and `_internal` export updated
- [ ] T005 [US1] `sim/gauntlet.mjs`: v4 knob `resistBerries=0|1`
- [ ] T006 [US1] `sim/test/resist_berries.test.mjs` part 2: super-effective hit halved and consumed; neutral unchanged and kept; a second
      super-effective hit after consumption unchanged; Chilan Normal neutral halved; multi-hit first-hit share; knob off unchanged; then the
      Node suite (replay byte-identical); confirm greedy-v1 needs no change; record that no replay or identity team holds a resist berry
      (reference team, benchmark team, the B2 winner, the replay fixtures: checked at analyze, recheck); record
- [ ] T007 [US1] Player check, alone (FR-008): `make_check_team.py`; 028's `paired_policies.py --battle-style shift`: conditions control
      (`b2-plain.json`, 200 pairs, both arms), pairing control `--self` (200), then `--a expectimax2-v4 --b 'expectimax2-v4?resistBerries=0'`
      on `b2-berry.json`, 2,000 pairs, out `runs/029-evidence/pairs`; record; **a supported loss stops the feature**; Commit 2
      `feat(029): the player models resist berries; v4 knob; engine checks; player check`; push

## Phase 4: User Story 2 - The optimizer offers the right berries (Priority: P2)

- [ ] T008 [US2] `src/platsim/optimizer/candidates.py`: `resist_berry_ranking(const_member, level, led) -> list[tuple[str, float]]` (R5:
      the League's stored damaging moves from `trainers.json`, weights as `league_opponents`, threat = power × accuracy × the opponent's
      STAB weight × its base attacking stat by category × type multiplier against the member ÷ the member's base Defense (physical) or
      base Special Defense (special); per mon and type the largest; per berry
      type the weighted sum halved; Chilan from Normal moves at any effectiveness; ties by type name; only berries with a copy);
      `extra_item_candidates` appends the top two after Shell Bell for every moveset with an attack (a member with no threat gets none)
- [ ] T009 [US2] `tests/unit/test_resist_berries.py`: the ranking on known members (e.g. Garchomp: Ice first; a member with no
      super-effective threat: empty); the defences rule on a synthetic member (high Defense, low Special Defense: with an equally strong
      physical and special super-effective threat of two types, the special threat's berry ranks first; swapped stats, the reverse); the berries last in `items_extra` and after `shell_bell`; over the 36 snapshot members only
      `appended` differences (028's attribution); update pins in `tests/unit/test_h4_items.py` and `tests/unit/test_shell_bell.py` that
      compare whole lists; run with the candidate tests (exit code kept) and record
- [ ] T010 [US2] Hand check and the fast suite (`runs/029-evidence/fast.log`, exit code kept); log; Commit 3
      `feat(029): resist berries ranked by blocked League damage, two per member, appended`; push

## Phase 5: User Story 3 - Measured on both codes (Priority: P3)

- [ ] T011 [US3] Branch side alone: `uv run python specs/029-h4-resist-berries/scripts/acceptance.py --side branch --workers 16 --runs 2000 > runs/029-evidence/acceptance.txt 2> runs/029-evidence/acceptance.err; echo exit=$?`; copy evidence
- [ ] T012 [US3] Merge gate (FR-010): a supported loss, a level diff above 1.0, a defect or a non-identical identity row: no merge, record
      and stop at the report; else continue
- [ ] T013 [US3] Docs: validation log (player check, acceptance table, which members took which berry); `README.md` (029 block with the
      Principle VII measurement statement and the partial-model note of FR-012; the items bullet names the berries); `FUTURE-FEATURES.md` section 0; `RUN-STATE.md`; Commit 4
      `feat(029): acceptance and player check; docs`; push

## Phase 6: Gates and close

- [ ] T014 Gates, nothing else running: engine diff empty; `sim` diff only the player, the knob and the test; hashes and ledger version
      as expected; Node suite; `uv run pytest -q --durations=25 > runs/029-evidence/full.log 2>&1; echo full exit=$?`; log and `evidence/gates.txt`
- [ ] T015 Closing commit `docs(029): gates recorded; feature closed on its branch`; push; report with the merge command; merge on the user's go

## Dependencies

- T001 → T002 (before any code change) → T003 → US1 (T004 → T005 → T006 → T007) → US2 (T008 → T009 → T010) → US3 (T011 → T012 →
  T013) → T014 → T015. T007 before T008 (reference-first). No commit during T002, T007, T011 or T014's measured steps.

## Parallel opportunities

- T001's scripts; T003 (engine tests) beside T004-T005 once T002 is done.

## Implementation strategy

- MVP = US1. 15 tasks, three stories, two layers.
