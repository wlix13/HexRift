"""Build Xray config dicts and serialize into json."""

from __future__ import annotations

import re

import orjson

from hexrift.components.render.context import ExitContext, HubContext, HubOutboundContext
from hexrift.constants import (
    WARP_VLESS_ROUTE,
    Socket,
    SpecialDestination,
    XrayNetwork,
    XrayProtocol,
    XraySecurity,
)
from hexrift.shared.xhttp import XHTTP_EXTRA, XHTTP_EXTRA_CDN, XMUX
from hexrift.shared.xray import DNS, LOG, SNIFFING, make_sockopt


def _warp_outbound(ipv6: bool) -> dict:
    return {
        "tag": SpecialDestination.WARP,
        "protocol": XrayProtocol.FREEDOM,
        "streamSettings": {
            "sockopt": {
                **make_sockopt(ipv6),
                "interface": "warp",
            }
        },
    }


def _xhttp_settings(host: str, path: str, mode: str = "auto", cdn: bool = False) -> dict:
    return {
        "host": host,
        "path": path,
        "mode": mode,
        "extra": XHTTP_EXTRA_CDN if cdn else XHTTP_EXTRA,
        "xmux": XMUX,
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
                "maxTimeDiff": 60000,
                "dest": ctx.reality_dest,
                "serverNames": ctx.reality_server_names,
                "privateKey": ctx.reality_private_key,
                "shortIds": [ctx.reality_short_id],
                "limitFallbackUpload": ctx.reality_fallback_limits.xray_settings,
                "limitFallbackDownload": ctx.reality_fallback_limits.xray_settings,
            },
            "sockopt": make_sockopt(ctx.ipv6),
        },
        "sniffing": SNIFFING,
    }

    routing_rules: list[dict] = [
        {
            "ip": ["127.0.0.1", "::1"],
            "port": 53,
            "outboundTag": SpecialDestination.DIRECT,
        },
    ]
    routing_rules.extend(ctx.extra_routes)
    routing_rules.append(
        {
            "vlessRoute": str(WARP_VLESS_ROUTE),
            "outboundTag": SpecialDestination.WARP,
        },
    )
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
            _warp_outbound(ctx.ipv6),
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
                    "xhttpSettings": _xhttp_settings(ctx.cdn_xhttp_host, ctx.cdn_xhttp_path, cdn=True),
                    "sockopt": make_sockopt(ctx.ipv6),
                },
                "sniffing": SNIFFING,
            }
        )
    config: dict = {
        "log": LOG,
    }

    config.update(
        {
            "inbounds": inbounds,
            "outbounds": outbounds,
            "routing": {
                "domainStrategy": "IPIfNonMatch",
                "rules": routing_rules,
            },
            "dns": DNS,
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
                "maxTimeDiff": 60000,
                "dest": ctx.reality_dest,
                "serverNames": ctx.reality_server_names,
                "privateKey": ctx.reality_private_key,
                "shortIds": ctx.reality_short_ids,
                "limitFallbackUpload": ctx.reality_fallback_limits.xray_settings,
                "limitFallbackDownload": ctx.reality_fallback_limits.xray_settings,
            },
            "sockopt": make_sockopt(ctx.ipv6),
        },
        "sniffing": SNIFFING,
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
        "sniffing": SNIFFING,
    }
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
                "sockopt": make_sockopt(ctx.ipv6),
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
            _warp_outbound(ctx.ipv6),
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
                    "xhttpSettings": _xhttp_settings(ctx.cdn_xhttp_host, ctx.cdn_xhttp_path, cdn=True),
                    "sockopt": make_sockopt(ctx.ipv6),
                },
                "sniffing": SNIFFING,
            }
        )
    if ctx.proxy_inbound:
        inbounds.append(proxy_inbound)

    config: dict = {
        "log": LOG,
    }
    config.update(
        {
            "inbounds": inbounds,
            "outbounds": outbounds,
            "routing": {
                "domainStrategy": "IPIfNonMatch",
                "balancers": ctx.balancers,
                "rules": ctx.routing_rules,
            },
            "dns": DNS,
        }
    )

    if ctx.observatory_selectors:
        config["burstObservatory"] = {
            "subjectSelector": ctx.observatory_selectors,
            "pingConfig": {
                "destination": "http://www.apple.com/library/test/success.html",
                "connectivity": "http://connectivitycheck.gstatic.com/generate_204",
                "interval": ctx.observatory.interval,
                "timeout": ctx.observatory.timeout,
                "sampling": ctx.observatory.sampling,
                "enableConcurrency": ctx.observatory.concurrency,
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
