"""Code versioning for provenance (Constitution IV): which code produced a result.

Content hashes (same byte scheme for both trees; `sim_code_hash` is also computed by the worker,
sim/version.mjs, and reported in its `hello`):

    "sha256:" + sha256( for each file, in ascending order of its repo-relative POSIX path (UTF-8 bytes):
                        <path utf-8> 0x00 <byte length, decimal ascii> 0x00 <file bytes> )

- `sim_code_hash`: every *.mjs and package.json under sim/, EXCLUDING sim/test/**, sim/spikes/** and
  node_modules/** (tests and spikes do not affect battle behaviour).
- `platsim_code_hash`: every src/platsim/**/*.py (not __pycache__) plus pyproject.toml.

Git state (informational: the content hashes are what identifies the code):
- `repo_commit`: `git rev-parse HEAD` of this repo (None if git is unavailable).
- `repo_dirty`: `git status --porcelain --untracked-files=all` is non-empty after ignoring runs/, data/generated/, .venv/
  and node_modules (None if git is unavailable).

`local_fingerprint()` is computed once per process (cached) on first use; WorkerPool calls it at
start, so a result names the Python code as it was when the run began.
"""

from __future__ import annotations

import functools
import hashlib
import platform
import subprocess
from pathlib import Path

from platsim.pins import REPO_ROOT

_DIRTY_IGNORED = ("runs/", "data/generated/", ".venv/")
_SIM_EXCLUDED_TOP = ("test", "spikes")

# Fields of a code fingerprint that identify behaviour; a resume across a change in any of them is
# refused (optimizer/run.py). repo_commit / repo_dirty are recorded but not compared: a commit that
# changes no behaviour file does not change what the code does.
BEHAVIOUR_KEYS = ("sim_code_hash", "platsim_code_hash", "node_version", "python_version", "decomp_commit",
                  "showdown_commit", "decomp_data_hash", "divergence_ledger_version", "divergence_patches_applied",
                  "pp_restore_between_battles")
CODE_KEYS = ("sim_code_hash", "platsim_code_hash", "repo_commit", "repo_dirty", "node_version", "python_version")


def hash_files(files: list[tuple[str, Path]]) -> str:
    """The content hash over (repo-relative POSIX path, file) pairs (see module doc)."""
    h = hashlib.sha256()
    for rel, path in sorted(files, key=lambda f: f[0].encode("utf-8")):
        data = Path(path).read_bytes()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(str(len(data)).encode("ascii"))
        h.update(b"\0")
        h.update(data)
    return "sha256:" + h.hexdigest()


def sim_code_files(repo_root: Path = REPO_ROOT) -> list[tuple[str, Path]]:
    root = Path(repo_root)
    sim = root / "sim"
    out = []
    for p in sim.rglob("*"):
        if not p.is_file() or not (p.suffix == ".mjs" or p.name == "package.json"):
            continue
        parts = p.relative_to(sim).parts
        if parts[0] in _SIM_EXCLUDED_TOP or "node_modules" in parts:
            continue
        out.append((p.relative_to(root).as_posix(), p))
    return out


def platsim_code_files(repo_root: Path = REPO_ROOT) -> list[tuple[str, Path]]:
    root = Path(repo_root)
    out = [(p.relative_to(root).as_posix(), p) for p in (root / "src" / "platsim").rglob("*.py")
           if p.is_file() and "__pycache__" not in p.parts]
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        out.append(("pyproject.toml", pyproject))
    return out


def sim_code_hash(repo_root: Path = REPO_ROOT) -> str:
    return hash_files(sim_code_files(repo_root))


def platsim_code_hash(repo_root: Path = REPO_ROOT) -> str:
    return hash_files(platsim_code_files(repo_root))


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False)
    except OSError:
        return None
    return r.stdout if r.returncode == 0 else None


def repo_commit(repo_root: Path = REPO_ROOT) -> str | None:
    out = _git(repo_root, "rev-parse", "HEAD")
    return out.strip() if out else None


def _porcelain_path(line: str) -> str:
    path = line[3:]
    if " -> " in path:  # rename: "old -> new"
        path = path.split(" -> ", 1)[1]
    return path.strip('"')


def repo_dirty(repo_root: Path = REPO_ROOT) -> bool | None:
    out = _git(repo_root, "status", "--porcelain", "--untracked-files=all")  # files, not collapsed dirs
    if out is None:
        return None
    for line in out.splitlines():
        path = _porcelain_path(line)
        if path.startswith(_DIRTY_IGNORED) or "node_modules" in path.split("/"):
            continue
        return True
    return False


@functools.cache
def local_fingerprint() -> dict:
    """The Python-side code fingerprint of this process (cached: computed once, at first use)."""
    return {"platsim_code_hash": platsim_code_hash(), "repo_commit": repo_commit(), "repo_dirty": repo_dirty(),
            "python_version": platform.python_version()}


def code_fingerprint(hello: dict) -> dict:
    """The full code + data fingerprint of a run: the worker's `hello` provenance plus this process's
    Python fingerprint. Contains no time or path, so it is identical across worker counts."""
    loc = local_fingerprint()
    return {
        "sim_code_hash": hello.get("sim_code_hash"),
        "platsim_code_hash": loc["platsim_code_hash"],
        "repo_commit": loc["repo_commit"],
        "repo_dirty": loc["repo_dirty"],
        "node_version": hello.get("node_version"),
        "python_version": loc["python_version"],
        "decomp_commit": hello.get("decomp_commit"),
        "showdown_commit": hello.get("showdown_commit"),
        "decomp_data_hash": hello.get("decomp_data_hash"),
        "divergence_ledger_version": hello.get("divergence_ledger_version"),
        "divergence_patches_applied": hello.get("divergence_patches_applied"),
        "pp_restore_between_battles": hello.get("pp_restore_between_battles"),
    }


def fingerprint_diff(old: dict | None, new: dict, keys=BEHAVIOUR_KEYS) -> dict:
    """{key: (old, new)} for every behaviour key that differs (all keys when `old` is missing)."""
    old = old or {}
    return {k: (old.get(k), new.get(k)) for k in keys if old.get(k) != new.get(k)}


__all__ = ["BEHAVIOUR_KEYS", "CODE_KEYS", "code_fingerprint", "fingerprint_diff", "hash_files", "local_fingerprint",
           "platsim_code_hash", "platsim_code_files", "repo_commit", "repo_dirty", "sim_code_files", "sim_code_hash"]
