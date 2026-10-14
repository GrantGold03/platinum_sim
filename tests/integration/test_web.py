"""T059 (+T067/T068): web page and HTTP API (contracts/http-api.md) with FastAPI's TestClient.

The optimizer is replaced by a STUB runner (create_app(runner=...)). The stub writes real report
files through platsim.report.write_all from a SYNTHETIC EvaluationReport: its moves, abilities,
items, rates and commits are made-up placeholders ("synthetic_move_1", ...), not game facts. The
species keys it receives are the ones the API accepted.

Species availability is real: the catalogue is built from the availability ledger and the legality
validator's source rule (~35 s once per session). Game facts used here:
- Garchomp's name: pokeplatinum/res/pokemon/garchomp/data.json:132 ("name": "GARCHOMP").
- Munchlax exclusion: project rule src/platsim/availability/ledger.py:171 (EXCLUDED_SPECIES).
- The post-game-only species are derived from the ledger here (positive control: the set is non-empty).
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import re

import pytest
from fastapi.testclient import TestClient

from _web_helpers import RESULT_NAMES, StubRunner, _available_team, _wait
from platsim.legality.models import LegalityOptions
from platsim.web import app as webapp


def test_page_is_served(tmp_path, catalog):
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    for needle in ('id="search"', 'id="slots"', 'id="min-clear"', 'value="75"', 'id="seed"',
                   ">Optimize<", "/static/app.js", 'name="viewport"'):
        assert needle in r.text, needle
    assert 'id="show-excluded"' not in r.text  # 003 FR-003: excluded pokemon are always listed
    assert client.get("/static/app.js").status_code == 200
    assert "prefers-color-scheme: dark" in client.get("/static/style.css").text


def test_species_search(tmp_path, catalog, ledger):
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    res = client.get("/api/species", params={"q": "gar"}).json()
    assert len(res) <= 25
    gar = next(s for s in res if s["key"] == "garchomp")  # data.json:132 "GARCHOMP"
    assert gar["name"] == "Garchomp" and gar["available"] is True and "reason" not in gar
    assert set(gar) >= {"key", "name", "types", "available"}
    assert len(client.get("/api/species", params={"q": ""}).json()) == 25

    # 003 FR-008: Munchlax and Snorlax are usable (001's Munchlax exclusion is superseded).
    for key in ("munchlax", "snorlax"):
        m = client.get("/api/species", params={"q": key}).json()
        assert m and m[0]["key"] == key and m[0]["available"] is True, m[:1]
    # A crossed-out pokemon is hidden only when a caller asks for excluded=0.
    assert client.get("/api/species", params={"q": "bulbasaur", "excluded": 0}).json() == []

    # Post-game-only species, derived from the ledger: every acquisition entry is post_game.
    from platsim.availability.ledger import POST
    from platsim.web.species_catalog import ACQUIRE_KINDS

    phases: dict[str, set] = {}
    for c in ledger.entries:
        if c.entry.kind in ACQUIRE_KINDS:
            phases.setdefault(c.entry.subject, set()).add(c.phase)
    post_only = [s for s in catalog.species if phases.get(s.const) == {POST} and not s.available]
    assert post_only, "positive control: the ledger has post-game-only species"
    for s in post_only[:5]:
        hit = next(x for x in client.get("/api/species", params={"q": s.key}).json() if x["key"] == s.key)
        assert hit["available"] is False and "post-game" in hit["reason"].lower(), hit
    assert sum(1 for s in post_only if s.reason_code == "post_game") >= 1


ID_RE = re.compile(r"\b(FR|SC)-\d+")


def catalog_ledger_entries(catalog):
    from platsim.availability.ledger import build_ledger

    return build_ledger().entries


def test_reasons_are_plain_and_excluded_pokemon_always_listed(tmp_path, catalog):
    """003 US1 (FR-001–FR-006, SC-002): every match is listed, usable or crossed out, with a short
    plain reason; no requirement id and never the word "species"."""
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    golem = client.get("/api/species", params={"q": "golem"}).json()[0]  # Graveler -> Golem is EVO_TRADE
    assert golem["key"] == "golem" and golem["available"] is False
    assert "Graveler" in golem["reason"] and "trade" in golem["reason"]
    assert client.get("/api/species", params={"q": "golem", "trade_evolutions": 1}).json()[0]["available"] is True

    # Caterpie: dual-slot entries only; Bulbasaur: no entry at all (research R4). Both are "Unavailable in Platinum".
    for key in ("caterpie", "bulbasaur"):
        hit = client.get("/api/species", params={"q": key}).json()[0]
        assert hit["key"] == key and hit["available"] is False
        assert hit["reason"] == "Unavailable in Platinum" and hit["reason_code"] == "unavailable", hit

    assert ID_RE.search("needs a second cartridge, FR-005"), "positive control: the id pattern matches"
    for trade in (False, True):
        opts = LegalityOptions(allow_trade_evolutions=trade)
        for s in catalog.species:
            st = catalog.status(s, opts)
            assert st.available or st.reason, s.key
            for text in (st.reason or "", st.note or ""):
                assert not ID_RE.search(text) and "species" not in text.lower(), (s.key, text)


def test_full_name_search_returns_that_pokemon_first(catalog):
    """003 SC-002: searching a pokemon's full name returns it first, usable or not, under every rule
    combination the options allow (T020 extends the combinations)."""
    import itertools

    names = [f.name for f in dataclasses.fields(LegalityOptions) if f.name != "allow_egg_moves"]
    for values in itertools.product((False, True), repeat=len(names)):
        opts = LegalityOptions(**dict(zip(names, values)))
        for s in catalog.species:
            hits = catalog.search(s.name, options=opts)
            assert hits and hits[0].key == s.key, (s.name, [h.key for h in hits[:3]], opts)


def test_loading_and_error_texts_say_pokemon(tmp_path, catalog):
    holder = webapp.CatalogHolder()
    with pytest.raises(webapp.HTTPException) as e:
        holder.require()
    assert e.value.status_code == 503 and "Pokémon" in e.value.detail and "species" not in e.value.detail.lower()
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    team = _available_team(catalog)
    for body in ({"species": team[:5]}, {"species": team[:5] + ["not_a_mon"]}, {"species": "x"}):
        r = client.post("/api/jobs", json=body).json()
        texts = [r["detail"], *r.get("reasons", {}).values()]
        assert all("species" not in t.lower() and not ID_RE.search(t) for t in texts), texts


def test_post_validation(tmp_path, catalog):
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    team = _available_team(catalog)
    r = client.post("/api/jobs", json={"species": team[:5]})
    assert r.status_code == 422 and "exactly 6" in r.json()["detail"]
    r = client.post("/api/jobs", json={"species": team[:5] + ["golem"]})
    assert r.status_code == 422 and "golem" in r.json()["reasons"]
    r = client.post("/api/jobs", json={"species": team[:5] + ["not_a_species"]})
    assert r.status_code == 422 and r.json()["reasons"] == {"not_a_species": "unknown Pokémon"}
    r = client.post("/api/jobs", json={"species": team, "min_clear": 1.5})
    assert r.status_code == 422
    r = client.post("/api/jobs", json={"species": team, "budget": "nope"})
    assert r.status_code == 422
    assert not any(tmp_path.iterdir()), "an invalid request must not create a job"


def test_job_lifecycle_and_results(tmp_path, catalog):
    stub = StubRunner(block=True)
    client = TestClient(webapp.create_app(runner=stub, runs_dir=tmp_path, catalog=catalog))
    team = _available_team(catalog)
    r = client.post("/api/jobs", json={"species": team, "min_clear": 0.8, "seed": "fixed"})
    assert r.status_code == 201
    jid = r.json()["id"]
    assert stub.started.wait(10)
    job = _wait(client, jid, {"running"})
    for name in RESULT_NAMES:
        assert client.get(f"/api/jobs/{jid}/{name}").status_code == 409, name
    job = _wait(client, jid, {"running"})
    assert job["progress"]["stage"] == "screen" and job["progress"]["runs_done"] == 10
    assert job["progress"]["best_so_far"]["clear_rate"] == 0.5
    stub.release.set()
    job = _wait(client, jid, {"done", "failed"})
    assert job["status"] == "done", job
    assert job["species"] == team and job["options"] == {"min_clear": 0.8, "seed": "fixed", "budget": "standard",
                                                           "allow_egg_moves": False, "allow_trade_evolutions": False,
                                                           "allow_post_game_pokemon": False, "allow_post_game_items": False,
                                                           "allow_unobtainable_pokemon": False}
    req = stub.calls[0]
    assert req.species == tuple(team) and req.min_clear == 0.8 and req.seed == "fixed" and req.out_dir == tmp_path / jid
    assert req.legality == LegalityOptions()  # both optional rules off by default
    assert "table" not in job and len(job["team"]) == 6  # 002: shaped view replaces the CSV table
    assert all(len(m["moves"]) == 4 and all(mv["source"] for mv in m["moves"]) for m in job["team"])
    assert job["summary"]["verdict"] == "qualified" and job["summary"]["n_runs"] == 100
    for name in RESULT_NAMES:
        r = client.get(f"/api/jobs/{jid}/{name}")
        assert r.status_code == 200, name
        assert r.content == (tmp_path / jid / name).read_bytes()
    assert client.get(f"/api/jobs/{jid}/result.xlsx").headers["content-disposition"].startswith("attachment")
    assert json.loads((tmp_path / jid / "job.json").read_text())["status"] == "done"
    assert client.get("/api/jobs/job-20000101T000000Z-abcdef").status_code == 404
    assert client.get("/api/jobs/..%2F..%2Fetc").status_code == 404


def test_fifo_queue_two_jobs(tmp_path, catalog):
    stub = StubRunner(block=True)
    client = TestClient(webapp.create_app(runner=stub, runs_dir=tmp_path, catalog=catalog))
    team = _available_team(catalog)
    a = client.post("/api/jobs", json={"species": team, "seed": "a"}).json()["id"]
    b = client.post("/api/jobs", json={"species": list(reversed(team)), "seed": "b"}).json()["id"]
    assert stub.started.wait(10)
    _wait(client, a, {"running"})
    jb = client.get(f"/api/jobs/{b}").json()
    assert jb["status"] == "queued" and jb["queue_position"] == 1 and jb["running_job"] == a
    assert client.get(f"/api/jobs/{b}/result.csv").status_code == 409
    stub.release.set()
    assert _wait(client, a, {"done", "failed"})["status"] == "done"
    assert _wait(client, b, {"done", "failed"})["status"] == "done"
    assert [c.seed for c in stub.calls] == ["a", "b"]


def test_failed_runner_and_restart(tmp_path, catalog):
    def boom(req, progress=None):
        raise RuntimeError("synthetic optimizer failure")

    client = TestClient(webapp.create_app(runner=boom, runs_dir=tmp_path, catalog=catalog))
    jid = client.post("/api/jobs", json={"species": _available_team(catalog)}).json()["id"]
    job = _wait(client, jid, {"done", "failed"})
    assert job["status"] == "failed" and "synthetic optimizer failure" in job["error"]
    assert client.get(f"/api/jobs/{jid}/result.json").status_code == 409

    # Simulated restart: one job left "running", one "queued" by a previous server.
    runs = tmp_path / "restart"
    team = _available_team(catalog)
    for jid2, status in (("job-20260101T000000Z-aaaaaa", "running"), ("job-20260101T000001Z-bbbbbb", "queued")):
        (runs / jid2).mkdir(parents=True)
        (runs / jid2 / "job.json").write_text(json.dumps({
            "id": jid2, "status": status, "species": team, "options": {"min_clear": 0.75, "seed": "s", "budget": "standard"},
            "progress": {"stage": status, "runs_done": 0}, "result_paths": None, "error": None,
            "created": jid2[4:20]}))
    stub = StubRunner()
    client = TestClient(webapp.create_app(runner=stub, runs_dir=runs, catalog=catalog))
    j1 = client.get("/api/jobs/job-20260101T000000Z-aaaaaa").json()
    assert j1["status"] == "failed" and "restart" in j1["error"]
    assert _wait(client, "job-20260101T000001Z-bbbbbb", {"done", "failed"})["status"] == "done"
    assert len(stub.calls) == 1


def test_serve_binds_localhost(tmp_path, monkeypatch):
    import uvicorn

    from platsim import cli

    seen = {}
    monkeypatch.setattr(webapp, "create_app", lambda **kw: ("app", kw))
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(app=app, **kw))
    assert cli.main(["serve", "--port", "8765", "--runs-dir", str(tmp_path)]) == 0
    assert seen["host"] == "127.0.0.1" and seen["port"] == 8765
    assert seen["app"][1]["runs_dir"] == tmp_path
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["serve", "--host", "0.0.0.0"])


def test_legality_options_page_search_and_jobs(tmp_path, catalog):
    """Two unchecked checkboxes; species search reflects trade evolutions; POST fields reach the
    optimizer request (OptimizeRequest.legality) and the job's options."""
    stub = StubRunner()
    client = TestClient(webapp.create_app(runner=stub, runs_dir=tmp_path, catalog=catalog))
    page = client.get("/").text
    rule_ids = ("allow-egg-moves", "allow-trade-evolutions", "allow-post-game-pokemon", "allow-post-game-items",
                "allow-unobtainable-pokemon")
    assert page.count('type="checkbox"') == len(rule_ids)
    for cid in rule_ids:
        tag = page[page.index(f'id="{cid}"') - 7:page.index(f'id="{cid}"') + 60]
        assert 'type="checkbox"' in tag and "checked" not in tag, tag
    js = client.get("/static/app.js").text
    assert "allow_egg_moves" in js and "allow_trade_evolutions" in js and "\"trade_evolutions\"" in js and "ruleQuery" in js

    off = client.get("/api/species", params={"q": "alakazam"}).json()
    assert off[0]["key"] == "alakazam" and off[0]["available"] is False and off[0]["reason_code"] == "trade_evolution"
    on = client.get("/api/species", params={"q": "alakazam", "trade_evolutions": 1}).json()
    assert on[0]["available"] is True and on[0]["trade_evolution"] is True
    assert client.get("/api/species", params={"q": "alakazam", "excluded": 0}).json() == []
    gar = client.get("/api/species", params={"q": "garchomp", "trade_evolutions": 1}).json()[0]  # control
    assert gar["available"] is True and "trade_evolution" not in gar

    team = _available_team(catalog)[:5] + ["alakazam"]
    r = client.post("/api/jobs", json={"species": team})
    assert r.status_code == 422 and "alakazam" in r.json()["reasons"]
    r = client.post("/api/jobs", json={"species": team, "allow_trade_evolutions": "yes"})
    assert r.status_code == 422 and "allow_trade_evolutions" in r.json()["detail"]
    assert not any(tmp_path.iterdir())
    r = client.post("/api/jobs", json={"species": team, "allow_trade_evolutions": True, "allow_egg_moves": True})
    assert r.status_code == 201, r.json()
    job = _wait(client, r.json()["id"], {"done", "failed"})
    assert job["status"] == "done", job
    assert job["options"]["allow_egg_moves"] is True and job["options"]["allow_trade_evolutions"] is True
    assert stub.calls[-1].legality == LegalityOptions(allow_egg_moves=True, allow_trade_evolutions=True)

    # 003: the three new rules (FR-010, FR-010a, FR-011).
    for k in ("allow_post_game_pokemon", "allow_post_game_items", "allow_unobtainable_pokemon"):
        r = client.post("/api/jobs", json={"species": _available_team(catalog), k: 1})
        assert r.status_code == 422 and k in r.json()["detail"], k
    bulba = client.get("/api/species", params={"q": "bulbasaur"}).json()[0]
    assert bulba["available"] is False
    assert client.get("/api/species", params={"q": "bulbasaur", "unobtainable_pokemon": 1}).json()[0]["available"]
    from platsim.availability.ledger import POST

    acq = ("wild_slot", "gift", "egg", "static", "roamer", "npc_trade")
    phases: dict[str, set] = {}
    for c in catalog_ledger_entries(catalog):
        if c.entry.kind in acq:
            phases.setdefault(c.entry.subject, set()).add(c.phase)
    x = next(s for s in catalog.species if phases.get(s.const) == {POST} and not s.available
             and catalog.status(s, LegalityOptions(allow_post_game_pokemon=True)).available)
    assert client.get("/api/species", params={"q": x.key, "post_game_pokemon": 1}).json()[0]["available"], x.key
    r = client.post("/api/jobs", json={"species": _available_team(catalog)[:5] + [x.key], "allow_post_game_pokemon": True})
    assert r.status_code == 201, r.json()
    job = _wait(client, r.json()["id"], {"done", "failed"})
    assert job["options"]["allow_post_game_pokemon"] is True
    assert stub.calls[-1].legality == LegalityOptions(allow_post_game_pokemon=True)


