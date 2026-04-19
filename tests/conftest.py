import pytest

from hexrift.app import HexRiftApp
from hexrift.core.application import BaseApplication


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the app singleton before and after every test."""

    BaseApplication._instance = None
    HexRiftApp._instance = None
    yield
    BaseApplication._instance = None
    HexRiftApp._instance = None
