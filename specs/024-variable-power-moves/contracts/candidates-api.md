# Contract: candidates, the additive list, the ledger

## `src/platsim/decomp/weights.py`

- `species_weight_hg(species_const: str) -> int`: hectograms, the Node algorithm; cached.
- `weight_tier_power(weight_hg: int) -> int`; `gyro_ball_power(atk_spe: int, def_spe: int) -> int`.

## `src/platsim/optimizer/candidates.py`

- `FRIENDSHIP = 255`; `OFFERED_VARIABLE = frozenset({"MOVE_RETURN", "MOVE_GRASS_KNOT", "MOVE_LOW_KICK", "MOVE_GYRO_BALL"})`;
  `NOT_OFFERED_VARIABLE: dict[str, str]` (move or effect -> reason) used only to document and to assert in tests.
- `league_opponents() -> tuple[LeagueOpponent, ...]` with `species, types, weight, level, iv, nature`.
- `variable_power(move_const, member_species_const, member_level, opp: LeagueOpponent) -> int | None` (None for fixed
  moves).
- `move_value(const_member, move_const, member_level: int) -> list[float]` (the new required level argument; all
  callers pass the level they already know: `member_candidates`'s `level`, `held_item_candidates`'s level,
  `resources._slot_cost`'s reference level).
- `member_candidates(...)`: unchanged signature; `MemberCandidates.movesets = chosen + extras`; `ranked` prefix
  unchanged; `summary()` gains `variable_offered: list[str]`, `extras: int`.
- `is_attack` and `prune` unchanged.

## Ledger

`mech-weight-tier-boundary` in `mechanics._ENTRIES` (accepted); `uv run platsim divergences` regenerates the file; the id
joins the pinned list in `tests/integration/test_divergences.py`.

## Acceptance scripts (`specs/024-variable-power-moves/scripts/`)

- `acceptance.py --side {main,branch} [--workers 16]`: `main` (run before any code commit) writes `runs/024-evidence/b2-main`,
  `ident-main/{ref,b2main}` and the candidate snapshot `evidence/b2-candidates-main.json`; `branch` writes `b2-branch`,
  `ident-branch/*`, runs `equal_levels.py`, `cmp`s the identity pairs and prints the table (JSON to `acceptance.json`).
  Every result records the code hashes; the script refuses to run while workers or pytest run (`assert_idle`).
- `equal_levels.py <b_dir> <a_dir> <runs> [--self]`: A at A's levels against B at A's levels, `run_full_gauntlets` with
  `expectimax2-v4`, master `024-equal|B2`, `mcnemar_exact`, mean final levels, JSON on stdout.
