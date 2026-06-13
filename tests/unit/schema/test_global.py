import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.global_ import CdnConfig, DnsServerConfig, GlobalConfig


class TestCdnConfigTrustedHeaders:
    def test_valid_custom_header_accepted(self):
        cfg = CdnConfig(
            exit_domain="e.example.com",
            hub_domain="h.example.com",
            trusted_forwarded_headers=["CF-Connecting-IP"],
        )
        assert cfg.trusted_forwarded_headers == ["CF-Connecting-IP"]

    def test_default_header_when_unset(self):
        cfg = CdnConfig(exit_domain="e.example.com", hub_domain="h.example.com")
        assert cfg.trusted_forwarded_headers == ["X-Real-IP"]

    @pytest.mark.parametrize("good", ["1-Real-IP", "X_Real_IP", "X-Real-IP"])
    def test_rfc_token_headers_accepted(self, good: str):
        cfg = CdnConfig(
            exit_domain="e.example.com",
            hub_domain="h.example.com",
            trusted_forwarded_headers=[good],
        )
        assert cfg.trusted_forwarded_headers == [good]

    @pytest.mark.parametrize("bad", ["CF-Connecting-IP\n", "X Real IP", "X-Real-IP:", ""])
    def test_invalid_header_token_rejected(self, bad: str):
        with pytest.raises(ValidationError, match="RFC-compliant HTTP header field-name"):
            CdnConfig(
                exit_domain="e.example.com",
                hub_domain="h.example.com",
                trusted_forwarded_headers=[bad],
            )


class TestDnsServerConfig:
    def test_valid_ip_accepted(self):
        assert DnsServerConfig(address="8.8.8.8").address == "8.8.8.8"

    def test_invalid_ip_rejected(self):
        with pytest.raises(ValidationError, match="valid IP address"):
            DnsServerConfig(address="not-an-ip")


class TestGlobalConfigDnsNames:
    def test_valid_dotted_names_accepted(self):
        g = GlobalConfig(namespace="test.hexrift", aphelion_domain="ap.test.hexrift")
        assert g.namespace == "test.hexrift"
        assert g.aphelion_domain == "ap.test.hexrift"

    @pytest.mark.parametrize("bad", ["has space", "bad/name", "name!", ""])
    def test_invalid_namespace_rejected(self, bad: str):
        # non-empty bad values trip the DnsName pattern; "" trips its min_length.
        with pytest.raises(ValidationError, match=r"should (match pattern|have at least)"):
            GlobalConfig(namespace=bad, aphelion_domain="ap.test.hexrift")

    def test_cdn_domains_validated(self):
        with pytest.raises(ValidationError, match="should match pattern"):
            CdnConfig(exit_domain="bad domain", hub_domain="h.example.com")
