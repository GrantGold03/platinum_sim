"""Species list for the web page (T067): display names, types, and pre-Champion availability.

Availability is the legality validator's rule, not a second copy of it: a species is available iff
`legality.movesources.source_options(SPECIES_*, ledger)` is non-empty, which is exactly the check
behind the validator's SPECIES_UNAVAILABLE / SPECIES_TRADE_EVOLUTION violations. Everything here is
read from the availability ledger and the decomp species data; nothing is typed by hand.

For an excluded species the catalogue explains why, in this order (several may apply):
- `trade_evolution`: only reachable by trade evolution (001 FR-005);
- `post_game`: its encounters are only reachable after the Champion (ledger phase post_game);
- `national_dex`: its encounters need the National Dex (001 FR-003a);
- `pre_evolution_unavailable`: no encounter of its own and its pre-evolution is unavailable;
- `unavailable`: only event-only / other-cartridge encounters (ledger phase unobtainable), or no
  encounter, gift, trade, egg or evolution source in the game data at all. Shown as "Unavailable in
  Platinum" and only when no other reason applies (003 FR-005).
Reason texts are shown on the page, so they carry no requirement ids (003 FR-001, FR-006).

Legality options (legality/models.LegalityOptions): availability is computed twice, with trade
evolutions off (the default, FR-005) and on (`allow_trade_evolutions`); `search`, `resolve_team`
and `SpeciesInfo.to_json` take `allow_trade_evolutions` to pick one. With trade evolutions on, a
species reachable only through a trade evolution is available and marked `trade_evolution: true`;
one whose trade evolution still has no pre-Champion path keeps reason_code `trade_evolution` with
the missing pre-evolution / held item named. `allow_egg_moves` never changes which species are
available (it only adds move sources; a Day-Care egg is a species source either way), so the
catalogue does not depend on it.

Only base forms are listed: the validator rejects alternate forms (SPECIES_FORM_UNSUPPORTED).
Building the ledger takes ~35 s on first use (it is cached per process and shared with the
optimizer when both run in the same process).
"""

from __future__ import annotations

import dataclasses
import functools
import re
from collections.abc import Callable
from dataclasses import dataclass

from platsim.legality.models import DEFAULT_LEGALITY, LegalityOptions
from platsim.optimizer.api import InvalidRequest

ACQUIRE_KINDS = ("wild_slot", "gift", "egg", "static", "roamer", "npc_trade")

# Shown on the page (003 FR-005, FR-006): plain sentences, no requirement ids, "pokemon" not "species".
REASON_TEXT = {
    "trade_evolution": "Evolves from {pre} by trade (needs a second cartridge; allowed with the trade-evolutions rule)",
    "trade_evolution_unavailable": "Evolves from {pre} by trade; trade evolutions are allowed, but {missing}",
    "post_game": "Post-game only ({where})",
    "national_dex": "Post-game only (needs the National Dex)",
    "unavailable": "Unavailable in Platinum",
    "pre_evolution_unavailable": "Evolves from {pre}, which is not available ({why})",
}
TRADE_NOTE = "Evolves by trade: needs a second cartridge for the trade"


def _norm(s: str) -> str:
    """Lower-case letters and digits only; the gender signs become m / f so that "Nidoran♂" matches
    the key nidoran_m and not Nidoran♀."""
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("♂", "m").replace("♀", "f"))


def _item_name(const: str) -> str:
    from platsim.decomp.items import load_items

    item = load_items().get(const)
    return item.name if item else const


def _type_name(t: str) -> str:
    return t.removeprefix("TYPE_").capitalize()


@dataclass(frozen=True)
class Status:
    """Availability of one species under one set of legality options."""

    available: bool
    reason: str | None = None
    reason_code: str | None = None
    note: str | None = None  # set for a species that only a trade evolution makes available


@dataclass(frozen=True)
class SpeciesInfo:
    key: str  # data/generated key, e.g. "garchomp"
    const: str  # SPECIES_GARCHOMP
    name: str  # display name, e.g. "Garchomp"
    types: tuple[str, ...]
    dex: int
    # Status under the default options. A catalogue built by `build_catalog` answers every other
    # options value from its per-options tables; a hand-made catalogue (tests) uses these fields.
    available: bool = True
    reason: str | None = None
    reason_code: str | None = None

    def default_status(self) -> Status:
        return Status(self.available, self.reason, self.reason_code)


