import pytest

from hexrift.app import HexRiftApp
from hexrift.core.application import BaseApplication


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset app singleton before and after every test."""

    BaseApplication.reset()
    HexRiftApp.reset()
    yield
    BaseApplication.reset()
    HexRiftApp.reset()
