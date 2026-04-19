import uuid

import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.users import Portal, PortalRoutes, User
from hexrift.constants import AccessType


class TestUser:
    def test_minimal_valid(self):
        u = User(
            username="alice",
            group="grp1",
            access=[AccessType.XHTTP],
        )
        assert u.uuid is None
        assert u.portals == []
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

    def test_with_portals(self):
        u = User(
            username="alice",
            group="grp1",
            access=[AccessType.XHTTP],
            portals=[
                Portal(
                    label="home",
                    routes=PortalRoutes(domains=["home.example.com"]),
                )
            ],
        )
        assert u.portals[0].label == "home"

    def test_with_guests(self):
        u = User(
            username="alice",
            group="grp1",
            access=[AccessType.XHTTP],
            guests=["device1"],
        )
        assert u.guests == ["device1"]


class TestPortalRoutes:
    def test_both_none_valid(self):
        pr = PortalRoutes()
        assert pr.domains is None
        assert pr.ips is None

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            PortalRoutes.model_validate({"extra": "x"})


class TestPortal:
    def test_valid(self):
        p = Portal(
            label="home",
            routes=PortalRoutes(domains=["home.example.com"]),
        )
        assert p.label == "home"

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            Portal.model_validate(
                {
                    "label": "home",
                    "routes": {},
                    "bad_field": "x",
                },
            )
