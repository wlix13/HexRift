import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.regions import (
    LeastLoadSettings,
    MtprotoConfig,
    Node,
    NodeMtprotoOverride,
)


class TestLeastLoadSettings:
    def test_defaults(self):
        s = LeastLoadSettings()
        assert s.tolerance == 0.5
        assert s.max_rtt == "750ms"
        assert s.expected == 1

    def test_tolerance_lower_bound(self):
        s = LeastLoadSettings(tolerance=0.0)
        assert s.tolerance == 0.0

    def test_tolerance_upper_bound(self):
        s = LeastLoadSettings(tolerance=1.0)
        assert s.tolerance == 1.0

    def test_tolerance_below_zero_raises(self):
        with pytest.raises(ValidationError):
            LeastLoadSettings(tolerance=-0.1)

    def test_tolerance_above_one_raises(self):
        with pytest.raises(ValidationError):
            LeastLoadSettings(tolerance=1.01)

    def test_max_rtt_ms_valid(self):
        assert LeastLoadSettings(max_rtt="750ms").max_rtt == "750ms"

    def test_max_rtt_s_valid(self):
        assert LeastLoadSettings(max_rtt="10s").max_rtt == "10s"

    def test_max_rtt_invalid_unit_raises(self):
        with pytest.raises(ValidationError):
            LeastLoadSettings(max_rtt="10m")

    def test_max_rtt_no_unit_raises(self):
        with pytest.raises(ValidationError):
            LeastLoadSettings(max_rtt="750")

    def test_expected_minimum_one(self):
        with pytest.raises(ValidationError):
            LeastLoadSettings(expected=0)

    def test_xray_settings_has_expected_keys(self):
        s = LeastLoadSettings()
        xs = s.xray_settings
        assert "baselines" in xs and "expected" in xs and "maxRTT" in xs and "tolerance" in xs


class TestMtprotoConfig:
    def test_valid_defaults(self):
        m = MtprotoConfig(domain="tg.example.com")
        assert m.port == 1234

    def test_custom_port(self):
        m = MtprotoConfig(domain="tg.example.com", port=5678)
        assert m.port == 5678

    def test_port_min_one(self):
        with pytest.raises(ValidationError):
            MtprotoConfig(domain="x.com", port=0)

    def test_port_max_65535(self):
        m = MtprotoConfig(domain="x.com", port=65535)
        assert m.port == 65535

    def test_port_above_max_raises(self):
        with pytest.raises(ValidationError):
            MtprotoConfig(domain="x.com", port=65536)

    def test_domain_empty_raises(self):
        with pytest.raises(ValidationError):
            MtprotoConfig(domain="")

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            MtprotoConfig.model_validate(
                {
                    "domain": "x.com",
                    "bad_field": 1,
                },
            )


class TestNode:
    def test_minimal_valid(self):
        n = Node(id="n1", hostname="n1.example.com")
        assert n.id == "n1"
        assert n.reality is None
        assert n.ipv6 is None

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            Node.model_validate(
                {
                    "id": "n1",
                    "hostname": "n1.example.com",
                    "unknown_field": "x",
                },
            )


class TestNodeMtprotoOverride:
    def test_all_none_valid(self):
        o = NodeMtprotoOverride()
        assert o.enabled is None and o.domain is None and o.port is None

    def test_empty_domain_raises(self):
        with pytest.raises(ValidationError):
            NodeMtprotoOverride(domain="")

    def test_port_zero_raises(self):
        with pytest.raises(ValidationError):
            NodeMtprotoOverride(port=0)
