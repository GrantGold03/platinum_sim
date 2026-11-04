# Research: Shift Battle Style

Sources read 2026-11-04 (read only): the decomp at c248fb3f (FUTURE-FEATURES section 3 holds the citations), the vendored
Showdown `sim/*.ts` and `data/mods/gen4/*`, `sim/gauntlet.mjs`, `sim/policy/*.mjs`, `sim/test/*`, `src/platsim/**`.

## R1. Driving the free switch from the worker (no engine edit)

- **Decision**: in the gauntlet loop, when the style is `shift`, p1 has no request and p2's request is a replacement
  (`!p1.requestState && p2.requestState === 'switch'`): compute `c2 = oppPolicy.choose(ctxFor(p2))` exactly once (its
  `decide` has side effects and already scores the replacement against p1's current active, the game's order), parse
  `switch N`, `incoming = p2.pokemon[N-1]`; apply the game's gate (p1's active standing, a bench member of p1 with HP);
  ask `playerPolicy.shiftChoice(ctx, incoming)`; on a switch set `p1.active[0].switchFlag = true` **before** calling
  `battle.makeRequest('switch')`, then `battle.makeChoices('switch k', c2)`; on stay, `battle.makeChoices('', c2)` as
  today. Showdown turns both answers into `instaswitch` actions, runs no move in between, runs the entry effects, ends
  the turn once (as a normal replacement does) and issues the next move request: no turn cost
  (`sim/battle.ts:1427-1436` request building from `switchFlag`; `:2996-3024` commitChoices; `:2948-2954` turnLoop;
  `sim/battle-actions.ts:62-158` switchIn: BeforeSwitchOut, SwitchOut (gen4 Natural Cure, `data/mods/gen4/abilities.ts:289-296`),
  `clearVolatile` resets boosts and volatiles).
- **Why not `battle.actions.switchIn` directly**: it bypasses the choice path and leaves the queued `runSwitch` to be
  drained by hand; the request path is the public contract and already drains it.
- **Rules learned**: (a) set the flag before `makeRequest`, or `forcedSwitchesLeft` stays 0 (`sim/side.ts:1118-1125`);
  (b) once the flag is set p1 must answer `switch N` (`''` or `pass` fail, `sim/side.ts:541, 1335-1340`), so the policy
  decides first and the flag is set only on a switch; (c) `makeRequest` writes nothing to the log (`sim/battle.ts:1381-1412`),
  so the Set path and the stay path are byte-identical to today; (d) Pursuit cannot fire on an `instaswitch` between
  turns (its volatile lasts one turn and needs the move still queued, `data/moves.ts:14387-14432`, gen4 `data/mods/gen4/moves.ts:1061-1075`).
- **Alternatives considered**: a Showdown format rule (none exists; `shift` is the triples choice, `sim/side.ts:1097-1106`);
  editing the vendored tree (forbidden by Principle II).

## R2. Ordering of the two entries: a recorded divergence, not a correction

- **Finding**: the engine sorts the two `instaswitch` actions by the outgoing Pokemon's speed with seeded tie shuffles
  (`sim/battle-queue.ts:177`, `sim/battle.ts:408-415, 433-462`), and runs each entering Pokemon's `runSwitch` (hazards,
  then switch-in abilities and items) after both have entered, in the entering Pokemon's speed order, each separately
  in gen4 (`data/mods/gen4/scripts.ts:18-53`, `sim/battle-actions.ts:156`, order 101). The game enters the player's
  Pokemon first, applies hazards in that order, then runs entry abilities by category and speed
  (`battle_controller_player.c:1844-1859`, `battle_lib.c:3649ff`).
- **Decision**: accept and record (`mech-shift-entry-order`, resolution `accepted`). The difference acts only when both
  entering Pokemon carry entry effects that interact (two Intimidates, hazards on both sides, a weather ability against
  another); the gauntlet's opponents are fixed parties, so the acceptance log can count such cases if wanted. Forcing
  the game's order would mean sequencing the two switches by hand outside the choice path (R1's rejected route).
