import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.routing import ExitRoute


def test_valid_domains_only():
    r = ExitRoute(destination="direct", domains=["example.com"])
    assert r.domains == ["example.com"]


def test_valid_ips_only():
    r = ExitRoute(destination="direct", ips=["1.2.3.4"])
    assert r.ips == ["1.2.3.4"]


def test_valid_both():
    r = ExitRoute(destination="direct", domains=["a.com"], ips=["10.0.0.1"])
    assert r.domains and r.ips


def test_requires_at_least_one_matcher():
    with pytest.raises(ValidationError, match="at least one matcher"):
        ExitRoute(destination="direct")


def test_empty_lists_treated_as_missing():
    # Empty lists are falsy — same as None
    with pytest.raises(ValidationError, match="at least one matcher"):
        ExitRoute(destination="direct", domains=[], ips=[])


def test_extra_field_forbidden():
    with pytest.raises(ValidationError):
        ExitRoute.model_validate(
            {
                "destination": "direct",
                "domains": ["a.com"],
                "extra_field": "bad",
            },
        )
