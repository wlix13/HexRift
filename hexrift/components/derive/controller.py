from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from hexrift.components.derive import views
from hexrift.components.derive.defaults import resolve_node_reality
from hexrift.components.derive.identity import Namespace
from hexrift.components.derive.topology import portal_tag
from hexrift.components.derive.wireguard import (
    derive_user_wireguard_keypair,
    iter_hub_wireguard_allocs,
    render_wireguard_client_conf,
)
from hexrift.components.schema.models.regions import Node, Region
from hexrift.components.schema.models.users import User
from hexrift.constants import (
    WIREGUARD_CLIENT_DNS,
    AccessType,
    RegionType,
)
from hexrift.core.controller import BaseController
from hexrift.errors import DeriveError
from hexrift.inbounds.cdn import build_cdn_share_url
from hexrift.inbounds.wireguard import resolve_node_wireguard
from hexrift.inbounds.xhttp import build_reality_share_url
from hexrift.shared.crypto import x25519_urlsafe_to_std


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp  # noqa: F401


@dataclass(frozen=True)
class _Identity:
    """Resolved share/wireguard identity: user, one of their guests, or their server."""

    uuid: UUID
    email: str
    label: str


class DeriveController(BaseController["HexRiftApp"]):
    def _resolve_user(self, username: str) -> User:
        user = next((u for u in self.app.schema.config.users if u.username == username), None)
        if user is None:
            raise DeriveError(f"User not found: {username!r}")
        return user

    def _resolve_identity(self, user: User, ns: Namespace, *, guest: str | None, server: bool) -> _Identity:
        if server and guest is not None:
            raise DeriveError("Flags 'server' and 'guest' are mutually exclusive")
        user_base = ns.user_uuid(user.username, override=user.uuid)
        if server:
            if AccessType.SERVER not in user.access:
                raise DeriveError(f"User {user.username!r} does not have server access")
            return _Identity(
                ns.server_uuid(user.username, user_base=user_base),
                ns.server_email(user.username),
                ns.server_email(user.username),
            )
        if guest is not None:
            if guest not in user.guests:
                raise DeriveError(f"Guest {guest!r} not found for user {user.username!r}")
            return _Identity(
                ns.guest_uuid(guest, user.username, user_base=user_base),
                ns.guest_email(guest, user.username),
                f"{guest}@{user.username}",
            )
        return _Identity(user_base, ns.user_email(user.username), user.username)

    def _hub_node_pairs(self, hub_id: str | None) -> list[tuple[Region, Node]]:
        cfg = self.app.schema.config
        if hub_id is not None:
            hub_region, hub_node = self.app.schema.get_node(hub_id)
            if hub_region.type != RegionType.HUB:
                raise DeriveError(f"Node {hub_id!r} is not a hub node")
            return [(hub_region, hub_node)]
        return [(region, node) for region in cfg.regions if region.type == RegionType.HUB for node in region.nodes]

    def _for_all_guests(self, user: User, build_one: Callable[[str], list[tuple[str, str]]]) -> list[tuple[str, str]]:
        if not user.guests:
            raise DeriveError(f"User {user.username!r} has no guests configured.")
        results: list[tuple[str, str]] = []
        for label in user.guests:
            results += build_one(label)
        return results

    def derive_users(self) -> list[views.User]:
        cfg = self.app.schema.config
        ns = Namespace(cfg.global_.namespace)
        rows: list[views.User] = []
        for user in cfg.users:
            user_base = ns.user_uuid(user.username, override=user.uuid)
            server_uuid = server_email = None
            if AccessType.SERVER in user.access:
                server_uuid = str(ns.server_uuid(user.username, user_base=user_base))
                server_email = ns.server_email(user.username)
            guests = [
                views.Guest(
                    label=label,
                    uuid=str(ns.guest_uuid(label, user.username, user_base=user_base)),
                    email=ns.guest_email(label, user.username),
                    short_id=ns.user_short_id(user.username),
                )
                for label in user.guests
            ]
            portals = [
                views.Portal(
                    label=p.label,
                    tag=portal_tag(p.label),
                    uuid=str(ns.portal_uuid(p.label, user.username, user_base=user_base)),
                    email=ns.portal_email(p.label, user.username),
                )
                for p in user.portals
            ]
            rows.append(
                views.User(
                    username=user.username,
                    group=user.group,
                    access=user.access,
                    uuid=str(user_base),
                    email=ns.user_email(user.username),
                    server_uuid=server_uuid,
                    server_email=server_email,
                    guests=guests,
                    portals=portals,
                )
            )
        return rows

    def derive_groups(self) -> list[views.Group]:
        cfg = self.app.schema.config
        ns = Namespace(cfg.global_.namespace)
        return [views.Group(id=g.id, short_id=ns.group_short_id(g)) for g in cfg.groups]

    def build_share_urls(
        self,
        username: str,
        hub_id: str | None,
        keys_dir: Path,
        fingerprint: str,
        *,
        cdn: bool = False,
        guest: str | None = None,
        server: bool = False,
        all_guests: bool = False,
    ) -> list[tuple[str, str]]:
        """Generate VLESS share URLs for user (or guest/server, or all guests) on hub node.

        Returns list of (label, url) pairs where label describes hub/mode.
        """

        cfg = self.app.schema.config
        ns = Namespace(cfg.global_.namespace)
        user = self._resolve_user(username)

        if all_guests:
            if guest is not None or server:
                raise DeriveError("Flag 'all_guests' cannot be combined with 'guest' or 'server'")
            return self._for_all_guests(
                user,
                lambda label: self.build_share_urls(
                    username,
                    hub_id,
                    keys_dir,
                    fingerprint,
                    cdn=cdn,
                    guest=label,
                ),
            )

        if cdn:
            if AccessType.CDN not in user.access:
                raise DeriveError(f"User {username!r} does not have CDN access")
        elif not server and AccessType.XHTTP not in user.access:
            raise DeriveError(f"User {username!r} does not have XHTTP access")

        identity = self._resolve_identity(user, ns, guest=guest, server=server)

        group = next((g for g in cfg.groups if g.id == user.group), None)
        if group is None:
            raise DeriveError(f"Group not found for user {username!r}: {user.group!r}")
        g_short_id = ns.user_short_id(username) if guest is not None else ns.group_short_id(group)

        hub_node_pairs = self._hub_node_pairs(hub_id)

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
                label = f"{hub_region.id}  CDN  {identity.label}"
                url = build_cdn_share_url(
                    identity_uuid=identity.uuid,
                    cdn_domain=cdn_domain,
                    cdn_path=hub_region.cdn_xhttp_path,
                    hub_keys=hub_keys,
                    short_id=g_short_id,
                    fingerprint=fingerprint,
                    fragment=f"{hub_region.id}(CDN)-{identity.label}",
                )
                results.append((label, url))
        else:
            seen_default_regions: set[str] = set()
            for hub_region, hub_node in hub_node_pairs:
                # Deduplicate: nodes sharing region-default reality → one URL per region
                if hub_node.reality is None:
                    if hub_region.id in seen_default_regions:
                        continue
                    seen_default_regions.add(hub_region.id)
                    fragment = f"{hub_region.id}-{identity.label}"
                    label = f"{hub_region.id}  Reality  {identity.label}"
                else:
                    fragment = f"{hub_node.id}-{identity.label}"
                    label = f"{hub_node.id}  Reality  {identity.label}"

                hub_keys = self.app.keys.load_node_keys(hub_node.id, keys_dir)
                url = build_reality_share_url(
                    identity_uuid=identity.uuid,
                    hostname=hub_node.hostname,
                    hub_keys=hub_keys,
                    reality=resolve_node_reality(hub_node, hub_region, cfg.defaults),
                    short_id=g_short_id,
                    fingerprint=fingerprint,
                    fragment=fragment,
                )
                results.append((label, url))

        if not results:
            kind = "CDN" if cdn else "Reality"
            raise DeriveError(f"No {kind} hub nodes found for user {username!r}")
        return results

    def build_wireguard_configs(
        self,
        username: str,
        hub_id: str | None,
        keys_dir: Path,
        *,
        guest: str | None = None,
        server: bool = False,
        all_guests: bool = False,
    ) -> list[tuple[str, str]]:
        """Generate WireGuard client configs for user (or guest/server, or all guests) on hub node(s).

        Returns list of (label, conf) pairs where conf is standard WireGuard `.conf`.
        """

        cfg = self.app.schema.config
        ns = Namespace(cfg.global_.namespace)
        user = self._resolve_user(username)

        if all_guests:
            if guest is not None or server:
                raise DeriveError("Flag 'all_guests' cannot be combined with 'guest' or 'server'")
            return self._for_all_guests(
                user,
                lambda label: self.build_wireguard_configs(
                    username,
                    hub_id,
                    keys_dir,
                    guest=label,
                ),
            )

        if AccessType.WIREGUARD not in user.access:
            raise DeriveError(f"User {username!r} does not have WireGuard access")

        identity = self._resolve_identity(user, ns, guest=guest, server=server)
        target_email = identity.email
        conf_label = identity.label

        hub_node_pairs = self._hub_node_pairs(hub_id)

        results: list[tuple[str, str]] = []
        for _hub_region, hub_node in hub_node_pairs:
            wg = resolve_node_wireguard(hub_node, cfg.defaults)
            if wg is None:
                continue

            # Same canonical allocation as the inbound, so the client address matches by construction.
            allocs = {a.email: a for a in iter_hub_wireguard_allocs(cfg.users, ns, wg.subnet)}
            alloc = allocs.get(target_email)
            if alloc is None:
                continue

            hub_keys = self.app.keys.load_node_keys(hub_node.id, keys_dir)
            client_private, _client_public = derive_user_wireguard_keypair(
                hub_keys.reality_private_key,
                alloc.identity_uuid,
                ns.name,
            )
            server_public = x25519_urlsafe_to_std(hub_keys.reality_public_key)

            conf = render_wireguard_client_conf(
                private_key=client_private,
                address=alloc.address,
                dns=[WIREGUARD_CLIENT_DNS],
                mtu=wg.mtu,
                server_public_key=server_public,
                endpoint=f"{hub_node.hostname}:{wg.port}",
                allowed_ips=["0.0.0.0/0"],
                keepalive=wg.keepalive,
            )
            results.append((f"{hub_node.id}  WireGuard  {conf_label}", conf))

        if not results:
            raise DeriveError(f"No WireGuard-enabled hub nodes found for user {username!r}")
        return results

    def derive_nodes(self) -> list[views.Node]:
        cfg = self.app.schema.config
        ns = Namespace(cfg.global_.namespace)
        hub_nodes = [n for r in cfg.regions if r.type == RegionType.HUB for n in r.nodes]
        rows: list[views.Node] = []
        for region in cfg.regions:
            for node in region.nodes:
                if region.type == RegionType.EXIT:
                    rows.append(
                        views.Node(
                            id=node.id,
                            region=region.id,
                            type=region.type,
                            short_id=ns.exit_short_id(node.id),
                            hub_exit_uuids={hub.id: str(ns.hub_exit_uuid(hub.id, node.id)) for hub in hub_nodes},
                        )
                    )
                else:
                    rows.append(
                        views.Node(
                            id=node.id,
                            region=region.id,
                            type=region.type,
                            hub_short_id=ns.hub_short_id(node.id),
                        )
                    )
        return rows
