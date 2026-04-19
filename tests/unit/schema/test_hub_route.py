import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.routing import HubRoute


def test_valid_domains_only():
    r = HubRoute(destination="direct", domains=["example.com"])
    assert r.domains == ["example.com"]


def test_valid_ips_only():
    r = HubRoute(destination="nl", ips=["1.2.3.4"])
    assert r.ips == ["1.2.3.4"]


def test_valid_users_only():
    r = HubRoute(destination="nl", users=["alice"])
    assert r.users == ["alice"]


def test_valid_proxy_users_only():
    r = HubRoute(destination="nl", proxy_users=["bob"])
    assert r.proxy_users == ["bob"]


def test_valid_all_matchers():
    r = HubRoute(
        destination="nl",
        domains=["a.com"],
        ips=["1.1.1.1"],
        users=["u"],
        proxy_users=["p"],
    )
    assert r.domains and r.ips and r.users and r.proxy_users


def test_requires_at_least_one_matcher():
    with pytest.raises(ValidationError, match="at least one matcher"):
        HubRoute(destination="nl")


def test_extra_field_forbidden():
    with pytest.raises(ValidationError):
        HubRoute.model_validate(
            {
                "destination": "nl",
                "domains": ["a.com"],
                "unexpected": "x",
            },
        )
