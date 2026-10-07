"""Pinned versions of the vendored sources (Constitution, Technical Constraints).

Bumping a pin is a tracked change: re-run extraction tests and the divergence ledger.
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DECOMP_ROOT = REPO_ROOT / "pokeplatinum"
SHOWDOWN_ROOT = REPO_ROOT / "pokemon-showdown"

DECOMP_COMMIT = "c248fb3f8cc9934ded800e489567c5c0eeee92eb"
SHOWDOWN_COMMIT = "c046106cbe075931b1ff8d8b800ff5be47a85f96"

# Platinum (USA) Rev 1, the decomp's default build target (pokeplatinum/README.md).
ROM_REV1_SHA1 = "0862ec35b24de5c7e2dcb88c9eea0873110d755c"

# Build outputs allowed inside the Showdown tree (npm ci / node build).
_SHOWDOWN_ALLOWED_DIRTY = ("node_modules/", "dist/", "config/config.js")


class PinError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise PinError(f"git {' '.join(args)} failed in {repo}: {result.stderr.strip()}")
    return result.stdout


def _check_repo(repo: Path, expected: str, allowed_dirty: tuple[str, ...] = ()) -> None:
    head = _git(repo, "rev-parse", "HEAD").strip()
    if head != expected:
        raise PinError(f"{repo.name} is at {head}, expected pinned commit {expected}")
    dirty = [
        line[3:]
        for line in _git(repo, "status", "--porcelain").splitlines()
        if not line[3:].startswith(allowed_dirty)
    ]
    if dirty:
        raise PinError(f"{repo.name} has local changes (vendored trees must not be edited): {dirty}")


def check_pins() -> None:
    """Raise PinError unless both vendored repos are at their pinned commits and unmodified."""
    _check_repo(DECOMP_ROOT, DECOMP_COMMIT)
    _check_repo(SHOWDOWN_ROOT, SHOWDOWN_COMMIT, _SHOWDOWN_ALLOWED_DIRTY)
