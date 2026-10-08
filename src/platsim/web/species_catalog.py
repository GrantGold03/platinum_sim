"""Species list for the web page (T067): display names, types, and pre-Champion availability.

Availability is the legality validator's rule, not a second copy of it: a species is available iff
`legality.movesources.source_options(SPECIES_*, ledger)` is non-empty, which is exactly the check
behind the validator's SPECIES_UNAVAILABLE / SPECIES_TRADE_EVOLUTION violations. Everything here is
read from the availability ledger and the decomp species data; nothing is typed by hand.

For an excluded species the catalogue explains why, in this order (several may apply):
- `excluded`: a project rule (ledger.EXCLUDED_SPECIES, e.g. Munchlax, spec FR-006a);
- `trade_evolution`: only reachable by trade evolution (FR-005);
- `post_game`: its encounters are only reachable after the Champion (ledger phase post_game);
- `national_dex`: its encounters need the National Dex (excluded, FR-003a);
- `unobtainable`: event-only / other-cartridge encounters (ledger phase unobtainable);
- `pre_evolution_unavailable`: no encounter of its own and its pre-evolution is unavailable;
- `no_source`: no encounter, gift, trade, egg or evolution source in the game data at all.

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

import re
from dataclasses import dataclass

from platsim.optimizer.api import InvalidRequest

ACQUIRE_KINDS = ("wild_slot", "gift", "egg", "static", "roamer", "npc_trade")

REASON_TEXT = {
    "excluded": "excluded by project rule (too costly to obtain, spec FR-006a)",
    "trade_evolution": "trade evolution from {pre} (needs a second cartridge, FR-005; allowed only with the "
                       "trade-evolutions option)",
    "trade_evolution_unavailable": "trade evolution from {pre}; trade evolutions are allowed, but {missing}",
    "post_game": "post-game only ({where})",
    "national_dex": "needs the National Dex (not allowed, FR-003a)",
    "unobtainable": "event-only or needs another cartridge",
    "pre_evolution_unavailable": "evolves from {pre}, which is not available ({why})",
    "no_source": "not obtainable in Platinum (no wild, gift, trade, egg or evolution source)",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _type_name(t: str) -> str:
    return t.removeprefix("TYPE_").capitalize()


@dataclass(frozen=True)
class SpeciesInfo:
    key: str  # data/generated key, e.g. "garchomp"
    const: str  # SPECIES_GARCHOMP
    name: str  # display name, e.g. "Garchomp"
    types: tuple[str, ...]
    dex: int
    available: bool
    reason: str | None = None
    reason_code: str | None = None
    # The same three fields with allow_trade_evolutions on, and whether only a trade evolution makes it available.
    available_trade: bool | None = None
    reason_trade: str | None = None
    reason_code_trade: str | None = None
    trade_evolution: bool = False

    def status(self, allow_trade_evolutions: bool = False) -> tuple[bool, str | None, str | None]:
        if allow_trade_evolutions and self.available_trade is not None:
            return self.available_trade, self.reason_trade, self.reason_code_trade
        return self.available, self.reason, self.reason_code

    def to_json(self, allow_trade_evolutions: bool = False) -> dict:
        available, reason, code = self.status(allow_trade_evolutions)
        d = {"key": self.key, "name": self.name, "types": list(self.types), "available": available}
        if not available:
            d["reason"] = reason
            d["reason_code"] = code
        if allow_trade_evolutions and available and self.trade_evolution:
            d["trade_evolution"] = True
            d["note"] = "trade evolution: needs a second cartridge for the trade"
        return d


class SpeciesCatalog:
    def __init__(self, species: list[SpeciesInfo]):
        self.species = sorted(species, key=lambda s: s.dex)
        self._by_norm: dict[str, SpeciesInfo] = {}
        for s in self.species:
            self._by_norm[_norm(s.key)] = s
            self._by_norm.setdefault(_norm(s.name), s)

    def get(self, key_or_name: str) -> SpeciesInfo | None:
        return self._by_norm.get(_norm(key_or_name or ""))

    def search(self, q: str, include_excluded: bool = True, limit: int = 25,
               allow_trade_evolutions: bool = False) -> list[SpeciesInfo]:
        """Prefix matches on name or key first, then substring matches; dex order within each."""
        nq = _norm(q or "")
        pool = [s for s in self.species if include_excluded or s.status(allow_trade_evolutions)[0]]
        if not nq:
            return pool[:limit]
        prefix = [s for s in pool if _norm(s.name).startswith(nq) or _norm(s.key).startswith(nq)]
        seen = {s.key for s in prefix}
        sub = [s for s in pool if s.key not in seen and (nq in _norm(s.name) or nq in _norm(s.key))]
        return (prefix + sub)[:limit]

    def resolve_team(self, species: object, allow_trade_evolutions: bool = False) -> tuple[str, ...]:
        """Validate a submitted team; returns the six keys or raises InvalidRequest with
        per-species reasons (keyed by the submitted value)."""
        if not isinstance(species, list) or not all(isinstance(x, str) for x in species):
            raise InvalidRequest("species must be a list of six species keys")
        reasons: dict[str, str] = {}
        keys = []
        for x in species:
            info = self.get(x)
            if info is None:
                reasons[x] = "unknown species"
            elif not info.status(allow_trade_evolutions)[0]:
                reasons[x] = f"{info.name}: {info.status(allow_trade_evolutions)[1]}"
            else:
                keys.append(info.key)
        if len(species) != 6:
            raise InvalidRequest(f"exactly 6 species are required, got {len(species)}", reasons)
        if reasons:
            raise InvalidRequest("some species cannot be used: " + "; ".join(f"{k}: {v}" for k, v in reasons.items()),
                                 reasons)
        return tuple(keys)


def build_catalog(ledger=None) -> SpeciesCatalog:
    from platsim.availability import ledger as L
    from platsim.legality import movesources as MS
    from platsim.legality.models import LegalityOptions

    base = ledger or L.build_ledger()
    led = base.with_options(LegalityOptions())
    trade_led = base.with_options(LegalityOptions(allow_trade_evolutions=True))
    consts = MS.by_constant()
    preds = MS._preds()
    by_subject: dict[str, list] = {}
    for c in led.entries:
        if c.entry.kind in ACQUIRE_KINDS:
            by_subject.setdefault(c.entry.subject, []).append(c)

    memo: dict[str, tuple[str, str] | None] = {}

    def why(const: str, depth: int = 0) -> tuple[str, str] | None:
        """(code, text) for an unavailable species, None if available."""
        if const in memo:
            return memo[const]
        if MS.source_options(const, led):
            memo[const] = None
            return None
        memo[const] = ("no_source", REASON_TEXT["no_source"])  # cycle guard
        found: list[tuple[str, str]] = []
        if const in L.EXCLUDED_SPECIES:
            found.append(("excluded", REASON_TEXT["excluded"]))
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
        if any(c.phase == L.NEVER for c in entries) and const not in L.EXCLUDED_SPECIES:
            found.append(("unobtainable", REASON_TEXT["unobtainable"]))
        if not found:
            for p, ev in preds.get(const, []):
                if ev.method in MS.TRADE_METHODS or depth > 4:
                    continue
                pw = why(p, depth + 1)
                if pw is not None:
                    found.append(("pre_evolution_unavailable", REASON_TEXT["pre_evolution_unavailable"].format(
                        pre=MS.species_name(p), why=pw[1])))
                    break
        if not found:
            found.append(("no_source", REASON_TEXT["no_source"]))
        res = (found[0][0], "; ".join(t for _, t in found))
        memo[const] = res
        return res

    def why_trade(const: str, w: tuple[str, str] | None) -> tuple[str, str] | None:
        """(code, text) with trade evolutions allowed; None if available."""
        if w is None or MS.source_options(const, trade_led):
            return None
        trade = [(p, ev) for p, ev in preds.get(const, []) if ev.method in MS.TRADE_METHODS]
        if not trade:
            return w  # nothing trade-related: same reason as without the option
        p, ev = trade[0]
        missing = ([f"{MS.species_name(p)} is not available"] if not MS.source_options(p, trade_led) else []) + \
                  ([f"{ev.param} has no pre-Champion copy"] if isinstance(ev.param, str) and led.item_copies(ev.param) == 0
                   else [])
        return ("trade_evolution", REASON_TEXT["trade_evolution_unavailable"].format(
            pre=MS.species_name(p), missing="; ".join(missing) or "no pre-Champion path reaches it"))

    out = []
    for const, sp in consts.items():
        w = why(const)
        wt = why_trade(const, w)
        out.append(SpeciesInfo(key=sp.key, const=const, name=MS.species_name(const),
                               types=tuple(_type_name(t) for t in dict.fromkeys(sp.types)), dex=sp.id,
                               available=w is None, reason=w[1] if w else None, reason_code=w[0] if w else None,
                               available_trade=wt is None, reason_trade=wt[1] if wt else None,
                               reason_code_trade=wt[0] if wt else None, trade_evolution=w is not None and wt is None))
    return SpeciesCatalog(out)
