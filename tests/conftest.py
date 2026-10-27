import sys
from pathlib import Path

import pytest

from platsim.pins import DECOMP_ROOT as _DECOMP_ROOT
from platsim.pins import SHOWDOWN_ROOT as _SHOWDOWN_ROOT

# Web test helper modules (_web_helpers, _fake_runners) import by name from any test folder, and
# from a `spawn` child, which inherits this sys.path (002 T004).
_INTEGRATION = str(Path(__file__).resolve().parent / "integration")
if _INTEGRATION not in sys.path:
    sys.path.insert(0, _INTEGRATION)


@pytest.fixture(scope="session")
def DECOMP_ROOT():
    return _DECOMP_ROOT


@pytest.fixture(scope="session")
def SHOWDOWN_ROOT():
    return _SHOWDOWN_ROOT


# Species availability for the web tests is real: the catalogue is built from the availability
# ledger (~35 s), once per test session (002 T004).
@pytest.fixture(scope="session")
def ledger():
    from platsim.availability.ledger import build_ledger

    return build_ledger()


@pytest.fixture(scope="session")
def catalog(ledger):
    from platsim.web.species_catalog import build_catalog

    return build_catalog(ledger)


@pytest.fixture
def fixture_runs_dir(tmp_path):
    """A runs dir holding one finished job: the frozen final-defaults run (tests/fixtures/web_final_defaults)."""
    from _web_helpers import copy_fixture_run

    copy_fixture_run(tmp_path)
    return tmp_path


# Temp files never go in /tmp or the repo (user rule). Each pytest process gets its own
# basetemp under /dev/shm so parallel runs can't wipe each other's, and it is removed at exit.
import os
import shutil


def pytest_configure(config):
    if not config.option.basetemp:
        config.option.basetemp = f"/dev/shm/platsim-pytest-{os.getpid()}"
        config._platsim_basetemp = config.option.basetemp


def pytest_unconfigure(config):
    path = getattr(config, "_platsim_basetemp", None)
    if path:
        shutil.rmtree(path, ignore_errors=True)


# Battle-test split (012): a `node` stand-in logs every start of sim/worker.mjs; see the module.
pytest_plugins = ["_battle_split"]