- The prompt itself is recorded as `mech-shift-prompt`, resolution `corrected` (the game layer implements it; `set`
  reproduces the engine's behaviour by choice), `test_id` naming the Node test.

## R3. The policies' answer (FR-007, FR-007a)

- **Interface**: an optional policy method `shiftChoice(ctx, incoming) -> null | 'switch N'` (N the 1-based slot in
  p1's party order, as a forced switch answers). Policies without it stay. The gauntlet, not the policy, writes the log
  marker (the determinism instrument checks that a policy never touches the log, `sim/test/determinism.test.mjs:41`).
- **expectimax2 (v1, v2, v4)**: a new exported `scoreShift(ctx, opts, name, foeIdx)` mirroring the forced-switch branch
  of `scoreActions` (`sim/policy/expectimax2.mjs:1234-1242`): `X = makeContext(ctx, opts, name)` works while p2's active
  is fainted (`rootState` reads the fainted slot, `:1184-1199`); stay value: `T = cloneState(X.root); doSwitch(X, T, 1,
  foeIdx); valuePly2(X, T)`; each bench candidate k: `T = cloneState(X.root); doSwitch(X, T, 0, k); doSwitch(X, T, 1,
  foeIdx); valuePly2(X, T)`. Our member is placed first, then the announced foe, which is the game's entry order: the
  foe's Intimidate hits our incoming member in the model; our member's Intimidate on the new foe is not modelled
  (`doSwitch` applies it only to a standing foe), a known approximation of the lookahead recorded in the policy header.
  Switch when the best candidate's value exceeds the stay value (ties stay; candidates in party order). The search's
  model of later turns is untouched (clarification: the rule is not modelled inside the search). Samples: `valuePly2`
  uses kPly2 samples per valuation through `predictOpponent`, seeded statelessly per state signature
  (`:932-966`), so no other decision's draws move; `STATS.aiDraws` grows only under Shift. `_internal` gains the
  helpers the test needs.
- **greedy-v1**: `memberScore(gd, battle, side, pokemon, foe = foeOf(...))` gains an optional foe; `shiftChoice` compares
  the active's score against `incoming` with each bench member's; switch when strictly better. No RNG. Caveat recorded:
  `fromShowdown` reads field abilities from standing Pokemon, so the not-yet-active foe's weather or Cloud Nine is missed
  in the greedy estimate (acceptable: greedy is the control player, not the default).
- **Wrappers that must forward the hook or lose it silently**: `runRecorded` (`sim/bench.mjs:78-117`), the determinism
  instrument (`sim/test/determinism.test.mjs:50-66`), test probe policies.

## R4. The per-battle record and the log marker (clarification: no aggregation in reports)

- **Decision**: under Shift only, the gauntlet adds to each battle record (`sim/gauntlet.mjs:183-185`)
  `shift: {offers, switches, events: [{turn, incoming, answer, reason}]}` and writes one log line per offer,
  `|-message|shift: <trainer> is about to send in <species>; player <stays|switches to X> (<reason>)`, before the
  choices are made. `processLog` ignores `-message` lines and `losses.py`'s regexes match only switch/drag/replace/faint,
  so neither the trainer AI nor the loss replay changes; under Set no field and no line is added, so `digest_full`,
  `digest_logs` and `log_hash` are unchanged. The run-level response echoes `battle_style` only when it is `shift`.
- Python keeps no per-run records in result.json (`EvaluationReport` is aggregated), so the acceptance script reads the
  pool responses directly (`TeamEvaluation.results` or its own `pool.map`), as the 018 pairing script does.

## R5. Plumbing the option through Python (the `player_policy` precedent)

- **Decision**: `battle_style: str = "set"` on every worker request builder: `evaluate.run_full_gauntlets` (`evaluate.py:148-150`),
  `sampling.cynthia_only_request` and `run_adaptive` (`sampling.py:118-123, 172-174`), `champion.request` (`champion.py:170-174`),
  `losses.replay_requests` (`losses.py:106-117`, copied from the run response with default `set`), the optimizer's
  `_paired`, screen, levels, abilities, confirm and runner-up requests (`run.py:249-257, 604-664`, `screen.py:58-59`,
  `levels.py:140-142`, `abilities.py:347-348`), and `bench.py:52`. Every echo check reads `r.get("battle_style", "set")`.
  The worker validates the field (`set` | `shift`, else a request error) and advertises `battle_styles` in hello,
  which joins `pool._PROVENANCE` and the hello checks beside `policies`.
- `evaluate(..., battle_style)` and `evaluate_team(..., battle_style)` thread it to `run_adaptive`, `run_full_gauntlets`,
  `champion_topup` and `collect_loss_causes`; `default_out_dir` adds the style to its hash only when non-default so
  existing directories keep their names.
- `OptimizeRequest.battle_style = "set"`, validated in `__post_init__` (`InvalidRequest`), `job_fingerprint` adds it only
  when non-default (`run.py:87-99`), `_optimizer_provenance.request` names it, `cli.optimize` reads its default from
  `OptimizeRequest` (the pinned rule, `test_optimizer_resume.py:163`). The web app keeps the default.
- **Report**: `EvaluationReport.battle_style = "set"` as a trailing defaulted field; `to_dict` writes it, `from_dict`
  reads it with default `set` (the 021 pattern, `json_report.py:243-244, 314, 358`); `summary_text`'s first line gains
  `style <set|shift>`; xlsx gains a "Battle style" row after "Sampling method"; provenance gains `battle_style`; the web
  result view exposes `battle_style` (SUMMARY_KEYS pin extended; the frozen web fixture reads as `set`).
- **Pre-feature checkpoints**: refused without a new rule: `sim_code_hash`, `platsim_code_hash` and
  `divergence_ledger_version` all change (`version.py:38-40`, `run.py:108-140`).

## R6. The divergence ledger

- Entries live in `src/platsim/divergence/mechanics.py:_ENTRIES`; required fields `id, area, description, decomp_ref,
  showdown_ref, resolution, impact, test_id`; refs must match `pokeplatinum/\S+:\d+` and `pokemon-showdown/\S+:\d+`
  (`compare.py:353-378`). `data/divergences.json` is tracked and regenerated by `uv run platsim divergences`;
  `tests/integration/test_divergences.py::test_ledger_matches_fresh_diff` (fast mode) pins the id list and the version,
  so both the file and that list change in the same commit.

## R7. Tests and harnesses

- Node: `leagueBattle(trainerKey, builds, {seed})` + `setHP` + the post-KO pattern of `sim/test/ai_golden.test.mjs:220-231`
  (set the foe to 1 HP, `makeChoices('move 1','move 1')`, p2 now replacing) reproduce the Shift moment on a real League
  battle; `customBattle` (`sim/test/ai_switch.test.mjs:20-26`) builds raw two-Pokemon positions for the policy controls;
  `registerPlayerPolicy` probes give a scripted player with `shiftChoice` for the hand-walk; `runGauntlet` with
  `trainers:['aaron']` runs one battle. `sim/test/replay.test.mjs` + `replay_prof_a.json` and `determinism.test.mjs`
  are the Set guard and need no change.
- Python: unit tests for the request field, report round trip (old JSON reads `set`), fingerprint rule, CLI defaults and
  validation; one `battle_sim` integration test: `evaluate --battle-style shift` at a small count on the reference team
  with 8 and 3 workers, byte-identical result.json, style in the report; `test_optimize_small.py:34`'s key list and the
  web view key set updated.

## R8. Acceptance tooling and cost

- **Decision**: a new `specs/023-shift-battle-style/scripts/paired_styles.py` that imports the 018 script's team loaders
  (`load_team_requests`: `ref`, `b2main`, `b2branch`, `file:<team.json>`; B3 from `runs/022-evidence/teams/b3.json`,
  rewritten from `runs/bench-010/B3/result.json` if absent), runs the same seeds under both styles with the v4 player,
  caches per `(team, style, n, sim_code_hash)`, and reports per team: clear rate and Wilson interval per style, McNemar
  exact, per-trainer pass rates from `battles[].won`, offers, switches and prompted-battle outcomes from `battles[].shift`,
  gauntlets/s and the wall ratio; `--self` plays Shift twice (0 discordant). The B2 quick runs reuse the 022 invocation
  (`optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2 --workers 16`) with
  `--battle-style` per side into `runs/023-evidence/b2quick-{set,shift}/`.
- **Cost**: Set side about 2 to 4 min per team at 9 to 17 gauntlets/s; Shift adds one policy valuation per offer (kPly2
  samples per candidate, no root samples), expected well under the cost of a root decision; two B2 quick runs about 6 min
  each; total about one hour alone on the machine. Measured, not assumed.
