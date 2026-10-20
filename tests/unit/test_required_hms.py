"""006: required HMs - the HM table, refusal, placement, fingerprint and provenance.

Game facts (decomp): each HM item's teachesMove (res/items, read by decomp.items.tm_moves) gives
HM01 Cut ... HM08 Rock Climb. Learnability is the engine's own MS.sources (no hand-typed data).
"""

import pytest

from platsim.legality import movesources as MS
from platsim.optimizer.api import InvalidRequest, OptimizeRequest

SIX = ("infernape", "garchomp", "gyarados", "lucario", "chatot", "staraptor")


def test_hm_table_from_decomp():
    hms = MS.hm_moves()
    assert [h.item for h in hms] == [f"HM0{i}" for i in range(1, 9)]
    assert (hms[0].key, hms[-1].key) == ("cut", "rock_climb")
    assert all(h.src for h in hms)
    assert MS.hm_key("Rock Smash") == MS.hm_key("rock_smash") == MS.hm_key("HM06") == "rock_smash"
    with pytest.raises(KeyError):
        MS.hm_key("dig")  # a TM move, not an HM


def test_request_normalises_required_hms():
    r = OptimizeRequest(species=SIX, required_hms=("Waterfall", "surf", "SURF"))
    assert r.required_hms == ("surf", "waterfall")
    assert OptimizeRequest(species=SIX).required_hms == ()
    with pytest.raises(InvalidRequest):
        OptimizeRequest(species=SIX, required_hms=("dig",))


# --- US2: refusal ------------------------------------------------------------------------------

GARCHOMPS = ["SPECIES_GARCHOMP"] * 6


def test_unlearnable_moves(ledger):
    assert MS.unlearnable_moves(GARCHOMPS, ["fly"], ledger) == ["fly"]
    assert MS.unlearnable_moves(GARCHOMPS[:5] + ["SPECIES_STARAPTOR"], ["fly"], ledger) == []  # control
    assert MS.unlearnable_moves(GARCHOMPS, ["waterfall", "fly", "defog"], ledger) == ["fly", "defog", "waterfall"]  # HM02, HM05, HM07
    assert MS.unlearnable_moves(GARCHOMPS, ["surf"], ledger) == []  # Garchomp learns Surf


def test_unlearnable_follows_the_ledger_options(ledger, monkeypatch):
    """Observed 2026-10-13: no legality option changes any of the 188 default species' HM
    learnability. So the option path is shown with a stand-in rule: a source that exists only in
    the option-on view."""
    from platsim.legality.models import LegalityOptions

    on = ledger.with_options(LegalityOptions(allow_post_game_items=True))
    real = MS.sources
    monkeypatch.setattr(MS, "sources", lambda c, m, lv, led, option=None:
                        real(c, m, lv, led, option) or (["stand-in"] if m == "MOVE_FLY" and MS.options_of(led).allow_post_game_items else []))
    assert MS.unlearnable_moves(GARCHOMPS, ["fly"], ledger) == ["fly"]
    assert MS.unlearnable_moves(GARCHOMPS, ["fly"], on) == []


def test_optimizer_refuses_before_any_battle(monkeypatch):
    from platsim.optimizer import run as R
    from platsim.sim import pool

    def no_pool(*a, **k):
        raise AssertionError("a WorkerPool was started for an impossible request")
    monkeypatch.setattr(pool, "WorkerPool", no_pool)  # run.py imports it inside run_optimization
    with pytest.raises(InvalidRequest) as e:
        R.run_optimization(OptimizeRequest(species=("garchomp",) * 6, required_hms=("fly", "surf"), budget="quick"))
    assert e.value.reasons == {"fly": "No team member can learn Fly"}


# --- US1: placement ---------------------------------------------------------------------------

TEAM6 = ["SPECIES_GARCHOMP", "SPECIES_GYARADOS", "SPECIES_STARAPTOR", "SPECIES_LUCARIO", "SPECIES_INFERNAPE",
         "SPECIES_CHATOT"]


