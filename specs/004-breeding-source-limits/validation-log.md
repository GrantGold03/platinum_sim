# Validation log: 004

## T001 Baseline (2026-10-13)

- HEAD: `b01203c151e3ebbe2544ad1172bc0c01a6fb8ce2` (branch 004-breeding-source-limits, no source edits yet)
- `uv run pytest -q tests/unit/test_validator.py tests/unit/test_source_preference.py tests/unit/test_source_text.py tests/unit/test_legality_options.py`:
  `83 passed in 88.16s`
- Hashes:
```
5e4cdab091d78255de55271278e64de9f153f236fcc4574153cb5b32ef401524  allowed_pokemon.md
4bcd3bb1fdc1dadb7c1f8cb2303e0beb7df02ba38338173fc9f81fe74362376d  tests/fixtures/web_final_defaults/job.json
308efe3f5054b45177dc2529c7de2ab6cdd6d5c4e8e728e743144d4b328c542a  tests/fixtures/web_final_defaults/README.md
8aef11f4ccb7639b55dcedd9c37d2aff47e0d966c52633768510e9bda6b1efd0  tests/fixtures/web_final_defaults/result.csv
ade487fb6ff4345910e40935449e49e7b288c51750259040249af30ccc64277d  tests/fixtures/web_final_defaults/result.json
78be928d6cc26625817cd102be4ccf8e4fd59d909f99ede94965977ff0250aed  tests/fixtures/web_final_defaults/result.xlsx
e2b11bf5818435cc6606c3aa900056b6d2776ec9d5bfa260c0c5203dc45ddb34  tests/fixtures/web_final_defaults/team.txt
```
- Allowed species under default options (catalog):
```
188
abomasnow abra absol aipom altaria ambipom azelf azumarill azurill barboach bastiodon beautifly bibarel bidoof blissey bonsly bronzong bronzor budew buizel buneary burmy carnivine cascoon chansey chatot cherrim cherubi chimchar chimecho chingling clefable clefairy cleffa combee cranidos croagunk crobat drapion drifblim drifloon dusclops duskull dustox eevee electabuzz elekid empoleon espeon feebas finneon flareon floatzel froslass gabite gallade garchomp gardevoir gastly gastrodon geodude gible girafarig giratina glaceon glalie gligar gliscor golbat goldeen golduck graveler grotle gyarados happiny haunter heracross hippopotas hippowdon hoothoot houndoom houndour infernape jolteon kadabra kirlia kricketot kricketune leafeon lickilicky lickitung lopunny lucario lumineon luxio luxray machoke machop magby magikarp magmar magnemite magneton magnezone mamoswine mantine mantyke marill medicham meditite mesprit milotic mime_jr monferno mothim mr_mime munchlax noctowl nosepass octillery onix pachirisu pelipper pichu pikachu piloswine piplup ponyta porygon prinplup probopass psyduck quagsire raichu ralts rampardos rapidash remoraid rhydon rhyhorn riolu roselia roserade rotom scyther seaking shellos shieldon shinx silcoon skorupi sneasel snorlax snorunt snover spiritomb staraptor staravia starly steelix sudowoodo swablu swinub tangela tangrowth tentacool tentacruel togekiss togepi togetic torterra toxicroak tropius turtwig umbreon unown uxie vaporeon vespiquen weavile whiscash wingull wooper wormadam wurmple yanma yanmega zubat
```

## T002 Runs finished before the first src edit

- `final-defaults`, `job-20261008T115114Z-feb186`, `job-20261008T235244Z-2d8f18`,
  `job-20261009T193751Z-1fdb5e`, `job-20261011T222457Z-c4aa1b`, `optimize-36cef906f4d5`,
  `optimize-smoke-quick`: finished (`stages.report` present).
- `job-20261009T193750Z-a1822a`: no stages. It is the cancelled T035 throwaway (6× Garchomp)
  recorded in RUN-STATE.md, so nothing will need resuming.

## T003–T008 Foundational (2026-10-13)

- `uv run platsim extract` → exit 0. `uv run platsim extract --check` → "data/generated is up to date (11 files)".
- Starter entries in `availability.json` carry `group_choice`:
  `[('SPECIES_TURTWIG','SPECIES_TURTWIG'), ('SPECIES_CHIMCHAR','SPECIES_CHIMCHAR'), ('SPECIES_PIPLUP','SPECIES_PIPLUP')]`.
- T001 test set → `83 passed in 87.16s`. That includes `test_starter_choice_is_exclusive`
  (two gift Chimchar), which now fails the team through the per-option quantity check.
- **Deviation from T005 as written**: `team_group_conflicts` checks only the group choices. It
  does not check per-option quantities or item copies, which stay with `resources.realize` and
  the validator.
  - Reason: refusing teams up front for quantities (e.g. two Gliscor needing two Razor Fangs)
    would change existing optimizer behaviour beyond 004's scope, and the contract defines no
    messages for those cases.

## T009–T015 US1 mixed starters (2026-10-13)

