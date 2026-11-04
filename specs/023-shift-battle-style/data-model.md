# Data Model: Shift Battle Style

## Battle style (request field, everywhere a worker request is built)

| Field | Values | Default | Where |
|---|---|---|---|
| battle_style | "set" \| "shift" | "set" (until the owner's decision) | evaluate/optimize requests, Cynthia-only and top-up requests, loss replays, optimizer stage requests, bench |

Worker: validated (`set` | `shift`, else a request error); hello advertises `battle_styles: ["set", "shift"]`, checked
by the pool like `policies`. Run response: `battle_style: "shift"` present only under Shift; readers use `get(..., "set")`.

## Free-switch offer (worker, per battle, Shift only)

Battle record `shift = {offers, switches, events: [{turn, incoming, answer, reason}]}`:

| Field | Notes |
|---|---|
| offers | number of times the gate held in this battle |
| switches | offers answered with a switch |
| events[].turn | the engine's turn number at the offer (the turn that just ended) |
| events[].incoming | announced species (the trainer's actual replacement) |
| events[].answer | "stay" or the member switched to (species) |
| events[].reason | the policy's reason string (values compared) |

Log line per offer: `|-message|shift: <trainer> is about to send in <incoming>; player <stays|switches to X> (<reason>)`.
Gate (all true): style `shift`; p1 has no request and p2's is a replacement; p1's active has HP; p1 has a member with
HP that is not active and not an egg. Exclusions: both replacing; only p1 replacing; no bench; the trainer's last fainted
(the battle is over, the loop exits).

## Policy hook

`shiftChoice(ctx, incoming) -> null | "switch N"`: optional on a player policy; `ctx` as `choose` receives it (p1's
request is a wait); `incoming` the Showdown Pokemon object `p2.pokemon[N-1]`; `N` 1-based in p1's party order; `null`
means stay. Policies without it stay. expectimax2: argmax over stay and bench candidates of `valuePly2` on the cloned
root with our member placed then the foe; ties stay. greedy: best bench `memberScore` against `incoming` strictly above
the active's.

## EvaluationReport (changed)

| Field | Default | Notes |
|---|---|---|
| battle_style | "set" | trailing defaulted field; `to_dict` writes it; `from_dict` reads with default; summary first line gains `style <x>`; xlsx row "Battle style"; provenance `battle_style`; web summary key `battle_style` |

## OptimizeRequest (changed)

| Field | Default | Fingerprint |
|---|---|---|
| battle_style | "set" | only when != default (006/018/022 rule); provenance `request.battle_style` |

## Divergence entries (mechanics)

| id | resolution | decomp_ref | showdown_ref | test_id |
|---|---|---|---|---|
| mech-shift-prompt | corrected | `pokeplatinum/src/battle/battle_controller_player.c:4144` (gate), `res/battle/scripts/subscripts/subscript_replace_fainted.s:35` (prompt) | `pokemon-showdown/sim/battle.ts:1427` (switch requests only for flagged Pokemon) | `sim/test/shift.test.mjs` (gate, hand-walk) |
| mech-shift-entry-order | accepted | `pokeplatinum/src/battle/battle_lib.c:3649` (entry abilities by category then speed), `battle_controller_player.c:1844` | `pokemon-showdown/sim/battle-queue.ts:177` (instaswitch order 3, speed-sorted), `data/mods/gen4/scripts.ts:18` (runSwitch per Pokemon) | `sim/test/shift.test.mjs` (documented, not corrected) |

## Acceptance table (per team, both styles)

clear rate and Wilson interval per style; McNemar exact (a_only, b_only, p, verdict); per-trainer pass rates per style;
offers, switches, prompted-battle outcomes (won/lost after an offer) under Shift; gauntlets/s per style and the wall
ratio; the control row (Shift vs Shift, discordant 0); the B2 quick pair (winner species, levels, confirmation clear
rate and interval, wall) per style.
