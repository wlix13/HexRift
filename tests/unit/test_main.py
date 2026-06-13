import pytest

from hexrift import __main__
from hexrift.errors import DeriveError, Error


def test_domain_error_prints_and_exits_1(monkeypatch, capsys):
    def boom() -> None:
        raise DeriveError("something derived wrong")

    monkeypatch.setattr(__main__, "cli", boom)
    with pytest.raises(SystemExit) as e:
        __main__.main()
    assert e.value.code == 1
    # The Error base wraps the message in rich markup; rich.print renders the text.
    assert "something derived wrong" in capsys.readouterr().out


def test_base_error_subclasses_are_caught(monkeypatch):
    def boom() -> None:
        raise Error("base error")

    monkeypatch.setattr(__main__, "cli", boom)
    with pytest.raises(SystemExit) as e:
        __main__.main()
    assert e.value.code == 1


def test_unexpected_eeption_prints_and_exits_1(monkeypatch, capsys):
    def boom() -> None:
        raise RuntimeError("unexpected boom")

    monkeypatch.setattr(__main__, "cli", boom)
    with pytest.raises(SystemExit) as e:
        __main__.main()
    assert e.value.code == 1
    out = capsys.readouterr().out
    assert "Error:" in out
    assert "unexpected boom" in out


def test_keyboard_interrupt_exits_130(monkeypatch):
    def boom() -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(__main__, "cli", boom)
    with pytest.raises(SystemExit) as e:
        __main__.main()
    assert e.value.code == 130


def test_clean_run_does_not_exit(monkeypatch):
    monkeypatch.setattr(__main__, "cli", lambda: None)
    # Should return normally without raising SystemExit.
    __main__.main()
