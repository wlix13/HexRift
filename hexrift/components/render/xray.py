"""Build Xray config dicts and serialize into json."""

from __future__ import annotations

import json
import re

from hexrift.constants import (
    WARP_VLESS_ROUTE,
    AccessType,
    RegionType,
    SpecialDestination,
    XrayNetwork,
    XrayProtocol,
    XraySecurity,
)
from hexrift.inbounds.base import InboundContext, SharedContext
from hexrift.inbounds.context import ExitContext, HubContext, HubOutboundContext
from hexrift.inbounds.registry import specs_for
from hexrift.shared.xhttp import make_xhttp_settings
from hexrift.shared.xray_defaults import (
    LOG,
    make_dns,
    make_dns_direct_rule,
    make_sockopt,
)


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


def _build_inbounds(role: RegionType, slots: dict[AccessType, InboundContext], shared: SharedContext) -> list[dict]:
    inbounds: list[dict] = []
    for spec in specs_for(role):
        spec_ctx = spec.narrow(slots)
        if spec_ctx is not None:
            inbounds.append(spec.fragment(spec_ctx, shared))
    return inbounds


def build_exit_config(ctx: ExitContext) -> dict:
    shared = ctx.shared
    inbounds = _build_inbounds(RegionType.EXIT, ctx.slots, shared)

    routing_rules: list[dict] = [
        make_dns_direct_rule(
            shared.dns_address,
            shared.dns_port,
        ),
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
                "settings": {
                    "domainStrategy": "UseIPv6v4" if shared.ipv6 else "UseIPv4",
                },
            },
            {
                "tag": SpecialDestination.BLOCKED,
                "protocol": XrayProtocol.BLACKHOLE,
                "settings": {},
            },
            _warp_outbound(shared.ipv6),
        ]
    )

    return {
        "log": LOG,
        "inbounds": inbounds,
        "outbounds": outbounds,
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": routing_rules,
        },
        "dns": make_dns(shared.dns_address, shared.dns_port),
    }


def build_hub_config(ctx: HubContext) -> dict:
    shared = ctx.shared
    inbounds = _build_inbounds(RegionType.HUB, ctx.slots, shared)

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
                "xhttpSettings": make_xhttp_settings(ob.xhttp_host, ob.xhttp_path),
                "realitySettings": {
                    "publicKey": ob.public_key,
                    "fingerprint": ob.fingerprint,
                    "serverName": ob.server_name,
                    "shortId": ob.short_id,
                },
                "sockopt": make_sockopt(shared.ipv6),
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
            _warp_outbound(shared.ipv6),
        ]
    )

    config: dict = {
        "log": LOG,
        "inbounds": inbounds,
        "outbounds": outbounds,
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "balancers": ctx.balancers,
            "rules": ctx.routing_rules,
        },
        "dns": make_dns(shared.dns_address, shared.dns_port),
    }

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
    raw = json.dumps(config, indent=2, ensure_ascii=False)
    if not compact:
        return (raw + "\n").encode()
    # Collapse arrays whose items are all simple scalars (strings/numbers/booleans)
    # that json.dumps(indent=2) expanded across multiple lines back to a single line.
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
