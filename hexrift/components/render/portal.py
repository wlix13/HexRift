from __future__ import annotations

from hexrift.components.derive.defaults import (
    derive_server_names,
    derive_xhttp_host,
    resolve_node_ipv6,
    resolve_node_reality,
)
from hexrift.components.derive.identity import Namespace
from hexrift.components.derive.topology import portal_tag
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.observability import LoggingConfig
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.constants import RegionType, XrayNetwork, XrayProtocol, XraySecurity
from hexrift.errors import RenderError
from hexrift.shared.xhttp import XHTTP_EXTRA, XMUX
from hexrift.shared.xray_defaults import make_log, make_sniffing, make_sockopt


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
    ipv6: bool = False,
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
                "sniffing": make_sniffing(),
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
            "sockopt": make_sockopt(ipv6),
        },
    }


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
                    ipv6=resolve_node_ipv6(node, region, cfg.defaults),
                )
            )

    outbounds.append(
        {
            "tag": "direct",
            "protocol": XrayProtocol.FREEDOM,
            # Xray blackholes vless-reverse traffic unless freedom carries explicit allow rule
            "settings": {
                "finalRules": [{"action": "allow"}],
            },
        },
    )

    return {
        "log": make_log(LoggingConfig()),
        "outbounds": outbounds,
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": [
                {
                    "inboundTag": [reverse_tag],
                    "outboundTag": "direct",
                },
                # Safety pin: unmatched traffic would otherwise fall to the first outbound, looping back in
                {
                    "network": "TCP,UDP",
                    "outboundTag": "direct",
                },
            ],
        },
    }
