"""Build Xray config dicts and serialize into json."""

from __future__ import annotations

import re

import orjson

from hexrift.components.render.context import ExitContext, HubContext, HubOutboundContext
from hexrift.constants import (
    WARP_VLESS_ROUTE,
    Socket,
    SpecialDestination,
    TagSuffix,
    XrayNetwork,
    XrayProtocol,
    XraySecurity,
)


_LOG = {
    "loglevel": "none",
    "access": "none",
    "error": "none",
    "dnsLog": False,
}

_SOCKOPT = {
    "tproxy": "off",
    "happyEyeballs": {
        "tryDelayMs": 250,
        "maxConcurrentTry": 2,
        "prioritizeIPv6": True,
    },
    "tcpFastOpen": True,
    "tcpKeepAliveInterval": 45,
    "tcpKeepAliveIdle": 45,
    "tcpWindowClamp": 0,
    "tcpcongestion": "bbr",
}

_SNIFFING = {
    "enabled": True,
    "destOverride": ["http", "tls", "quic", "fakedns"],
}

_XHTTP_EXTRA = {
    "scStreamUpServerSecs": "30-60",
    "xPaddingBytes": "80-1400",
    "scMaxEachPostBytes": "500000-1000000",
    "scMinPostsIntervalMs": "10-50",
    "scMaxBufferedPosts": 45,
}

_XMUX = {
    "maxConcurrency": "16-32",
    "maxConnections": 0,
    "cMaxReuseTimes": "10-100",
    "hMaxRequestTimes": "600-900",
    "hMaxReusableSecs": "1800-3000",
    "hKeepAlivePeriod": 0,
}

_DNS = {
    "servers": [
        {
            "address": "127.0.0.1",
            "port": 53,
        }
    ],
    "enableParallelQuery": True,
    "useSystemHosts": True,
}

_WARP_OUTBOUND = {
    "tag": SpecialDestination.WARP,
    "protocol": XrayProtocol.FREEDOM,
    "streamSettings": {
        "sockopt": {
            **_SOCKOPT,
            "interface": "warp",
        }
    },
}


def _xhttp_settings(host: str, path: str, mode: str = "auto") -> dict:
    return {
        "host": host,
        "path": path,
        "mode": mode,
        "extra": _XHTTP_EXTRA,
        "xmux": _XMUX,
    }


def build_exit_config(ctx: ExitContext) -> dict:
    # Available inbounds
    direct_inbound = {
        "tag": "direct-xhttp",
        "listen": Socket.VLESS_REALITY,
        "protocol": XrayProtocol.VLESS,
        "settings": {
            "clients": ctx.direct_clients,
            "decryption": ctx.decryption,
        },
        "streamSettings": {
            "network": XrayNetwork.XHTTP,
            "security": XraySecurity.REALITY,
            "xhttpSettings": _xhttp_settings(ctx.reality_xhttp_host, ctx.reality_xhttp_path),
            "realitySettings": {
                "xver": 0,
                "show": False,
                "dest": ctx.reality_dest,
                "serverNames": ctx.reality_server_names,
                "privateKey": ctx.reality_private_key,
                "shortIds": [ctx.reality_short_id],
            },
            "sockopt": _SOCKOPT,
        },
        "sniffing": _SNIFFING,
    }

    routing_rules: list[dict] = [
        {
            "ip": ["127.0.0.1", "::1"],
            "port": 53,
            "outboundTag": SpecialDestination.DIRECT,
        },
        {
            "vlessRoute": str(WARP_VLESS_ROUTE),
            "outboundTag": SpecialDestination.WARP,
        },
    ]
    if ctx.warp_domains:
        routing_rules.append(
            {
                "domain": ctx.warp_domains,
                "outboundTag": SpecialDestination.WARP,
            }
        )

    outbounds: list[dict] = []
    outbounds.extend(
        [
            {
                "tag": SpecialDestination.DIRECT,
                "protocol": XrayProtocol.FREEDOM,
                "settings": {},
            },
            {
                "tag": SpecialDestination.BLOCKED,
                "protocol": XrayProtocol.BLACKHOLE,
                "settings": {},
            },
            _WARP_OUTBOUND,
        ]
    )

    inbounds: list[dict] = [direct_inbound]
    if ctx.cdn_xhttp_host and ctx.cdn_xhttp_path:
        inbounds.append(
            {
                "tag": "cdn-xhttp",
                "listen": Socket.VLESS_TLS,
                "protocol": XrayProtocol.VLESS,
                "settings": {
                    "clients": ctx.cdn_clients,
                    "decryption": ctx.decryption,
                },
                "streamSettings": {
                    "network": XrayNetwork.XHTTP,
                    "security": XraySecurity.NONE,
                    "xhttpSettings": _xhttp_settings(ctx.cdn_xhttp_host, ctx.cdn_xhttp_path),
                    "sockopt": _SOCKOPT,
                },
                "sniffing": _SNIFFING,
            }
        )
    config: dict = {
        "log": _LOG,
    }

    config.update(
        {
            "inbounds": inbounds,
            "outbounds": outbounds,
            "routing": {
                "domainStrategy": "IPIfNonMatch",
                "rules": routing_rules,
            },
            "dns": _DNS,
        }
    )

    return config


