# Validation log: feature 022 adaptive sampling in the optimizer's confirmation stage

Branch `022-confirm-adaptive-sampling` from `main` 93ac7c8. All times US Eastern. Measurements run alone on the machine.
Raw evidence under `runs/022-evidence/` (local, gitignored); small files copied to `specs/022-confirm-adaptive-sampling/evidence/`.

## T001 Setup (2026-11-04 11:17 AM EST)

Before-hashes:

```
sha256:299b1b556a0066a2d004e6026d9e2c12fd7bb47fa04c6446e34c24565301b59b sha256:f9128d6b68f493ce5d1beeb3d4f15053e5b6936e411b9cfbce5ef8215e6748c8
```

`sim_code_hash` must be unchanged at T021 (FR-011).

## T002-T009, T013-T014 Code and tests (12:26 PM EST)

- `src/platsim/optimizer/pairing.py` (new): `paired_outcomes`, full runs by run index, Cynthia-only runs by ordinal, surplus excluded (R4).
- `src/platsim/sampling.py`: `run_adaptive(..., borderline_threshold, borderline_max_runs)`, the borderline loop by the extension rule
  (the needed half-width is the estimate's distance from the threshold), consumed in order, stopping at the first non-straddling run;
  `AdaptiveRuns.borderline_extended`. `src/platsim/evaluate.py`: the 021 guard removed, the borderline arguments passed through,
  `evaluate_team(..., adaptive_runs=)` for a precomputed run. **Correction to 021 found by T010:** the discard counts depend on the
  chunk size (16 workers give a 128-run chunk, 3 workers a 64-run chunk), so `discarded` was a worker-count-dependent field in
  result.json; it is now logged only (`sampling_detail` and the xlsx row dropped; README's 021 block corrected).
- `src/platsim/optimizer/api.py`: `OptimizeRequest.sampling` (default full) and `.floor` (0.98) with validation; `run.py`: the
  fingerprint rule (only when non-default), `_confirm` on `evaluate_team(sampling, floor)` with the run mix in every attempt
  (`_run_mix`), the runner-up on the same method with `paired_outcomes` and `_comparison_record` (pairs, full and Cynthia-only pairs,
  excluded, p), confirmed from its own runs when better, `sampling_per_stage` in provenance; `cli.py`: `optimize --sampling`, `--floor`.
- Tests: `tests/unit/test_confirm_pairing.py` (pairing: neither / both / one switched, controls, the comparison record incl. the
  no-pairs case; the borderline extension on a scripted pool: seed 5 straddles at 200 and resolves with 389 Cynthia-only runs at 589
  total, chunk sizes 4 and 16 identical; the cap case), `tests/unit/test_optimizer_resume.py` (+2: fingerprint rule, CLI defaults and
  the floor usage error), `tests/integration/test_optimize_adaptive.py` (battle_sim).
- `uv run pytest -q tests/unit/test_reports.py tests/unit/test_sampling.py tests/unit/test_confirm_pairing.py tests/unit/test_optimizer_resume.py`: **49 passed**.

## T010 Integration test

First run 11:19:30 to 11:42:42 AM EST: **failed**, result.json differed between 16 and 3 workers at one byte: the `discarded` field (see
above). Rerun after the fix 11:53:03 AM to 12:16:27 PM EST: **1 passed in 1,404.1 s (23 min 24 s)**: byte-identical result.json across
worker counts, `sampling_per_stage.confirm == adaptive`, the confirm attempt with a switch run and Cynthia-only runs, the comparison's
pair counts consistent (`specs/022-confirm-adaptive-sampling/evidence/t010.log`).

## T011 Hand check (12:16:27 to 12:24:56 PM EST, alone, 8 workers)

`uv run platsim optimize infernape staraptor luxray garchomp gyarados gardevoir --budget quick --seed q022 --sampling adaptive --floor 0.9 --workers 8`
exit 0, 507.6 s (confirm 94.1 s). Three confirm attempts: at [54, 56, 56, 55, 56, 55] the switch came after 280 full runs (Lucian cost
runs; 220 Cynthia-only) and the checks failed; at [55, 57, 57, 56, 57, 56] switch 127 / 373, failed; at [56, 58, 58, 57, 58, 57] switch
35 / 465, passed (clear 0.876 [0.8476, 0.9054]). Runner-up at the same levels switched at 35 too: 500 pairs (35 full + 465
Cynthia-only), 0 excluded, winner-only 101 vs runner-up-only 51, p 6.1e-5, winner better. `sampling_per_stage`: level search and setup
check full, confirm adaptive, floor 0.9. Copies under `evidence/hand/`. Note: commits 1 and 2 of the task plan are one commit, since
the runner-up branch lives in the same files as the confirm wiring.

## T016-T017 Acceptance (first run 12:26:16 to 1:04:48 PM EST; rerun of blocks 1 and 3 1:07:25 to 1:26:39 PM EST; alone, 16 workers)

`scripts/acceptance.py` (four blocks; `--reuse` added for block 1). First run: blocks 2 and 4 passed; block 1 failed because the script
compared the final results at different levels (the full method bumped a level, the adaptive did not), and block 3 reported a
difference that was only dictionary key order in `provenance.optimizer.stages` (a resumed job reloads its stage records from the
checkpoint; semantically identical with sorted keys). **Fixes:** block 1 now judges containment on the first confirm attempt, which is
always at the level search's levels on both sides; `run.py` canonicalises the stage records (`_canonical`) so result.json is
byte-identical whether or not a job was resumed (a pre-existing artefact of every resumed job, fixed here). Rerun of blocks 1 and 3:
```
b2quick full: wall 355s confirm 98.7s clear 0.8860 [0.8551509101576845, 0.9109630990059973] not_qualified levels [54, 52, 54, 54, 54, 55] attempts 2 mix full/cyn 500/0 switch None
b2quick adaptive: wall 307s confirm 51.3s clear 0.8120 [0.7784653449469561, 0.8469792576892773] not_qualified levels [53, 51, 53, 53, 53, 54] attempts 1 mix full/cyn 189/311 switch 189
b2quick: same build True, same levels False, first attempt at [53, 51, 53, 53, 53, 54]: full 0.7760 [0.7374, 0.8104] borderline True vs adaptive 0.8120 [0.7785, 0.847] borderline False; contained both ways at equal levels False, final verdicts not_qualified/not_qualified, ratio confirm 1.9239766081871346, whole 1.16x; equal-levels exit 0; pass False
resume: killed True (during the confirmation attempt (checkpoint granularity: per attempt)); identical to the uninterrupted run: True
{"b2quick": false, "resume": true}
```
Blocks 2 and 4 (first run):
```
confirm b2main: full 0.9090 [0.8955988359412409, 0.9208330193826942] n 2000 qualified 131s | adaptive 0.9178 [0.9032993269685703, 0.9326246782952907] n 2000 qualified 56s | contained True agree True ratio 2.33x | mix full/cyn 281/1719 switch 281 ext {'full': 0, 'cynthia_only': 0} borderline_ext False
confirm b3: full 0.7490 [0.7353286210798616, 0.7621935761618671] n 4000 borderline 277s | adaptive 0.7490 [0.7353286210798616, 0.7621935761618671] n 4000 borderline 276s | contained True agree True ratio 1.00x | mix full/cyn 4000/0 switch None ext {'full': 2000, 'cynthia_only': 0} borderline_ext True
pairing: switch {'b2main': 853, 'b2branch': 361}; full pairs 361, Cynthia-only pairs 1147, excluded 984; counts on full pairs full [76, 32] vs adaptive [76, 32] exact True; all pairs adaptive {'a_only': 277, 'b_only': 101, 'p': 4.5742899598372007e-20, 'verdict': 'A'} vs full {'a_only': 393, 'b_only': 132, 'p': 4.0850544869018576e-31, 'verdict': 'A'}
```

**Block 2 (SC-002): PASS.** b2-main at the standard count: full 0.9090 [0.8956, 0.9208] qualified, 131 s; adaptive 0.9178 [0.9033, 0.9326]
qualified, 56 s: contained, agree, **2.33x**; switch after 281 full runs, 1,719 Cynthia-only. B3: both sides extended to 4,000 runs by
the borderline loop (full gauntlets on both, the floor never reached) and ended identical at 0.7490 borderline: **1.00x**.
**Block 3 (SC-003): PASS** after the key-order fix: killed during the confirmation attempt (checkpoint granularity per attempt), the
resumed run's result.json is byte-identical to the uninterrupted one.
**Block 4 (SC-004): PASS.** b2-main vs b2-branch: switch runs 853 and 361, so 361 full pairs, 1,147 Cynthia-only pairs, 984 excluded;
the McNemar counts on the full-kind pairs are identical under both methods (76 / 32); on all pairs adaptive 277 / 101 (p 4.6e-20,
winner better) vs full 393 / 132 (p 4.1e-31): the same verdict with fewer pairs.
**Block 1 (SC-001): FAIL by the clarified rule, with the cause recorded.** Same build (species, moves, items) on both sides. First
confirm attempt at [53, 51, 53, 53, 53, 54], quick count 500: full 0.7760 [0.7374, 0.8104] borderline (failed, bumped to
[54, 52, 54, 54, 54, 55], 0.8860, passed); adaptive 0.8120 [0.7785, 0.8470] not borderline (passed at the lower levels; switch after
189 full runs, 311 Cynthia-only). Each estimate lies just outside the other's interval (0.8120 vs 0.8104; 0.7760 vs 0.7785), so
containment at equal levels fails by 0.0016 and 0.0025. The 010 equal-levels comparison (018's script, 500 paired runs, reference
player v2, both teams at the adaptive result's levels): identical team, 0 discordant pairs, indistinguishable, mean final level
53.34 on both sides. Reading: the two estimates differ by 3.6 points on 311 Cynthia-only battles against 311 full gauntlets (about 1.1
standard errors at n 500); the quick count cannot resolve a team this close to the threshold, and the adaptive run settled one level
lower. Wall: confirm stage 98.7 s vs 51.3 s (1.92x); whole run 355 s vs 307 s (1.16x). Note: the quick preset never qualifies, so the
flip changes a quick result's levels, not a qualification.