TableFn = Callable[[LegalityOptions], dict[str, Status]]


class SpeciesCatalog:
    """Species list plus availability per legality-options value (003 research R13).

    `table(options)` is computed on first use and cached (LRU of 16 option values), because which
    species are usable depends on several options and most combinations are never asked for."""

    def __init__(self, species: list[SpeciesInfo], table: TableFn | None = None):
        self.species = sorted(species, key=lambda s: s.dex)
        self._by_norm: dict[str, SpeciesInfo] = {}
        for s in self.species:
            self._by_norm[_norm(s.key)] = s
            self._by_norm.setdefault(_norm(s.name), s)
        self._table = functools.lru_cache(maxsize=16)(table) if table else None

    def get(self, key_or_name: str) -> SpeciesInfo | None:
        return self._by_norm.get(_norm(key_or_name or ""))

    def status(self, info: SpeciesInfo, options: LegalityOptions = DEFAULT_LEGALITY) -> Status:
        if self._table is None:
            return info.default_status()
        return self._table(options)[info.key]

    def to_json(self, info: SpeciesInfo, options: LegalityOptions = DEFAULT_LEGALITY) -> dict:
        st = self.status(info, options)
        d = {"key": info.key, "name": info.name, "types": list(info.types), "available": st.available,
             "sprite_icon": f"/api/sprites/{info.key}/icon.png"}
        if not st.available:
            d["reason"] = st.reason
            d["reason_code"] = st.reason_code
        if st.available and st.note:
            d["trade_evolution"] = True
            d["note"] = st.note
        return d

    def search(self, q: str, include_excluded: bool = True, limit: int = 25,
               options: LegalityOptions = DEFAULT_LEGALITY) -> list[SpeciesInfo]:
        """An exact name or key match first (003 SC-002), then prefix matches, then substring
        matches; dex order within each."""
        nq = _norm(q or "")
        pool = [s for s in self.species if include_excluded or self.status(s, options).available]
        if not nq:
            return pool[:limit]
        exact = [s for s in pool if nq in (_norm(s.name), _norm(s.key))]
        prefix = exact + [s for s in pool if s not in exact and (_norm(s.name).startswith(nq) or _norm(s.key).startswith(nq))]
        seen = {s.key for s in prefix}
        sub = [s for s in pool if s.key not in seen and (nq in _norm(s.name) or nq in _norm(s.key))]
        return (prefix + sub)[:limit]

    def resolve_team(self, species: object, options: LegalityOptions = DEFAULT_LEGALITY) -> tuple[str, ...]:
        """Validate a submitted team; returns the six keys or raises InvalidRequest with
        per-species reasons (keyed by the submitted value)."""
        if not isinstance(species, list) or not all(isinstance(x, str) for x in species):
            raise InvalidRequest("Pokémon must be a list of six Pokémon keys")
        reasons: dict[str, str] = {}
        keys = []
        for x in species:
            info = self.get(x)
            if info is None:
                reasons[x] = "unknown Pokémon"
                continue
            st = self.status(info, options)
            if not st.available:
                reasons[x] = f"{info.name}: {st.reason}"
            else:
                keys.append(info.key)
        if len(species) != 6:
            raise InvalidRequest(f"exactly 6 Pokémon are required, got {len(species)}", reasons)
        if reasons:
            raise InvalidRequest("some Pokémon cannot be used: " + "; ".join(f"{k}: {v}" for k, v in reasons.items()),
                                 reasons)
        return tuple(keys)


