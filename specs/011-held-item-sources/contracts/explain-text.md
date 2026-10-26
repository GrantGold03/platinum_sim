# Contract: `platsim explain` text for the new item sources

Applies to the source line of every ledger entry that the new script reading adds (Route 221 house,
Pastoria City berry house, Amity Square, and any other site the sentinel lists). Other lines are
unchanged (spec Assumptions).

## Rules

1. The line keeps its current shape: `- [phase] kind at Place (MAP_HEADER), quantity N: <reason>  [refs]`.
2. `<reason>` is a plain-English sentence for a player. It MUST NOT match any of these (case-insensitive;
   this fixed list is what the test checks):
   - feature or task ids: the regexes `\b0\d\d\b`, `\bT\d{3}\b`, `\bFR-\d+`, `\bSC-\d+`;
   - implementation terms: `dataflow`, `Return-aware`, `GetRandom`, `AddVar`, `save-var`, `C table`,
     `once flag`, `guards this give`;
   - script command names: `GetDailyRandomLevel`, `CheckPartyHasSpecies`;
   - decomp constants: the regex `\b(FLAG|VAR|ITEM|SPECIES)_[A-Z0-9_]+`.
3. Every decomp file:line that the archived text cited stays on the line, in the `[refs]` list. That
   includes the file:line where a daily flag is set and where the level or party check is made: they move
   out of the sentence and into the refs.

Entries at sites that are not newly found keep `main`'s text exactly, including `daily (FLAG_... set at ...)`;
the plain wording applies only to newly found sites, so `main`'s existing lines do not change.

## Required wording (meaning fixed; exact words may vary)

| Source | Reason text |
|---|---|
| Route 221 house | once a day, only if a party Pokémon is at that day's random level; counted as 1 copy of each item it can give |
| Pastoria City berry house | once a day, a random berry from <first>-<last>; each counted as unlimited |
| Amity Square partner pickup / Gift Man | can be received again; needs one of N partner species in the party |
| Other newly found sites (Route 208 house, News Press, Flower Shop) | plain wording for their kind of gift (for example "once a day" or "one of several possible items; each counted once"), with no tag and no decomp constants |

## Check

`tests/integration/test_explain_item_sources.py` runs `explain` for every item with a newly found source
and fails if any of those source lines matches the forbidden list in rule 2, or lost a ref from rule 3.
Positive control: the test embeds three archived lines as fixture strings (the Route 221 Focus Sash line,
one Pastoria line and the Amity Belue line, copied from `runs/008-evidence/explain.txt` into the test
file) and asserts that the check rejects each of them. The test reads nothing outside the repo.
