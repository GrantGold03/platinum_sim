"""Species weight and the variable-power formulas the optimizer needs (feature 024).

Mirrors `sim/variable_power.mjs` (one source of truth on the battle side; this module is its Python twin, checked
against it by `tests/unit/test_variable_power.py`):

- `species_weight_hg`: hectograms as the dataproc build computes them (tools/dataproc/src/speciesproc.c:735-752):
  `round(kg * 10)` from `res/pokemon/<name>/data.json` `pokedex_data.weight_kilograms`, or from `weight_pounds` minus
  the `species_weight_rounding_override` of that C file (:698-716), times 0.45359237.
- `weight_tier_power`: BtlCmd_CalcWeightBasedPower (src/battle/battle_script.c:6808-6828) with sWeightToPower
  (include/data/battle/weight_to_power.h): the first limit >= weight gives the power, else 120; a weight exactly on a
  limit takes the lower tier (Showdown differs: ledger `mech-weight-tier-boundary`).
- `gyro_ball_power`: BtlCmd_CalcGyroBallPower (:7123-7133): 1 + 25*def/att, capped at 150; 0 when the attacker's
  speed is 0.
- `return_power`: effect_script_0121.s: friendship*10/25.
"""

from __future__ import annotations

import json
import re
from functools import cache

from platsim.pins import DECOMP_ROOT

LB_TO_KG = 0.45359237
WEIGHT_TO_POWER: tuple[tuple[int, int], ...] = ((100, 20), (250, 40), (500, 60), (1000, 80), (2000, 100))
WEIGHT_TOP_POWER = 120


@cache
def _weight_overrides() -> dict[str, float]:
    text = (DECOMP_ROOT / "tools" / "dataproc" / "src" / "speciesproc.c").read_text()
    lines = text.split("\n")
    start = next((i for i, l in enumerate(lines) if "species_weight_rounding_override(enum Species species) {" in l), -1)
    if start < 0:
        raise ValueError("species_weight_rounding_override not found in speciesproc.c")
    out: dict[str, float] = {}
    pending: list[str] = []
    for line in lines[start + 1:]:
        t = line.strip()
        m = re.match(r"^case (SPECIES_\w+):$", t)
        if m:
            pending.append(m.group(1))
            continue
        m = re.match(r"^return (-?[\d.]+);$", t)
        if m:
            for s in pending:
                out[s] = float(m.group(1))
            pending = []
            continue
        if t.startswith("default:"):
            break
    if not out:
        raise ValueError("no weight overrides parsed from speciesproc.c")
    return out


@cache
def species_weight_hg(species_const: str) -> int:
    """Hectograms of the base form of `species_const` (e.g. 'SPECIES_SNORLAX' -> 4600)."""
    name = species_const.removeprefix("SPECIES_").lower()
    d = json.loads((DECOMP_ROOT / "res" / "pokemon" / name / "data.json").read_text())["pokedex_data"]
    if "weight_kilograms" in d:
        kg = float(d["weight_kilograms"])
    elif "weight_pounds" in d:
        kg = (float(d["weight_pounds"]) - _weight_overrides().get(species_const, 0.0)) * LB_TO_KG
    else:
        raise ValueError(f"no weight for {species_const}")
    return int(kg * 10 + 0.5)  # C round(): half away from zero; kg >= 0


def weight_tier_power(weight_hg: int) -> int:
    for limit, power in WEIGHT_TO_POWER:
        if limit >= weight_hg:
            return power
    return WEIGHT_TOP_POWER


def gyro_ball_power(attacker_speed: int, defender_speed: int) -> int:
    if attacker_speed <= 0:
        return 0
    return min(150, 1 + 25 * defender_speed // attacker_speed)


def return_power(friendship: int) -> int:
    return friendship * 10 // 25
