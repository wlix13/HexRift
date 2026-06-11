import pytest

from hexrift.components.schema.models.fields import normalize_cidr_subnet, parse_host_port


class TestParseHostPort:
    @pytest.mark.parametrize(
        "value,host,port",
        [
            ("a.com:443", "a.com", 443),
            ("1.2.3.4:53", "1.2.3.4", 53),
            ("[2001:db8::1]:8443", "2001:db8::1", 8443),
        ],
    )
    def test_valid(self, value: str, host: str, port: int):
        assert parse_host_port(value) == (host, port)

    @pytest.mark.parametrize(
        "value",
        [
            "a.com",  # no port
            "a.com:0",  # port below range
            "a.com:70000",  # port above range
            "a.com:x",  # non-numeric port
            ":443",  # missing host
            "[2001:db8::1:443",  # missing closing bracket
            "2001:db8::1",  # unbracketed IPv6 must be rejected
        ],
    )
    def test_invalid(self, value: str):
        with pytest.raises(ValueError):
            parse_host_port(value)


class TestNormalizeCidrSubnet:
    def test_normalizes_to_network_base(self):
        assert normalize_cidr_subnet("10.0.0.5/24") == "10.0.0.0/24"

    def test_invalid_rejected(self):
        with pytest.raises(ValueError, match="invalid CIDR subnet"):
            normalize_cidr_subnet("not-a-subnet")
