# Tasks: Shift Battle Style

**Input**: Design documents from `/specs/023-shift-battle-style/`

**Prerequisites**: plan.md, spec.md (two clarifications), research.md (R1-R8), data-model.md, contracts/worker-and-policy.md,
contracts/cli-and-reports.md, quickstart.md

**Tests**: requested by the spec (FR-011): Node tests for the gate, the hand-walked battle and the policy controls; Python
unit tests for the field, the report round trip and the fingerprint rule; one `battle_sim` integration test; the existing
replay and determinism tests are the Set guard.

**Organization**: by user story. US1 is the rule in the battle behind the option, end to end through Python, with a
scripted test player (the MVP); US2 the real policies' answer; US3 the acceptance, docs and the owner's default decision.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1, US2, US3
- Measurements (T014, T018, T020, T023) run alone on the machine with Eastern start and end times in the validation log;
  no commit or suite while one runs; raw evidence under `runs/023-evidence/` (local, gitignored), small files copied to
  `specs/023-shift-battle-style/evidence/`.

## Path Conventions

- Worker and policies: `sim/` (behaviour change: `sim_code_hash` changes); package: `src/platsim/` (`platsim_code_hash`
  changes); ledger: `src/platsim/divergence/mechanics.py` + `data/divergences.json` (`divergence_ledger_version` changes)
- Tests: `sim/test/`, `tests/unit/`, `tests/integration/` (battle_sim marker only on tests that start the worker)
- Feature scripts: `specs/023-shift-battle-style/scripts/`; log: `specs/023-shift-battle-style/validation-log.md`
- The B2 quick request (018/022): `platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2 --workers 16`

---

## Phase 1: Setup

- [X] T001 Create `specs/023-shift-battle-style/scripts/`, `specs/023-shift-battle-style/evidence/`, `runs/023-evidence/`, and start `specs/023-shift-battle-style/validation-log.md` with the branch point (`main` 581e836), the Eastern start time and the before-values from `uv run python -c "from platsim import version; print(version.sim_code_hash(), version.platsim_code_hash())"` and `data/divergences.json`'s `version` (all three are expected to change; record the after-values at the end)

---

## Phase 2: Foundational

**Purpose**: the ledger entries and the worker's request contract, before the offer is written.

- [X] T002 [P] Add to `src/platsim/divergence/mechanics.py` `_ENTRIES` the two entries of data-model.md: `mech-shift-prompt` (area mechanics, resolution `corrected`, description of the game's Shift prompt and gate, `decomp_ref` `pokeplatinum/src/battle/battle_controller_player.c:4144` plus the subscript, `showdown_ref` `pokemon-showdown/sim/battle.ts:1427`, impact: the player may switch for free after a KO under `battle_style=shift`; `set` keeps the engine's behaviour, `test_id` `sim/test/shift.test.mjs`) and `mech-shift-entry-order` (resolution `accepted`, `decomp_ref` `pokeplatinum/src/battle/battle_lib.c:3649`, `showdown_ref` `pokemon-showdown/sim/battle-queue.ts:177`, impact: order of the two entries and their entry effects differs only when both carry interacting entry effects); regenerate with `uv run platsim divergences`; add both ids to the pinned list in `tests/integration/test_divergences.py`; run `uv run pytest -q tests/integration/test_divergences.py -m "not battle_sim"` and record the output
- [X] T003 [P] `sim/worker.mjs`: read `req.battle_style ?? 'set'` next to the log mode, throw a `RequestError` naming the field for any value other than `set`/`shift` (contracts/worker-and-policy.md), pass it into `runGauntlet`; hello gains `battle_styles: ['set', 'shift']`; `sim/gauntlet.mjs` `runGauntlet` reads `battleStyle` from the request (no behaviour yet)

**Checkpoint**: the ledger validates; the worker accepts and advertises the field.

---

## Phase 3: User Story 1 - The rule in the battle, behind a style option (Priority: P1) 🎯 MVP

