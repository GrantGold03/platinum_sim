import pytest

from platsim.pins import DECOMP_ROOT as _DECOMP_ROOT
from platsim.pins import SHOWDOWN_ROOT as _SHOWDOWN_ROOT


@pytest.fixture(scope="session")
def DECOMP_ROOT():
    return _DECOMP_ROOT


@pytest.fixture(scope="session")
def SHOWDOWN_ROOT():
    return _SHOWDOWN_ROOT


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
