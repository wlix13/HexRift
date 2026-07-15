"""Xray config defaults."""

from __future__ import annotations

from hexrift.constants import DEFAULT_TRUSTED_HEADER, SpecialDestination


LOG = {
    "loglevel": "none",
    "access": "none",
    "error": "none",
    "dnsLog": False,
}


def make_sniffing(route_only: bool = True) -> dict:
    return {
        "enabled": True,
        "destOverride": ["http", "tls", "quic"],
        "routeOnly": route_only,
    }


def make_dns(address: str, port: int) -> dict:
    return {
        "servers": [
            {
                "address": address,
                "port": port,
            }
        ],
        "enableParallelQuery": True,
        "useSystemHosts": True,
    }


def make_dns_direct_rule(address: str, port: int) -> dict:
    ips = ["127.0.0.1", "::1"]
    if address not in ips:
        ips.append(address)
    return {
        "ip": ips,
        "port": port,
        "outboundTag": SpecialDestination.DIRECT,
    }


MKCP_SETTINGS_XDNS: dict = {
    "mtu": 128,
    "tti": 50,
    "uplinkCapacity": 1,
    "downlinkCapacity": 1,
}


def make_sockopt(ipv6: bool) -> dict:
    return {
        "tproxy": "off",
        "domainStrategy": "UseIPv6v4" if ipv6 else "UseIPv4",
        "happyEyeballs": {
            "tryDelayMs": 150,
            "maxConcurrentTry": 2,
            "prioritizeIPv6": ipv6,
        },
        "tcpFastOpen": True,
        "tcpKeepAliveInterval": 45,
        "tcpKeepAliveIdle": 45,
        "tcpWindowClamp": 0,
        "tcpcongestion": "bbr",
    }


def make_inbound_sockopt(ipv6: bool, trusted_headers: list[str]) -> dict:
    return {
        **make_sockopt(ipv6),
        "trustedXForwardedFor": trusted_headers or [DEFAULT_TRUSTED_HEADER],
    }