**Goal**: under `shift` the gauntlet offers the free switch exactly at the game's gate and applies it through the engine's
request path; under `set` nothing changes by a byte; the option flows CLI → request → echo → report, provenance, summary,
xlsx, web view, fingerprint.

**Independent Test**: `sim/test/shift.test.mjs` with a scripted player that always switches (the hand-walk and the four
exclusions), the replay and determinism tests unchanged, the battle_sim evaluate test under Shift at two worker counts,
quickstart step 3.

- [X] T004 [US1] `sim/gauntlet.mjs`: the offer (contracts/worker-and-policy.md, R1, R4): in the turn loop, when `battleStyle === 'shift' && !p1.requestState && p2.requestState === 'switch'`: `c2 = oppPolicy.choose(ctxFor(p2))` once; parse `switch N`, `incoming = p2.pokemon[N-1]`; gate: `p1.active[0].hp > 0` and some `p1.pokemon` member with `hp > 0` that is not active; `{choice, reason} = playerPolicy.shiftChoice?.(ctxFor(p1), incoming) ?? {choice: null, reason: 'no hook'}` (contracts/worker-and-policy.md); validate `choice` is null or `switch N` naming such a member (else throw as an illegal choice); append `battle.add('-message', 'shift: <trainer> is about to send in <species>; player <stays|switches to X> (<reason>)')` before the choices; on a switch `p1.active[0].switchFlag = true; battle.makeRequest('switch'); battle.makeChoices(choice, c2)`, on stay `battle.makeChoices('', c2)`; per-battle record `shift = {offers, switches, events: [{turn, incoming, answer, reason}]}` added only under Shift; the run response gains `battle_style: 'shift'` only under Shift; under Set the loop is byte-for-byte today's path; the offer fires when the foe's active fainted by any cause and p1's did not (the engine's request state, FR-002)
- [X] T005 [P] [US1] Forward the hook in the wrappers: `sim/bench.mjs` `runRecorded` (beside `choose`/`afterTurn`), the instrument in `sim/test/determinism.test.mjs`, so a wrapped policy's `shiftChoice` is not silently lost (R3)
- [X] T006 [US1] Write `sim/test/shift.test.mjs` part 1 (R7): a scripted probe policy registered with `registerPlayerPolicy` whose `shiftChoice` always switches to the first eligible member and counts calls; using `leagueBattle` + `setHP` and the post-KO pattern (`sim/test/ai_golden.test.mjs:220-231`) with `battle_style: 'shift'`: (a) the hand-walk: a stat boost set on p1's active before the KO; after the offer the log carries the `-message` line, p1's active is the probe's member with boosts cleared, p2's active is the announced species, the turn counter incremented once as for a normal replacement with no `|move|` line between the KO turn's end and the next `|turn|`, and the next request is a move request for both; a second hand-walk where the foe faints from poison at the end of the turn also fires the offer (FR-002); (b) exclusions, each asserting no `-message` line and the probe not called: both actives faint in the same turn (both replaced, p1 first in the `|switch|` lines is NOT asserted, the engine orders by speed, R2), only p1's faints, p1 has no bench member with HP, the foe's last Pokemon faints (battle ends); (c) Set: the same battles with `battle_style: 'set'` never call the probe and produce the same `log_hash` as without the probe; run `(cd sim && node --test test/shift.test.mjs)` and record
- [X] T007 [US1] Run `(cd sim && node --test test/replay.test.mjs test/determinism.test.mjs test/gauntlet.test.mjs test/bench.test.mjs)` (the Set guard: all three replay fixture policies' `digest_full`, `digest_logs`, choices and draw counts unchanged) and then the whole Node suite `(cd sim && node --test test/*.test.mjs)`; record counts in the validation log
- [X] T008 [P] [US1] `src/platsim/report/json_report.py`: `EvaluationReport.battle_style: str = "set"` as a trailing defaulted field, written by `to_dict`, read by `from_dict` with default `"set"`; `src/platsim/report/xlsx.py`: row "Battle style" after "Sampling method"; `src/platsim/web/result_view.py`: summary key `battle_style` (default `set`) (contracts/cli-and-reports.md)
- [X] T009 [US1] `src/platsim/evaluate.py`: `evaluate(..., battle_style="set")` (UsageError on other values) and `evaluate_team(..., battle_style="set")`; `run_full_gauntlets(..., battle_style)` puts `battle_style` in every request and the echo check compares `r.get("battle_style", "set")`; hello check requires `battle_style in hello["battle_styles"]`; thread it to `run_adaptive`, `champion_topup`, `collect_loss_causes`; provenance gains `battle_style`; `EvaluationReport(battle_style=...)`; `summary_text` first line gains `style <x>`; `default_out_dir` adds the style to its hash only when non-default; `src/platsim/sampling.py` (`cynthia_only_request`, `run_adaptive` requests and echo), `src/platsim/sim/champion.py` (`request(k)` and the top-up echo), `src/platsim/report/losses.py` (`replay_requests` copies `r.get("battle_style", "set")`), `src/platsim/bench.py` (request), `src/platsim/sim/pool.py` (`battle_styles` in `_PROVENANCE`) (R5)
- [X] T010 [US1] Optimizer plumbing: `src/platsim/optimizer/api.py` `OptimizeRequest.battle_style: str = "set"` validated in `__post_init__` (`InvalidRequest` with `{"battle_style": ...}`); `src/platsim/optimizer/run.py` `job_fingerprint` adds `battle_style` only when it differs from `OptimizeRequest.battle_style`, `_optimizer_provenance.request` names it, the hello check, `_paired`, the confirm `evaluate_team` calls and the runner-up `run_adaptive`/`run_full_gauntlets` carry it, `_no_qualifying`'s report carries it; `src/platsim/optimizer/screen.py`, `levels.py`, `abilities.py`: requests carry it and echo checks read it (R5)
- [X] T011 [US1] `src/platsim/cli.py`: `evaluate --battle-style {set,shift}` (default `set`) passed to `evaluate(...)`; `optimize --battle-style` with the default read from `OptimizeRequest.battle_style`; `optimize_request` passes it (contracts/cli-and-reports.md)
- [X] T012 [US1] Python tests: `tests/unit/test_reports.py` (round trip of `battle_style`, old JSON without the key reads `set`, xlsx "Battle style" row, summary line contains `style shift`), `tests/unit/test_optimizer_resume.py` (fingerprint carries `battle_style` only when non-default; CLI default equals the request default; `InvalidRequest` on `foo`), `tests/integration/test_web_result_view.py` `SUMMARY_KEYS` + default `set`, `tests/integration/test_optimize_small.py` (the report/provenance key list at its line 34); run `uv run pytest -q -m "not battle_sim"` (fast mode, about 10 min) and record the line
- [X] T013 [US1] Write `tests/integration/test_evaluate_shift.py` (`@pytest.mark.battle_sim`): `python -m platsim.cli evaluate tests/fixtures/reference_team.json --runs 40 --seed t023 --battle-style shift --sampling full` with `--workers 8` and `--workers 3`: byte-identical result.json, `battle_style == "shift"` in the report and provenance, the summary line names the style; and the same request with `--battle-style set` equals the same request without the flag; run `uv run pytest -q tests/integration/test_evaluate_shift.py` and record
- [X] T014 [US1] Hand check (quickstart step 3, alone, Eastern times): `uv run platsim evaluate tests/fixtures/reference_team.json --runs 100 --seed q023 --battle-style shift --sampling full --workers 8 --out runs/023-evidence/hand` (expected `battle_style` in result.json and the summary; `--workers 3` rerun byte-identical); then Commit 1 `feat(023): Shift battle style behind --battle-style (the offer in the worker, the option end to end, two ledger entries); set byte-identical`; push

**Checkpoint**: Shift works with a scripted player; Set is untouched; the option is everywhere.

---

## Phase 4: User Story 2 - The player answers the prompt (Priority: P2)

**Goal**: greedy-v1 and expectimax2 v1/v2/v4 answer the offer with their existing scoring, deterministically, with a
reason; the trainer AI untouched.

**Independent Test**: `sim/test/shift.test.mjs` part 2: the must-switch and must-stay positions for every policy, same
answer and draw counts on repeat, Set never calls the hook (replay fixtures unchanged).

- [X] T015 [P] [US2] `sim/policy/expectimax2.mjs`: `scoreShift(ctx, opts, name, foeIdx)` mirroring the forced-switch branch of `scoreActions` (R3, contracts/worker-and-policy.md): `X = makeContext(ctx, opts, name)`; stay: `T = cloneState(X.root); doSwitch(X, T, 1, foeIdx); v0 = valuePly2(X, T)`; each bench member k with HP and not active, in party order: `T = cloneState(X.root); doSwitch(X, T, 0, k); doSwitch(X, T, 1, foeIdx); vk = valuePly2(X, T)`; return `{stay: v0, candidates: [{idx, v}], reason}` with `reason` naming the values; `shiftChoice(ctx, incoming)` on every `makeExpectimax2` policy (v1, v2, v4 share it) returns `{choice: 'switch N', reason}` for the best candidate only when `vk > v0` (ties stay), else `{choice: null, reason}`, `reason` naming `v0` and the best `vk`; export the helpers in `_internal`; a header note recording the two approximations (our incoming Intimidate on the new foe not modelled; the search's model of later turns stays Set per clarification 1)
- [X] T016 [P] [US2] `sim/policy/greedy.mjs`: `memberScore(gd, battle, side, pokemon, foe = foeOf(battle, side))`; `shiftChoice(ctx, incoming)` returning `{choice, reason}`: the active's score against `incoming` versus each bench member's; `choice: 'switch N'` for the best member only when strictly greater, else `null`; `reason` names both scores; a header note on the field-ability caveat (R3)
- [X] T017 [US2] `sim/test/shift.test.mjs` part 2 (R7): with `customBattle`-style raw positions (`sim/test/ai_switch.test.mjs:20-26`) for each of `greedy-v1`, `expectimax2-v1`, `expectimax2-v2`, `expectimax2-v4`: (a) must switch: the active cannot damage the announced foe (a type immunity, e.g. Normal moves into a Ghost) while a bench member one-shots it; `shiftChoice` returns that member; (b) must stay: the active one-shots the announced foe and outspeeds it; `shiftChoice` returns null; (c) determinism: the same position twice gives the same answer and the same `STATS.aiDraws` delta; (d) a real one-trainer gauntlet (`trainers: ['aaron']`, the reference team, v4, `battle_style: 'shift'`) returns at least one battle with `shift.offers >= 1` and an event with a reason; run the file and record
- [X] T018 [US2] Run `(cd sim && node --test test/*.test.mjs)` (the replay fixtures must still match: the hook is never called under Set); then the fast pytest set is unaffected (no Python change in this story) ; Commit 2 `feat(023): player policies answer the Shift offer (expectimax2 v1/v2/v4, greedy-v1), controls pinned`; push

**Checkpoint**: every player answers the offer; Set unchanged.

---

## Phase 5: User Story 3 - Measured difference and the default decision (Priority: P3)

**Goal**: the acceptance table on four teams plus the B2 quick pair; docs; the owner's default decision.

**Independent Test**: the script's table is complete, the control row shows 0 discordant, the validation log carries
Eastern times.

- [X] T019 [US3] Write `specs/023-shift-battle-style/scripts/paired_styles.py` (R8): import the 018 script's `load_team_requests` by path (register the module in `sys.modules` before exec, the 019 lesson), teams `ref`, `b2main`, `b2branch` and `b3` (written from `runs/bench-010/B3/result.json` to `runs/023-evidence/teams/b3.json` as 022 did); for each team run the same seeds (`derive_seed(master, i, 0)`, master `023-pairs|<team>`) under `battle_style` `set` and `shift` with `expectimax2-v4`, `stop_on_loss` True, `log` `summary`, cached per `(team, style, n, sim_code_hash)`; report per team: clear rate and Wilson interval per style, `mcnemar_exact` (a_only, b_only, p, verdict), per-trainer pass rates per style from `battles[].won`, offers, switches and prompted-battle outcomes from `battles[].shift`, gauntlets/s per style and the wall ratio; `--self` plays Shift twice on the first team and exits 1 unless 0 discordant; `--b2quick` runs `python -m platsim.cli optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2 --workers 16 --battle-style <x> --force-new --out runs/023-evidence/b2quick-<x>` for both styles and reports winner species, levels, the confirmation's clear rate and interval, and wall; write `summary.json` and print the table
- [X] T020 [US3] Acceptance run alone (about 1 h, Eastern start and end times): `uv run python specs/023-shift-battle-style/scripts/paired_styles.py --teams ref,b2main,b2branch,b3 --runs 2000 --workers 16 --self --b2quick --out runs/023-evidence/pairs > runs/023-evidence/acceptance.txt 2> runs/023-evidence/acceptance.err`; copy `acceptance.txt`, `pairs/summary.json` and the two B2 quick `result.json`/`team.txt` to `specs/023-shift-battle-style/evidence/`
- [X] T021 [US3] Validation log: the acceptance table with the reading (direction per team, offers and switch rates, prompted-battle outcomes, wall ratios, the B2 quick pair); README: the rule (gate, order, no turn cost), `--battle-style` on both commands in the command rows, a feature-023 block with the numbers and the current default, the ledger entries; FUTURE-FEATURES section 3: outcome recorded; RUN-STATE START HERE; Commit 3 `feat(023): acceptance (paired Shift vs Set on four teams, B2 quick pair); docs`; push
- [X] T022 [US3] Present the table to the owner with the options (keep `set`; `shift` as the default) and record the decision in the validation log, README and FUTURE-FEATURES; if the owner says go: the request default in `OptimizeRequest`, `evaluate`'s default, the CLI defaults (read from the request), the worker's absent-field default stays `set` (Python always sends the field), the tests that pin the default, one commit `feat(023): shift is the default battle style (user's go)`, push

---

## Phase 6: Polish, gates, close

- [ ] T023 Gates, in order, nothing else running: `git diff --stat main -- pokemon-showdown` empty (FR-006) and recorded; record the after-values of `sim_code_hash`, `platsim_code_hash` and the ledger version (changed, as expected) in the validation log; `(cd sim && node --test test/*.test.mjs)` green; the full pytest suite `uv run pytest -q --durations=25 > runs/023-evidence/full.log 2>&1` green (about 1 h 30 min); log each output with Eastern times; copy a gates summary to `specs/023-shift-battle-style/evidence/gates.txt`
- [ ] T024 Closing commit `docs(023): gates recorded; feature closed on its branch`; push; report to the user. Merge to `main` only on the user's go (`git checkout main && git merge --ff-only 023-shift-battle-style && git push`, or a merge commit if `main` moved)

---

## Dependencies and execution order

- Phase 1 → Phase 2 (T002 ∥ T003) → US1 (T004 → T005 ∥ T006 → T007; T008 ∥ T009 → T010 → T011 → T012 → T013 → T014)
  → US2 (T015 ∥ T016 → T017 → T018) → US3 (T019 → T020 → T021 → T022) → T023 → T024.
- US1's Python tasks (T008-T013) depend only on T003's request contract and can start while T004-T007 are in progress
  if the worker's echo field is agreed first (`battle_style: 'shift'` only under Shift).
- T022 blocks on the owner's answer; T023 runs on the final code (after the flip, if any); no commit during T014, T018,
  T020 or T023's measured steps.

## Parallel opportunities

- T002 ∥ T003; T005 ∥ T006; T008 ∥ T009; T015 ∥ T016.

## Implementation strategy

- MVP = US1 with the scripted test player: proves the rule and the plumbing with Set byte-identical.
- US2 makes the real players use it; US3 measures and lets the owner decide the default.
- Size: 24 tasks, three stories, two layers (worker/policies, Python plumbing). If the owner wants a smaller branch,
  T010 and the `--b2quick` part of T019/T020 can move to a follow-on (evaluate-only Shift here).
