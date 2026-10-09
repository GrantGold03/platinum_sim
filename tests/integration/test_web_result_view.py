"""002 T007: the result view of a finished job (data-model ResultView, spec US1).

Uses the frozen real run in tests/fixtures/web_final_defaults (runs/final-defaults, 2026-10-08).
Values asserted below were read from its result.json / result.csv:
- expected_avg_final_level 58.227..., final_level_gap_max 4.0, clear_rate 0.8645 over 2000 runs.
- per_battle cynthia: rate 0.8688..., 1990 battles.
- Slot 3 luxray ABILITY_RIVALRY (tie_default); decomp luxray abilities [RIVALRY, INTIMIDATE].
- Slot 6 gardevoir tie_default; slot 1 infernape Blaze (single_ability).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from _web_helpers import FIXTURE_DIR, FIXTURE_ID, RESULT_NAMES, make_app

SUMMARY_KEYS = {"verdict", "clear_rate", "clear_ci95", "n_runs", "avg_final_level", "level_gap", "threshold",
                "budget", "legality_options", "warnings", "no_qualifying", "platsim_version"}
HIDDEN_TEAM_KEYS = {"nature", "ivs", "evs", "ability_choice", "held_item_source"}


def test_result_view(fixture_runs_dir, catalog):
    client = TestClient(make_app(fixture_runs_dir, catalog))
    job = client.get(f"/api/jobs/{FIXTURE_ID}").json()
    assert job["status"] == "done"

    s = job["summary"]
    assert set(s) == SUMMARY_KEYS
    assert s["verdict"] == "qualified" and s["platsim_version"] is None
    assert abs(s["avg_final_level"] - 58.227) < 0.001 and s["level_gap"] == 4.0
    assert s["n_runs"] == 2000 and s["budget"] == "standard" and s["threshold"] == 0.75

    pt = job["per_trainer"]
    assert [p["trainer"] for p in pt] == ["aaron", "bertha", "flint", "lucian", "cynthia"]
    assert abs(pt[-1]["rate"] - 0.8688) < 0.0001 and pt[-1]["battles"] == 1990 and pt[-1]["label"] == "Cynthia"

    team = job["team"]
    assert len(team) == 6
    assert team[0]["ability"] == "Blaze"
    assert team[2]["species_key"] == "luxray"
    assert team[2]["ability"] == "Rivalry/Intimidate (no significant difference)"
    assert team[5]["ability"].endswith("(no significant difference)")
    assert team[0]["sprite"] == "/api/sprites/infernape/front.png"
    for m in team:
        assert not HIDDEN_TEAM_KEYS & set(m), m
        assert len(m["moves"]) == 4 and all(mv["name"] and mv["source"] for mv in m["moves"])
    assert "table" not in job

    assert set(job["downloads"]) == set(RESULT_NAMES)
    for name in RESULT_NAMES:
        r = client.get(f"/api/jobs/{FIXTURE_ID}/{name}")
        assert r.status_code == 200 and r.content == (FIXTURE_DIR / name).read_bytes(), name


def test_result_view_older_run_without_per_battle(tmp_path, catalog):
    from _web_helpers import copy_fixture_run

    jid = copy_fixture_run(tmp_path, drop_keys=("per_battle",))
    job = TestClient(make_app(tmp_path, catalog)).get(f"/api/jobs/{jid}").json()
    assert job["per_trainer"] == [] and job["summary"]["verdict"] == "qualified"
