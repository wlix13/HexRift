import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.groups import Group


class TestGroup:
    def test_minimal_valid(self):
        g = Group(id="main")
        assert g.id == "main"
        assert g.short_id is None

    @pytest.mark.parametrize("good", ["ab", "aabbccddeeff0011", "AABB"])
    def test_valid_short_id_accepted(self, good: str):
        assert Group(id="main", short_id=good).short_id == good

    @pytest.mark.parametrize("bad_id", ["bad id", "no!", "dotted.id", ""])
    def test_invalid_id_rejected(self, bad_id: str):
        with pytest.raises(ValidationError):
            Group.model_validate({"id": bad_id})

    @pytest.mark.parametrize(
        "bad_short",
        [
            "abc",  # odd length
            "xyz0",  # non-hex chars
            "a" * 18,  # exceeds SHORT_ID_LENGTH
            "abcg",  # 'g' is not hex
        ],
    )
    def test_invalid_short_id_rejected(self, bad_short: str):
        with pytest.raises(ValidationError):
            Group.model_validate({"id": "main", "short_id": bad_short})
