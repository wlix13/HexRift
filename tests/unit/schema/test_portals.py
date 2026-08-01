import uuid

import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.portals import Portal, PortalRoutes


class TestPortalRoutes:
    def test_domains_only_valid(self):
        pr = PortalRoutes(domains=["home.example.com"])
        assert pr.domains == ["home.example.com"]
        assert pr.ips is None

    def test_ips_only_valid(self):
        pr = PortalRoutes(ips=["192.168.1.0/24"])
        assert pr.ips == ["192.168.1.0/24"]

    def test_no_matchers_rejected(self):
        with pytest.raises(ValidationError, match="at least one matcher"):
            PortalRoutes()

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            PortalRoutes.model_validate({"domains": ["a.com"], "extra": "x"})

    def test_blank_domain_rejected(self):
        with pytest.raises(ValidationError, match="non-empty"):
            PortalRoutes(domains=["ok.example.com", "  "])


class TestPortal:
    def test_valid(self):
        p = Portal(
            id="home",
            users=["alice"],
            routes=PortalRoutes(domains=["home.example.com"]),
        )
        assert p.id == "home"
        assert p.users == ["alice"]
        assert p.uuid is None

    def test_uuid_override(self):
        uid = uuid.uuid4()
        p = Portal(
            id="home",
            users=["alice"],
            routes=PortalRoutes(domains=["home.example.com"]),
            uuid=uid,
        )
        assert p.uuid == uid

    def test_users_required(self):
        with pytest.raises(ValidationError):
            Portal.model_validate(
                {
                    "id": "home",
                    "routes": {"domains": ["home.example.com"]},
                },
            )

    def test_empty_users_rejected(self):
        with pytest.raises(ValidationError):
            Portal.model_validate(
                {
                    "id": "home",
                    "users": [],
                    "routes": {"domains": ["home.example.com"]},
                },
            )

    def test_duplicate_users_rejected(self):
        with pytest.raises(ValidationError, match="duplicate user"):
            Portal.model_validate(
                {
                    "id": "home",
                    "users": ["alice", "alice"],
                    "routes": {"domains": ["home.example.com"]},
                },
            )

    def test_invalid_id_rejected(self):
        with pytest.raises(ValidationError):
            Portal.model_validate(
                {
                    "id": "bad id",
                    "users": ["alice"],
                    "routes": {"domains": ["home.example.com"]},
                },
            )

    def test_invalid_user_rejected(self):
        with pytest.raises(ValidationError, match="invalid identifier"):
            Portal.model_validate(
                {
                    "id": "home",
                    "users": ["bad user"],
                    "routes": {"domains": ["home.example.com"]},
                },
            )

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            Portal.model_validate(
                {
                    "id": "home",
                    "users": ["alice"],
                    "routes": {"domains": ["home.example.com"]},
                    "bad_field": "x",
                },
            )
