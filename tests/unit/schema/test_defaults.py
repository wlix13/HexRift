import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.defaults import KeysConfig, ObservatoryConfig


class TestObservatoryConfig:
    def test_defaults(self):
        o = ObservatoryConfig()
        assert o.sampling == 8
        assert o.interval == "15s"
        assert o.timeout == "5s"
        assert o.concurrency is True

    def test_sampling_minimum(self):
        assert ObservatoryConfig(sampling=1).sampling == 1

    def test_sampling_maximum(self):
        assert ObservatoryConfig(sampling=24).sampling == 24

    def test_sampling_below_min_raises(self):
        with pytest.raises(ValidationError):
            ObservatoryConfig(sampling=0)

    def test_sampling_above_max_raises(self):
        with pytest.raises(ValidationError):
            ObservatoryConfig(sampling=25)

    def test_interval_ms_valid(self):
        assert ObservatoryConfig(interval="100ms").interval == "100ms"

    def test_interval_s_valid(self):
        assert ObservatoryConfig(interval="15s").interval == "15s"

    def test_interval_m_valid(self):
        assert ObservatoryConfig(interval="5m").interval == "5m"

    def test_interval_h_valid(self):
        assert ObservatoryConfig(interval="1h").interval == "1h"

    def test_interval_no_unit_raises(self):
        with pytest.raises(ValidationError):
            ObservatoryConfig(interval="15")

    def test_interval_invalid_unit_raises(self):
        with pytest.raises(ValidationError):
            ObservatoryConfig(interval="15d")

    def test_timeout_pattern_same_as_interval(self):
        assert ObservatoryConfig(timeout="500ms").timeout == "500ms"
        with pytest.raises(ValidationError):
            ObservatoryConfig(timeout="bad")

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            ObservatoryConfig.model_validate({"bad_field": 1})


class TestKeysConfig:
    def test_minimal_valid(self):
        k = KeysConfig(mode="native", session_time="600s")
        assert k.enabled is True
        assert k.padding is None

    def test_enabled_false(self):
        k = KeysConfig(enabled=False, mode="native", session_time="600s")
        assert k.enabled is False

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            KeysConfig.model_validate(
                {
                    "mode": "native",
                    "session_time": "600s",
                    "mystery": "x",
                },
            )