def test_budget_and_species_icons(tmp_path, catalog):
    """002 T015: species items carry their icon URL (FR-004); the chosen budget reaches the job (FR-005)."""
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    gar = next(s for s in client.get("/api/species", params={"q": "garch"}).json() if s["key"] == "garchomp")
    assert gar["sprite_icon"] == "/api/sprites/garchomp/icon.png"
    assert client.get(gar["sprite_icon"]).status_code == 200
    team = _available_team(catalog)
    a = client.post("/api/jobs", json={"species": team, "budget": "thorough"}).json()["id"]
    b = client.post("/api/jobs", json={"species": team}).json()["id"]
    for jid, budget in ((a, "thorough"), (b, "standard")):
        _wait(client, jid, {"done", "failed"})
        assert json.loads((tmp_path / jid / "job.json").read_text())["options"]["budget"] == budget


def test_running_view_fields(tmp_path, catalog):
    """002 T022 (thread mode): elapsed_s / eta_s / stage_started / platsim_version while running;
    stage_started survives same-stage updates (P3-01, P4-03); verdict stored when done (P3-02)."""
    import importlib.metadata
    import time

    import _fake_runners

    _fake_runners.HOLD.clear()
    client = TestClient(webapp.create_app(runner=_fake_runners.two_beat_runner, runs_dir=tmp_path, catalog=catalog))
    jid = client.post("/api/jobs", json={"species": _available_team(catalog)}).json()["id"]
    first = None
    end = time.monotonic() + 10
    while time.monotonic() < end:  # first "screen" update (runs_done 1)
        job = client.get(f"/api/jobs/{jid}").json()
        if job["progress"].get("stage") == "screen" and job["progress"].get("runs_done") == 1:
            first = job
            break
        time.sleep(0.02)
    assert first, "never saw the first screen update"
    job = _wait(client, jid, {"running"})
    end = time.monotonic() + 10
    while time.monotonic() < end and job["progress"].get("runs_done") != 2:
        time.sleep(0.05)
        job = client.get(f"/api/jobs/{jid}").json()
    assert job["progress"]["runs_done"] == 2
    assert job["progress"]["stage_started"] == first["progress"]["stage_started"]  # carried forward, not reset
    assert "eta_s" in job and job["elapsed_s"] > 0
    assert job["platsim_version"] == importlib.metadata.version("platsim")
    _fake_runners.HOLD.set()
    done = _wait(client, jid, {"done", "failed"})
    assert done["status"] == "done", done
    stored = json.loads((tmp_path / jid / "job.json").read_text())
    assert stored["verdict"] == "qualified"
    assert done["elapsed_s"] == client.get(f"/api/jobs/{jid}").json()["elapsed_s"]  # fixed once finished


