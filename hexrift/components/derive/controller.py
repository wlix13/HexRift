from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

import orjson

from hexrift.components.derive.defaults import derive_server_names, derive_xhttp_host, resolve_node_reality
from hexrift.components.derive.identity import Namespace
from hexrift.constants import VLESS_FLOW, AccessType, RegionType, UplinkHttpMethod
from hexrift.core.controller import BaseController
from hexrift.errors import DeriveError


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp  # noqa: F401


class DeriveController(BaseController["HexRiftApp"]):
    def derive_users(self) -> list[dict]:
        cfg = self.app.schema.config
        ns = Namespace(cfg.global_.namespace)
        rows = []
        for user in cfg.users:
            user_base = ns.user_uuid(user.username, override=user.uuid)
            row: dict = {
                "username": user.username,
                "group": user.group,
                "access": user.access,
                "uuid": str(user_base),
                "email": ns.user_email(user.username),
            }
            if AccessType.SERVER in user.access:
                row["server_uuid"] = str(ns.server_uuid(user.username, user_base=user_base))
                row["server_email"] = ns.server_email(user.username)
            if user.guests:
                row["guests"] = [
                    {
                        "label": label,
                        "uuid": str(ns.guest_uuid(label, user.username, user_base=user_base)),
                        "email": ns.guest_email(label, user.username),
                    }
                    for label in user.guests
                ]
            if user.portals:
                row["portals"] = [
                    {
                        "label": p.label,
                        "uuid": str(ns.portal_uuid(p.label, user.username, user_base=user_base)),
                        "email": ns.portal_email(p.label, user.username),
                    }
                    for p in user.portals
                ]
            rows.append(row)
        return rows

    def derive_groups(self) -> list[dict]:
        cfg = self.app.schema.config
        ns = Namespace(cfg.global_.namespace)
        return [
            {
                "id": g.id,
                "short_id": ns.group_short_id(g),
            }
            for g in cfg.groups
        ]

    def build_share_urls(
        self,
        username: str,
        hub_id: str | None,
        fingerprint: str,
        keys_dir: Path,
        cdn: bool = False,
        guest: str | None = None,
    ) -> list[tuple[str, str]]:
        """Generate VLESS share URLs for user (or guest) on hub node.

        Returns a list of (label, url) pairs where label describes the hub/mode.
        """

        cfg = self.app.schema.config
        ns = Namespace(cfg.global_.namespace)

        user = next((u for u in cfg.users if u.username == username), None)
        if user is None:
            raise DeriveError(f"User not found: {username!r}")

        if AccessType.XHTTP not in user.access:
            raise DeriveError(f"User {username!r} does not have XHTTP access")

        user_base = ns.user_uuid(username, override=user.uuid)
        if guest is not None:
            if guest not in user.guests:
                raise DeriveError(f"Guest {guest!r} not found for user {username!r}")
            identity_uuid = ns.guest_uuid(guest, username, user_base=user_base)
            identity_label = f"{guest}@{username}"
        else:
            identity_uuid = user_base
            identity_label = username

        group = next((g for g in cfg.groups if g.id == user.group), None)
        if group is None:
            raise DeriveError(f"Group not found for user {username!r}: {user.group!r}")
        g_short_id = ns.group_short_id(group)

        if hub_id is not None:
            hub_region, hub_node = self.app.schema.get_node(hub_id)
            if hub_region.type != RegionType.HUB:
                raise DeriveError(f"Node {hub_id!r} is not a hub node")
            hub_node_pairs = [(hub_region, hub_node)]
        else:
            hub_node_pairs = [
                (region, node) for region in cfg.regions if region.type == RegionType.HUB for node in region.nodes
            ]

        results: list[tuple[str, str]] = []

        if cdn:
            if cfg.global_.cdn is None:
                raise DeriveError("CDN is not configured in global settings.")
            cdn_domain = cfg.global_.cdn.hub_domain
            seen_regions: set[str] = set()
            for hub_region, hub_node in hub_node_pairs:
                if hub_region.id in seen_regions:
                    continue
                seen_regions.add(hub_region.id)
                if not hub_region.cdn_xhttp_path:
                    continue
                hub_keys = self.app.keys.load_node_keys(hub_node.id, keys_dir)
                flow = VLESS_FLOW if hub_keys.encryption != "none" else ""
                extra = orjson.dumps(
                    {
                        "uplinkHTTPMethod": UplinkHttpMethod.PATCH,
                    }
                ).decode()
                params = "&".join(
                    [
                        f"encryption={hub_keys.encryption}",
                        f"flow={flow}",
                        "security=tls",
                        f"sni={cdn_domain}",
                        f"fp={fingerprint}",
                        f"sid={g_short_id}",
                        f"spx={quote('/', safe='')}",
                        f"alpn={quote('h3,h2,http/1.1', safe='')}",
                        "insecure=0",
                        "allowInsecure=0",
                        "type=xhttp",
                        f"host={cdn_domain}",
                        f"path={quote(hub_region.cdn_xhttp_path, safe='')}",
                        "mode=auto",
                        f"extra={quote(extra, safe='')}",
                    ]
                )
                fragment = f"{hub_region.id}(CDN)-{identity_label}"
                label = f"{hub_region.id}  CDN  {identity_label}"
                results.append((label, f"vless://{identity_uuid}@{cdn_domain}:443?{params}#{fragment}"))
        else:
            seen_default_regions: set[str] = set()
            for hub_region, hub_node in hub_node_pairs:
                # Deduplicate: nodes sharing region-default reality → one URL per region
                if hub_node.reality is None:
                    if hub_region.id in seen_default_regions:
                        continue
                    seen_default_regions.add(hub_region.id)
                    fragment = f"{hub_region.id}-{identity_label}"
                    label = f"{hub_region.id}  Reality  {identity_label}"
                else:
                    fragment = f"{hub_node.id}-{identity_label}"
                    label = f"{hub_node.id}  Reality  {identity_label}"

                hub_keys = self.app.keys.load_node_keys(hub_node.id, keys_dir)
                flow = VLESS_FLOW if hub_keys.encryption != "none" else ""
                reality = resolve_node_reality(hub_node, hub_region, cfg.defaults)
                server_names = derive_server_names(reality)
                xhttp_host = derive_xhttp_host(reality)
                params = "&".join(
                    [
                        f"encryption={hub_keys.encryption}",
                        f"flow={flow}",
                        "security=reality",
                        f"sni={server_names[0]}",
                        f"fp={fingerprint}",
                        f"pbk={hub_keys.reality_public_key}",
                        f"sid={g_short_id}",
                        "type=xhttp",
                        f"host={xhttp_host}",
                        f"path={quote(reality.xhttp_path, safe='')}",
                        "mode=auto",
                    ]
                )
                results.append(
                    (
                        label,
                        f"vless://{identity_uuid}@{hub_node.hostname}:443?{params}#{fragment}",
                    )
                )

        return results

    def derive_nodes(self) -> list[dict]:
        cfg = self.app.schema.config
        ns = Namespace(cfg.global_.namespace)
        hub_nodes = [n for r in cfg.regions if r.type == RegionType.HUB for n in r.nodes]
        rows = []
        for region in cfg.regions:
            for node in region.nodes:
                row: dict = {
                    "id": node.id,
                    "region": region.id,
                    "type": region.type,
                }
                if region.type == RegionType.EXIT:
                    row["short_id"] = ns.exit_short_id(node.id)
                    row["hub_exit_uuids"] = {hub.id: str(ns.hub_exit_uuid(hub.id, node.id)) for hub in hub_nodes}
                else:
                    row["hub_short_id"] = ns.hub_short_id(node.id)
                rows.append(row)
        return rows
