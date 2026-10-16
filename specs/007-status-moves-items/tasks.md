---
description: "Task list for 007 Status Moves and Held Items"
---

# Tasks: Status Moves and Held Items in Team Optimization

**Input**: the design documents in `specs/007-status-moves-items/`: plan.md, spec.md, research.md (R1–R11), data-model.md, contracts/ (candidate-report.md, player-v3.md, ledger-sources.md) and quickstart.md.

**Tests**: included. The constitution requires positive controls (Principle V) and reference comparisons (Principle VI). The spec's SC-001, SC-007 and SC-008 name test cases.

**Format**: `[ID] [P?] [Story] Description`. `[P]` means the task touches different files from the other `[P]` tasks around it and has no unfinished dependency.

## Ground rules for every task

- **Where:** the main checkout `/home/grant/Desktop/platinum_sim`, branch `007-status-moves-items`. There is no worktree, and the web server stays stopped unless the user asks for it.
- **Commits:** commit on the branch. **Push every commit that touches `src/`, `sim/`, `tests/` or static web files** (`git push`, then check with `git ls-remote origin refs/heads/007-status-moves-items`). Never commit `*.nds`, `runs/` or `data/generated/`. Don't merge into `main` until the user has tested it.
- **Spec Kit:** a behaviour change not covered by these tasks goes into spec.md (Clarifications / FRs) first, then through `/speckit-converge`.
- **Constitution I:** no hand-typed game data. Rule tables are keyed on decomp constants, never move or item names, and each one has a completeness test.
- **Constitution VI:** every approximation has its reference built and measured first. Comparisons and run times are recorded in `validation-log.md`.
- **v1/v2 player output must stay byte-identical** (golden test from T004). Every v3 behaviour sits behind `V3_OPTS` flags.
- **Recording:** paste the real output of every checkpoint into `specs/007-status-moves-items/validation-log.md`. Update `RUN-STATE.md` as work lands.
- **Temp files** go in the session scratchpad. Run probes with `uv run python -u`.
- **Contention:** don't run a heavy test or benchmark while another one is running; it causes false timeouts. Long runs go in the background and are noted in `RUN-STATE.md` with their output paths.

## Path conventions

- **Python:** `src/platsim/optimizer/`, `src/platsim/availability/`, `src/platsim/decomp/`, `src/platsim/report/`, `src/platsim/web/`, `src/platsim/evaluate.py`, `src/platsim/cli.py`.
- **Node:** `sim/policy/expectimax2.mjs`, `sim/gauntlet.mjs`, `sim/team.mjs`, `sim/test/`.
- **Tests:** `tests/unit/`, `tests/integration/`, `tests/browser/`, `sim/test/`.

---

## Phase 1: Setup (baseline before any change)

- [X] T001 Create `specs/007-status-moves-items/validation-log.md` and record: `git rev-parse HEAD` (expect `e3273d5` or later, code equal to `f88cdd0`), `uv sync`, `uv run platsim extract`, `uv run platsim extract --check`, and `nproc`.
- [X] T002 Run the full Python suite `uv run pytest -q` (about 2.5 h, in the background) and `node --test sim/test`. Record the pass/fail counts in `validation-log.md` as the pre-change baseline. Start the running total of one-time hours there (all suite runs together are budgeted at 8 h). Add its wall-clock hours to the running total of one-time hours in `validation-log.md` (budget: 100 h for every one-time run, spec FR-017 table); stop and ask the user before any run would take the total over 100 h.
- [X] T003 Write the benchmark definitions B1–B5 (research R9) into `tests/fixtures/bench_007.json`: species lists, B3's `required_hms` (`surf`, `waterfall`), and seed `bench-007`. Check that each team resolves with `candidates.resolve_species` under `DEFAULT_LEGALITY` and record the output.
- [X] T004 Record the golden player hashes before any `sim/` edit. Run fixed-seed gauntlets (seeds `golden-007|0..19`) of `expectimax2-v1` and `expectimax2-v2` on `tests/fixtures/policy_benchmark_team.json` and on B1, and store each battle's `log_hash` in `sim/test/fixtures/golden_v1_v2.json`. Add `sim/test/golden_v1_v2.test.mjs`, which replays them and asserts equality. Positive control: changing one seed must make the test fail. Record the output.
- [X] T005 Baseline benchmark, about 8–11 h, in the background. Run `uv run platsim optimize --budget standard --seed bench-007 …` for B1–B5 on the current code (equal to `f88cdd0`), with `--out runs/bench-007-baseline/<B>`. Record each team's `state.json` timing per stage, total wall time, final levels, clear rate and CI in `validation-log.md` (table "Baseline"). No other heavy run (T036, T046, T063 onwards) may overlap it, because each uses all 16 workers. Budgeted at 11 h. Add its wall-clock hours to the running total of one-time hours in `validation-log.md` (budget: 100 h for every one-time run, spec FR-017 table); stop and ask the user before any run would take the total over 100 h.
- [X] T006 [P] Confirm battles already use friendship 255. Run a Node probe in the scratchpad that builds a B1 battle through `sim/team.mjs` and prints `pokemon.happiness` and Return's base power for p1. Record that both are 255 and 102 (positive control for R3).

---

## Phase 2: Foundational (blocks every user story)

- [X] T007 Create `src/platsim/optimizer/move_classes.py` (research R1):
  - `effect_script(effect)` maps an effect to `pokeplatinum/res/battle/scripts/effects/effect_script_NNNN.s` through the line index in `pokeplatinum/generated/move_battle_effects.txt`;
  - parse each script's `MOVE_SIDE_EFFECT_{TO_ATTACKER|TO_DEFENDER}|MOVE_SUBSCRIPT_PTR_*` flags, `CalcDamage` / `BTLVAR_DAMAGE` writes and commands (TryWish, Ingrain, Aqua Ring, FollowMe…);
  - apply the derived rules from the R1 table;
  - add the rule table `RULES = {BATTLE_EFFECT_* or MOVE_SUBSCRIPT_PTR_*: (category, reason)}` for the about 20 non-derivable constants: Focus Energy, Minimize, Stockpile, Belly Drum, Acupressure, Curse (non-Ghost), Follow Me, Memento, Healing Wish, Lunar Dance, Counter, Mirror Coat, Metal Burst, Bide, Spit Up, Present, Flail/Reversal, Trump Card, Natural Gift, Fling, Frustration;
  - export `classify(effect) -> MoveClass` (data-model.md) and `move_class(move_const)`.

  An unknown effect raises `ValueError`.
