import pytest

from platsim.pins import DECOMP_ROOT as _DECOMP_ROOT
from platsim.pins import SHOWDOWN_ROOT as _SHOWDOWN_ROOT


@pytest.fixture(scope="session")
def DECOMP_ROOT():
    return _DECOMP_ROOT


@pytest.fixture(scope="session")
def SHOWDOWN_ROOT():
    return _SHOWDOWN_ROOT
