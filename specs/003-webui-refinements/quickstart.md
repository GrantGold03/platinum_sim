# Quickstart: validating 003

Each scenario says how to check one part of the feature. Contracts: [http-api](contracts/http-api.md),
[ui](contracts/ui.md). Entities: [data-model](data-model.md).

## Prerequisites

- Branch `002-webui-redesign` (003 is built on it, by the user's choice).
- `uv sync`.
- The system Chrome is needed for the browser tests (see the README).
- Regenerate the generated data after any ledger change: `uv run platsim extract`. Then
  `uv run platsim extract --check` must pass.

## Fast checks (about 2 min)

```bash
uv run pytest -q tests/unit tests/integration/test_web*.py tests/integration/test_availability_controls.py
uv run pytest -q -m browser tests/browser/
```

## V1. Wording scan (spec SC-001)

- **Do**: run the browser test that visits setup, searches under every rule combination, opens every
  fixture run, and triggers a 422 error.
- **Expect**: zero matches of `\b(FR|SC)-\d+` and of `species` (any case) in the visible text, the
  attributes and the tooltips.
- **Positive control**: the same scan run on the 002 page source (or on a page with an injected
  "species" string) reports a hit.

## V2. Search always shows excluded pokemon (spec SC-002)

```bash
curl -s 'http://127.0.0.1:8000/api/species?q=golem&excluded=1' | jq '.[0] | {name, available, reason}'
curl -s 'http://127.0.0.1:8000/api/species?q=golem&excluded=1&trade_evolutions=1' | jq '.[0].available'
```

- **Expect**: Golem is crossed out with a trade-evolution reason, then available.
- **Test**: for all 493 pokemon × 16 rule combinations, searching the full name returns that pokemon.

## V3. Rules (spec SC-003, SC-003a)

Each rule must unlock its pokemon or resources, and nothing else:

| Rule | Unlocks | Stays locked |
|---|---|---|
| post-game pokemon | a `post_game` pokemon | TM50 |
| post-game items | TM50, TM37, TM42, TM53, Victory Road Leftovers; TM04, TM08, TM61, TM73, Focus Band (Frontier exchange) | the unused-map entries (condominium TM04 gift and Focus Band, Battle Park Razor Fang) are never a named source |
| unobtainable pokemon | Caterpie (dual-slot), Bulbasaur (synthetic, level 1) | |
| unobtainable pokemon | Ivysaur, as an evolution | |

With all rules off, the usable set equals today's plus Munchlax and Snorlax.

## V4. Munchlax and Leftovers (spec SC-004)

The validator must give these results:

| Team | Leftovers on | Expected result |
|---|---|---|
| Munchlax + 5 others | 3 members | legal |
| same team without Munchlax | 1 member | `LEFTOVERS_NEEDS_MUNCHLAX` |
| no Munchlax, post-game items on | 1 member | legal |
| no Munchlax, post-game items on | 2 members | illegal |

Also check: `source_options(SPECIES_MUNCHLAX)` has levels 5–15, and Snorlax is available through
friendship.

## V5. "Obtained from" text (spec SC-005)

- **Leak test**: no `SourceOption.detail` for any pokemon under any rule combination contains
  `[A-Z]{2,}_[A-Z_]+` or `EVO`.
- **Re-render**:

  ```bash
  uv run platsim report --rerender tests/fixtures/web_final_defaults --out "$SCRATCH/rr"
  jq '.obtained_from' "$SCRATCH/rr/result.json"
  ```

- **Expect**:
  - Infernape: `Gift - Route 201 (Chimchar, starter) -> Monferno at level 14 -> Infernape at level 36`.
    The levels come from the decomp; check them against the output, don't assume them.
  - Weavile names Razor Claw and night.
  - Rotom reads `Static encounter - <map>`.
  - Every battle number is unchanged (the re-render guarantees this).
- **1% rule**: Gabite is not counted as 1% on Victory Road (5%). A pokemon whose only locations are 1%
  still gets a location.
- **Earliest location**: the chosen map has the lowest badge rank among legal options (research R9).
  Check this on Staravia and Sneasel. Garchomp must be named from Gible in Wayward Cave B1F, not
  from Gabite on Victory Road, because the earliest location wins across evolution stages.

## V6. Results order, pop-up, move colours, theme (spec SC-006, SC-007)

- **Browser test**:
  - Results order is summary, cards, chart, downloads (by DOM order and by the `y` position of each
    box).
  - For each of the five chart bars, hover, Tab-focus and tap all open `#trainer-pop`, with 1 trainer
    image and 5 or 6 pokemon images (`img.naturalWidth > 0`). Escape closes it.
  - Each move chip has `data-type`, and its tooltip starts with the type.
  - Clicking `#theme-toggle` changes `data-theme`, reloading keeps it, and clearing storage returns to
    the system setting.
- **Contrast**: a unit test reads `style.css` and checks that every `--type-*` has a contrast of at
  least 4.5 against the card background in both themes.
- **Screenshots**: set `PLATSIM_SCREENSHOT_DIR`; light, dark and 360 px screenshots are inspected by
  eye.

## V7. Reports and determinism

- **Same run, new code**: run a `quick` optimize from the command line and through the page with the
  same request. The `result.json` files must be byte-identical (002 V7 method).
- **Old runs**: their reports are untouched. `sha256sum runs/job-*/result.json` before and after
  matches.
- **New fields**: `provenance.legality_options` has five keys, and `platsim_version` is 0.2.0.

## V8. Full suite before merge

```bash
uv run pytest -q          # about 2.5 h; record the result in validation-log.md
```