def test_job_list_labels_and_cap(tmp_path, catalog):
    """002 T030: GET /api/jobs newest first with labels (FR-015); failed / cancelled views (FR-016);
    the list is capped at 50 (SC-005)."""
    import time

    import _fake_runners
    from _web_helpers import copy_fixture_run

    _fake_runners.HOLD.clear()
    runs = tmp_path / "a"
    client = TestClient(webapp.create_app(runner=_fake_runners.seed_switch_runner, isolate=False, runs_dir=runs,
                                          catalog=catalog))
    team = _available_team(catalog)
    ids = {}
    for seed in ("ok1", "ok2", "fail"):
        ids[seed] = client.post("/api/jobs", json={"species": team, "seed": seed}).json()["id"]
        _wait(client, ids[seed], {"done", "failed"})
        time.sleep(1.05)  # distinct `created` seconds keep "newest first" unambiguous
    ids["hold"] = client.post("/api/jobs", json={"species": team, "seed": "hold"}).json()["id"]
    _wait(client, ids["hold"], {"running"})
    ids["queued"] = client.post("/api/jobs", json={"species": team, "seed": "q"}).json()["id"]
    r = client.post(f"/api/jobs/{ids['queued']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    _fake_runners.HOLD.set()
    _wait(client, ids["hold"], {"done", "failed"})

    listed = client.get("/api/jobs").json()
    order = [j["id"] for j in listed]
    assert order == [ids["queued"], ids["hold"], ids["fail"], ids["ok2"], ids["ok1"]]
    by_id = {j["id"]: j for j in listed}
    assert by_id[ids["ok1"]]["label"].endswith("· qualified")
    assert by_id[ids["fail"]]["label"].endswith("· failed")
    assert by_id[ids["queued"]]["label"].endswith("· cancelled")
    names = [catalog.get(k).name for k in team]
    assert by_id[ids["ok1"]]["label"].startswith(", ".join(names))
    failed = client.get(f"/api/jobs/{ids['fail']}").json()
    assert "synthetic failure" in failed["error"] and "team" not in failed
    assert client.get(f"/api/jobs/{ids['queued']}").json()["error"] == "cancelled by user"

    # Cap: 51 finished copies of the fixture run, each in a folder named by its id.
    big = tmp_path / "big"
    for i in range(51):
        copy_fixture_run(big, job_id=f"job-20261008T{i // 60:02d}{i % 60:02d}00Z-{i:06x}",
                         created=f"2026-10-08T{i // 60:02d}:{i % 60:02d}:00Z")
    listed = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=big, catalog=catalog)).get("/api/jobs").json()
    assert len(listed) == 50 and listed[0]["id"] == "job-20261008T005000Z-000032"
    assert all(j["label"].endswith("· qualified") for j in listed)


