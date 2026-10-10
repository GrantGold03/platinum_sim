# Contract: Page structure and behaviour

The page is `src/platsim/web/static/` (`index.html`, `app.js`, `style.css`). It stays build-free,
with no CDN and no framework.

## Layout (FR-001, FR-002)

The element ids are `#setup` (left) and `#results-col` (right). `#results` is already the species list.

```text
┌──────────────── setup (left, ~40%) ────────────────┬──────────── results (right, ~60%) ─────────────┐
│ Legality: [ ] egg moves  [ ] trade evolutions       │ ┌ Progress (only while queued/running) ──────┐ │
│ Search: [________]                                  │ │ stage · elapsed 12:04 · about 41 min left  │ │
│   (list hidden until typing; [ ] show excluded)     │ │ [Cancel]                                   │ │
│ Team (n/6):                                         │ └────────────────────────────────────────────┘ │
│   [icon] Infernape   [×]                            │ Run: [ 2026-10-08 23:52 · Infernape… · qualified ▾]   │
│   …                                                 │ QUALIFIED · clear 86.5% · 58.23 (level gap of 4)│
│ Min clear rate [75] %   Budget [standard ▾]         │ threshold · budget · legality · platsim 0.1.0  │
│ Seed* [default]   (*explanation on hover/focus)     │ Per-trainer clear rate (bar chart + CI)        │
│ [Optimize]                                          │ Team: 6 cards (sprite, levels, ability, item,  │
│                                                     │       obtained from, 4 moves with source tip)  │
│                                                     │ Downloads: xlsx · csv · json · team.txt        │
└─────────────────────────────────────────────────────┴────────────────────────────────────────────────┘
```

- Below about 900 px, the columns stack with setup first. There is no horizontal scroll at
  360 px.
- The left column is sticky on wide screens, so setup stays visible while results scroll
  (SC-003).

## Behaviour

| Control | Behaviour | FR |
|---|---|---|
| Species search | List hidden while the input is empty (after trimming). Shown on the first character. Hidden again when cleared. 503 → "species are loading…" | FR-003 |
| Team slot | `<img>` icon (32×32 first frame, pixelated) + name + remove. A 404 icon gets a same-size placeholder | FR-004 |
| Budget | `<select>` quick/standard/thorough. Default standard. Sent in POST | FR-005 |
| Seed | The label word "Seed" is a focusable term (`tabindex=0`, `aria-describedby`). A tooltip is shown on `:hover` and `:focus-visible` only | FR-006 |
| Progress | Rendered only while any job is queued or running. It shows the running job (elapsed time ticking every 1 s on the client from `started`, and the ETA from `eta_s`: "about N min left" or "estimating…"), then a list of the queued jobs, each shown as "position N · <species>". If nothing is running, the first queued job shows as "waiting to start" | FR-008–FR-010 |
| Cancel | One button for the running job, and one for each queued job. Each uses a `confirm()` dialog, then POST cancel. The button is disabled while waiting. The status is announced through `aria-live` | FR-011, FR-012 |
| Status line | `#run-status` (`aria-live`), above the result. Announces "Run queued.", "Run started.", "Run finished: <label>", "Run failed: <reason>" and "Run cancelled". The last message stays until the next one, even when an older run is picked | FR-028 |
| Run picker | `<select>` filled from `GET /api/jobs`. Shows the newest `done` job on load and whenever a new job finishes. A pick is not remembered, and nothing goes into `localStorage` | FR-014, FR-015 |
| Failed or cancelled run | The panel shows the status and `error` instead of the result | FR-016 |
| Clear rate | Shown as `NN.N%`. It is focusable (`tabindex=0`), and on hover or focus it shows a tooltip "95% interval A–B% · N runs", also referenced by `aria-describedby` | FR-017 |
| Team card | Sprite, species, "Lv start → final", ability, held item, the full "obtained from" text (wrapped, never cut off), and the four moves | FR-023 |
| Move | Each move is a focusable chip. Its source shows as a tooltip on hover or focus, and is also in `aria-describedby` | FR-026 |
| Chart | Inline SVG. Bars with a CI whisker and a threshold line. Focusable groups, with a visible tooltip on hover and focus showing the interval and battle count. Visually hidden data table | FR-027 |

## Not displayed

These are not displayed anywhere on the page:
- Cynthia win rate
- Policies
- Objective
- Commit hashes
- Clear-rate interval and run count inline (they appear only in the clear-rate tooltip)
- Nature, IVs and EVs
- Ability-choice code
- Held-item source
- Move-source columns
- "Best so far" dump

## Kept

- Dark mode via the existing `prefers-color-scheme` variables
- `aria-live` status regions
- Labelled controls
- Visible focus outline