- [X] T008 [P] Write `tests/unit/test_move_classes.py`:
  - every effect of every move in `load_moves()` classifies without error;
  - every constant in `RULES` exists in the decomp's generated lists;
  - positive controls: Screech and Growl → foe_drop; Seismic Toss, Night Shade, Sonic Boom, Dragon Rage, Super Fang, Endeavor and Psywave → fixed_damage; **Magnitude → variable_attack** (effect named `BATTLE_EFFECT_PSYWAVE`); Swords Dance → self_boost; Thunder Wave → inflict_status; Toxic → inflict_status; Leech Seed → leech_seed; Recover and Rest → recovery; Protect and Substitute → protection; Reflect → screen; Rain Dance → weather; Helping Hand, Teleport and Splash → no_effect_singles; Defog → other; Memento → sacrifice; Counter → reactive; Return → variable_attack; Frustration → conditional_attack;
  - the derived foe_drop set equals `FOE_DROPS` parsed from `sim/policy/expectimax2.mjs` plus `SP_ATK_DOWN_2_OPPOSITE_GENDER`.
- [X] T009 Create `src/platsim/optimizer/item_classes.py` (research R2):
  - `hold_effect_references()` greps `pokeplatinum/src/battle/*.c` and `pokeplatinum/res/battle/scripts/**` for each `HOLD_EFFECT_*` by name and by number (the line index in `generated/item_hold_effects.txt`, as the resist-berry subscript compares by literal);
  - the `NO_OUTCOME` rule table (MONEY_UP, FLEE, FRIENDSHIP_UP), each with the function it must be referenced from;
  - `EXP_EV` is derived from references inside `BtlCmd_CalcExpGain`, `BattleScript_GetExpTask` and `BattleScript_CalcEffortValues`;
  - species gates are parsed from `battle_lib.c` conditions of the form `heldItemEffect == HOLD_EFFECT_X … species == SPECIES_Y`;
  - `item_class(item_const) -> ItemClass`;
  - `offerable_items(member_species, team, led) -> list[item key]`, which uses `team_item_copies(led, const, team) != 0`.
