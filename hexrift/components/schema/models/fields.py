from __future__ import annotations

import ipaddress
import re
from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints

from hexrift.constants import (
    DNS_NAME_PATTERN,
    DURATION_PATTERN,
    HOST_PORT_PATTERN,
    IDENTIFIER_PATTERN,
    RTT_PATTERN,
    SHORT_ID_LENGTH,
    SHORT_ID_PATTERN,
)


_DNS_NAME_RE = re.compile(DNS_NAME_PATTERN)


def normalize_cidr_subnet(value: str) -> str:
    """Validate CIDR subnet and normalize to network base."""

    try:
        return str(ipaddress.ip_network(value, strict=False))
    except ValueError as e:
        raise ValueError(f"invalid CIDR subnet {value!r}: {e}") from e


def validate_cidr_strict(value: str) -> str:
    """Validate CIDR without widening: host bits must be clear."""

    try:
        return str(ipaddress.ip_network(value, strict=True))
    except ValueError as e:
        if "has host bits set" not in str(e):
            raise ValueError(f"invalid CIDR subnet {value!r}: {e}") from e
        base = ipaddress.ip_network(value, strict=False)
        raise ValueError(
            f"{value!r} has host bits set; write the network base ({base}) or a single host (/32, /128)"
        ) from e


def parse_host_port(value: str) -> tuple[str, int]:
    """Split `host:port` or `[ipv6]:port`, validating host shape and port range."""

    bracketed = value.startswith("[")
    if bracketed:
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
    if bracketed:
        try:
            ipaddress.ip_address(host)
        except ValueError as e:
            raise ValueError(f"{value!r} bracketed host must be an IP literal") from e
    elif not _DNS_NAME_RE.fullmatch(host):
        raise ValueError(f"{value!r} host must be an IP literal or DNS name")
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
    StringConstraints(pattern=HOST_PORT_PATTERN),
    AfterValidator(validate_host_port),
]
"""`host:port` or `[ipv6]:port` string with valid host and port."""

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

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
"""Stripped string that must not be blank."""

Cidr = Annotated[str, AfterValidator(validate_cidr_strict)]
"""CIDR subnet or bare IP; host bits must be clear."""

CidrSubnet = Annotated[str, AfterValidator(normalize_cidr_subnet)]
"""CIDR subnet normalized to its network base (address pools)."""

NonBlankList = list[NonBlank]
"""List of strings with no blank/whitespace-only elements."""

IdentifierList = list[Identifier]
"""List of safe identifiers."""

CidrList = list[Cidr]
"""List of CIDR subnets, each rejected when host bits are set."""

Port = Annotated[int, Field(ge=1, le=65535)]
"""TCP/UDP port number."""
