"""002 T020: the ETA from per-stage timing history (research R2, src/platsim/web/eta.py)."""

from __future__ import annotations

import json

from platsim.pins import REPO_ROOT
from platsim.web import eta


def _state(d, budget, timing):
    d.mkdir(parents=True)
    (d / "state.json").write_text(json.dumps({"fingerprint": {"budget": budget}, "timing": timing}))


def test_history_and_eta(tmp_path):
    _state(tmp_path / "a", "standard", {"calibrate": 10, "ability_screen": 20, "screen": 100, "level_search": 1000,
                                         "confirm": 2000, "total_s_this_session": 3130})
    _state(tmp_path / "b", "standard", {"calibrate": 30, "ability_screen": 20, "screen": 300, "level_search": 3000,
                                         "confirm": 4000})
    _state(tmp_path / "c", "standard", {"calibrate": 20, "ability_screen": 20, "screen": 200, "level_search": 2000,
                                         "confirm": 3000})
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "state.json").write_text(json.dumps({"fingerprint": {"budget": "standard"}}))  # no timing
    h = eta.StageHistory.load(tmp_path)
    assert h.median("standard", "screen") == 200 and h.median("standard", "confirm") == 3000
    assert h.median("standard", "total_s_this_session") is None

    # Rate-based within the stage: (100 - 25) * 60 / 25 = 180 s, then the later medians.
    got = eta.eta_seconds(h, "standard", "screen", 25, 100, 60.0, seen_stages=["starting", "prune", "calibrate", "prune",
                                                                             "ability_screen", "screen"])
    assert got == 180 + 2000 + 3000

    # Median-based when the stage has no planned count.
    assert eta.eta_seconds(h, "standard", "level_search", 5, None, 500.0, seen_stages=["level_search"]) == 1500 + 3000
    # Second prune (after calibrate): ability_screen onwards is still to come.
    assert eta.eta_seconds(h, "standard", "prune", 0, None, 0.0, seen_stages=["prune", "calibrate", "prune"]) == \
        20 + 200 + 2000 + 3000
    # First prune / starting: calibrate onwards.
    assert eta.eta_seconds(h, "standard", "starting", 0, None, 0.0, seen_stages=["starting"]) == 20 + 20 + 200 + 2000 + 3000
    assert eta.eta_seconds(h, "standard", "setup_check", 0, None, 0.0, seen_stages=["level_search"]) == 2000 + 3000

    # No history for the budget, or a server-side stage: None, never an exception.
    assert eta.eta_seconds(h, "thorough", "screen", 25, 100, 60.0) is None
    for stage in ("queued", "done", "failed", "cancelled", "something_new"):
        assert eta.eta_seconds(h, "standard", stage, 0, None, 0.0) is None


def test_history_from_real_runs():
    """Positive control: the repo's own runs/ have a standard confirm timing (runs/final-defaults)."""
    h = eta.StageHistory.load(REPO_ROOT / "runs")
    assert h.median("standard", "confirm") is not None
