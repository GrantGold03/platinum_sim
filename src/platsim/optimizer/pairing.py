"""Pairing of two adaptive-sampling evaluations for the runner-up comparison (feature 022, research R4).

Full runs are paired by run index: run i of both teams uses the request seed `derive_seed(master, i, 0)`. Cynthia-only
runs are paired by their ordinal: the j-th Cynthia-only run of each team uses `derive_seed(master, j, 98)` (feature
021), each played from that team's own banked state. Pairing by run index would pair runs with different seeds
whenever the two teams switch at different runs, so the ordinal is the seed-faithful choice; the pair count is the
same either way. Every run without a same-kind, same-seed partner is excluded and counted. When neither team switched
this is exactly the full method's pairing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PairedOutcomes:
    a_flags: list[bool]
    b_flags: list[bool]
    full_pairs: int
    cynthia_only_pairs: int
    excluded: int

    @property
    def pairs(self) -> int:
        return self.full_pairs + self.cynthia_only_pairs


def _won(cyn_result: dict) -> bool:
    (b,) = cyn_result["battles"]
    return bool(b["won"])


def paired_outcomes(a_full: list[dict], a_cyn: list[dict], b_full: list[dict], b_cyn: list[dict]) -> PairedOutcomes:
    nf = min(len(a_full), len(b_full))
    nc = min(len(a_cyn), len(b_cyn))
    a_flags = [bool(r["cleared"]) for r in a_full[:nf]] + [_won(r) for r in a_cyn[:nc]]
    b_flags = [bool(r["cleared"]) for r in b_full[:nf]] + [_won(r) for r in b_cyn[:nc]]
    excluded = (len(a_full) + len(b_full) - 2 * nf) + (len(a_cyn) + len(b_cyn) - 2 * nc)
    return PairedOutcomes(a_flags, b_flags, nf, nc, excluded)


__all__ = ["PairedOutcomes", "paired_outcomes"]
