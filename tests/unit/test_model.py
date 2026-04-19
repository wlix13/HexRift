from io import StringIO

from rich.console import Console

from hexrift.core.model import BaseModel


class SampleModel(BaseModel):
    name: str
    reality_private_key: str
    decryption: str
    other: str


def _capture(model: SampleModel) -> str:
    buf = StringIO()
    con = Console(file=buf, highlight=False, markup=False)
    model.display(console=con)
    return buf.getvalue()


def test_display_normal_fields_visible():
    m = SampleModel(name="test", reality_private_key="s1", decryption="s2", other="value")
    out = _capture(m)
    assert "test" in out
    assert "value" in out


def test_display_redacted_fields_hidden():
    m = SampleModel(name="x", reality_private_key="priv_secret", decryption="dec_secret", other="y")
    out = _capture(m)
    assert "priv_secret" not in out
    assert "dec_secret" not in out


def test_display_shows_redacted_placeholder():
    m = SampleModel(name="x", reality_private_key="priv", decryption="dec", other="y")
    buf = StringIO()
    con = Console(file=buf, highlight=False)
    m.display(console=con)
    # Rich strips markup when printing to non-terminal; the raw markup tag is stripped
    # but the word "redacted" should appear
    assert "redacted" in buf.getvalue()


def test_display_uses_default_console_when_none():
    m = SampleModel(name="x", reality_private_key="p", decryption="d", other="o")
    m.display()  # must not raise


def test_display_field_names_appear():
    m = SampleModel(name="x", reality_private_key="p", decryption="d", other="val")
    out = _capture(m)
    assert "name" in out
    assert "other" in out
