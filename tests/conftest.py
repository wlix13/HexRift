import gettext

import pytest

import hexrift.i18n as _i18n
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


@pytest.fixture(autouse=True)
def force_english_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the i18n catalog to the English passthrough for all tests."""

    monkeypatch.setenv("HEXRIFT_LANG", "en")
    monkeypatch.setattr(_i18n, "_current", gettext.NullTranslations())
