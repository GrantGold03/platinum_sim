# Contract: `platsim explain` text for the new item sources

Applies to the source line of every ledger entry that the new script reading adds (Route 221 house,
Pastoria City berry house, Amity Square, and any other site the sentinel lists). Other lines are
unchanged (spec Assumptions).

## Rules

1. The line keeps its current shape: `- [phase] kind at Place (MAP_HEADER), quantity N: <reason>  [refs]`.
2. `<reason>` is a plain-English sentence for a player. It MUST NOT contain:
   - a feature number or task id (`007`, `011`, `T053`, `FR-018`);
   - implementation terms: `dataflow`, `Return-aware`, `GetRandom`, `AddVar`, `save-var`, `C table`,
     `once flag`, `give` used as a noun;
   - script command names (`GetDailyRandomLevel`, `CheckPartyHasSpecies`).
3. Every decomp file:line that the archived text cited stays on the line, in the `[refs]` list.
4. Daily-flag constants may stay in parentheses after "once a day", as on `main`'s existing daily gifts.

## Required wording (meaning fixed; exact words may vary)

| Source | Reason text |
|---|---|
| Route 221 house | once a day, only if a party Pokémon is at that day's random level; counted as 1 copy of each item it can give |
| Pastoria City berry house | once a day, a random berry from <first>-<last>; each counted as unlimited |
| Amity Square partner pickup / Gift Man | can be received again; needs one of N partner species in the party |
| Other newly found sites (Route 208 house, News Press, Flower Shop) | the same wording as `main` uses for that kind of gift, with no tag |

## Check

`tests/integration/test_explain_item_sources.py` runs `explain` for every item with a newly found source
and fails if any of those source lines matches the forbidden list in rule 2, or lost a ref from rule 3.
Positive control: the same check run over `runs/008-evidence/explain.txt` (the archived text) must fail.
