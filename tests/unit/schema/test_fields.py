import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from hexrift.components.schema.models.fields import (
    bandwidth_bytes_per_sec,
    normalize_cert_pin,
    normalize_cidr_subnet,
    parse_host_port,
    validate_bandwidth,
    validate_masquerade_url,
)


# Hosts for non-bracket branch of parse_host_port: non-empty, no ':'
_hosts = st.from_regex(r"[A-Za-z0-9.\-]+", fullmatch=True)
_valid_ports = st.integers(min_value=1, max_value=65535)


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

    @given(_hosts, _valid_ports)
    def test_valid_host_port_round_trips(self, host: str, port: int):
        assert parse_host_port(f"{host}:{port}") == (host, port)

    @given(_hosts, st.integers())
    def test_out_of_range_port_is_always_rejected(self, host: str, port: int):
        assume(not 1 <= port <= 65535)
        with pytest.raises(ValueError, match="port must be in 1..65535"):
            parse_host_port(f"{host}:{port}")


class TestNormalizeCidrSubnet:
    def test_normalizes_to_network_base(self):
        assert normalize_cidr_subnet("10.0.0.5/24") == "10.0.0.0/24"

    def test_invalid_rejected(self):
        with pytest.raises(ValueError, match="invalid CIDR subnet"):
            normalize_cidr_subnet("not-a-subnet")

    @given(st.ip_addresses(v=4).map(str), st.integers(min_value=0, max_value=32))
    def test_normalization_is_idempotent(self, ip: str, prefix: int):
        once = normalize_cidr_subnet(f"{ip}/{prefix}")
        assert normalize_cidr_subnet(once) == once


class TestBandwidth:
    @pytest.mark.parametrize(
        "value,bytes_per_sec",
        [
            ("100 mbps", 13107200),  # binary megabits / 8
            ("1gbps", 134217728),
            ("512 kbps", 65536),
            ("1000000", 125000),  # bare number is bits/s
            ("1.5 gbps", 201326592),  # decimals, like Xray's ParseFloat
        ],
    )
    def test_bytes_per_sec_matches_xray(self, value: str, bytes_per_sec: int):
        assert bandwidth_bytes_per_sec(value) == bytes_per_sec

    def test_below_floor_rejected(self):
        with pytest.raises(ValueError, match="512 kbps floor"):
            validate_bandwidth("0.4 mbps")


class TestMasqueradeUrl:
    def test_requires_host(self):
        assert validate_masquerade_url("https://www.line.me/") == "https://www.line.me/"
        with pytest.raises(ValueError, match="no host"):
            validate_masquerade_url("https://?q")

    def test_accepts_explicit_port(self):
        assert validate_masquerade_url("https://www.line.me:8443/") == "https://www.line.me:8443/"

    @pytest.mark.parametrize("value", ["https://host:99999/", "https://host:http/", "https://host:0/"])
    def test_rejects_unusable_port(self, value: str):
        with pytest.raises(ValueError, match="port"):
            validate_masquerade_url(value)


class TestCertPin:
    def test_normalizes_hex_with_or_without_colons(self):
        colons = ":".join(["AB"] * 32)
        assert normalize_cert_pin("ab" * 32) == colons
        assert normalize_cert_pin(colons.lower()) == colons

    @pytest.mark.parametrize("value", ["ab" * 31, "zz" * 32, ""])
    def test_rejects_non_sha256(self, value: str):
        with pytest.raises(ValueError, match="64-hex-digit"):
            normalize_cert_pin(value)
