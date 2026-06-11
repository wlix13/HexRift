import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.shared import RealityConfig


class TestRealityConfigServerNames:
    def test_none_allowed(self):
        # server_names is optional; derive_server_names falls back to the dest host.
        cfg = RealityConfig(dest="a.com:443", xhttp_path="/x/")
        assert cfg.server_names is None

    def test_non_empty_accepted(self):
        cfg = RealityConfig(dest="a.com:443", xhttp_path="/x/", server_names=["sni.a.com"])
        assert cfg.server_names == ["sni.a.com"]

    def test_empty_list_rejected(self):
        with pytest.raises(ValidationError, match="should have at least 1"):
            RealityConfig(dest="a.com:443", xhttp_path="/x/", server_names=[])

    @pytest.mark.parametrize("bad", ["", "   ", "\t"])
    def test_blank_entries_rejected(self, bad: str):
        with pytest.raises(ValidationError, match="must be non-empty"):
            RealityConfig(dest="a.com:443", xhttp_path="/x/", server_names=["sni.a.com", bad])


class TestRealityConfigDest:
    @pytest.mark.parametrize("good", ["a.com:443", "1.2.3.4:8443", "[2001:db8::1]:443"])
    def test_valid_host_port_accepted(self, good: str):
        assert RealityConfig(dest=good, xhttp_path="/x/").dest == good

    @pytest.mark.parametrize("bad", ["a.com", "a.com:0", "a.com:70000", "a.com:port", ":443", "[2001:db8::1]443"])
    def test_invalid_dest_rejected(self, bad: str):
        with pytest.raises(ValidationError):
            RealityConfig(dest=bad, xhttp_path="/x/")


class TestRealityConfigPaths:
    def test_xhttp_path_must_start_with_slash(self):
        with pytest.raises(ValidationError, match="must start with"):
            RealityConfig(dest="a.com:443", xhttp_path="x/")

    def test_xhttp_host_dns_name_validated(self):
        assert RealityConfig(dest="a.com:443", xhttp_path="/x/", xhttp_host="cdn.a.com").xhttp_host == "cdn.a.com"
        with pytest.raises(ValidationError):
            RealityConfig(dest="a.com:443", xhttp_path="/x/", xhttp_host="bad host")
