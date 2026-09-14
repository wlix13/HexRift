from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING

from hexrift.components.derive.defaults import (
    derive_server_names,
    derive_xhttp_host,
    resolve_node_reality,
)
from hexrift.components.derive.identity import Namespace
from hexrift.components.derive.topology import portal_tag
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.observability import LoggingConfig
from hexrift.components.schema.models.resolve import resolve_region_tls
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.constants import (
    XHTTP_TLS_ALPN,
    DomainStrategy,
    SpecialDestination,
    XrayNetwork,
    XrayProtocol,
    XraySecurity,
)
from hexrift.errors import RenderError
from hexrift.shared.xhttp import XHTTP_EXTRA, XMUX
from hexrift.shared.xray_defaults import make_log, make_sniffing, make_sockopt


if TYPE_CHECKING:
    from hexrift.components.schema.models.portals import Portal


def reverse_dial_outbound(
    *,
    tag: str,
    address: str,
    port: int,
    identity_uuid: str,
    flow: str,
    encryption: str,
    security: XraySecurity,
    security_settings: dict,
    xhttp_host: str,
    xhttp_path: str,
    reverse_tag: str,
    sniffing: bool = True,
) -> dict:
    """VLESS outbound that dials hub node and opens reverse tunnel."""

    return {
        "tag": tag,
        "protocol": XrayProtocol.VLESS,
        "settings": {
            "address": address,
            "port": port,
            "id": identity_uuid,
            "flow": flow,
            "encryption": encryption,
            "reverse": {
                "tag": reverse_tag,
                # routeOnly sniffing routes on the client-supplied SNI, not the destination the hub sent
                "sniffing": make_sniffing() if sniffing else {"enabled": False},
            },
        },
        "streamSettings": {
            "network": XrayNetwork.XHTTP,
            "security": security,
            f"{security}Settings": security_settings,  # Xray keys them realitySettings / tlsSettings
            "xhttpSettings": {
                "host": xhttp_host,
                "path": xhttp_path,
                "mode": "auto",
                "extra": XHTTP_EXTRA,
                "xmux": XMUX,
            },
            "sockopt": make_sockopt(None),
        },
    }


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def build_portal_rules(portal: Portal, reverse_tag: str) -> list[dict]:
    """Build portal-side rules for traffic emerging from reverse tunnel."""

    if not portal.strict:
        return [
            {
                "inboundTag": [reverse_tag],
                "outboundTag": SpecialDestination.DIRECT,
            }
        ]

    rules: list[dict] = []
    if portal.routes.domains:
        rules.append(
            {
                "inboundTag": [reverse_tag],
                "domain": portal.routes.domains,
                "outboundTag": SpecialDestination.DIRECT,
            }
        )
    if portal.routes.ips:
        rules.append(
            {
                "inboundTag": [reverse_tag],
                "ip": portal.routes.ips,
                "outboundTag": SpecialDestination.DIRECT,
            }
        )
    for entry in portal.publish:
        host, port = entry.target_host_port
        matcher = {"ip": [host]} if _is_ip_literal(host) else {"domain": [f"full:{host}"]}
        rules.append(
            {
                "inboundTag": [reverse_tag],
                **matcher,
                "port": port,
                "outboundTag": SpecialDestination.DIRECT,
            }
        )
    rules.append(
        {
            "inboundTag": [reverse_tag],
            "outboundTag": SpecialDestination.BLOCKED,
        }
    )
    return rules


def build_portal_config(
    cfg: ConglomerateConfig,
    portal_id: str,
    hub_node_keys: dict[str, NodeKeys],
    fingerprint: str,
) -> dict:
    ns = Namespace(cfg.global_.namespace)
    portal = next((p for p in cfg.portals if p.id == portal_id), None)
    if portal is None:
        raise RenderError(f"Portal not found: {portal_id!r}")
    identity = str(ns.portal_uuid(portal.id, override=portal.uuid))

    short_id = ns.portal_short_id(portal.id)

    reverse_tag = portal_tag(portal.id)
    outbounds: list[dict] = []
    for region in cfg.hub_regions:
        tls = resolve_region_tls(region, cfg.defaults)
        for node in region.nodes:
            keys = hub_node_keys[node.id]
            if tls is not None:
                security = XraySecurity.TLS
                settings = {"serverName": node.hostname, "alpn": list(XHTTP_TLS_ALPN), "fingerprint": fingerprint}
                xhttp_host, xhttp_path = node.hostname, tls.xhttp_path
            else:
                reality = resolve_node_reality(node, region, cfg.defaults)
                security = XraySecurity.REALITY
                settings = {
                    "publicKey": keys.reality_public_key,
                    "fingerprint": fingerprint,
                    "serverName": derive_server_names(reality)[0],
                    "shortId": short_id,
                }
                xhttp_host, xhttp_path = derive_xhttp_host(reality), reality.xhttp_path
            outbounds.append(
                reverse_dial_outbound(
                    tag=f"portal-{node.id}",
                    address=node.hostname,
                    port=443,
                    identity_uuid=identity,
                    flow=keys.client_flow,
                    encryption=keys.encryption,
                    security=security,
                    security_settings=settings,
                    xhttp_host=xhttp_host,
                    xhttp_path=xhttp_path,
                    reverse_tag=reverse_tag,
                    sniffing=not portal.strict,
                )
            )

    outbounds.append(
        {
            "tag": SpecialDestination.DIRECT,
            "protocol": XrayProtocol.FREEDOM,
            # Xray blackholes vless-reverse traffic unless freedom carries explicit allow rule
            "settings": {
                "finalRules": [{"action": "allow"}],
            },
        },
    )
    if portal.strict:
        outbounds.append(
            {
                "tag": SpecialDestination.BLOCKED,
                "protocol": XrayProtocol.BLACKHOLE,
                "settings": {},
            },
        )

    rules = build_portal_rules(portal, reverse_tag)
    # Safety pin: unmatched traffic would otherwise fall to the first outbound, looping back in
    rules.append(
        {
            "network": "TCP,UDP",
            "outboundTag": SpecialDestination.DIRECT,
        }
    )

    return {
        "log": make_log(LoggingConfig()),
        "outbounds": outbounds,
        "routing": {
            # Strict's catch-all always matches first, so IPIfNonMatch never gets its DNS-backed pass
            "domainStrategy": DomainStrategy.IP_ON_DEMAND if portal.strict else DomainStrategy.IP_IF_NON_MATCH,
            "rules": rules,
        },
    }
