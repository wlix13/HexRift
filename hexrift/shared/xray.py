"""General Xray config defaults shared across components."""

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

DNS = {
    "servers": [
        {
            "address": "127.0.0.1",
            "port": 53,
        }
    ],
    "enableParallelQuery": True,
    "useSystemHosts": True,
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
