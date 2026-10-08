"""Code-version fingerprint (platsim/version.py, sim/version.mjs): provenance, Constitution IV.

Every change test works on a copy of the tree under tmp_path; the real files are never edited.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from platsim import version
from platsim.pins import REPO_ROOT

NODE_HASH = ("import(process.argv[1]).then((m) => process.stdout.write(m.simCodeHash(process.argv[2])))")


def _copy_tree(dst):
    shutil.copytree(REPO_ROOT / "sim", dst / "sim", ignore=shutil.ignore_patterns("node_modules"))
    shutil.copytree(REPO_ROOT / "src" / "platsim", dst / "src" / "platsim", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(REPO_ROOT / "pyproject.toml", dst / "pyproject.toml")
    return dst


@pytest.fixture
def tree(tmp_path):
    return _copy_tree(tmp_path / "repo")


def _node_hash(sim_dir) -> str:
    p = subprocess.run(["node", "-e", NODE_HASH, str(REPO_ROOT / "sim" / "version.mjs"), str(sim_dir)],
                       capture_output=True, text=True, check=False)
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_hashes_are_stable_and_well_formed(tree):
    for fn in (version.sim_code_hash, version.platsim_code_hash):
        a, b = fn(), fn()
        assert a == b and a.startswith("sha256:") and len(a) == len("sha256:") + 64
        assert fn(tree) == a  # an exact copy hashes the same: the hash depends on content, not location


def test_file_sets():
    sim = {rel for rel, _ in version.sim_code_files()}
    assert {"sim/worker.mjs", "sim/gauntlet.mjs", "sim/package.json", "sim/version.mjs", "sim/ai/interp.mjs"} <= sim
    assert not any(r.startswith(("sim/test/", "sim/spikes/")) or not (r.endswith(".mjs") or r.endswith("package.json"))
                   for r in sim)
    py = {rel for rel, _ in version.platsim_code_files()}
    assert {"pyproject.toml", "src/platsim/version.py", "src/platsim/sim/pool.py"} <= py
    assert not any("__pycache__" in r for r in py)


@pytest.mark.parametrize("rel", ["sim/worker.mjs", "sim/ai/interp.mjs", "sim/package.json"])
def test_sim_hash_changes_with_a_behaviour_file(tree, rel):
    before = version.sim_code_hash(tree)
    with (tree / rel).open("a", encoding="utf-8") as f:
        f.write("\n// edited\n" if rel.endswith(".mjs") else "\n")
    assert version.sim_code_hash(tree) != before
    assert _node_hash(tree / "sim") == version.sim_code_hash(tree)  # both implementations see the edit


def test_sim_hash_new_or_renamed_file_changes_it(tree):
    before = version.sim_code_hash(tree)
    (tree / "sim" / "policy" / "extra.mjs").write_text("export const x = 1;\n", encoding="utf-8")
    added = version.sim_code_hash(tree)
    assert added != before
    (tree / "sim" / "policy" / "extra.mjs").rename(tree / "sim" / "policy" / "extra2.mjs")
    assert version.sim_code_hash(tree) not in (before, added)  # the path is part of the hash


def test_sim_hash_ignores_tests_spikes_and_docs(tree):
    before = version.sim_code_hash(tree)
    node_before = _node_hash(tree / "sim")
    with (tree / "sim" / "test" / "seeds.test.mjs").open("a", encoding="utf-8") as f:
        f.write("\n// edited\n")
    (tree / "sim" / "spikes").mkdir(exist_ok=True)
    (tree / "sim" / "spikes" / "new_spike.mjs").write_text("console.log(1);\n", encoding="utf-8")
    (tree / "sim" / "ai" / "NOTES.md").write_text("notes\n", encoding="utf-8")
    (tree / "sim" / "node_modules" / "pkg").mkdir(parents=True)
    (tree / "sim" / "node_modules" / "pkg" / "index.mjs").write_text("export {};\n", encoding="utf-8")
    assert version.sim_code_hash(tree) == before
    assert _node_hash(tree / "sim") == node_before == before


def test_node_and_python_agree_on_the_real_tree():
    assert _node_hash(REPO_ROOT / "sim") == version.sim_code_hash()


def test_platsim_hash_changes_with_code_not_pycache(tree):
    before = version.platsim_code_hash(tree)
    cache = tree / "src" / "platsim" / "__pycache__"
    cache.mkdir(exist_ok=True)
    (cache / "fake.py").write_text("x = 1\n", encoding="utf-8")
    (tree / "src" / "platsim" / "notes.txt").write_text("not code\n", encoding="utf-8")
    assert version.platsim_code_hash(tree) == before
    with (tree / "src" / "platsim" / "evaluate.py").open("a", encoding="utf-8") as f:
        f.write("\n# edited\n")
    edited = version.platsim_code_hash(tree)
    assert edited != before
    with (tree / "pyproject.toml").open("a", encoding="utf-8") as f:
        f.write("\n")
    assert version.platsim_code_hash(tree) not in (before, edited)


def _git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                       capture_output=True, text=True, check=False)
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_repo_commit_and_dirty(tmp_path):
    repo = tmp_path / "g"
    repo.mkdir()
    assert version.repo_commit(repo) is None and version.repo_dirty(repo) is None  # not a git repo
    _git(repo, "init", "-q")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-q", "-m", "init")
    head = _git(repo, "rev-parse", "HEAD").strip()
    assert version.repo_commit(repo) == head and len(head) == 40
    assert version.repo_dirty(repo) is False
    for ignored in ("runs/x/result.json", "data/generated/species.json", ".venv/lib/x.py", "sim/node_modules/p/i.js"):
        (repo / ignored).parent.mkdir(parents=True, exist_ok=True)
        (repo / ignored).write_text("{}\n", encoding="utf-8")
    assert version.repo_dirty(repo) is False  # build/run outputs do not count
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")  # positive control
    assert version.repo_dirty(repo) is True


def test_code_fingerprint_and_diff():
    hello = {"sim_code_hash": "sha256:" + "a" * 64, "node_version": "v22.0.0", "decomp_commit": "d", "showdown_commit": "s",
             "decomp_data_hash": "sha256:x", "divergence_ledger_version": "v", "divergence_patches_applied": 5,
             "pp_restore_between_battles": False}
    fp = version.code_fingerprint(hello)
    assert set(version.CODE_KEYS) | set(version.BEHAVIOUR_KEYS) <= set(fp)
    assert fp["platsim_code_hash"] == version.platsim_code_hash() and fp["sim_code_hash"] == hello["sim_code_hash"]
    json.dumps(fp)  # JSON-serialisable, no time or path
    assert version.fingerprint_diff(fp, dict(fp)) == {}
    assert version.fingerprint_diff(fp, dict(fp, repo_commit="other", repo_dirty=not fp["repo_dirty"])) == {}
    assert version.fingerprint_diff(fp, dict(fp, sim_code_hash="sha256:b")) == {"sim_code_hash": (hello["sim_code_hash"],
                                                                                                    "sha256:b")}
    assert set(version.fingerprint_diff(None, fp)) == set(version.BEHAVIOUR_KEYS)
