"""Xray config defaults."""

from __future__ import annotations


LOG = {
    "loglevel": "none",
    "access": "none",
    "error": "none",
    "dnsLog": False,
}

SNIFFING = {
    "enabled": True,
    "destOverride": ["http", "tls", "quic"],
    "routeOnly": True,
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


MKCP_SETTINGS_XDNS: dict = {
    "mtu": 128,
    "tti": 50,
    "uplinkCapacity": 1,
    "downlinkCapacity": 1,
}


def make_sockopt(ipv6: bool) -> dict:
    return {
        "tproxy": "off",
        **({"domainStrategy": "UseIPv4"} if not ipv6 else {}),
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
        **({"trustedXForwardedFor": trusted_headers} if trusted_headers else {}),
    }
