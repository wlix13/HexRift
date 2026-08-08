"""Dokodemo-door inbound forwarding published port into portal's reverse tunnel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hexrift.constants import XrayProtocol
from hexrift.shared.xray_defaults import make_sockopt


if TYPE_CHECKING:
    from hexrift.components.derive.topology import PublishedPort
    from hexrift.inbounds.base import SharedContext


def forward_fragment(published: PublishedPort, shared: SharedContext) -> dict:
    """Build Xray inbound JSON fragment for published port."""

    return {
        "tag": published.tag,
        # Xray binds only IPv4 if `0.0.0.0`, dualstack if `::` (if no ipv6Only sockopt)
        "listen": "::" if shared.ipv6 else "0.0.0.0",  # noqa: S104
        "port": published.port,
        "protocol": XrayProtocol.DOKODEMO,
        "settings": {
            "address": published.target_host,
            "port": published.target_port,
            "network": published.network,
            "followRedirect": False,
        },
        "streamSettings": {
            "sockopt": make_sockopt(shared.ipv6),
        },
        # fixed-target forwards gain nothing from sniffing, and attacker-chosen SNI must not route
        "sniffing": {"enabled": False},
    }