def test_rerendered_run_is_listed_and_labelled(tmp_path, catalog):
    """003 T042a (SC-005): a re-rendered copy of an older run is listed, says "(re-rendered)", and its
    "obtained from" text has no internal code. The original run is untouched."""
    from _web_helpers import copy_fixture_run

    from platsim.report.rerender import rerender

    orig_id = copy_fixture_run(tmp_path)
    orig = tmp_path / orig_id
    before = {p.name: p.read_bytes() for p in orig.iterdir() if p.is_file()}
    new_id = orig_id[:-6] + "abc003"
    rerender(orig, tmp_path / new_id)
    job = json.loads((orig / "job.json").read_text())
    job.update(id=new_id, rerendered_from=orig_id,
               result_paths={k: str(tmp_path / new_id / pathlib.Path(v).name) for k, v in job["result_paths"].items()})
    (tmp_path / new_id / "job.json").write_text(json.dumps(job))
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    labels = {j["id"]: j["label"] for j in client.get("/api/jobs").json()}
    assert labels[new_id].endswith("(re-rendered)") and not labels[orig_id].endswith("(re-rendered)")
    team = client.get(f"/api/jobs/{new_id}").json()["team"]
    assert team and not any(re.search(r"EVO_|[A-Z]{2,}_[A-Z_]{2,}", m["obtained_from"]) for m in team), team
    old_team = client.get(f"/api/jobs/{orig_id}").json()["team"]
    assert any("EVO_" in m["obtained_from"] for m in old_team), "positive control: the original keeps its old text"
    assert {p.name: p.read_bytes() for p in orig.iterdir() if p.is_file()} == before


