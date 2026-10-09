"""Launcher for the shutdown test (002 T023): a real uvicorn server whose jobs run
`_fake_runners.sleepy_runner` in their own process group.

Usage: python _serve_fake.py PORT RUNS_DIR

The catalog is six hand-built entries, so there is no 35 s ledger build. The uvicorn start MUST
stay inside the __main__ guard: a `spawn` job child re-imports this file as `__mp_main__`, and
without the guard every job would start a second server (analysis N7).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _fake_runners  # noqa: E402
from platsim.web.app import HOST, create_app  # noqa: E402
from platsim.web.species_catalog import SpeciesCatalog, SpeciesInfo  # noqa: E402

FAKE_SPECIES = ("infernape", "staraptor", "luxray", "garchomp", "gyarados", "gardevoir")


def fake_catalog() -> SpeciesCatalog:
    return SpeciesCatalog([SpeciesInfo(key=k, const=f"SPECIES_{k.upper()}", name=k.capitalize(), types=("Normal",),
                                       dex=i + 1, available=True) for i, k in enumerate(FAKE_SPECIES)])


if __name__ == "__main__":
    import uvicorn

    port, runs_dir = int(sys.argv[1]), sys.argv[2]
    app = create_app(runner=_fake_runners.sleepy_runner, isolate=True, runs_dir=runs_dir, catalog=fake_catalog())
    uvicorn.run(app, host=HOST, port=port, log_level="warning")