- **Tests written first, run before the fix**: 6 failed and 3 passed. The 3 passes were the
  helper control, one starter line, and the same starter line accepted. The 6 failures were the
  expected ones: no conflict found, breed option ungrouped (`(None, None)`), the validator
  accepting Torterra + Infernape, and the web returning 201 instead of 422.
- **After T012–T014**, `extract` exit 0 and `extract --check` up to date. Then
  `pytest -q tests/unit/test_team_groups.py tests/unit/test_validator.py tests/integration/test_web.py`
  gave `1 failed, 64 passed`. The one failure is `test_fossil_lines_need_one_trainer_id`, which
  belongs to US4 (T016) and is not implemented yet.
- **FR-008**: the allowed species under default options are identical to the T001 baseline
  (diff empty, 188 keys).

## T016–T020a US4 fossils (2026-10-13)

- `extract` exit 0; `extract --check` up to date (11 files).
- Fossil revival entries in `availability.json`:
  - `SPECIES_SHIELDON unlimited trainer_id_parity even pre_champion src/underground/mining.c:647`
  - `SPECIES_CRANIDOS unlimited trainer_id_parity odd pre_champion src/underground/mining.c:648`
- `pytest -q tests/unit/test_team_groups.py tests/unit/test_validator.py` → `53 passed in 77.60s`.
- **T020a observation**: with `allow_post_game_pokemon` on, there are no ungrouped starter entries
  (`[]`). Positive control: the post-game view does admit more entries overall (`True`). So the
  starter rule still holds with post-game Pokémon on.
  - The test takes the "no free line" branch.
  - B1's "one ungrouped entry frees the eggs" logic is checked directly through `_line_group`
    (Infernape alone → starter/Chimchar; plus Garchomp → ungrouped).

## T021–T023 US2 breeding partner (2026-10-13)

- `compatible_father(mothers, led)` is now shared by `breed_mothers` (species level) and
  `find_father` (egg moves), through `_father_species`.
- `pytest -q tests/unit/test_team_groups.py -k partner` → `2 passed`:
  - the 86 breed sources are unchanged, and each has a partner;
  - Ditto has no pre-Champion source;
  - positive control: with no father for the Gible line, its breed source disappears and other
    lines stay.
- `pytest -q tests/unit/test_validator.py tests/unit/test_legality_options.py` → `65 passed`.
  That includes the egg-move father tests.

## T024–T028 US3 one-time parents and text (2026-10-13)

- **B3**: `female_possible` and `_female_with` apply pokemon.c `SpeciesData_GetGenderOf`, with
  thresholds from `generated/gender_ratios.txt`.
  - Chatot trade personality 2151 → female; personality 200 → male.
  - Positive control: forcing the Riolu line to male removes its breed source, and it comes back
    after the patch is undone.
- **Breed text** as observed:
  - `Day Care egg from your starter Chimchar -> ...`
  - `Day Care egg from a revived Skull Fossil (odd Trainer ID) -> ...`
  - `Day Care egg from a one-time parent: Gift egg - Iron Island B2F Left Room (Riolu) -> ...`
  - `... Gift - Hearthome City Northwest House (Eevee) -> Vaporeon with Water Stone`
  - `Day Care egg (mother: Gible, Gabite, Garchomp) -> ...`
  - `Fossil - Mining Museum (Skull Fossil, odd Trainer ID) -> ...`
- **Contract revised**: the fossil revival keeps the 003 `Fossil - <where>` prefix.
- **Tests**:
  - `pytest -q tests/unit/test_team_groups.py tests/unit/test_source_text.py` → first run
    `1 failed, 22 passed`. The failure was in my SC-005 test: it counted breed options inherited
    through a pre-evolution's egg (93 vs 86). I fixed the test to count each egg once. Then
    `test_source_text.py` → `10 passed`.
  - `pytest -q tests/unit/test_source_preference.py tests/unit/test_team_groups.py` → `28 passed`.

## T029–T032 Polish (2026-10-13)

- **T029** `test_species_team_count` → passed. The engine's count is 55,192,424,630. Positive
  control: with the group rule off it is C(188,6) = 56,574,476,596.
- **T030** `test_allowed_final_forms` → passed: 188 allowed species and 98 final forms, equal to
  the list in `allowed_pokemon.md`. Positive control: without Garchomp, Gabite becomes a final
  form. The `allowed_pokemon.md` sha256 is unchanged
  (`5e4cdab091d78255de55271278e64de9f153f236fcc4574153cb5b32ef401524`, as at T001).
- **T031** `pyproject.toml` 0.2.0 → 0.3.0. `uv sync` printed `- platsim==0.2.0 / + platsim==0.3.0`,
  and `_platsim_version()` prints `0.3.0`. No test hard-codes 0.2.0 (grep found nothing).
- **T032** README "Legality" now has the starter/fossil choice rule and the breeding-pair rule.

## T033 Full suite (2026-10-13)

Started about 17:06 and ended 19:34 local time. Local CPU only, nothing paid. Browser tests
included: no `-m` filter, using the system Chrome.

`uv run pytest -q`:
```
478 passed, 4 xfailed, 1 warning in 8866.97s (2:27:46)
exit=0
```
