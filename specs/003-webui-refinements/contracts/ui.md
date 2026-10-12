# Contract: Page changes (003)

This file lists only the changes. Everything else is as in `specs/002-webui-redesign/contracts/ui.md`.

## Wording (spec FR-001, FR-002)

- **Rule**: no shown text has a requirement id or the word "species". This covers text nodes, `title`,
  `aria-label`, `placeholder`, tooltips, `option` labels and `alert`/`confirm` text.
- The word is always spelled "Pokémon" in page text (FR-002 as amended 2026-10-11); the unaccented
  "pokemon" is rejected by the browser wording scan.
- Changed labels:

  | Before | After |
  |---|---|
  | "Pick six species obtainable before the Champion…" | "Pick six Pokémon for the Elite 4 and Champion fight…" |
  | "1. Choose species" | "1. Choose Pokémon" |
  | "Search species" | "Search Pokémon" |
  | "Loading species data…" | "Loading Pokémon data…" |
  | "Choose exactly six species." | "Choose exactly six Pokémon." |
  | "No species match “q”." | "No Pokémon match “q”." (only shown when no name matches) |

## Header

`header.site` is a flex row: the title and lede on the left, and the theme toggle on the right.

## Theme toggle (spec FR-023)

- `button#theme-toggle` with `aria-pressed` and a label ("Dark mode" or "Light mode") naming the
  theme it switches to.
- A click sets `data-theme` on `<html>` and stores the choice in `localStorage["platsim-theme"]`
  inside try/catch.
- An inline `<head>` script applies a stored choice before the first paint.
- With no stored choice, `prefers-color-scheme` decides, as before.
- This supersedes 002 `ui.md` "Kept: Dark mode via prefers-color-scheme" and the "nothing goes into
  localStorage" note, for the theme only. The run picker still stores nothing.

## Setup

- **Rule checkboxes** (all unchecked on load), in this order:
  1. Allow egg moves
  2. Allow trade evolutions
  3. Allow post-game exclusive Pokémon
  4. Allow post-game items and moves
  5. Allow Pokémon unobtainable in Platinum
- The fieldset legend reads "Optional rules (all off by default)".
- **Trade-evolution note**: `#trade-help` is now the tooltip of "Allow trade evolutions". It is shown
  on hover and focus only, and is still linked by `aria-describedby`.
- **Search**: `#show-excluded` is removed and the page always asks for excluded entries. Any rule
  change re-runs the search. A crossed-out entry keeps `li.excluded`, a disabled add button, and its
  `.reason` text.

## Results panel (spec FR-019)

- The order is `#summary`, then `#team-cards`, then `figure#chart`, then `p#downloads`.
- The summary "Legality options" row lists all five rules as "allowed" or "off". For old runs it
  lists the recorded keys and shows the rest as "off".

## Moves (spec FR-022)

- Each move chip has `data-type="<Type>"` and its colour comes from `--type-<type>`.
- The chip's tooltip starts with the type: "Fire · <source>".

## Trainer pop-up (spec FR-020)

- **Opens** on mouseenter, focus or click/tap of a chart `g.bar-group`. The pop-up is a
  `div#trainer-pop[role=dialog]`, not modal and not focus-trapping, labelled "<Name>'s team".
- **Content**: the trainer sprite (80×80, first frame) on the left, and a 3×2 grid of pokemon front
  sprites on the right, in party order. An empty cell keeps its place.
- **Closes** on Escape, mouseleave, blur or a click outside.
- **Placement**: kept fully inside the viewport. It replaces the old `#chart-tip`, and the clear-rate
  text (rate, interval, battles) moves into the pop-up header, so nothing from the 002 tooltip is lost.
- **Data**: from `GET /api/league`, fetched once. If that fails, the chart keeps working without a
  pop-up.