def build_hub_config(ctx: HubContext) -> dict:
    # Available inbounds
    direct_inbound = {
        "tag": "direct-xhttp",
        "listen": Socket.VLESS_REALITY,
        "protocol": XrayProtocol.VLESS,
        "settings": {
            "clients": ctx.vless_clients,
            "decryption": ctx.decryption,
        },
        "streamSettings": {
            "network": XrayNetwork.XHTTP,
            "security": XraySecurity.REALITY,
            "xhttpSettings": _xhttp_settings(ctx.reality_xhttp_host, ctx.reality_xhttp_path),
            "realitySettings": {
                "xver": 0,
                "show": False,
                "dest": ctx.reality_dest,
                "serverNames": ctx.reality_server_names,
                "privateKey": ctx.reality_private_key,
                "shortIds": ctx.reality_short_ids,
            },
            "sockopt": _SOCKOPT,
        },
        "sniffing": _SNIFFING,
    }

    proxy_inbound = {
        "tag": "mixed-inbound",
        "listen": Socket.MIXED,
        "port": 80,
        "protocol": XrayProtocol.MIXED,
        "settings": {
            "auth": "password",
            "accounts": ctx.proxy_inbound_accounts,
            "allowTransparent": True,
            "udp": True,
            "ip": "127.0.0.1",
        },
        "sniffing": _SNIFFING,
    }
    # Build reverse.portals
    portals_section = [
        {
            "tag": f"{p.label}{TagSuffix.PORTAL}",
            "domain": p.domain,
        }
        for p in ctx.portals
    ]

    # Build outbounds list
    outbounds: list[dict] = []

    def _exit_outbound(ob: HubOutboundContext) -> dict:
        tag = f"{ob.tag_prefix}{ob.exit_id}"
        return {
            "tag": tag,
            "protocol": XrayProtocol.VLESS,
            "settings": {
                "vnext": [
                    {
                        "address": ob.address,
                        "port": 443,
                        "users": [
                            {
                                "id": ob.user_id,
                                "encryption": ob.encryption,
                                "flow": ob.flow,
                            }
                        ],
                    }
                ],
            },
            "streamSettings": {
                "network": XrayNetwork.XHTTP,
                "security": XraySecurity.REALITY,
                "xhttpSettings": _xhttp_settings(ob.xhttp_host, ob.xhttp_path),
                "realitySettings": {
                    "publicKey": ob.public_key,
                    "fingerprint": ob.fingerprint,
                    "serverName": ob.server_name,
                    "shortId": ob.short_id,
                },
                "sockopt": _SOCKOPT,
            },
        }

    for ob in ctx.outbounds + ctx.warp_outbounds:
        outbounds.append(_exit_outbound(ob))

    outbounds.extend(
        [
            {
                "tag": SpecialDestination.DIRECT,
                "protocol": XrayProtocol.FREEDOM,
                "settings": {},
            },
            {
                "tag": SpecialDestination.BLOCKED,
                "protocol": XrayProtocol.BLACKHOLE,
                "settings": {},
            },
            _WARP_OUTBOUND,
        ]
    )

    inbounds: list[dict] = [direct_inbound]
    if ctx.cdn_xhttp_host and ctx.cdn_xhttp_path:
        inbounds.append(
            {
                "tag": "cdn-xhttp",
                "listen": Socket.VLESS_TLS,
                "protocol": XrayProtocol.VLESS,
                "settings": {
                    "clients": ctx.cdn_clients,
                    "decryption": ctx.decryption,
                },
                "streamSettings": {
                    "network": XrayNetwork.XHTTP,
                    "security": XraySecurity.NONE,
                    "xhttpSettings": _xhttp_settings(ctx.cdn_xhttp_host, ctx.cdn_xhttp_path),
                    "sockopt": _SOCKOPT,
                },
                "sniffing": _SNIFFING,
            }
        )
    if ctx.proxy_inbound:
        inbounds.append(proxy_inbound)

    config: dict = {
        "log": _LOG,
    }
    if portals_section:
        config["reverse"] = {"portals": portals_section}

    config.update(
        {
            "inbounds": inbounds,
            "outbounds": outbounds,
            "routing": {
                "domainStrategy": "IPIfNonMatch",
                "balancers": ctx.balancers,
                "rules": ctx.routing_rules,
            },
            "dns": _DNS,
        }
    )

    if ctx.observatory_selectors:
        config["burstObservatory"] = {
            "subjectSelector": ctx.observatory_selectors,
            "pingConfig": {
                "destination": "http://www.apple.com/library/test/success.html",
                "interval": "15s",
                "connectivity": "http://connectivitycheck.platform.hicloud.com/generate_204",
                "timeout": "2s",
                "sampling": 2,
            },
        }

    return config


def serialize_config(config: dict, compact: bool = True) -> bytes:
    raw = orjson.dumps(config, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS).decode()
    if not compact:
        return (raw + "\n").encode()
    # Collapse arrays whose items are all simple scalars (strings/numbers/booleans)
    # that orjson expanded across multiple lines back to single line.
    scalar = r'(?:"[^"]*"|-?\d+(?:\.\d+)?|true|false|null)'

    def _collapse(m: re.Match) -> str:
        items = ", ".join(s.strip() for s in m.group(1).split(",\n"))
        collapsed = f"[{items}]"
        # Keep the original if collapsing would make the line too long (80 chars).
        line_start = raw.rfind("\n", 0, m.start()) + 1
        indent = m.start() - line_start
        if indent + len(collapsed) > 80:
            return m.group(0)
        return collapsed

    raw = re.sub(
        rf"\[\n\s+({scalar}(?:,\n\s+{scalar})*)\n\s+\]",
        _collapse,
        raw,
    )
    return (raw + "\n").encode()