- [X] T010 [P] Write `tests/unit/test_item_classes.py`:
  - all 17 resist berries are `in_battle` (the numeric-reference positive control);
  - Everstone, Cleanse Tag and Mail are not in battle;
  - Amulet Coin, Smoke Ball and Soothe Bell are `no_outcome`, and each reference lies in its named function;
  - Lucky Egg, Exp. Share, Macho Brace and the Power items are `exp_ev`;
  - Light Ball is offered only to Pikachu;
  - Leftovers is offered on a Snorlax team and not on B1;
  - Sitrus Berry is offered;
  - Choice Band is not offered (0 copies);
  - under default options, at least 87 items are offered to some member before species gates; record the count;
  - every offered item has a Showdown id (via the worker's `gd.sdItem` mapping, or the Python mirror used by `worker_team`).
- [X] T011 Remove the stale `EXP_HOLD_EFFECTS` from `src/platsim/optimizer/candidates.py` and use `item_classes` instead. `held_item_candidates` keeps its current output for now (US2 replaces it). Confirm with `uv run pytest -q tests/unit/test_optimizer_candidates.py`.
- [X] T012 Add `adopted: tuple[str, ...] = ()` to `MemberSpec` in `src/platsim/optimizer/resources.py`:
  - `spec_to_json` writes it only when non-empty, and `spec_from_json` reads `d.get("adopted", ())`;
  - replace every positional `MemberSpec(...)` rebuild with `dataclasses.replace`: `run.py` `_apply_abilities` (~:185-194), the screen combos (~:410), the setup alternative (~:497) and `resources.repair` (~:332);
  - `grep -n "MemberSpec(" src/` must show only constructions of new members.
- [X] T013 Change `_slot_cost` in `src/platsim/optimizer/resources.py` to the tiers from data-model.md, lowest replaced first:
  1. non-adopted status;
  2. attacks by League value;
  3. non-adopted modelled boost;
  4. adopted.

  `place_required_hms` reads `spec.adopted`. Update the docstring.
- [X] T014 [P] Write `tests/unit/test_required_hms_adopted.py`:
  - with Surf required and the carrier's moveset `(attack, attack, Toxic, Recover)`, where Toxic is adopted, Surf replaces Recover;
  - with both adopted, it replaces the weakest attack;
  - with none adopted, it replaces a status move first;
  - positive control: an existing 006 test in `tests/unit/test_required_hms.py` (or its current name) still passes unchanged;
  - with no HM required and `adopted=()`, `spec_to_json` output is byte-identical to before.
- [X] T015 Add the v3 scaffold to `sim/policy/expectimax2.mjs` **with no behaviour change**:
  - `EXPECTIMAX2_V3 = 'expectimax2-v3'` and `EXPECTIMAX2_V3_REF = 'expectimax2-v3-ref'`;
  - `V3_OPTS = {...V2_OPTS}` and `V3_REF_OPTS`, where every new flag defaults off;
  - export `expectimax2v3` and `expectimax2v3ref`;
  - `export const MODELLED = {...}`, a literal table of the modelled `BATTLE_EFFECT` names (without prefix) and `HOLD_EFFECT` names for v1, v2, v3 and v3-ref, filled from the current code paths (`statusMove`, `SELF_BOOSTS`, `FOE_DROPS`, `STATUS_OF`, `HEAL_HALF`, the variable-power list, and the items in the damage port: Sitrus, Leftovers, Focus Sash, Life Orb, Wise Glasses, Expert Belt, Razor Claw / Scope Lens, Wide Lens, the type boosts, Choice Specs damage).
  - Register both in `sim/gauntlet.mjs:31,41-42` and update the VERSIONS header comment.
  - `node --test sim/test` must still pass the golden test from T004.
- [X] T016 Set `happiness: 255` explicitly for player builds in `sim/team.mjs` `memberSet`. The golden test must still pass, since Showdown already defaults to 255; record it.
- [X] T017 Add a Python parser for `MODELLED` in `src/platsim/optimizer/move_classes.py`, mirroring `expectimax_self_boosts()`: `modelled(policy) -> (effects, items)` and `not_modelled(policy, moves, item) -> list`. Add `tests/unit/test_modelled_table.py`, which checks:
  - the parse is non-empty for each version;
  - v2's effects include `ATK_UP_2` and `STATUS_BADLY_POISON`;
  - v2's effects exclude `WEATHER_RAIN`;
  - its policy names match `sim/gauntlet.mjs` registrations.
- [X] T018 Shadow and state plumbing in `sim/policy/expectimax2.mjs`, active only when `opts.v3State` is set:
  - `rootState` reads `battle.field.weather` and its duration, the volatiles (`leechseed`, `substitute.hp`, `taunt`, `encore`, `confusion`, `attract`, `aquaring`, `ingrain`, choice lock), and the side conditions (`spikes.layers`, `toxicspikes.layers`, `stealthrock`, `safeguard`, `wish`, reflect/lightscreen duration), following `sim/ai/adapter.mjs`;
  - `cloneState` / `cloneMon` copy them;
  - `shadowBattle` materialises them, including a new `field` shadow made with `Object.create(real.field)`;
  - `signature()` and the `damageTable` cache key include weather and every new field.
- [X] T019 [P] Write `sim/test/expectimax2_v3_state.test.mjs`:
  - setting weather, Leech Seed, a substitute, Taunt, Spikes and Safeguard on a `leagueBattle` fixture through Showdown APIs (`field.setWeather`, `addVolatile`, `addSideCondition`) round-trips into the v3 state and the shadow;
  - the shadow AI's choice equals the live AI's choice in a weather position (positive control: a position where weather changes the AI's choice).
  - If the Showdown setters don't work on fixtures, record it and build the positions by playing moves instead.
- [X] T020 Checkpoint: `node --test sim/test` (golden v1/v2 unchanged) and `uv run pytest -q tests/unit`. Record the output and its hours in the running total, then commit and push.

**Checkpoint**: classification, item filter, adopted flag, v3 scaffold and state are ready. User stories can start.

---

## Phase 3: User Story 1 — Status moves are offered and tested (Priority: P1) 🎯 MVP

**Goal**: each member's offered status moves are tested with a player that can use them, and adopted only when they are significantly better near the clear threshold.

**Independent Test**: optimize B4 in `reference` mode. `candidate_tests` contains Toxic/recovery alternatives for Milotic and Blissey, each played by expectimax2-v3 with paired statistics. Excluded moves carry their reasons.

### Player mechanics for status moves (v3, behind flags; each with a decomp-cited unit test in `sim/test/expectimax2_v3_mechanics.test.mjs`)

- [X] T021 [US1] Weather setting in `sim/policy/expectimax2.mjs`:
  - Rain Dance, Sunny Day, Sandstorm and Hail set `S.weather` for 5 turns, or 8 with the matching rock (ES 0136/0137/0115/0164, effect_param 3);
  - weather expires at end of turn (BCP:1113-1212);
  - Sand Stream and the other weather abilities apply on switch-in;
  - `damageTable` uses the state's weather;
  - Thunder and Blizzard accuracy follow the weather (BCP:2915, 3025-3029);
  - Moonlight, Morning Sun and Synthesis heal 1/2, 2/3 or 1/4 by weather (BS:5966-5978), fixing the v2 model bug **only under v3 flags**.

  Tests check each turn count and heal fraction against the cited lines.
- [X] T022 [US1] Leech Seed: Grass types are immune; Substitute blocks it; it drains 1/8 at end of turn to the seeder's active (BCP:1378-1392); it clears on switch (BL:2055-2076).
- [X] T023 [US1] Substitute:
  - costs ¼ max HP and fails at or below that (BS:5211-5226);
  - damage goes to the substitute's HP, and the outcome buckets include "breaks the substitute";
  - it blocks status, stat drops and Leech Seed (BS:9173);
  - read recoil/drain on hitting a substitute from the decomp and record it.
- [X] T024 [US1] Wish (heals ½ of the recipient's max HP at the end of the next turn, BCP:1085-1110), Aqua Ring and Ingrain (1/16, BCP:1311-1345; Ingrain also removes our switch actions), Safeguard (5 turns; blocks major status and confusion, BS:5754-5766), Endure (shares the Protect counter, BS:5149-5160; survives at 1 HP, BCP:3387-3403).
- [X] T025 [US1] Taunt (blocks status moves, BCP:2558; the turn count read from BS TryTaunt and recorded), Encore (BS:4725, BCP:1591-1616; our own lock is honoured in `playerMoveActs` and at ply 2), confusion from Confuse Ray, Swagger and Flatter (50% self-hit at 40 power, typeless, BCP:2617-2668; Swagger +2 Atk, Flatter +1 SpA), Attract (gender check BS:5727; 50% immobilised, BCP:2669). Measure and record the added decision time per chance node.
- [X] T026 [US1] Hazards in `doSwitch`: Spikes (1/8, 1/6, 1/4, BS:5388-5450), Stealth Rock (scaled by Rock-type effectiveness, BS:8302-8335), Toxic Spikes (BS:7592-7650; absorbed by Poison types). The leaf hazard term per remaining foe switch-in is behind flag `leafHazards`.
- [X] T027 [US1] Baton Pass: detect the mid-turn switch request (find Showdown's field for it and record it), choose the target, and pass boosts, substitute and volatiles (BL:2055-2110 `SYSCTL_BATON_PASS`) without zeroing them in `doSwitch`.
- [X] T028 [US1] Residual-projection leaf behind flag `leafResidual`: per active, the per-turn HP drift from tox n/16, psn/brn 1/8, Leech Seed ±1/8, weather 1/16, Leftovers/Black Sludge, Aqua Ring/Ingrain and a pending Wish, projected over H turns (option `leafHorizon`). Also add state-dependent status penalties behind `leafStatusState`. Both are off in `V3_REF_OPTS` (the reference relies on search, not projection).
- [X] T028b [US1] Speed probe: 20 gauntlets each of `expectimax2-v3` (current `V3_OPTS`) and `expectimax2-v3-ref` on `tests/fixtures/policy_benchmark_team.json`. Record gauntlets/s and ms per decision against v2's measured 37-49 ms. T031 uses these numbers; T063 records the final ones and logs any change to the round sizes.
- [X] T029 [US1] SC-008 positions for status categories in `sim/test/expectimax2_v3_positions.test.mjs`, built with `sim/test/ai_fixtures.mjs` `leagueBattle`. For each of weather, Leech Seed, Substitute, Toxic stall, a sleep move, Thunder Wave, Wish/Recover at low HP, Taunt, hazards and Baton Pass:
  - a position where `expectimax2-v3-ref` chooses the move and v2 doesn't;
  - a matching position where the move doesn't help and v3-ref doesn't choose it.

  Record any category where no such position can be found as a finding, not a pass.

### Optimizer: alternatives stage (reference mode)

- [X] T030 [US1] In `src/platsim/optimizer/candidates.py` `member_candidates`:
  - record `excluded = {move: reason}` for every legal move whose `move_class` is not offered (FR-002/003);
  - record `legal_status`, the offered status moves sorted;
  - a status move is offered only if `move_classes.modelled(policy)` (T017) contains its effect. Otherwise it goes in `excluded` as `"not offered: not modelled by <policy>"` (spec FR-001, analysis U2);
  - remove `setup_moveset` and its uses (the alternatives stage replaces it), and update the tests that reference it (`tests/unit/test_optimizer_candidates.py` and any others found by `grep -rn setup_moveset tests/`);
  - extend `summary()` with `excluded`, `legal_status` and the alternative count.
- [X] T031 [US1] Create `src/platsim/optimizer/alternatives.py`:
  - `generate(member_spec, mc, led, team, required_hms)` yields `Alternative`s, deterministic and sorted:
    - the current set with its weakest attack, its second-weakest attack, or both, replaced by offered status moves from `mc.legal_status` (user 2026-10-15; weakest by `mc.scores`, ties by slot);
    - **structured** 3-4-status sets (spec FR-005, research R5.1): for every choice of 3 or 4 categories the member can fill (inflict-status, protection, recovery, Leech Seed, self-boost, screen), each category's best move under the deterministic per-category order, plus the best attack in the 4th slot of a 3-status set.

    Items are added in T040 (US2).
  - Record the measured N (alternatives per member and per team) for B1-B5 in `validation-log.md`, before any reference run. With the v3 throughput from T028b, compute the round size r for the reference teams B4, B5 and B3 from research R5. If r = 25 doesn't fit a team's 10 h share, stop and ask the user.
  - Every alternative is made buildable with `resources.repair` (copies), never skipped silently. An unbuildable one is recorded with the refusal reason.
  - The moves under test go into `adopted` for the duration of the test (research R6).
- [X] T032 [US1] In `src/platsim/optimizer/alternatives.py`, `run_stage(...)`:
  - levels are the current team's first failing neighbour from the bisection (`fail_u` from `LevelSearch`), or the bisection levels when there is none; record which;
  - per member in slot order, **successive halving** over all of that member's alternatives with the expectimax2-v3 player: rounds r/2r/4r/8r paired runs, with r from the request (`alternatives_round` option, chosen per research R5; record it), recording every seed's outcome for every alternative so prefilters can be compared offline (seeds `derive_seed(f"{seed}|alternatives", i, 0)`, the same seeds for every alternative), keeping the top third each round. Reuse `optimizer/screen.py` `successive_halving` if it fits; otherwise write it in `alternatives.py` and record why. Record each alternative's `round_reached` and counts;
  - the finalists (the last round's top 3) are each played against the current team for `preset.ability_screen` paired runs, compared with McNemar exact (`stats.mcnemar_exact`) and Holm-corrected within the member;
  - the best significant winner is confirmed on a fresh block (`f"{seed}|alternatives-confirm"`) and adopted if it is confirmed;
  - `adopted` is set on the spec;
  - state is checkpointed after every alternative under `state.data["stages"]["level_search"]["alternatives"]`;
  - `mode="reference"` puts every alternative through the successive halving (spec FR-017 step 1).
- [X] T033 [US1] Wire the stage into `src/platsim/optimizer/run.py` in place of the setup check (~:485-519):
  - add `candidates: str = "reference"` to `OptimizeRequest` in `src/platsim/optimizer/api.py`;
  - put the mode in `job_fingerprint`;
  - `STATE_VERSION = 4`;
  - add `alternatives` to `_optimizer_provenance` `policy_per_stage` and `seeds`;
  - keep the "adopted set must still pass at the bisection levels" re-check.
- [X] T034 [US1] Add `--candidates reference|prefilter` to `src/platsim/cli.py` optimize, and the optional `candidates` field to the web optimize request in `src/platsim/web/` (no UI control). Add `alternatives` to `src/platsim/web/eta.py` `STAGE_ORDER`, with `setup_check` mapped to it for old state files.
- [X] T035 [P] [US1] Write `tests/unit/test_alternatives.py`:
  - generation is deterministic across two processes (`PYTHONHASHSEED` differs) and sorted;
  - Screech and Seismic Toss never appear (SC-007; a member that learns both, e.g. found via `legal_moves`);
  - an alternative needing an exhausted 1-copy TM (Toxic TM06 taken by an earlier member) is repaired or recorded with its reason;
  - Holm correction is applied, with a hand-computed example;
  - a member that learns Toxic, Protect, Recover and Leech Seed (B4 Roserade or Milotic) gets at least one `structured` alternative;
  - a legal unmodelled move (e.g. Trick or Haze on a member that learns it) is not offered and appears in `excluded` as "not offered: not modelled";
  - a moved-under-test status move survives `place_required_hms` on B3.
- [X] T036 [US1] Integration test `tests/integration/test_alternatives_quick.py`, marked slow like `test_policy_strength`: a **smoke test, not a reference**. It is a `--budget quick` B4 run with `--candidates reference`, the test-only options `alternatives_round=5` and `alternatives_members=2` (two members only; added to `OptimizeRequest` and recorded in provenance), and its time recorded. It is outside the 100 h budget. `candidate_tests` lists every generated alternative, `excluded_moves` has reasons, the validator passes, and the result is byte-identical on a second run with the same seed (SC-005). Commit and push.

**Checkpoint**: US1 works end to end with the reference player settings (production v3 settings come in Phase 8).

---

## Phase 4: User Story 2 — Every useful held item is considered (Priority: P1)

**Goal**: item candidates cover every obtainable item that does something in battle, paired with the moves they need, with copy limits respected.

**Independent Test**: for B4 Bronzong with Light Screen, its candidates include Light Clay. Choice Specs is given to only one B1 member. No post-Champion item is offered under default options.

- [X] T037 [US2] Pairing rules in `src/platsim/optimizer/item_classes.py` (research R2.5):
  - derive rock ↔ weather pairs by scanning effect scripts for `HOLD_EFFECT_*`;
  - Light Clay ↔ Reflect/Light Screen from its referencing functions;
  - Chesto/Lum ↔ Rest from "the status Rest puts on the user" ∩ "the status the berry cures" (BL:4608, 4662);
  - Big Root ↔ drain/Leech Seed/Ingrain/Aqua Ring subscripts;
  - Power Herb ↔ the charge effects;
  - Black Sludge for Poison types only;
  - Choice Specs for all-attack sets only;
  - resist berries for members weak to a type carried by some League move (`trainers.json`);
  - drawback items only with Trick/Switcheroo.

  Export `items_for(member, moveset, team, led) -> list[item key]`.
- [X] T038 [US2] Type-boost tie rule (FR-011) in `src/platsim/optimizer/item_classes.py`: more copies, then higher effect_param, then classic `STRENGTHEN_*` before `ARCEUS_*`, then item key. Export it as the constant `ITEM_TIE_RULE` (the text in contracts/candidate-report.md).
- [X] T039 [US2] (Done with one recorded deviation: the greedy screen keeps the old 3-item `held_item_candidates`, because greedy can't value the new items; every new item reaches the strong player through the alternatives stage instead, which is what FR-007 asks. See validation-log T037-T045.) Filter `item_classes.items_for` through `move_classes.modelled(policy)` (T017): an item whose hold effect isn't modelled is not offered and goes in `excluded` as "not offered: not modelled by <policy>" (spec FR-009). Then replace `held_item_candidates` in `src/platsim/optimizer/candidates.py` with `item_classes.items_for`, keeping the old function name as a thin wrapper for callers (`resources.repair`). Record the new per-moveset item count for B1 in `validation-log.md`.
- [X] T040 [US2] Extend `alternatives.generate` (`src/platsim/optimizer/alternatives.py`) with `status+item` (each status alternative × its paired items) and `item` (item-only swaps on the current set, from `items_for`). Team-wide copies go through `resources.repair`.
- [X] T041 [US2] Player item mechanics in `sim/policy/expectimax2.mjs` (v3 flags), each with a decomp-cited test in `sim/test/expectimax2_v3_mechanics.test.mjs`:
  - Light Clay at 8 turns (BS:4229, 4272), replacing the hard 5 at ~:778-779;
  - Chesto/Lum and the status berries, including both trigger paths at BL:4608/4998 and 4662/5052;
  - type-resist berries halving the matching super-effective hit once, and Chilan for Normal (`subscript_type_resist_berry.s`);
  - Shell Bell, damage dealt ÷ 8 (BCP:4734-4745);
  - Black Sludge (BL:4939-4950);
  - Zoom Lens (BCP:2963-2965);
  - Quick Claw at 1/5 (BL:1278-1284, 1344), with an order branch in `resolveTurn`;
  - King's Rock/Razor Fang 10% flinch on flagged moves when moving first (BCP:4632-4645), with flinch added to the model;
  - the choice lock (BCP:3923, 4492);
  - Big Root, Power Herb.

  Add positive-control tests for the items already modelled through the damage port: Wise Glasses, Expert Belt, Scope Lens/Razor Claw, Wide Lens.
- [X] T042 [US2] Update `MODELLED` in `sim/policy/expectimax2.mjs` for v3/v3-ref with every effect and item added in T021–T028 and T041. Add a test that every **offered** item's `HOLD_EFFECT` is in the policy's `MODELLED` (true by construction after T039), and that every obtainable item not offered for that reason is listed in `excluded`. Record the list of skipped items in `validation-log.md`.
- [X] T043 [US2] SC-008 positions for items in `sim/test/expectimax2_v3_positions.test.mjs`: Light Clay with screens, a rock with weather, Chesto + Rest, a resist berry, the Choice Specs lock and Quick Claw. Each has a helps/doesn't-help pair, as in T029.
- [X] T044 [US2] Mechanics-divergence pass (research R8). For each offered status effect and hold effect, compare decomp and Showdown gen4 behaviour (`pokemon-showdown/data/mods/gen4/*`), starting with Encore (decomp 3–7 turns, BS:4742, vs Showdown `random(4,9)`). Record each as `corrected` or `accepted` with its impact in `data/divergences.json` through the existing divergence tooling (`src/platsim/divergence/`). Extend the divergence test so every new entry is checked.
- [X] T045 [P] [US2] Write `tests/unit/test_item_pairings.py`:
  - Light Clay is offered with Reflect and not without;
  - Damp Rock with Rain Dance only;
  - Chesto with Rest only;
  - Black Sludge to Roserade and not to Milotic;
  - Choice Specs only with all-attack sets, and given to only one member team-wide (copy 1);
  - the tie rule picks Mystic Water over Splash Plate when both have equal copies (set up through `allow_post_game_items`) and picks the unlimited item otherwise;
  - no post-Champion or never item is offered under default options.
- [X] T046 [US2] Integration smoke test (outside the budget): a quick B1 run with `--candidates reference`, `alternatives_round=5` and `alternatives_members=2` has `item` and `status+item` alternatives in `candidate_tests`, and the validator passes. Commit and push.

**Checkpoint**: US1 and US2 both work.

---

## Phase 5: User Story 3 — The report explains what was offered, tested and chosen (Priority: P2)

**Goal**: every offered alternative appears in the result with its outcome, and unmodelled moves and items are flagged.

**Independent Test**: any quick run's `result.json` meets contracts/candidate-report.md, and the "Candidates" sheet matches it row for row.

- [X] T047 [US3] In `src/platsim/optimizer/run.py` `_report` / `_optimizer_provenance`, write into `provenance.optimizer`:
  - `candidate_mode`, `item_tie_rule`, `assumptions` (friendship 255, IVs 15, Hidden Power from `default_ivs`, computed and not typed in);
  - `excluded_moves`;
  - `candidate_tests`, with every offered alternative exactly once, untested ones as `"not tested: <reason>"`, and `not_modelled` from `move_classes.not_modelled(policy, …)`.
- [X] T048 [US3] Add the warning in `src/platsim/optimizer/run.py` (or wherever `rep.warnings` is filled for optimize) for final-team moves and items the policy doesn't model, using the contract wording.
- [X] T049 [US3] Add the "Candidates" sheet after "Resources" in `src/platsim/report/xlsx.py` (update `SHEET_NAMES`). Amend `specs/001-champion-team-optimizer/contracts/spreadsheet.md` and `cli.md`/`http-api.md` with a pointer to `specs/007-status-moves-items/contracts/candidate-report.md`.
- [X] T050 [P] [US3] Write `tests/unit/test_reports.py` additions: the sheet tuple includes "Candidates"; the rows equal `candidate_tests`; `report --rerender` carries `candidate_tests`; a result with an unmodelled move gets exactly one warning per member and move.
- [X] T051 [US3] Web: in `src/platsim/web/result_view.py`, add a per-member "offered N / tested M / adopted K" line linking to the report files, with warnings shown as today. Run `uv run pytest -q -m browser tests/browser/` (SC-003 of 002 still fits 1080p). Commit and push.

---

## Phase 6: User Story 5 — Missing item sources are recorded (Priority: P2)

**Goal**: the Route 221, Pastoria and Amity Square sources are in the ledger, extracted from the decomp.

**Independent Test**: `uv run platsim explain item:focus_sash` shows the Route 221 house, 1 copy, before the Champion. The counts are 74 unlimited, 40 finite and 44 unavailable.

- [X] T052 [P] [US5] Write `tests/integration/test_availability_controls.py` additions first, in the existing `_line(path, line, text)` style:
  - Route 221 `:39` gives Black Belt, Expert Belt and Focus Sash entries, **quantity 1 each** with their own `once_flag`, and detail naming `FLAG_DAILY_RECEIVED_ROUTE_221_HOUSE_REWARD` and the daily random level. `item_copies` is 1 for each (spec FR-018, user 2026-10-14). Negative control: the News Press daily Poké Ball (no level check) stays UNLIMITED;
  - Pastoria gives exactly the 17 item ids [id(Occa), id(Occa)+17), and **Liechi stays 0** (negative control);
  - the Amity pickup berry set equals the `sBerryAndAccessoryManOptions` `ITEM_*` set, with no `ACCESSORY_*`;
  - the Gift Man detail says 5 per gift;
  - a sentinel lists the give sites whose resolved items change: Route 221, Pastoria, Amity ×2, News Press, Flower Shop, Route 208, and no others;
  - update `:522` (66 → 74), `:525` (37 → 40) and `:526` (55 → 44).

  Confirm these fail before T053.
- [X] T053 [US5] Make `_const_dataflow` in `src/platsim/availability/sources.py` (~:914-942) return-aware: `Return` carries the callee's state to the call's fall-through, using a call stack in the work item. Add the detail text for Route 221's level condition (refs :15-21, `system_vars.c:267-271`). Add the rule: a daily gift whose guarded path contains `GetDailyRandomLevel` counts each possible item once (quantity 1, a per-item `once_flag`), instead of daily → UNLIMITED. Detect it from the script command, never the map name.
- [X] T054 [US5] Support the `GetRandom V, N` + `AddVar V, ITEM_X` idiom in `src/platsim/availability/sources.py`, giving the item range by id order of `pokeplatinum/generated/items.txt`.
- [X] T055 [US5] Resolve save vars whose every write is a literal `ITEM_*` (`VAR_FOLLOWER_MON_PICKUP_ITEM_ID`) in `src/platsim/availability/sources.py`. Add a "repeatable, no flag" rule giving UNLIMITED, with the detail citing the step counter (`field_control.c:763`). Put Amity's partner species in `requires_any`, parsed from `scripts_amity_square.s:726-748`.
- [X] T056 [US5] Parse `sBerryAndAccessoryManOptions` (`pokeplatinum/src/scrcmd_amity_square.c:148-165`, `ITEM_*` tokens only), following the `frontier_exchange_lists` C-array pattern, and bind it to the Gift Man's `AddItem` (`scripts_amity_square.s:940`) in `src/platsim/availability/sources.py`.
- [X] T057 [US5] Regenerate with `uv run platsim extract`, then `uv run platsim extract --check`. Run `uv run pytest -q tests/integration/test_availability_controls.py tests/unit/test_validator.py tests/integration/test_extract.py`. Add a validator test in which a team holding Focus Sash has no `ITEM_UNAVAILABLE`, and Choice Band is still refused. Record the new counts. Commit and push.
- [X] T058 [P] [US5] Regenerate `held_items.md` (repo root, untracked analysis note) with the T009/T037 filter and the new sources, or mark it as superseded in its header. Record which was done.

---

## Phase 7: User Story 4 — Variable-power attacks are considered (Priority: P3)

**Goal**: Return, Hidden Power, Low Kick and the other variable-power attacks compete with ordinary attacks, at their decomp-computed power.

**Independent Test**: for a member that learns Return, the candidate pool scores Return at power 102. Low Kick's value against Hippowdon uses power 120.

- [X] T059 [P] [US4] Extract species weight in hectograms in `src/platsim/decomp/species.py` from `pokeplatinum/res/pokemon/<sp>/data.json` `pokedex_data.weight_pounds`, using the conversion in `pokeplatinum/tools/dataproc/src/speciesproc.c:696-751`. Positive controls: Garchomp = 950, Mr. Mime = 545 (cross-check only). Regenerate if this changes `data/generated/species.json`.
- [X] T060 [US4] Extend `league_opponents()` in `src/platsim/optimizer/candidates.py` with each foe's level and stats (from `trainers.json` and base stats with the trainer IVs/EVs the battle uses) and weight. Add `variable_power(member variant, move, foe)` implementing the R3 table, sharing formulas with `sim/policy/expectimax2.mjs` `variablePower`:
  - Return 102 (friendship 255);
  - Hidden Power type and power from the variant's IVs (`default_ivs` or `fixed_mon["ivs"]`);
  - Low Kick / Grass Knot from `include/data/battle/weight_to_power.h`;
  - Gyro Ball with stats at the member's ref level;
  - Wring Out / Crush Grip 121;
  - Magnitude 71;
  - Punishment 60.
- [X] T061 [US4] In `src/platsim/optimizer/candidates.py`, `is_attack` accepts `variable_attack` moves. `move_value` uses `variable_power` per foe, and the Hidden Power type comes from the IVs.
- [X] T062 [P] [US4] Write `tests/unit/test_variable_power.py`:
  - Return = 102;
  - default Hidden Power = Dark 70;
  - an NPC-trade variant with fixed IVs gets its own Hidden Power;
  - Low Kick = 120 vs Hippowdon and 40 vs Roserade;
  - Gyro Ball is capped at 150;
  - Frustration, Seismic Toss, Flail and Natural Gift are not offered (SC-007), and their reasons are recorded;
  - a member's pool on B1 changes only by adding variable-power attacks (record the before/after pools).

  Commit and push.

---

## Phase 8: Reference, prefilter and acceptance (Principle VI; FR-017, FR-019; cross-cutting)

- [X] T063 Player reference vs cheap variants (T063 and T064 together get 15 h of the 100 h budget), on `tests/fixtures/policy_benchmark_team.json` and as many of B4, B5, B1 as fit the budget, in that order. Run paired gauntlets (McNemar, at least 400 per team, seeds `v3-accept|i`) of `expectimax2-v3-ref` (T015 `V3_REF_OPTS`: all mechanics, no roll-bucket compression, K_ROOT 32, K_PLY2 8, all switches, ply-2 switches) against each cheap candidate:
  - today's knobs + `leafResidual`;
  - plus `leafStatusState`;
  - plus `leafHazards`;
  - re-fitted leaf weights. Fit them by logistic regression on v3-ref-played games, as in the v2 header :20-26. Put the fitting script in `sim/policy/fit/` or the scratchpad, and record which.

  Also try depth 3 or rollouts as a second reference if time allows, and record it. Record per-decision time and gauntlets/s for each. The production `V3_OPTS` = the cheapest candidate not significantly worse than the reference on any team. Record the table and the choice in `validation-log.md`. Add its wall-clock hours to the running total of one-time hours in `validation-log.md` (budget: 100 h for every one-time run, spec FR-017 table); stop and ask the user before any run would take the total over 100 h.
- [X] T064 Acceptance of v3 against v2 and against greedy-v1 using the `tests/integration/test_policy_strength.py` pattern (add v3 to it). Run the SC-008 positions with the production v3. A position that passes with v3-ref but fails with v3 is a finding, recorded with its effect on the T063 choice. Add its wall-clock hours to the running total of one-time hours in `validation-log.md` (budget: 100 h for every one-time run, spec FR-017 table); stop and ask the user before any run would take the total over 100 h.
- [X] T065 Switch the defaults to `expectimax2-v3`: `src/platsim/optimizer/run.py` `POLICY`, `src/platsim/optimizer/levels.py` `POLICY`, `src/platsim/evaluate.py` `DEFAULT_PLAYER_POLICY`, the `src/platsim/cli.py` default. The golden v1/v2 test still passes. Commit and push.
- [ ] T066 Generation-rule and item-relevance references (spec FR-005, FR-009, FR-019, Complexity Tracking; 8 h of the 100 h budget).
  - **Weakest-two-slots rule:** for B4 Milotic, also run all-slot 1-2 replacements through the same reference; the rule is accepted if no set outside it wins significantly.
  - **Generation rule:** for B4 Milotic and B4 Roserade, run the alternatives stage again with **full 3-4-slot generation** (every 3- and 4-slot replacement by offered status moves) as well, at the same levels and seeds, through the same two-level reference. The rule is accepted if no full-generation set beats the best structured or 1-2-slot set significantly. Otherwise widen the rule through `/speckit-converge`.
  - **Item relevance:** for B4 Milotic and B1 Gardevoir, also generate alternatives offering **every** offered (modelled, obtainable) item with each status set, not only the paired items, through the same reference. The pairing rule is accepted if no unpaired item set wins significantly; otherwise widen it through `/speckit-converge`.
  - Record both comparisons with their run times. Add its wall-clock hours to the running total of one-time hours in `validation-log.md` (budget: 100 h for every one-time run, spec FR-017 table); stop and ask the user before any run would take the total over 100 h.
- [ ] T066b Screening check (Constitution VI; 3 h of the budget). For B4 Milotic, take a fixed sample of about 40 alternatives: every finalist the reference screen picked, plus others drawn with seed `sh-check`. Give each the full 200-run paired test against the current team. The screening is **verified** if no non-finalist beats the finalists significantly. Otherwise label it unverified in plan Complexity Tracking and `validation-log.md`, with the evidence. Add its wall-clock hours to the running total of one-time hours in `validation-log.md` (budget: 100 h for every one-time run, spec FR-017 table); stop and ask the user before any run would take the total over 100 h.
- [ ] T067 Reference benchmark (31 h of the budget): standard runs of **B4, B5 and B3** with `--candidates reference`, seed `bench-007`, `--out runs/bench-007-reference/<B>`, in the background, one team at a time in that order, with each team's round size from T031. Every seed's outcome for every alternative is kept for offline prefilter comparison (T068). Add its wall-clock hours to the running total of one-time hours in `validation-log.md` (budget: 100 h for every one-time run, spec FR-017 table); stop and ask the user before any run would take the total over 100 h.
  - Record per-stage timings, final levels, clear rate and CI, and adopted alternatives.
  - **SC-002** (for these three teams here; B1 and B2 in T069): evaluate the baseline final team and the new final team with the same player version (production v3) and seeds (`platsim evaluate --runs <confirm_min> --seed sc002-<B>`) at their own reported start levels. Apply the SC-002 test: McNemar on clear rate, and expected average final level against the combined CI half-width.
  - **SC-001:** a table of each in-scope category, with which benchmark team and member offered it and how far it got (round reached, tested, adopted).
  - **SC-004:** assert that the validator passes on every final team, including B3's required HMs.
- [ ] T068 Implement `mode="prefilter"` in `src/platsim/optimizer/alternatives.py` with at least two variants:
  - (a) smaller successive-halving rounds than the reference (e.g. 25/50/100/200), then the same finalist test;
  - (b) a static pre-score (`move_value`/variable power for attacks plus category priors, computed from the reference results of T067 and recorded) keeping the top N per member, with N chosen from T067's adoption ranks.

  Both are deterministic and seeded. Variant (a)'s seeds are a prefix of the reference's seeds, so it can be scored offline.
  - **Offline comparison, no new battles:** for each variant, on B4, B5 and B3, replay its decisions from T067's recorded per-seed outcomes. Record whether it keeps the reference's adopted alternative for every member, and its estimated alternatives-stage time from the run counts and the T028b/T063 speed.
- [ ] T069 Prefilter acceptance (22 h of the budget, plus 2 h of SC-002 evaluations).
  - Pick the cheapest variant that keeps every reference-adopted alternative in T068's offline comparison and whose estimated time is at most 2.0× baseline.
  - Run **only that variant** live on B1-B5 (seed `bench-007`).
  - Compare with T067 (B4, B5, B3: adopted sets, final levels, clear rate) and with the T005 baseline on all five teams (wall time; SC-002 test from T067).
  - Accept it if it is not worse than the reference on B4, B5 and B3, not worse than the baseline on any team, and takes **at most 2.0×** the baseline time on every team (SC-006).
  - If it fails, record why and ask the user before a second live run (budget). Add its wall-clock hours to the running total of one-time hours in `validation-log.md` (budget: 100 h for every one-time run, spec FR-017 table); stop and ask the user before any run would take the total over 100 h. Make it the `--candidates` default in `src/platsim/optimizer/api.py` and `src/platsim/cli.py`. If none qualifies, keep `reference` as the default and record why. Record the table in `validation-log.md`. Commit and push.

---

## Phase 9: Polish and cross-cutting

- [X] T070 [P] Update `README.md`: `--candidates`, `expectimax2-v3`, the status-move and item behaviour, the friendship assumption, the new ledger sources, and the Pickup ability as a known gap.
- [X] T071 [P] Update the docstrings in `src/platsim/optimizer/candidates.py` (module doc steps 2, 5 and 6), `src/platsim/optimizer/run.py` (stage list: alternatives replaces the setup check) and `src/platsim/optimizer/resources.py` (slot tiers).
- [ ] T072 Full Python suite `uv run pytest -q` and `node --test sim/test`. Record the output against the T002 baseline, and explain every changed count. Add its hours to the running total.
- [ ] T073 SC-005: re-run one smoke request (B4, `--budget quick`, both modes, `alternatives_round=5`, `alternatives_members=2`) with the same seed and confirm `result.json` is byte-identical. Record it.
- [ ] T074 Write the final summary in `validation-log.md` and `RUN-STATE.md`: SC-001 to SC-009 each with its evidence or "not met" and why; adopted status moves and items per benchmark team; what v3 still doesn't model. Then hand over for the user's hands-on testing (restart `uv run platsim serve` from this branch on request). Don't merge.

---

## Dependencies & execution order

- **Phase 1** → **Phase 2** → user stories. T005 (baseline benchmark) runs in the background during Phase 2–7 work, but must finish before T067/T069 and must not overlap other heavy runs.
- **US1 (Phase 3)** needs T007, T012–T019.
- **US2 (Phase 4)** needs T009 and US1's T031–T033 (the alternatives stage it extends). Its player tasks T041–T043 need T018.
- **US3 (Phase 5)** needs T032–T033. It can start once US1 is done, in parallel with US2.
- **US5 (Phase 6)** is independent of US1–US4 and can run any time after Phase 1. It changes item counts, so finish it before T067.
- **US4 (Phase 7)** needs T007 (classification). It is independent of the player work.
- **Phase 8** needs US1, US2 and US4 complete. T063 → T064 → T065 → T066/T067 → T066b → T068 → T069. T028b (Phase 3) must come before T031's round-size calculation.
- **Phase 9** comes last.

## Parallel opportunities

- Phase 2: T008 ∥ T010 ∥ T014 (tests in different files); T015–T019 (sim) ∥ T007–T014 (Python).
- After Phase 2: US5 (T052–T058) ∥ US4 (T059–T062) ∥ the US1 player mechanics (T021–T028).
- US2: T045 ∥ T041–T043.
- Phase 9: T070 ∥ T071.

## Implementation strategy

- **MVP = Phase 1 + 2 + US1** (status moves tested by v3-ref in reference mode). It is already useful: the user can see whether status moves get adopted.
- Then US2 (items), US3 (reporting), US5 (ledger) and US4 (variable power).
- Then Phase 8 makes it fast: the production player settings and the prefilter, each accepted against its reference.
- Hand over only after Phase 9.
