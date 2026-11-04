# Contract: sampling API (src/platsim/sampling.py and the changed signatures)

```python
# pure
def switch_index(results: list[dict], floor: float, members=E4) -> int | None
def start_index(master: str, k: int, battle_index: int, n: int) -> int          # top-up rule generalised (champion.py keeps 99)
def e4_pass_stats(full_results: list[dict]) -> tuple[int, int]                   # (reached, full_runs)
def delta_interval(p1: float, n1: int, p2: float, n2: int, z: float = Z95) -> tuple[float, float]
def composite_estimate(reached: int, full_runs: int, cyn_wins: int, cyn_battles: int) -> CompositeEstimate  # estimate, ci95, half_width
def extension_kind(reached: int, full_runs: int, cyn_wins: int, cyn_battles: int, target: float, floor_met: bool) -> str  # "full" | "cynthia_only"
def cynthia_only_request(team, master, k, bank, player_policy, opponent_policy) -> dict   # trainers ["cynthia"], start_state, seed index 98, log "summary"

# pool-driving
def run_adaptive(pool, team, *, master, min_runs, max_runs, target, player_policy, floor, on_batch=None) -> AdaptiveRuns

# changed
def evaluate_team(team, led, pool, *, ..., sampling: str = "full", floor: float = 0.99, ...) -> tuple[EvaluationReport, TeamEvaluation]
def champion_topup(pool, team, full_results, *, master_seed, budget, max_topup=..., extra_cynthia: tuple[int, int] = (0, 0)) -> ChampionResult
```

Rules: `switch_index` counts, per member, battles faced and won across the runs in order and returns the first index
k (1-based count of runs) after which all four have faced ≥ 1 and `wilson_ci(won, faced)[0] >= floor`. `run_adaptive`
discards full results with index ≥ k. `extension_kind` returns `"cynthia_only"` when the floor is met and the
composite half-width with Cynthia's variance term set to zero is below the target; otherwise `"full"`.
`TeamEvaluation.results` keeps the counted full results; a new `TeamEvaluation.cynthia_only_results` holds the rest.