@pytest.fixture(scope="module")
def specs(ledger):
    """Each member's best attack moveset (the optimizer's own baseline)."""
    from platsim.optimizer import candidates as C
    from platsim.optimizer import resources as R

    out, ranked = [], []
    for c in TEAM6:
        v = C.variants(c, ledger)[0]
        mc = C.member_candidates(c, v, 57, ledger, team=tuple(TEAM6))
        out.append(R.MemberSpec(c, v.key, mc.movesets[0]))
        ranked.append(mc.ranked)
    fixed = R.repair(tuple(out), [57] * 6, ledger, ranked)  # single-copy TMs: as the optimizer does
    assert not isinstance(fixed, R.Refusal), fixed
    return fixed[0]


def _carriers(real, move_key):
    return [i for i, b in enumerate(real.team.builds) if any(m.move == move_key for m in b.moves)]


def test_realize_places_a_missing_hm(ledger, specs):
    from platsim.legality.validator import validate
    from platsim.optimizer import candidates as C
    from platsim.optimizer import resources as R

    levels = [57] * 6
    base = R.realize(specs, levels, ledger)
    assert not isinstance(base, R.Refusal) and not _carriers(base, "surf"), "Surf already in a baseline moveset"
    real = R.realize(specs, levels, ledger, required_hms=("surf",))
    assert not isinstance(real, R.Refusal)
    assert len(_carriers(real, "surf")) == 1
    # expected carrier, computed here: among Surf learners, the member whose weakest attack is worth least
    learners = [i for i, s in enumerate(specs) if MS.sources(s.species, "MOVE_SURF", 57, ledger)]
    cost = {i: min(sum(C.move_value(specs[i].species, m)) for m in specs[i].moves) for i in learners}
    assert _carriers(real, "surf") == [min(cost, key=lambda i: (cost[i], i))]
    assert validate(real.team, ledger, required_hms=("surf",)) == []
    # positive control: without the requirement realize is unchanged
    assert R.realize(specs, levels, ledger).team.to_dict() == base.team.to_dict()


def test_several_hms_and_a_status_hm(ledger, specs):
    from platsim.optimizer import resources as R

    real = R.realize(specs, [57] * 6, ledger, required_hms=("surf", "waterfall", "defog"))
    assert not isinstance(real, R.Refusal)
    for k in ("surf", "waterfall", "defog"):  # Defog is a status move: never in the search pool
        assert _carriers(real, k), k


def test_unplaceable_hm_is_a_refusal(ledger, specs):
    from platsim.optimizer import resources as R

    no_fly = tuple(s for s in specs if s.species not in ("SPECIES_STARAPTOR", "SPECIES_CHATOT"))
    if any(MS.sources(s.species, "MOVE_FLY", 57, ledger) for s in no_fly):
        pytest.skip("another member learns Fly")
    r = R.realize(no_fly, [57] * len(no_fly), ledger, required_hms=("fly",))
    assert isinstance(r, R.Refusal) and "Fly" in r.reason


# --- US1: fingerprint and provenance ------------------------------------------------------------

T001_FINGERPRINT = {"species": ["SPECIES_INFERNAPE", "SPECIES_GARCHOMP", "SPECIES_GYARADOS", "SPECIES_LUCARIO",
                                "SPECIES_CHATOT", "SPECIES_STARAPTOR"], "min_clear": 0.75, "seed": "default",
                    "budget": "standard", "legality_options": {"allow_egg_moves": False, "allow_trade_evolutions": False},
                    "state_version": 4}


def test_fingerprint_default_unchanged_and_hms_included(ledger):
    from platsim.optimizer import candidates as C
    from platsim.optimizer.run import default_out_dir, job_fingerprint

    req = OptimizeRequest(species=SIX)
    consts = C.resolve_species(req.species, ledger)
    assert job_fingerprint(consts, req) == T001_FINGERPRINT  # recorded at T001 (validation-log.md)
    hm = job_fingerprint(consts, OptimizeRequest(species=SIX, required_hms=("surf",)))
    assert hm["required_hms"] == ["surf"] and default_out_dir(hm) != default_out_dir(T001_FINGERPRINT)
