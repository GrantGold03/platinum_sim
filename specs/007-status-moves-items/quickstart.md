# Quickstart: validating 007

Run everything locally with `uv run`. The benchmark teams B1-B5 are defined in `research.md` R9.

Compute estimates are rough and unverified, taken from recorded throughput on 16 workers. The baseline is about 8-11 h. A reference run is about baseline plus 75 min per team.

## 0. Before any change

```bash
uv run pytest -q                        # full suite, about 2.5 h; record the output in validation-log.md
node --test sim/test                   # JS tests
```

- Record the golden v1/v2 `log_hash`es (contract `player-v3.md`).
- Record a baseline standard run per benchmark team on `f88cdd0` (seed `bench-007`), with its stage timings.

## 1. Classification and items (US1/US2 groundwork)

- Every effect classifies to exactly one category. The R1 positive controls pass: Screech → foe_drop, Magnitude ≠ fixed, and so on.
- The item filter offers 87 or more items under default options. Every offered item maps to a Showdown id. Leftovers is offered only on a Munchlax/Snorlax team.
- The type-boost tie rule picks a classic item over a Plate when copies are equal.

## 2. Ledger sources (US5)

```bash
uv run platsim extract && uv run platsim extract --check
uv run platsim explain item:focus_sash     # expect: Route 221 house, daily, before the Champion
```

The counts become 77 unlimited and 44 unavailable. Liechi Berry stays at 0 copies.

## 3. Variable-power attacks (US4)

Positive controls:
- Return = 102.
- Hidden Power = Dark 70.
- Low Kick = 120 vs Hippowdon and 40 vs Roserade.
- Frustration and Seismic Toss are not offered.

## 4. Player v3

```bash
node --test sim/test                         # golden v1/v2 hashes unchanged; v3 mechanic tests; SC-008 positions
uv run pytest -q tests/integration/test_policy_strength.py
```

- v3 against v2 and greedy-v1, paired.
- Each cheap v3 candidate against `expectimax2-v3-ref`, paired. Record run times and the accepted settings.

## 5. Optimizer, reference mode

```bash
uv run platsim optimize --candidates reference --seed bench-007 <B4 team>
```

Expected in `result.json`:
- `provenance.optimizer.candidate_tests` lists every offered alternative.
- Excluded moves have reasons.
- The validator passes.
- For B3, Surf and Waterfall are still carried, and no adopted status move was displaced by an HM.

## 6. Prefilter acceptance (FR-017, FR-019, SC-002, SC-006)

- Run B1-B5 in `prefilter` mode on the same seeds.
- For each team, compare with the reference (paired) and with the baseline. Record the table and run times in `validation-log.md`.
- The prefilter becomes the default only if it is not worse than the reference on any team, and its time is about 2× baseline or less.

## 7. Reproducibility (SC-005)

Re-run one benchmark request with the same seed. `result.json` must be byte-identical.
