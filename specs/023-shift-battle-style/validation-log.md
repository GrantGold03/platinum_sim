# Validation log: feature 023 Shift battle style

Branch `023-shift-battle-style` from `main` 581e836, main checkout. Times US Eastern.

## T001 Setup (4:06 PM EST)

Before-values (all three expected to change by the end):

```
sim_code_hash platsim_code_hash: sha256:299b1b556a0066a2d004e6026d9e2c12fd7bb47fa04c6446e34c24565301b59b sha256:83396c29c564437125f17fd53ad82e21ead8fa4048d4364fc4a74b372fb448fe
divergence_ledger_version: sha256:8fc3728d461fba56
```

## T002-T003 Foundational (4:08 PM EST)

Ledger: `mech-shift-prompt` (corrected) and `mech-shift-entry-order` (accepted) added to `mechanics._ENTRIES`;
`uv run platsim divergences` wrote 75 entries, version `sha256:baeaf406c676c665` (was `8fc3728d461fba56`); the pinned
id list in `tests/integration/test_divergences.py` extended. Worker: `battle_style` read and validated in `runGauntlet`
(`set` | `shift`, else a request error), hello `battle_styles: ['set', 'shift']`.

## T004-T007 The offer in the worker, the Node tests (4:10 to 4:15 PM EST)

`sim/gauntlet.mjs`: `shiftWanted(p1, p2)` and `shiftOffer(...)` (exported for the tests); the loop computes the
trainer's choice once, then the offer; `switchFlag` set before `makeRequest('switch')`; per-battle `shift` record and the
`|-message|shift: ...` log line under Shift only; `battle_style: 'shift'` echoed only under Shift. Wrappers forward the
hook (`sim/bench.mjs` `runRecorded`, the determinism instrument).

`sim/test/shift.test.mjs` part 1 (8 tests): the hand-walk (Scizor Bullet Punch KOs Flint's Houndoom at 1 HP; the AI's
pick Infernape is the announced species; Bronzong enters with Scizor's +2 Atk cleared; Infernape enters; the turn counter
+1; no `|move|` between; both sides on a move request), the poison hand-walk (Protect, residual poison KOs the foe: offer
fires, stay is `''`), the four exclusions (both faint: both replacing, `shiftWanted` false; player-only faint; no bench:
no call, no line; last foe: battle ended), illegal answers thrown, and the gauntlet check (Set never calls the hook and
matches a hookless run's `log_hash`es; no echo, no `shift` field; Shift echoes, offers == calls, an event with the reason;
`shuffle` refused). Fixture lesson: Scizor and Bronzong are Steel (poison immune): the poisonable cases use Gyarados; the
last-foe case must decrement `side.pokemonLeft`.

```
node --test test/shift.test.mjs: pass 8, fail 0
Set guard, node --test test/replay.test.mjs test/determinism.test.mjs test/gauntlet.test.mjs test/bench.test.mjs: pass 24, fail 0
  (replay_prof_a.json: v1/v2/v4 digest_full, digest_logs, choices and draw counts unchanged)
```

## T008-T012 Python plumbing and tests (4:15 to 4:26 PM EST)

New `src/platsim/battle_style.py` (constants, `style_of`). `EvaluationReport.battle_style` (default `set`, round trip,
old JSON reads `set`), xlsx row "Battle style", web summary key, `summary_text` `style <x>`, provenance `battle_style`;
every request builder carries the field and every echo check reads `r.get("battle_style", "set")` (evaluate, sampling,
champion top-up, loss replays, bench, the optimizer's calibrate/setup pairs, screen, level search, ability screen, confirm,
runner-up); `pool._PROVENANCE` gains `battle_styles`; `OptimizeRequest.battle_style` validated, fingerprint only when
non-default, provenance `request.battle_style`; `evaluate --battle-style`, `optimize --battle-style` (default from the
request). Tests added or extended: `test_reports.py`, `test_optimizer_resume.py` (+2), `test_web_result_view.py` key set,
`test_optimize_small.py` key list, `test_divergences.py` ids.

```
targeted: 59 passed (reports, resume, default policy, sampling, pairing, divergences)
fast mode, 4:15:36 to 4:26:12 PM EST: 583 passed, 30 deselected, 4 xfailed in 632.02s (0:10:32); 0 battle worker starts
```

## T013 Integration test (4:26:21 to 4:29:44 PM EST)

`tests/integration/test_evaluate_shift.py` (battle_sim): Shift at 40 runs on the reference team with 8 and 3 workers
byte-identical, style in the report, its provenance and the summary line; `--battle-style set` equals the default.

```
2 passed in 202.27s (0:03:22); 27 battle worker starts; 2 marked tests reached it
```

## T014 Hand check (4:29:53 to 4:34:47 PM EST, alone)

`platsim evaluate tests/fixtures/reference_team.json --runs 100 --seed q023 --battle-style shift --sampling full
--workers 8 --out runs/023-evidence/hand` and the same with `--workers 3` into `hand-w3`: result.json byte-identical
(`cmp`). Summary line `runs 492 player expectimax2-v4 opponent decomp-ai budget standard sampling full style shift`
(the standard budget extended to the CI target); clear rate 0.9472 [0.9237, 0.9637]; `battle_style` `shift` in the
report and its provenance. Note: at this point no real policy answers the offer (US2 follows), so every offer is a stay
and the result equals Set's except for the echo; the offers are recorded in the worker's per-battle records.

