# Contract: `platsim explain` reason text for the new item sources

Applies to the reason text (`Entry.detail`) of the entries this feature adds. `main`'s existing reason phrases stay
as they are (research R4).

## Rules

1. The line keeps `main`'s shape: `- [phase] kind at Place (MAP_HEADER), quantity N: <reason>  [refs]`.
2. Every phrase this feature adds is plain English for a player. The reason MUST NOT contain the project's own labels
   or implementation words. The test checks this fixed list (case-insensitive):
   - ids: the regexes `\b0\d\d\b` (feature numbers), `\bT\d{3}\b`, `\bFR-\d+`, `\bSC-\d+`, `\bR\d\b`;
   - implementation words: `dataflow`, `call stack`, `Return-aware`, `AddVar`, `save-var`, `saved variable`,
     `C table`, `sentinel`, `once flag`, `guards this give`.
3. Decomp identifiers are citations and are allowed (flag names, script command names, file:line), as on `main`'s
   existing lines. Every decomp file:line the source depends on appears in the reason or the refs.

## Wording (meaning fixed; exact words may vary)

| Source | Reason |
|---|---|
| Route 221 house | `main`'s daily phrase, then: only if a party Pokémon is at that day's random level (`GetDailyRandomLevel` at file:line); the items rotate Black Belt, Expert Belt, Focus Sash; counted as 1 copy of each |
| Pastoria City SW house | `main`'s daily phrase, then: one of 17 berries at random |
| Amity Square partner pickup | `main`'s phrase for a several-item gift (the partner condition is not stated; spec Clarifications 2026-10-26) |
| Amity Square Gift Man | `main`'s daily phrase, then: one of the man's 9 berries or 7 accessories at random |
| Any other newly read site | `main`'s phrase for its kind of gift, plus "one of N possible items" when several are possible |

A daily gift with several possible items gains "; one of N possible items" after `main`'s phrase wherever it is, so the
4 Great Marsh 6 daily-shard lines that `main` already had gain that clause too (measured in T016; wording only).

## Check

`tests/integration/test_gift_reader.py` runs the explain function for Focus Sash, an Occa-range berry and Belue
Berry and checks rule 2 and the refs in rule 3. Positive control: the check is also run on a made-up line containing
`T053` and `dataflow`, and must reject it.