def build_catalog(ledger=None) -> SpeciesCatalog:
    from platsim.availability import ledger as L
    from platsim.legality import movesources as MS

    base = ledger or L.build_ledger()
    consts = MS.by_constant()
    preds = MS._preds()

    def why_for(led):
        """(code, text) for an unavailable species under `led`'s options, None if available."""
        by_subject: dict[str, list] = {}
        for c in led.entries:
            if c.entry.kind in ACQUIRE_KINDS:
                by_subject.setdefault(c.entry.subject, []).append(c)
        memo: dict[str, tuple[str, str] | None] = {}

        def why(const: str, depth: int = 0) -> tuple[str, str] | None:
            if const in memo:
                return memo[const]
            if MS.source_options(const, led):
                memo[const] = None
                return None
            memo[const] = ("unavailable", REASON_TEXT["unavailable"])  # cycle guard
            found: list[tuple[str, str]] = []
            trade = [p for p, ev in preds.get(const, []) if ev.method in MS.TRADE_METHODS]
            if trade:
                found.append(("trade_evolution", REASON_TEXT["trade_evolution"].format(pre=MS.species_name(trade[0]))))
            entries = [c for c in by_subject.get(const, []) if c.phase != L.PRE]
            post = [c for c in entries if c.phase == L.POST and not any("national_dex" in r for r in c.reasons)]
            if post:
                where = sorted({MS.human_map(c.entry.map_header) for c in post})
                found.append(("post_game", REASON_TEXT["post_game"].format(
                    where=", ".join(where[:3]) + (" …" if len(where) > 3 else ""))))
            if any(c.phase == L.POST and any("national_dex" in r for r in c.reasons) for c in entries):
                found.append(("national_dex", REASON_TEXT["national_dex"]))
            if not found:
                for p, ev in preds.get(const, []):
                    if ev.method in MS.TRADE_METHODS or depth > 4:
                        continue
                    pw = why(p, depth + 1)
                    if pw is not None:
                        found.append(("pre_evolution_unavailable", REASON_TEXT["pre_evolution_unavailable"].format(
                            pre=MS.species_name(p), why=pw[1])))
                        break
            if not found:  # only other-cartridge / event entries, or no source at all
                found.append(("unavailable", REASON_TEXT["unavailable"]))
            res = (found[0][0], "; ".join(t for _, t in found))
            memo[const] = res
            return res

        return why

    def table(options: LegalityOptions) -> dict[str, Status]:
        """Availability of every species under `options`. Without trade evolutions the reasons come
        from `why`; with them, a species that only a trade evolution unlocks is marked (note), and
        one whose trade evolution still has no pre-Champion path names what is missing."""
        no_trade = dataclasses.replace(options, allow_trade_evolutions=False)
        led0 = base.with_options(no_trade)
        why = why_for(led0)
        trade_led = base.with_options(options) if options.allow_trade_evolutions else None

        def why_trade(const: str, w: tuple[str, str] | None) -> tuple[str, str] | None:
            if w is None or MS.source_options(const, trade_led):
                return None
            trade = [(p, ev) for p, ev in preds.get(const, []) if ev.method in MS.TRADE_METHODS]
            if not trade:
                return w  # nothing trade-related: same reason as without the option
            p, ev = trade[0]
            missing = ([f"{MS.species_name(p)} is not available"] if not MS.source_options(p, trade_led) else []) + \
                      ([f"{_item_name(ev.param)} has no pre-Champion copy"]
                       if isinstance(ev.param, str) and led0.item_copies(ev.param) == 0 else [])
            return ("trade_evolution", REASON_TEXT["trade_evolution_unavailable"].format(
                pre=MS.species_name(p), missing="; ".join(missing) or "no pre-Champion path reaches it"))

        out: dict[str, Status] = {}
        for const, sp in consts.items():
            w = why(const)
            if trade_led is None:
                out[sp.key] = Status(w is None, w[1] if w else None, w[0] if w else None)
                continue
            wt = why_trade(const, w)
            note = TRADE_NOTE if (w is not None and wt is None) else None
            out[sp.key] = Status(wt is None, wt[1] if wt else None, wt[0] if wt else None, note)
        return out

    cached = functools.lru_cache(maxsize=16)(table)
    default = cached(DEFAULT_LEGALITY)
    out = []
    for const, sp in consts.items():
        st = default[sp.key]
        out.append(SpeciesInfo(key=sp.key, const=const, name=MS.species_name(const),
                               types=tuple(_type_name(t) for t in dict.fromkeys(sp.types)), dex=sp.id,
                               available=st.available, reason=st.reason, reason_code=st.reason_code))
    return SpeciesCatalog(out, cached)
