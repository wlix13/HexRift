import uuid

import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.users import User
from hexrift.constants import AccessType


class TestUser:
    def test_minimal_valid(self):
        u = User(
            username="alice",
            group="grp1",
            access=[AccessType.XHTTP],
        )
        assert u.uuid is None
        assert u.guests == []

    def test_valid_with_uuid(self):
        uid = uuid.uuid4()
        u = User(
            username="alice",
            group="grp1",
            access=[AccessType.XHTTP],
            uuid=uid,
        )
        assert u.uuid == uid

    def test_valid_all_access_types(self):
        u = User(
            username="alice",
            group="grp1",
            access=[AccessType.XHTTP, AccessType.SERVER, AccessType.CDN, AccessType.PROXY],
        )
        assert len(u.access) == 4

    def test_invalid_access_type_raises(self):
        with pytest.raises(ValidationError):
            User.model_validate(
                {
                    "username": "alice",
                    "group": "grp1",
                    "access": ["unknown"],
                }
            )

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            User.model_validate(
                {
                    "username": "alice",
                    "group": "grp1",
                    "access": [AccessType.XHTTP.value],
                    "bad": 1,
                }
            )

    def test_with_guests(self):
        u = User(
            username="alice",
            group="grp1",
            access=[AccessType.XHTTP],
            guests=["device1"],
        )
        assert u.guests == ["device1"]

    @pytest.mark.parametrize("bad", ["bad name", "no!", "dotted.name", ""])
    def test_invalid_username_rejected(self, bad: str):
        with pytest.raises(ValidationError):
            User.model_validate(
                {
                    "username": bad,
                    "group": "grp1",
                    "access": ["xhttp"],
                },
            )

    def test_invalid_guest_rejected(self):
        with pytest.raises(ValidationError, match="invalid identifier"):
            User.model_validate(
                {
                    "username": "alice",
                    "group": "grp1",
                    "access": ["xhttp"],
                    "guests": ["ok", "bad guest"],
                },
            )