def test_mixed_starters_refused_before_a_job(tmp_path, catalog):
    """004 FR-004: two starter lines cannot both come from one game (starter choice + breeding)."""
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    others = ["garchomp", "gyarados", "lucario", "staraptor"]
    r = client.post("/api/jobs", json={"species": ["torterra", "infernape", *others]})
    assert r.status_code == 422, r.json()
    body = r.json()
    assert set(body["reasons"]) == {"torterra", "infernape"}
    assert "only one starter" in body["detail"] and "species" not in body["detail"].lower()
    assert not any(tmp_path.iterdir()), "an invalid request must not create a job"
    # positive control: one starter line, several members
    r = client.post("/api/jobs", json={"species": ["infernape", "monferno", *others]})
    assert r.status_code == 201, r.json()


def test_mixed_starters_allowed_with_second_game_option(tmp_path, catalog):
    """005 FR-003: with "Pokémon unobtainable in one Platinum game" on, a mixed team starts a job;
    without it the 004 refusal stands (test_mixed_starters_refused_before_a_job)."""
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    team = ["torterra", "infernape", "rampardos", "bastiodon", "garchomp", "gyarados"]
    r = client.post("/api/jobs", json={"species": team, "allow_unobtainable_pokemon": True})
    assert r.status_code == 201, r.json()
    r = client.post("/api/jobs", json={"species": team})
    assert r.status_code == 422 and set(r.json()["reasons"]) == {"torterra", "infernape", "rampardos", "bastiodon"}


