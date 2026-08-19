"""Ordered inbound spec registry."""

from __future__ import annotations

from typing import Any, Final

from hexrift.constants import AccessType, RegionType
from hexrift.inbounds.base import InboundContext, InboundEnv, InboundSpec
from hexrift.inbounds.cdn import CDN_SPEC
from hexrift.inbounds.hysteria import HYSTERIA_SPEC
from hexrift.inbounds.proxy import PROXY_SPEC
from hexrift.inbounds.wireguard import WIREGUARD_SPEC
from hexrift.inbounds.xdns import XDNS_SPEC
from hexrift.inbounds.xhttp import XHTTP_SPEC


INBOUND_SPECS: Final[tuple[InboundSpec[Any], ...]] = (
    XHTTP_SPEC,
    CDN_SPEC,
    PROXY_SPEC,
    XDNS_SPEC,
    WIREGUARD_SPEC,
    HYSTERIA_SPEC,
)
"""Order is load-bearing: reproduces inbound order in generated config."""


def specs_for(role: RegionType) -> tuple[InboundSpec[Any], ...]:
    return tuple(s for s in INBOUND_SPECS if role in s.roles)


def build_slots(env: InboundEnv) -> dict[AccessType, InboundContext]:
    slots: dict[AccessType, InboundContext] = {}
    seen: set[AccessType] = set()
    for spec in specs_for(env.role):
        if spec.access_type in seen:
            raise ValueError(f"Duplicate inbound spec for access type {spec.access_type!r}")
        seen.add(spec.access_type)
        ctx = spec.build_context(env)
        if ctx is not None:
            slots[spec.access_type] = ctx
    return slots
