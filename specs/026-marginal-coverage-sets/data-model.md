# Data model: Candidate sets by marginal coverage

## MemberCandidates (candidates.py), new fields

| Field | Type | Meaning |
|---|---|---|
| `pool` | list[str] | now the marginal pool (10), in entry order |
| `dead_moves` | dict[tuple, list[str]] | per offered set, the moves with zero marginal contribution (expected empty) |
| `no_live_reason` | str or None | set when a set with dead moves was accepted (pass 3): "no better option: the two strongest moves cover every League opponent" |
| `one_apart` | list[tuple] | sets accepted one move apart (FR-004a) |
| `unavailable` | frozenset[str] | moves excluded by the allocation (story 3) |
| `summary()` | adds the four fields above |

Rules: every offered set is all-live unless `no_live_reason` is set; `one_apart` sets differ by exactly one move from an
earlier offered set; ties broken by score then name.

## Pool, live, dead (definitions used by the code and the acceptance)

- `coverage(vals)` = Σ over opponents of max over moves (unchanged).
- `marginal(m, S)` = coverage(S) − coverage(S \ {m}); `dead(m, S)` ⇔ marginal 0.
- `live(m)` ⇔ m is the best against ≥ 1 opponent given the member's top two moves by score.
- `takeover(m, S)` = opponents where m would be the best move in S ∪ {m}.
- Cost class: `effect_class(effect) == "cost"` (025).

## Allocation record (prune stage and provenance `optimizer.allocation`)

```json
{"TM26": {"copies": 1, "contenders": [["SPECIES_GARCHOMP", 61234.0], ["SPECIES_INFERNAPE", 18910.0]],
          "given_to": ["SPECIES_GARCHOMP"], "rebuilt": ["SPECIES_INFERNAPE"]}}
```

Rules: contenders sorted by gain desc then slot; `given_to` the first `copies`; required moves never contested; bounded loop.

## EvaluationReport

- `member_notes: list[str]` (default `[]`; absent in files before 026 reads as empty); one line per member with filler moves.

## Attribution record (scripts/attribution.py), new cause

- `cause: "marginal_pool"` with `kind` in {pool, moveset, setup} and `moves`; the dead-moves table `{member: {before: {set:
  [moves]}, after: {...}}}`.
