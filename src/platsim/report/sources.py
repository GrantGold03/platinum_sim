"""Display text for a team's sources (contracts/spreadsheet.md "Obtained from" / "Held item source").

`team_sources(team, ledger)` -> (obtained_from[], held_item_sources[], held_item_source_refs[]),
one entry per build, from each build's own `source` option (legality/movesources.source_options)
and the availability ledger (`movesources.held_item_source`). Shared by `platsim optimize`,
`platsim evaluate` and `platsim report --rerender`, so the three cannot drift apart.

A held item whose source cannot be named raises `movesources.NoNamedSource`: that is a legality
error (FR-006), never printed as a placeholder.
"""

from __future__ import annotations

from platsim.legality import movesources as MS
from platsim.legality.models import TeamCandidate


def build_option(build, led):
    """The SourceOption a Build names (None if the id is not one of the species' options)."""
    from platsim.legality.validator import _resolve, _species_index

    species = _resolve(_species_index(), build.species) or build.species
    opts = MS.source_options(species, led) if species in MS.by_constant() else []
    return next((o for o in opts if o.id == build.source), None)


def team_sources(team: TeamCandidate, led) -> tuple[list[str], list[str | None], list[list[str]]]:
    obtained, held, refs = [], [], []
    for b in team.builds:
        opt = build_option(b, led)
        if opt is None:
            raise MS.NoNamedSource(f"{b.species}: source {b.source!r} is not a pre-Champion source option")
        obtained.append(opt.detail)
        if not b.held_item:
            held.append(None)
            refs.append([])
            continue
        text, src = MS.held_item_source(b.held_item, led, opt)
        held.append(text)
        refs.append(src)
    return obtained, held, refs


__all__ = ["build_option", "team_sources"]
