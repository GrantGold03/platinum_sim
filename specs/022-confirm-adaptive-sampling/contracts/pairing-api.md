# Contract: pairing and the borderline extension

```python
# src/platsim/optimizer/pairing.py (pure)
@dataclass(frozen=True)
class PairedOutcomes:
    a_flags: list[bool]; b_flags: list[bool]; full_pairs: int; cynthia_only_pairs: int; excluded: int
    @property
    def pairs(self) -> int

def paired_outcomes(a_full: list[dict], a_cyn: list[dict], b_full: list[dict], b_cyn: list[dict]) -> PairedOutcomes
# full runs paired by index for i < min(len(a_full), len(b_full)); Cynthia-only by ordinal for j < min(len(a_cyn), len(b_cyn));
# flags: full run -> cleared; Cynthia-only run -> battles[0].won; excluded = the rest on both sides.

# src/platsim/sampling.py (021, extended)
def run_adaptive(pool, team, *, master, min_runs, max_runs, target, player_policy, floor, opponent_policy="decomp-ai",
                 on_batch=None, borderline_threshold: float | None = None, borderline_max_runs: int | None = None) -> AdaptiveRuns
# after the half-width phase: while the current interval straddles borderline_threshold and n < min(max_runs, borderline_max_runs or max_runs):
#   kind = extension_kind(...); batch size min(max(n // 2, MIN_BATCH), room) as the full method; consume in order; stop at the first run
#   after which the interval no longer straddles; discard the rest (counted).

# src/platsim/evaluate.py (021, extended)
def evaluate_team(..., sampling="full", floor=DEFAULT_FLOOR, adaptive_runs: AdaptiveRuns | None = None)
# adaptive with extend_borderline is now allowed; `adaptive_runs` reuses a precomputed run (the runner-up), like `full=`.
```
