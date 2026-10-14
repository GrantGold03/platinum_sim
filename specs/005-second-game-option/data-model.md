# Data Model: Second-Game Option (005)

No stored data changes:
- `availability.json` is not regenerated;
- `Entry` and `SourceOption` fields are unchanged;
- report schemas are unchanged.

## Derived values (computed, not stored)

| Name | Where | Meaning |
|---|---|---|
| `groups_enforced(led)` | `legality/movesources.py` | `True` unless the ledger view's `allow_unobtainable_pokemon` is on. When `False`, the 004 one-choice-per-group rule is not applied anywhere. |
| `second_game_members(opts)` | `legality/movesources.py` | Indices of the team's chosen options (in team order) whose `group_choice` differs from the first choice seen in that `exclusive_group`. |
| `SECOND_GAME_NOTE` | `legality/movesources.py` | `" (from a second Platinum game, allowed by rule)"`, appended to those members' "Obtained from" text. |

## Rules

- **G1**: with `groups_enforced` true, behaviour is exactly as in 004 (data-model "Team-level
  group rule").
- **G2**: with `groups_enforced` false, members of one group may use different choices.
  Per-option quantity and item copies still apply.
- **G3**: a member is labelled iff its index is in `second_game_members`. With G1 in force, no
  accepted team has such a member.
