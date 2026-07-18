from __future__ import annotations

from hexrift.components.derive.defaults import derive_server_names, derive_xhttp_host, resolve_node_reality
from hexrift.components.derive.identity import Namespace
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.observability import LoggingConfig
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.constants import RegionType, XrayNetwork, XrayProtocol, XraySecurity
from hexrift.errors import RenderError
from hexrift.shared.xhttp import XHTTP_EXTRA, XMUX
from hexrift.shared.xray_defaults import make_log, make_sniffing, make_sockopt


def build_portal_config(
    cfg: ConglomerateConfig,
    username: str,
    label: str,
    hub_node_keys: dict[str, NodeKeys],
    fingerprint: str,
    group_id: str | None = None,
) -> dict:
    ns = Namespace(cfg.global_.namespace)
    user = next((u for u in cfg.users if u.username == username), None)
    if user is None:
        raise RenderError(f"User not found: {username!r}")
    user_base = ns.user_uuid(username, override=user.uuid)
    portal_id = str(ns.portal_uuid(label, username, user_base=user_base))

    resolved_group_id = group_id if group_id is not None else user.group
    group = next((g for g in cfg.groups if g.id == resolved_group_id), None)
    if group is None:
        raise RenderError(f"Group not found: {resolved_group_id!r}")
    short_id = ns.group_short_id(group)

    outbounds: list[dict] = []
    for region in cfg.regions:
        if region.type != RegionType.HUB:
            continue
        for node in region.nodes:
            keys = hub_node_keys[node.id]
            reality = resolve_node_reality(node, region, cfg.defaults)
            server_names = derive_server_names(reality)
            xhttp_host = derive_xhttp_host(reality)
            flow = keys.client_flow

            outbounds.append(
                {
                    "tag": f"portal-{node.id}",
                    "protocol": XrayProtocol.VLESS,
                    "settings": {
                        "address": node.hostname,
                        "port": 443,
                        "id": portal_id,
                        "flow": flow,
                        "encryption": keys.encryption,
                        "reverse": {
                            "tag": "direct",
                            "sniffing": make_sniffing(),
                        },
                    },
                    "streamSettings": {
                        "network": XrayNetwork.XHTTP,
                        "security": XraySecurity.REALITY,
                        "realitySettings": {
                            "publicKey": keys.reality_public_key,
                            "fingerprint": fingerprint,
                            "serverName": server_names[0],
                            "shortId": short_id,
                        },
                        "xhttpSettings": {
                            "host": xhttp_host,
                            "path": reality.xhttp_path,
                            "mode": "auto",
                            "extra": XHTTP_EXTRA,
                            "xmux": XMUX,
                        },
                        "sockopt": make_sockopt(False),
                    },
                }
            )

    outbounds.append(
        {
            "tag": "direct",
            "protocol": XrayProtocol.FREEDOM,
            "settings": {},
        },
    )

    return {
        "log": make_log(LoggingConfig()),
        "outbounds": outbounds,
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": [
                {
                    "network": "TCP,UDP",
                    "outboundTag": "direct",
                },
            ],
        },
    }
