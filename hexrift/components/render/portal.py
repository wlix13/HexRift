from __future__ import annotations

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
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.constants import (
    DomainStrategy,
    RegionType,
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
    reality_public_key: str,
    server_name: str,
    short_id: str,
    fingerprint: str,
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
            "security": XraySecurity.REALITY,
            "realitySettings": {
                "publicKey": reality_public_key,
                "fingerprint": fingerprint,
                "serverName": server_name,
                "shortId": short_id,
            },
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
    for region in cfg.regions:
        if region.type != RegionType.HUB:
            continue
        for node in region.nodes:
            keys = hub_node_keys[node.id]
            reality = resolve_node_reality(node, region, cfg.defaults)
            outbounds.append(
                reverse_dial_outbound(
                    tag=f"portal-{node.id}",
                    address=node.hostname,
                    port=443,
                    identity_uuid=identity,
                    flow=keys.client_flow,
                    encryption=keys.encryption,
                    reality_public_key=keys.reality_public_key,
                    server_name=derive_server_names(reality)[0],
                    short_id=short_id,
                    fingerprint=fingerprint,
                    xhttp_host=derive_xhttp_host(reality),
                    xhttp_path=reality.xhttp_path,
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
