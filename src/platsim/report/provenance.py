"""025 (H4, FR-007): the average-Pokemon assumptions every report states.

`member_defaults_block(team)` is the `provenance.member_defaults` block: the fixed nature, IVs, EVs and friendship the tool
assumes for the player's Pokemon (constitution v1.5.0: the average Pokemon a player has, not a bred or trained one), and the
species whose build the game fixes differently (an NPC-trade or gift mon with set IVs or nature), so a reader can see which
members the assumptions do not describe.
"""

from __future__ import annotations

from platsim.legality.models import DEFAULT_EV, DEFAULT_IV, DEFAULT_NATURE, TeamCandidate

FRIENDSHIP = 255  # maximum friendship, the worker's value and candidates.FRIENDSHIP (Return's power); not imported here
# because candidates imports evaluate, which imports this module
REASON = "the average Pokemon a player has, not a bred or trained one (constitution v1.5.0)"


def member_defaults_block(team: TeamCandidate | None) -> dict:
    fixed = []
    for b in (team.builds if team is not None else []):
        if (b.nature != DEFAULT_NATURE or any(v != DEFAULT_IV for v in b.ivs.values())
                or any(v != DEFAULT_EV for v in b.evs.values())):
            fixed.append(b.species)
    return {"nature": DEFAULT_NATURE, "ivs": DEFAULT_IV, "evs": DEFAULT_EV, "friendship": FRIENDSHIP, "reason": REASON,
            "fixed_by_game": fixed}
