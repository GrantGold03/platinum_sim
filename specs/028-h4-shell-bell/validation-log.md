# Validation log: feature 028 H4, Shell Bell

Branch `028-h4-shell-bell` from `main` 634e270, main checkout. Times US Eastern.

## T001 Setup (10:15 AM EST, 2026-11-20)

`git diff --stat main -- src sim tests pyproject.toml`: 0 lines. Before-values:

```
sim_code_hash platsim_code_hash: sha256:e968ff0f403539460e6c0260db6253ad971d1a3eb7c02feaa8c9fbe393e74b7d sha256:85fa0353274dcefe4ec170f28ff6f17e3eb555853d9c7dad3fe7b2e3902c53b9
divergence_ledger_version: sha256:feb2a48ef2e1dd08 (027's results; unchanged since)
```

Scripts adapted from 027 under `scripts/`: `attribution.py` (027's plus: extras must be unchanged; an appended-items list may
only gain `shell_bell` at its end, cause `appended`; anything else a defect), `acceptance.py` (evidence `runs/028-evidence`,
identity seed `028-ident`, Shell Bell holders reported per winner), `equal_levels.py` (master `028-equal|B2`), `hand_check.py`
(appended items per set), `make_check_team.py` (the B2 winner with Garchomp's Sitrus Berry replaced by Shell Bell, validated).

## T002 Pre-feature side (10:15:49 to 10:27:00 AM EST, alone, exit 0; code identical to `main` 634e270)

B2 quick: levels [52, 50, 50, 50, 51, 53], clear 0.9440 [0.9203, 0.961] (n 500, 2 attempts), wall 492.9 s, no Shell Bell holder
(not offered on main): the same winner as 027. Generation at the job's reference level 47: 1.7 s for six members, 7.2 s for the
team build with the allocation. Identity evaluations `ident-main/{ref,b2main}` (seed 028-ident). Snapshot
`evidence/candidates-main.json`: 36 records with the appended-item lists.

## T003 Engine against game (10:30 to 10:50 AM EST; `sim/test/shell_bell.test.mjs` part 1, the vendored engine)

| Case | Game (decomp) | Engine (observed) | Result |
|---|---|---|---|
| hurt holder, damaging hit | heal = dealt / 8, at least 1 | Garchomp 110 → 129 after knocking out Houndoom (heal 19 = floor(dealt / 8)) | equal |
| holder at full HP | no heal | no heal | equal |
| U-turn | heals on the pivot path (`battle_lib.c:7345`) | heals (U-turn sets `switchFlag`, the engine skips only `forceSwitchFlag`) | equal; the spec's "engine skips U-turn" was wrong (research R2) |
| holder knocked out by its own recoil | no heal (holder at 0 HP) | no heal | equal |
| hit that breaks a substitute | heals from the substitute HP lost (`battle_controller_player.c:3361-3366`) | **no heal** (`move.totalDamage` gains nothing from a substitute hit) | **divergence**: ledger entry `mech-shell-bell-substitute`, accepted; impact none in the League (no League Pokemon knows Substitute; the player does not model Substitute) |

Ledger regenerated (`uv run platsim divergences`, exit 0): one entry added, none changed; version `sha256:feb2a48ef2e1dd08` →
`sha256:821f33356f6a61bb`. Test-side fixes on the way (no code change): Showdown writes each split log line twice, so duplicates
are dropped before counting; a substitute broken by the hit logs `-end`, not `-activate`; the no-item control used Expert Belt
(Sitrus Berry heals on its own at half HP).

## T004 to T006 The player's model (10:50 AM EST)

`sim/policy/expectimax2.mjs` `applyHit`: after recoil, the drain heal and Life Orb, a Shell Bell holder with 0 < hp < max heals
max(1, floor(dmg / effect_param)) (the param read from the item data, 8), `dmg` the HP the target lost; `X.opts.shellBell === false`
turns it off; `_internal` exports `applyHit` for the tests; the header's held-items list names Shell Bell. `sim/gauntlet.mjs`: the
v4 candidate knob `shellBell=0|1` (any other value an `invalid_policy` error). Player tests (part 2): half HP dealing 80 heals 10;
full HP 0; 7 damage heals 1; the heal uses the HP lost (a target at 16 HP: heal 2); fainted by recoil 0; no Shell Bell 0; the knob
off 0. The screening player (greedy-v1) needs no change: `moveScores` and `memberScore` (`sim/policy/greedy.mjs:83-100`) rank by
expected damage only and never model HP after the user's own hit (FR-004).

```
(cd sim && node --test test/*.test.mjs) → tests 395, pass 395, fail 0, exit 0 (replay.test.mjs green: byte-identical decisions)
```

## T007 Player check (reference-first, FR-008; 10:32 to 10:49 AM EST, alone; `evidence/player-check/`)

Team: the 028 pre-feature B2 winner with Garchomp's Sitrus Berry replaced by Shell Bell (`make_check_team.py`, validated).
Policies: `expectimax2-v4` (the model) against `expectimax2-v4?shellBell=0` (reference), same seeds.

**Run 1 (Set style, by mistake).** Feature 018's `paired_policies.py` sends no `battle_style`, and a request without one is Set
(023's `style_of`), not today's Shift default. Pairing control 0 discordant; model 0.4960 vs reference 0.5175 (only-model 327,
only-reference 370, p 0.112): no supported loss. A conditions control showed the cause of the low rates: the original Sitrus team
also cleared only 0.44 under that script (0 discordant pairs between the arms: the knob changes nothing without the item).

**Run 2 (Shift, today's default; the check of record).** A copy of the script under `scripts/paired_policies.py` passes
`--battle-style` (default shift) on every request.

| Control or check | n | Model | Reference | only model / only reference | p |
|---|---|---|---|---|---|
| Sitrus team (no Shell Bell; conditions control) | 200 | 0.9450 | 0.9450 | 0 / 0 | 1 |
| pairing control (`--self`, Shell Bell team) | 200 | 0.9650 | 0.9650 | 0 / 0 | 1 |
| **Shell Bell team** | 2,000 | **0.9565** | **0.9515** | 65 / 55 | **0.411** |

The Sitrus team's 0.945 matches the optimizer's own 0.944 for that team, so the conditions are right. **Verdict: not worse (no
supported loss); point estimate +0.5 points.** Gate passed (clarify decision: a gain is reported, not required).

## T008 to T010 The optimizer offers Shell Bell (10:50 to 11:05 AM EST)

`candidates.py`: `HP_RESTORE_ON_DMG_EFFECT`; `extra_item_candidates` appends `_item_for_effect(HP_RESTORE_ON_DMG_EFFECT)` after
the claw for every set with an attack (no item-conditioned extras; docstring says why). `tests/unit/test_shell_bell.py`: the item
is `shell_bell` with 1 copy; last in `items_extra` exactly for the B2 sets with an attack and never among the existing candidates;
over the 36 snapshot members the only differences are `appended` (base sets, extras and existing items unchanged; 0 defects); a
second Shell Bell on a team is refused by `resources.realize`. Two 025 pins in `test_h4_items.py` updated to the new lists
(`[lens, claw, bell]`, `[claw, bell]`). Hand check (`evidence/b2-candidates-branch.txt`): Shell Bell on all 18 B2 base sets;
generation 1.9 s for six members, 6.9 s with the allocation.

```
candidate, item, report and resume tests → 102 passed, exit 0
uv run pytest -q -m "not battle_sim" (10:54:16 to 11:05:31 AM EST) → 637 passed, 32 deselected, 4 xfailed, exit 0
```

## T011 Branch side (11:05:53 to 11:23:28 AM EST, alone, exit 0; on 9c58e3c; copies in `evidence/acceptance/`)

| Measure | main (634e270 code) | branch (9c58e3c) |
|---|---|---|
| B2 quick winner | levels [52, 50, 50, 50, 51, 53], clear 0.9440 | identical team, moves, items and levels; no Shell Bell holder |
| equal levels, 2,000 pairs | 0.9505 | 0.9505 (0 discordant pairs) |
| screened teams | 173 | 205 (item deviations 46 → 78: Shell Bell on base sets); overlap 173 of 173 |
| identity evaluations | | identical without volatile fields (the player change is invisible without the item) |
| attributed diff, 36 members | | 0 defects; only `appended` (Shell Bell at the end of the appended-item lists) |
| generation (six members / with allocation) | 1.7 s / 7.2 s | 1.7 s / 7.2 s |

## T012 Merge gate: pass. T013 docs: README 028 block (with the Principle VII measurement statement), FUTURE-FEATURES section 0,
the spec's U-turn statements finalised (both heal), RUN-STATE.

## T014 Gates (11:24:10 AM to 12:56:39 PM EST, nothing else running, on 940d825)

```
git diff --stat main -- pokemon-showdown: 0 lines (the vendored engine untouched)
git diff --stat main -- sim: sim/gauntlet.mjs (+1), sim/policy/expectimax2.mjs (+12/-2), sim/test/shell_bell.test.mjs (new)
sim_code_hash after:     sha256:6c038ef7601b38e3b400c96159a24968a7c0998d915f0586a50dcd1f0fa472d1  (was e968ff0f...: the player changed)
platsim_code_hash after: sha256:4e8673d95a2ff503a0b7325977601ac4cc128f962f868d6426f236e799de842b  (was 85fa0353...)
divergence_ledger_version after: sha256:821f33356f6a61bb  (was feb2a48ef2e1dd08: one entry added, mech-shell-bell-substitute)
(cd sim && node --test test/*.test.mjs): tests 395, pass 395, fail 0, exit 0
uv run pytest -q --durations=25 (11:26:50 AM to 12:56:39 PM EST): 669 passed, 4 xfailed, 1 warning in 5386.08s (1:29:46), exit 0
```

All gates green; pre-028 optimizer checkpoints are refused (both code hashes and the ledger version changed). **The feature is
closed on its branch. Merge on the user's go:** `git checkout main && git merge --ff-only 028-h4-shell-bell && git push`.
