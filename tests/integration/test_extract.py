"""T020: `platsim extract` is deterministic, `--check` passes on fresh output and fails on a
corrupted byte (positive control, Constitution V).

Runs the real CLI as a subprocess into a pytest tmp dir (`--out`, under /dev/shm per conftest),
so data/generated is not touched; one test also checks the real default directory.
"""

import json
import subprocess
import sys

from platsim.extract import DEFAULT_OUT, OUTPUTS
from platsim.pins import DECOMP_COMMIT

EXPECTED = {f"{n}.json" for n in OUTPUTS} | {"manifest.json"}


def run(*args):
    return subprocess.run([sys.executable, "-m", "platsim.cli", "extract", *args],
                          capture_output=True, text=True, check=False)


def read_all(d):
    return {p.name: p.read_bytes() for p in sorted(d.glob("*.json"))}


def test_extract_twice_identical_check_and_corruption(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    ra = run("--out", str(a))
    assert ra.returncode == 0, ra.stderr
    rb = run("--out", str(b))
    assert rb.returncode == 0, rb.stderr
    fa, fb = read_all(a), read_all(b)
    assert set(fa) == EXPECTED
    assert fa == fb  # identical bytes

    manifest = json.loads(fa["manifest.json"])
    assert manifest["decomp_commit"] == DECOMP_COMMIT
    assert set(manifest["files"]) == EXPECTED - {"manifest.json"}

    ok = run("--check", "--out", str(a))
    assert ok.returncode == 0, ok.stderr

    # Positive control: flip one byte in one output; --check must fail and name the file.
    target = a / "moves.json"
    data = bytearray(target.read_bytes())
    i = len(data) // 2
    data[i] = ord("X") if data[i] != ord("X") else ord("Y")
    target.write_bytes(bytes(data))
    bad = run("--check", "--out", str(a))
    assert bad.returncode == 1
    assert "moves.json" in bad.stderr

    # A missing file is also caught.
    (b / "exp.json").unlink()
    missing = run("--check", "--out", str(b))
    assert missing.returncode == 1 and "exp.json: missing" in missing.stderr


def test_known_values_in_output(tmp_path):
    """Spot checks so an extractor that silently emits empty tables fails."""
    r = run("--out", str(tmp_path))
    assert r.returncode == 0, r.stderr
    species = json.loads((tmp_path / "species.json").read_text())["species"]
    # pokeplatinum/res/pokemon/garchomp/data.json:2-9 base_stats hp 108, attack 130, defense 95,
    # speed 102, special_attack 80, special_defense 85
    assert species["garchomp"]["base_stats"] == {"hp": 108, "atk": 130, "def": 95, "spa": 80, "spd": 85, "spe": 102}
    moves = json.loads((tmp_path / "moves.json").read_text())["moves"]
    # pokeplatinum/res/moves/dark_pulse/data.json:14 "pp": 15
    assert moves["dark_pulse"]["pp"] == 15
    trainers = json.loads((tmp_path / "trainers.json").read_text())["trainers"]
    assert [t["key"] for t in trainers] == [
        "elite_four_aaron", "elite_four_bertha", "elite_four_flint", "elite_four_lucian", "champion_cynthia"]
    assert len(species) > 490 and len(moves) > 460


def test_real_default_dir_is_current():
    """The committed-to-disk data/generated (gitignored, reproducible) matches the readers."""
    r = run()
    assert r.returncode == 0, r.stderr
    c = run("--check")
    assert c.returncode == 0, c.stderr
    assert set(p.name for p in DEFAULT_OUT.glob("*.json")) >= EXPECTED