def test_unobtainable_option_wording(tmp_path, catalog):
    """005 FR-005: the checkbox and the results summary name "one Platinum game"; the old label is gone."""
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    page, js = client.get("/").text, client.get("/static/app.js").text
    assert "Allow Pokémon unobtainable in one Platinum game" in " ".join(page.split())
    assert '"Pokémon unobtainable in one Platinum game"' in js
    assert "unobtainable in Platinum\n" not in page and '"Pokémon unobtainable in Platinum"' not in js


def test_required_hm_nobody_can_learn_is_refused(tmp_path, catalog):
    """006 FR-005: refused before a job, naming the HM; bad values are 422 too."""
    client = TestClient(webapp.create_app(runner=StubRunner(), runs_dir=tmp_path, catalog=catalog))
    six = ["garchomp"] * 6
    r = client.post("/api/jobs", json={"species": six, "required_hms": ["fly"]})
    assert r.status_code == 422, r.json()
    assert r.json()["reasons"] == {"fly": "No team member can learn Fly"}
    for bad in (["dig"], "fly", [3]):
        assert client.post("/api/jobs", json={"species": six, "required_hms": bad}).status_code == 422, bad
    assert not any(tmp_path.iterdir()), "an invalid request must not create a job"
    # positive control: Surf is learnable by Garchomp, so the job starts
    assert client.post("/api/jobs", json={"species": six, "required_hms": ["surf"]}).status_code == 201


