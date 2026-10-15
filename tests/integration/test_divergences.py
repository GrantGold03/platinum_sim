"""T053: divergence ledger (Constitution II).

- positive control: a fake stat difference injected into a copy of the Showdown dump produces a
  ledger entry (and the untouched dump produces none for that species);
- the committed ledger equals a fresh diff (`platsim divergences --check`) and every entry has a
  resolution and both citations;
- an entry without a resolution makes `platsim divergences` exit 1;
- the Endure priority patch (decomp +3, Showdown gen4 +4) changes turn order in a live Showdown
  battle, and the worker's `hello` reports the ledger version.
"""

import copy
import json
import subprocess

import pytest

from platsim.divergence import compare
from platsim.pins import REPO_ROOT

LEDGER = REPO_ROOT / "data" / "divergences.json"


def platsim(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["uv", "run", "platsim", *args], cwd=REPO_ROOT, capture_output=True,
                          text=True, timeout=300, check=False)


@pytest.fixture(scope="module")
def dump():
    return compare.run_dump()


@pytest.fixture(scope="module")
def gen():
    return compare.load_generated()


def test_positive_control_fake_stat_difference(dump, gen):
    clean = [e["id"] for e in compare.diff_species(dump, gen) if e["id"].startswith("data-species-garchomp")]
    assert clean == []  # control: no Garchomp divergence in the real data

    fake = copy.deepcopy(dump)
    sd = next(s for s in fake["species"] if s["id"] == "garchomp")
    real_atk = gen["species"]["garchomp"]["base_stats"]["atk"]
    sd["baseStats"]["atk"] = real_atk + 1
    entries = {e["id"]: e for e in compare.diff_species(fake, gen)}
    e = entries["data-species-garchomp-basestats-atk"]
    assert e["resolution"] == "corrected"
    assert e["patch"] == {"table": "Pokedex", "id": "garchomp", "path": ["baseStats", "atk"], "value": real_atk}
    # the decomp line really holds the value it cites
    path, line = e["decomp_ref"].removeprefix("pokeplatinum/").rsplit(":", 1)
    assert f'"attack": {real_atk}' in (compare.DECOMP_ROOT / path).read_text().splitlines()[int(line) - 1]
    assert e["showdown_ref"].startswith("pokemon-showdown/data/")
    assert compare.problems([e]) == []


def test_ledger_matches_fresh_diff():
    proc = platsim("divergences", "--check")
    print(proc.stdout, proc.stderr)
    assert proc.returncode == 0, proc.stderr
    ledger = json.loads(LEDGER.read_text())
    assert ledger["version"] == compare.version_of(ledger["entries"])
    assert compare.problems(ledger["entries"]) == []
    by_id = {e["id"]: e for e in ledger["entries"]}
    endure = by_id["data-move-endure-priority"]
    assert endure["patch"] == {"table": "Moves", "id": "endure", "path": ["priority"], "value": 3}
    assert endure["decomp_ref"] == "pokeplatinum/res/moves/endure/data.json:20"
    for i in ("damage-type-chart-sequential-truncation", "mech-resist-berry-order", "mech-full-restore-pseudo-move",
              "exp-gain-and-participation", "mech-pp-ups", "mech-stats-overwrite", "ai-trainer-ai", "mech-rng",
              "exp-auto-learn-spec-conflict", "mech-baton-pass-taunt", "mech-kings-rock-serene-grace",
              "mech-shell-bell-substitute", "mech-accuracy-stages-rounding", "mech-trainer-friendship"):
        assert i in by_id


def test_missing_resolution_exits_1(tmp_path):
    ledger = json.loads(LEDGER.read_text())
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps(ledger))
    proc = platsim("divergences", "--ledger", str(ok))
    assert proc.returncode == 0, proc.stderr  # control: the real ledger passes

    del ledger["entries"][0]["resolution"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(ledger))
    proc = platsim("divergences", "--ledger", str(bad))
    assert proc.returncode == 1
    assert f"{ledger['entries'][0]['id']}: missing or invalid resolution" in proc.stderr


# Slow Snorlax uses Endure, fast Jolteon uses Protect (+3 in both engines). With Showdown's
# Endure +4 Snorlax moves first; with the decomp's +3 both are +3 and Jolteon (faster) moves first.
BATTLE_JS = """
import { prepareDex } from '%(gamedata)s';
import { Battle } from '%(showdown)s';
const p = prepareDex(process.argv[1]);
const b = new Battle({ formatid: 'gen4customgame', seed: 'sodium,' + '0'.repeat(32) });
const mon = (species, move) => ({ species, name: species, level: 50, moves: [move], ability: 'No Ability',
  evs: {}, ivs: {}, nature: 'Hardy', item: '' });
b.setPlayer('p1', { name: 'A', team: [mon('Snorlax', 'Endure')] });
b.setPlayer('p2', { name: 'B', team: [mon('Jolteon', 'Protect')] });
b.makeChoices('move 1', 'move 1');
const order = b.log.filter((l) => l.startsWith('|move|')).map((l) => l.split('|')[2].slice(0, 2));
console.log(JSON.stringify({ version: p.version, applied: p.applied, endure: b.dex.moves.get('endure').priority, order }));
"""


def run_battle(ledger_path):
    code = BATTLE_JS % {"gamedata": (REPO_ROOT / "sim" / "gamedata.mjs").as_uri(),
                        "showdown": (REPO_ROOT / "sim" / "showdown.mjs").as_uri()}
    proc = subprocess.run(["node", "--input-type=module", "-e", code, str(ledger_path)],
                          capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_endure_patch_in_live_battle(tmp_path):
    control = run_battle(tmp_path / "no-ledger.json")  # file does not exist -> no patches
    assert control["version"] == "none" and control["endure"] == 4
    assert control["order"] == ["p1", "p2"]  # Showdown's +4 Endure beats the faster +3 Protect

    patched = run_battle(LEDGER)
    print(control, patched)
    assert "data-move-endure-priority" in patched["applied"]
    assert patched["endure"] == 3
    assert patched["order"] == ["p2", "p1"]  # both +3 -> the faster Jolteon moves first


def test_worker_hello_reports_ledger_version():
    ledger = json.loads(LEDGER.read_text())
    proc = subprocess.run(["node", str(REPO_ROOT / "sim" / "worker.mjs")], input='{"id":1,"op":"hello"}\n',
                          capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    hello = json.loads(proc.stdout.splitlines()[0])
    assert hello["divergence_ledger_version"] == ledger["version"]
    assert hello["divergence_patches_applied"] == sum(1 for e in ledger["entries"] if e.get("patch"))
