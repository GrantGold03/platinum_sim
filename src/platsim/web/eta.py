"""Estimated time left for a running web job (002 research R2).

The optimizer does not know its total run count up front (level search is open-ended), so the
estimate combines:
- the current stage: `(planned - done) * in_stage / done` when the stage reports a planned count,
  otherwise `max(median(stage) - in_stage, 0)`;
- every later stage: its median duration from earlier runs with the same budget, read from
  `<runs_dir>/*/state.json` "timing".

It returns None (the page shows "estimating…") when a needed median is missing, and for stages it
can't place. It never raises. The value is only an estimate: confirm times on the standard budget
varied from about 1.3k to 11.4k s across three runs.
"""

from __future__ import annotations

import json
import statistics
import threading
from pathlib import Path

STAGE_ORDER = ("calibrate", "ability_screen", "screen", "level_search", "confirm")
_SKIP_KEYS = {"total_s_this_session"}


class StageHistory:
    def __init__(self, runs_dir: Path | None = None):
        self.runs_dir = Path(runs_dir) if runs_dir else None
        self._medians: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()

    @classmethod
    def load(cls, runs_dir) -> StageHistory:
        h = cls(runs_dir)
        h.refresh()
        return h

    def refresh(self) -> None:
        samples: dict[str, dict[str, list[float]]] = {}
        if self.runs_dir and self.runs_dir.is_dir():
            for f in self.runs_dir.glob("*/state.json"):
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                    budget = d["fingerprint"]["budget"]
                    timing = d.get("timing") or {}
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                for stage, secs in timing.items():
                    if stage in _SKIP_KEYS or not isinstance(secs, (int, float)):
                        continue
                    samples.setdefault(budget, {}).setdefault(stage, []).append(float(secs))
        medians = {b: {s: statistics.median(v) for s, v in st.items()} for b, st in samples.items()}
        with self._lock:
            self._medians = medians

    def median(self, budget: str, stage: str) -> float | None:
        with self._lock:
            return self._medians.get(budget, {}).get(stage)


def _remaining_from(stage: str, seen: list[str]) -> tuple[str | None, int | None]:
    """(stage whose own time counts as "current", index in STAGE_ORDER of the first later stage)."""
    if stage in STAGE_ORDER:
        return stage, STAGE_ORDER.index(stage) + 1
    if stage in ("setup_check", "alternatives"):  # interleaved with level_search (optimizer/run.py; 007 renamed it)
        return "level_search", STAGE_ORDER.index("level_search") + 1
    if stage in ("starting", "resolve"):
        return None, 0
    if stage == "prune":  # pass A before calibrate, pass B after it (optimizer/run.py:309, :344)
        return None, (STAGE_ORDER.index("ability_screen") if "calibrate" in seen else 0)
    return None, None  # queued / done / failed / cancelled / unknown


def eta_seconds(history: StageHistory, budget: str, stage: str, runs_done: int | None, runs_planned: int | None,
                in_stage_s: float, seen_stages=()) -> float | None:
    try:
        current, later_from = _remaining_from(stage or "", list(seen_stages or ()))
        if later_from is None:
            return None
        total = 0.0
        if current is not None:
            done, planned = runs_done or 0, runs_planned
            if planned and done > 0:
                total += max(planned - done, 0) * max(in_stage_s, 0.0) / done
            else:
                m = history.median(budget, current)
                if m is None:
                    return None
                total += max(m - max(in_stage_s, 0.0), 0.0)
        for s in STAGE_ORDER[later_from:]:
            m = history.median(budget, s)
            if m is None:
                return None
            total += m
        return total
    except Exception:  # noqa: BLE001 - an estimate must never break the job view
        return None
