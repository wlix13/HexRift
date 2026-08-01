from __future__ import annotations

import ipaddress
import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

from hexrift.constants import (
    DNS_NAME_PATTERN,
    DURATION_PATTERN,
    IDENTIFIER_PATTERN,
    RTT_PATTERN,
    SHORT_ID_LENGTH,
    SHORT_ID_PATTERN,
)


_IDENTIFIER_RE = re.compile(IDENTIFIER_PATTERN)


def normalize_cidr_subnet(value: str) -> str:
    """Validate CIDR subnet and normalize to network base."""

    try:
        return str(ipaddress.ip_network(value, strict=False))
    except ValueError as e:
        raise ValueError(f"invalid CIDR subnet {value!r}: {e}") from e


def parse_host_port(value: str) -> tuple[str, int]:
    """Split `host:port` or `[ipv6]:port`, validating port range."""

    if value.startswith("["):
        close = value.find("]")
        if close == -1:
            raise ValueError(f"malformed IPv6 address in {value!r} (missing ']')")
        host = value[1:close]
        rest = value[close + 1 :]
        if not rest.startswith(":"):
            raise ValueError(f"{value!r} must be in host:port form")
        port_str = rest[1:]
    else:
        host, sep, port_str = value.rpartition(":")
        if not sep:
            raise ValueError(f"{value!r} must be in host:port form")
        if ":" in host:
            raise ValueError(f"IPv6 address in {value!r} must be bracketed as [host]:port")

    if not host:
        raise ValueError(f"{value!r} is missing a host")
    try:
        port = int(port_str)
    except ValueError as e:
        raise ValueError(f"{value!r} has a non-numeric port {port_str!r}") from e
    if not 1 <= port <= 65535:
        raise ValueError(f"{value!r} port must be in 1..65535")
    return host, port


def validate_host_port(value: str) -> str:
    parse_host_port(value)
    return value


def validate_xray_path(value: str) -> str:
    if not value.startswith("/"):
        raise ValueError(f"path must start with '/': {value!r}")
    return value


def validate_short_id(value: str) -> str:
    if len(value) % 2 != 0:
        raise ValueError(f"short_id must have an even number of hex digits: {value!r}")
    return value


def validate_identifier_list(value: list[str]) -> list[str]:
    for item in value:
        if not _IDENTIFIER_RE.fullmatch(item):
            raise ValueError(f"invalid identifier {item!r}: must match {IDENTIFIER_PATTERN}")
    return value


def strip_non_blank(value: list[str]) -> list[str]:
    stripped = [item.strip() for item in value]
    if any(not item for item in stripped):
        raise ValueError("entries must be non-empty")
    return stripped


Identifier = Annotated[str, StringConstraints(pattern=IDENTIFIER_PATTERN, min_length=1)]
"""Safe identifier (ids, usernames, portal ids)."""

DnsName = Annotated[str, StringConstraints(pattern=DNS_NAME_PATTERN, min_length=1)]
"""DNS name (namespace, hostnames, domains)."""

Duration = Annotated[str, StringConstraints(pattern=DURATION_PATTERN)]
"""Duration string (ms/s/m/h)."""

Rtt = Annotated[str, StringConstraints(pattern=RTT_PATTERN)]
"""Round-trip-time string (ms/s)."""

HostPort = Annotated[
    str,
    AfterValidator(validate_host_port),
]
"""`host:port` or `[ipv6]:port` string with valid port."""

XrayPath = Annotated[
    str,
    AfterValidator(validate_xray_path),
]
"""Path that must start with `/`."""

ShortId = Annotated[
    str,
    StringConstraints(pattern=SHORT_ID_PATTERN, max_length=SHORT_ID_LENGTH),
    AfterValidator(validate_short_id),
]
"""Reality shortId: hex, even length, <= SHORT_ID_LENGTH chars."""

NonBlankList = Annotated[
    list[str],
    AfterValidator(strip_non_blank),
]
"""List of strings with no blank/whitespace-only elements."""

IdentifierList = Annotated[
    list[str],
    AfterValidator(validate_identifier_list),
]
"""List of safe identifiers."""