**Commit 1**: `feat(023): Shift battle style behind --battle-style ...`.

## T015-T018 The policies' answer (4:35 to 4:39 PM EST)

`sim/policy/expectimax2.mjs`: `scoreShift(ctx, opts, name, foeIdx)` (stay: the announced foe placed on the cloned root
and `valuePly2`; each bench candidate: our member placed first, then the foe, `valuePly2`); `shiftChoice` on every
`makeExpectimax2` policy (v1, v2, v4) switches only when the best candidate strictly beats staying; the header records the
two approximations (our incoming Intimidate on the new foe not modelled; the lookahead's model of later turns stays Set).
`sim/policy/greedy.mjs`: `memberScore(..., foe)` and `shiftChoice` on the same scale as the forced-switch pick.

`sim/test/shift.test.mjs` part 2 (13 tests): for each of greedy-v1, expectimax2-v1, -v2, -v4 on Cynthia battles at the
offer moment (Spiritomb at 1 HP KO'd by move 1): must switch (Roserade with only Poison moves against the announced
Lucario, Infernape on the bench) -> `switch 2`; must stay (Infernape with Flare Blitz against the announced Roserade,
Blissey with no attack on the bench) -> stay; the same position twice gives the same answer, reason and `aiDraws`
delta; a one-trainer Aaron gauntlet under Shift with v4 records offers with reasons, events == offers, switches == non-stay
events.

```
node --test test/shift.test.mjs: pass 21, fail 0
Node suite, 4:36:19 to 4:39:09 PM EST: tests 372, pass 372, fail 0  (replay fixtures still match: the hook is never called under Set)
```

**Commit 2**: `feat(023): player policies answer the Shift offer ...`.

## T019-T020 Acceptance (4:39:33 to 5:14:05 PM EST, alone, exit 0)

`uv run python specs/023-shift-battle-style/scripts/paired_styles.py --teams ref,b2main,b2branch,b3 --runs 2000 --workers 16
--self --b2quick --out runs/023-evidence/pairs` (evidence under `runs/023-evidence/`, copies in `evidence/acceptance/`).
Player expectimax2-v4, decomp-ai, stop_on_loss, the same seeds under both styles (`023-pairs|<team>`), sim hash
`c07be275...`. Pairing control (ref, Shift twice): **0 discordant pairs**.

| team | Set clear rate [95% CI] | Shift clear rate [95% CI] | only Shift / only Set | p (exact) | Cynthia Set -> Shift | Lucian Set -> Shift | offers / gauntlet | switch share | prompted battles won | wall Shift/Set |
|---|---|---|---|---|---|---|---|---|---|---|
| ref | 0.9510 [0.9406, 0.9596] | 0.9740 [0.9661, 0.9801] | 93 / 47 | 0.000126 | 0.952 -> 0.975 | 1.000 -> 1.000 | 20.9 | 0.69 | 9944/9995 | 1.04x |
| b2main | 0.9120 [0.8988, 0.9236] | 0.9870 [0.9810, 0.9911] | 170 / 20 | 7.91e-31 | 0.921 -> 0.989 | 0.993 -> 0.999 | 21.3 | 0.64 | 9971/9997 | 1.07x |
| b2branch | 0.7755 [0.7567, 0.7932] | 0.9785 [0.9712, 0.9840] | 433 / 27 | 2.37e-95 | 0.782 -> 0.980 | 0.995 -> 1.000 | 21.0 | 0.63 | 9952/9995 | 0.96x |
| b3 | 0.7605 [0.7413, 0.7787] | 0.9850 [0.9787, 0.9895] | 471 / 22 | 7.93e-111 | 0.859 -> 0.987 | 0.886 -> 0.999 | 21.0 | 0.66 | 9967/9997 | 0.91x |

B2 quick (`--seed 014-b2`, 16 workers): Set winner levels [54, 52, 54, 54, 54, 55] clear 0.8860 [0.8552, 0.911] (n 500, 2 confirm attempts, wall 407 s); Shift winner levels [51, 52, 52, 53, 52, 53] clear 0.9300 [0.9042, 0.9492] (n 500, 2 attempts, wall 416 s); same species, moves and items; expected average final level 54.30 (Set) vs 52.79 (Shift).

**Reading.** Shift is better for the player on every team, with statistical support far beyond the threshold (p from
1e-4 to 1e-111): the free switch lets the player counter-pick before each incoming Pokemon, so the losses that decided
Set results, Cynthia on every team and Lucian on bench-010 B3, mostly disappear (B3's Lucian pass rate 0.886 -> 0.999,
Cynthia 0.859 -> 0.987). The offer fires about 21 times per gauntlet (nearly every foe faint) and the v4 policy takes it
on about two thirds of them. Wall cost is within 10% either way (the extra valuations are offset by shorter battles).
The direction matches the spec's expectation (Shift never worse); the magnitude means the Set numbers in every stored
result and the README understate what the game's default rule allows. The B2 quick optimizer settles about two levels
lower under Shift (expected average final level 54.30 -> 52.79) with the same build. Not gated.

## T021 Docs (5:20 PM EST)

README: the command rows (`--battle-style` on `evaluate` and `optimize`), a known-limitations bullet, the feature-023
block with the table above; FUTURE-FEATURES section 3: outcome; RUN-STATE. **Commit 3**: `feat(023): acceptance ...`.

