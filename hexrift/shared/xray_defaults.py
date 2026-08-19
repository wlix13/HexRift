"""Xray config defaults."""

from __future__ import annotations

from hexrift.components.schema.models.observability import LoggingConfig
from hexrift.constants import DEFAULT_TRUSTED_HEADER, SpecialDestination


def make_log(logging: LoggingConfig) -> dict:
    return {
        "loglevel": logging.loglevel,
        "access": logging.access,
        "error": logging.error,
        "dnsLog": logging.dns_log,
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


SOCKOPT_DOMAIN_STRATEGY: dict[bool | None, str] = {
    True: "UseIPv6v4",
    False: "UseIPv4",
    None: "UseIPv4v6",
}
"""Address family preference of a dialing machine; `None` when it is unknown."""


def make_sockopt(ipv6: bool | None) -> dict:
    return {
        "tproxy": "off",
        "domainStrategy": SOCKOPT_DOMAIN_STRATEGY[ipv6],
        "happyEyeballs": {
            "tryDelayMs": 150,
            "maxConcurrentTry": 2,
            "prioritizeIPv6": bool(ipv6),
        },
        "tcpFastOpen": True,
        "tcpKeepAliveInterval": 45,
        "tcpKeepAliveIdle": 45,
        "tcpWindowClamp": 0,
        "tcpcongestion": "bbr",
    }


def make_udp_sockopt(ipv6: bool) -> dict:
    """Outbound sockopt for a UDP dial."""

    return {"domainStrategy": SOCKOPT_DOMAIN_STRATEGY[ipv6]}


def make_inbound_sockopt(ipv6: bool, trusted_headers: list[str]) -> dict:
    return {
        **make_sockopt(ipv6),
        "trustedXForwardedFor": trusted_headers or [DEFAULT_TRUSTED_HEADER],
    }
