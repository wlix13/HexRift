import json

from hexrift.components.render.xray import serialize_config


class TestReturnType:
    def test_returns_bytes(self):
        result = serialize_config({"key": "value"})
        assert isinstance(result, bytes)

    def test_ends_with_newline(self):
        result = serialize_config({"key": "value"})
        assert result.endswith(b"\n")

    def test_is_valid_json(self):
        result = serialize_config({"key": "value", "num": 42})
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_has_indentation(self):
        result = serialize_config({"outer": {"inner": "val"}})
        assert b"  " in result


class TestCompactMode:
    def test_string_array_collapsed(self):
        result = serialize_config({"a": ["hello", "world"]})
        assert b'["hello", "world"]' in result

    def test_bool_array_collapsed(self):
        result = serialize_config({"a": [True, False]})
        assert b"[true, false]" in result

    def test_number_array_collapsed(self):
        result = serialize_config({"a": [1, 2, 3]})
        assert b"[1, 2, 3]" in result

    def test_object_array_not_collapsed(self):
        result = serialize_config({"a": [{"x": 1}, {"x": 2}]})
        # Objects should remain expanded
        assert b"[\n" in result

    def test_long_array_not_collapsed(self):
        # 10 long strings — collapsed form would exceed 80 chars
        long_strings = [f"very-long-string-value-{i}" for i in range(10)]
        result = serialize_config({"a": long_strings})
        # Not collapsed: the inline form must be absent
        assert b'"very-long-string-value-0", "very-long-string-value-1"' not in result

    def test_nested_arrays_of_scalars_collapsed(self):
        result = serialize_config({"outer": {"inner": [1, 2, 3]}})
        assert b"[1, 2, 3]" in result


class TestNonCompactMode:
    def test_non_compact_ends_with_newline(self):
        result = serialize_config({"a": [1, 2]}, compact=False)
        assert result.endswith(b"\n")

    def test_non_compact_string_array_not_collapsed(self):
        result = serialize_config({"a": ["x", "y"]}, compact=False)
        # In non-compact mode, arrays are NOT collapsed
        assert b"[\n" in result