def test_required_hms_web(tmp_path, catalog):
    """006 US3: /api/hms lists the HMs from the decomp; step 3 is in the page; a job keeps them."""
    stub = StubRunner()
    client = TestClient(webapp.create_app(runner=stub, runs_dir=tmp_path, catalog=catalog))
    hms = client.get("/api/hms").json()
    assert [h["key"] for h in hms] == ["cut", "fly", "surf", "strength", "defog", "rock_smash", "waterfall", "rock_climb"]
    assert hms[2] == {"key": "surf", "name": "Surf", "item": "HM03"}
    page = client.get("/").text
    i1, i2, i3, i4 = (page.index(t) for t in ("1. Choose Pokémon", "2. Team", "3. Required HMs", "4. Optimize"))
    assert i1 < i2 < i3 < i4 and 'id="hm-step"' in page
    six = ["garchomp"] * 5 + ["gyarados"]  # Gyarados learns Waterfall (Garchomp can't: refused otherwise)
    r = client.post("/api/jobs", json={"species": six, "required_hms": ["Waterfall", "surf"]})
    assert r.status_code == 201, r.json()
    job = json.loads((tmp_path / r.json()["id"] / "job.json").read_text())
    assert job["options"]["required_hms"] == ["surf", "waterfall"]
    # no HMs: the stored options have no required_hms key at all (FR-009)
    r = client.post("/api/jobs", json={"species": ["garchomp"] * 6})
    assert "required_hms" not in json.loads((tmp_path / r.json()["id"] / "job.json").read_text())["options"]
