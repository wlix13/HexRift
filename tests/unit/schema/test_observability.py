from ipaddress import IPv4Address, IPv6Address

import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.observability import (
    LoggingConfig,
    LoggingOverride,
    MetricsConfig,
    MetricsOverride,
    ObservabilityConfig,
    ObservabilityOverride,
)
from hexrift.constants import LogLevel


class TestMetricsConfig:
    def test_defaults(self):
        m = MetricsConfig()
        assert m.enabled is False
        assert m.listen == IPv4Address("127.0.0.1")
        assert m.port == 10085
        assert m.user_stats is True
        assert m.online is True

    def test_listen_parsed_to_ip_object(self):
        assert isinstance(MetricsConfig(listen="10.0.0.5").listen, IPv4Address | IPv6Address)

    def test_valid_ipv4_listen_accepted(self):
        assert MetricsConfig(listen="0.0.0.0").listen == IPv4Address("0.0.0.0")  # noqa: S104 0.0.0.0 is valid

    def test_valid_ipv6_listen_accepted(self):
        assert MetricsConfig(listen="::1").listen == IPv6Address("::1")

    def test_invalid_listen_rejected(self):
        with pytest.raises(ValidationError, match="valid IPv4 or IPv6 address"):
            MetricsConfig(listen="not-an-ip")

    def test_port_minimum(self):
        assert MetricsConfig(port=1).port == 1

    def test_port_maximum(self):
        assert MetricsConfig(port=65535).port == 65535

    def test_port_zero_rejected(self):
        with pytest.raises(ValidationError):
            MetricsConfig(port=0)

    def test_port_above_max_rejected(self):
        with pytest.raises(ValidationError):
            MetricsConfig(port=65536)

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            MetricsConfig.model_validate({"bogus": 1})


class TestLoggingConfig:
    def test_defaults(self):
        log = LoggingConfig()
        assert log.loglevel is LogLevel.NONE
        assert log.access == "none"
        assert log.error == "none"
        assert log.dns_log is False

    def test_loglevel_string_coerced(self):
        assert LoggingConfig.model_validate({"loglevel": "warning"}).loglevel is LogLevel.WARNING

    def test_loglevel_invalid_rejected(self):
        with pytest.raises(ValidationError):
            LoggingConfig.model_validate({"loglevel": "trace"})

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            LoggingConfig.model_validate({"bogus": 1})


class TestObservabilityConfig:
    def test_defaults_are_disabled(self):
        o = ObservabilityConfig()
        assert o.metrics.enabled is False
        assert o.logging.loglevel is LogLevel.NONE

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            ObservabilityConfig.model_validate({"bogus": 1})


class TestMetricsOverride:
    def test_all_none_by_default(self):
        m = MetricsOverride()
        assert m.enabled is None
        assert m.listen is None
        assert m.port is None
        assert m.user_stats is None
        assert m.online is None

    def test_invalid_listen_rejected(self):
        with pytest.raises(ValidationError, match="valid IPv4 or IPv6 address"):
            MetricsOverride(listen="not-an-ip")

    def test_port_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            MetricsOverride(port=0)

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            MetricsOverride.model_validate({"bogus": 1})


class TestLoggingOverride:
    def test_all_none_by_default(self):
        log = LoggingOverride()
        assert log.loglevel is None
        assert log.access is None
        assert log.error is None
        assert log.dns_log is None

    def test_loglevel_invalid_rejected(self):
        with pytest.raises(ValidationError):
            LoggingOverride.model_validate({"loglevel": "trace"})

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            LoggingOverride.model_validate({"bogus": 1})


class TestObservabilityOverride:
    def test_both_none_by_default(self):
        o = ObservabilityOverride()
        assert o.metrics is None
        assert o.logging is None

    def test_partial_override_accepted(self):
        o = ObservabilityOverride.model_validate({"metrics": {"enabled": True}})
        assert o.metrics is not None
        assert o.metrics.enabled is True
        assert o.logging is None

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            ObservabilityOverride.model_validate({"bogus": 1})
