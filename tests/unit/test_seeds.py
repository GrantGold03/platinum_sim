"""T033: Python and Node seed derivation agree (sim/seeds.mjs vs platsim.sim.seeds)."""

import json
import random
import subprocess

from platsim.pins import REPO_ROOT
from platsim.sim.seeds import derive_seed


def test_known_vector():
    # `printf 'master|0|0' | sha256sum` -> 39d2367647c627c2d5276f07f486e388a3abbc12e7adc2162d8a46f17fa37e37
    assert derive_seed("master", 0, 0) == "sodium,39d2367647c627c2d5276f07f486e388"


def test_matches_node_for_100_inputs():
    rng = random.Random(20261007)
    masters = ["master", "", "x|y", "émoji-ü", "12345"]
    triples = [
        [rng.choice(masters) if i % 2 else rng.randrange(0, 2**53), rng.randrange(0, 10_000),
         rng.choice([0, 1, 2, 3, 4, 99])]
        for i in range(100)
    ]
    out = subprocess.run(
        ["node", str(REPO_ROOT / "sim" / "seeds.mjs")],
        input=json.dumps(triples), capture_output=True, text=True, check=False,
    )
    assert out.returncode == 0, out.stderr
    node = json.loads(out.stdout)
    py = [derive_seed(m, r, b) for m, r, b in triples]
    assert len(node) == len(py) == 100
    assert node == py
    assert len(set(py)) == 100  # positive control: inputs actually differ
    assert all(s.startswith("sodium,") and len(s) == 7 + 32 for s in py)
