from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from hexrift.components.derive import views
from hexrift.components.derive.identity import Namespace, iter_hub_identities
from hexrift.components.derive.topology import portal_tag
from hexrift.components.derive.wireguard import (
    derive_user_wireguard_keypair,
    iter_hub_wireguard_allocs,
    render_wireguard_client_conf,
)
from hexrift.components.schema.models.regions import HubNode, HubRegion
from hexrift.components.schema.models.resolve import resolve_node_wireguard, resolve_region_tls
from hexrift.components.schema.models.users import User
from hexrift.constants import (
    WIREGUARD_CLIENT_DNS,
    AccessType,
    RegionType,
)
from hexrift.core.controller import BaseController
from hexrift.errors import DeriveError
from hexrift.inbounds.base import InboundEnv, ShareClient
from hexrift.inbounds.cdn import CDN_SPEC
from hexrift.inbounds.hysteria import HYSTERIA_SPEC
from hexrift.inbounds.xhttp import XHTTP_SPEC, TlsXhttpContext
from hexrift.shared.crypto import x25519_urlsafe_to_std


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp  # noqa: F401
    from hexrift.components.schema.models.portals import PortalPublish
    from hexrift.components.schema.models.root import ConglomerateConfig


def _format_publish(entry: PortalPublish) -> str:
    allow = ", ".join(entry.allow) if entry.allow else "any"
    nodes = ", ".join(entry.nodes) if entry.nodes else "all"
    return f"{entry.port}/{entry.network} -> {entry.target}  allow: {allow}  nodes: {nodes}"


@dataclass(frozen=True)
class _Identity:
    """Resolved share/wireguard identity: user, one of their guests, or their server."""

    uuid: UUID
    email: str
    label: str


class DeriveController(BaseController["HexRiftApp"]):
    def check_identity_collisions(self, cfg: ConglomerateConfig) -> None:
        """Reject uuid overrides landing on an identity another owner already claims."""

        ns = Namespace(cfg.global_.namespace)
        owners: dict[UUID, str] = {}
        for identity, owner in iter_hub_identities(cfg, ns):
            claimed = owners.get(identity)
            if claimed is not None:
                raise DeriveError(f"UUID {identity} is claimed by both {claimed} and {owner}")
            owners[identity] = owner

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

    def _hub_node_pairs(self, hub_id: str | None) -> list[tuple[HubRegion, HubNode]]:
        cfg = self.app.schema.config
        if hub_id is not None:
            match self.app.schema.get_node(hub_id):
                case (HubRegion() as hub_region, HubNode() as hub_node):
                    return [(hub_region, hub_node)]
            raise DeriveError(f"Node {hub_id!r} is not a hub node")
        return [(region, node) for region in cfg.hub_regions for node in region.nodes]

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
                )
            )
        return rows

    def derive_portals(self) -> list[views.Portal]:
        cfg = self.app.schema.config
        ns = Namespace(cfg.global_.namespace)
        return [
            views.Portal(
                id=p.id,
                tag=portal_tag(p.id),
                uuid=str(ns.portal_uuid(p.id, override=p.uuid)),
                email=ns.portal_email(p.id),
                short_id=ns.portal_short_id(p.id),
                strict=p.strict,
                users=list(p.users),
                publish=[_format_publish(entry) for entry in p.publish],
            )
            for p in cfg.portals
        ]

    def derive_groups(self) -> list[views.Group]:
        cfg = self.app.schema.config
        ns = Namespace(cfg.global_.namespace)
        return [views.Group(id=g.id, short_id=ns.group_short_id(g)) for g in cfg.groups]

    def _share_env(self, hub_region: HubRegion, hub_node: HubNode, keys_dir: Path) -> InboundEnv:
        keys = self.app.keys.load_node_keys(hub_node.id, keys_dir)
        return InboundEnv(self.app.schema.config, hub_region, hub_node, keys)

    def _cdn_share_urls(
        self,
        hub_node_pairs: list[tuple[HubRegion, HubNode]],
        identity: _Identity,
        short_id: str,
        keys_dir: Path,
        fingerprint: str,
    ) -> list[tuple[str, str]]:
        if self.app.schema.config.global_.cdn is None:
            raise DeriveError("CDN is not configured in global settings.")
        results: list[tuple[str, str]] = []
        seen_regions: set[str] = set()
        for hub_region, hub_node in hub_node_pairs:
            if hub_region.id in seen_regions:
                continue
            seen_regions.add(hub_region.id)
            env = self._share_env(hub_region, hub_node, keys_dir)
            ctx = CDN_SPEC.build_context(env)
            if ctx is None:
                continue
            client = ShareClient(identity.uuid, short_id, fingerprint, f"{hub_region.id}(CDN)-{identity.label}")
            results.append((f"{hub_region.id}  CDN  {identity.label}", CDN_SPEC.share_url(ctx, env, client)))
        return results

    def _hysteria_share_urls(
        self,
        hub_node_pairs: list[tuple[HubRegion, HubNode]],
        identity: _Identity,
        short_id: str,
        keys_dir: Path,
        fingerprint: str,
    ) -> list[tuple[str, str]]:
        listeners = []
        for hub_region, hub_node in hub_node_pairs:
            env = self._share_env(hub_region, hub_node, keys_dir)
            ctx = HYSTERIA_SPEC.build_context(env)
            if ctx is not None:
                listeners.append((hub_region, hub_node, env, ctx))

        per_region: dict[str, set[tuple]] = {}
        for hub_region, _node, _env, ctx in listeners:
            per_region.setdefault(hub_region.id, set()).add((ctx.config.port, ctx.sni, ctx.pin, ctx.obfs_password))

        results: list[tuple[str, str]] = []
        emitted: dict[str, set[tuple]] = {}  # region id → emitted endpoint material
        for hub_region, hub_node, env, ctx in listeners:
            material = (ctx.config.port, ctx.sni, ctx.pin, ctx.obfs_password)
            region_emitted = emitted.setdefault(hub_region.id, set())
            if material in region_emitted:
                continue
            region_emitted.add(material)
            owner = hub_region.id if len(per_region[hub_region.id]) == 1 else hub_node.id
            client = ShareClient(identity.uuid, short_id, fingerprint, f"{owner}-{identity.label}")
            results.append((f"{owner}  Hysteria  {identity.label}", HYSTERIA_SPEC.share_url(ctx, env, client)))
        return results

    def _direct_share_urls(
        self,
        hub_node_pairs: list[tuple[HubRegion, HubNode]],
        user: User,
        identity: _Identity,
        short_id: str,
        keys_dir: Path,
        fingerprint: str,
        *,
        server: bool,
    ) -> list[tuple[str, str]]:
        cfg = self.app.schema.config
        results: list[tuple[str, str]] = []
        emitted: dict[str, list[tuple]] = {}  # region id -> material of emitted URLs
        for hub_region, hub_node in hub_node_pairs:
            if resolve_region_tls(hub_region, cfg.defaults) is not None:
                if AccessType.TLS not in user.access:
                    continue
            elif not server and AccessType.XHTTP not in user.access:
                continue
            env = self._share_env(hub_region, hub_node, keys_dir)
            ctx = XHTTP_SPEC.build_context(env)
            if isinstance(ctx, TlsXhttpContext):
                # Cert names host, so TLS URLs are per node
                owner, kind = hub_node.id, "TLS"
            else:
                # Nodes rendering same inbound with same keys share one URL, first one named by region
                region_emitted = emitted.setdefault(hub_region.id, [])
                if (ctx, env.node_keys) in region_emitted:
                    continue
                owner = hub_node.id if region_emitted else hub_region.id
                region_emitted.append((ctx, env.node_keys))
                kind = "Reality"
            client = ShareClient(identity.uuid, short_id, fingerprint, f"{owner}-{identity.label}")
            results.append((f"{owner}  {kind}  {identity.label}", XHTTP_SPEC.share_url(ctx, env, client)))
        return results

    def build_share_urls(
        self,
        username: str,
        hub_id: str | None,
        keys_dir: Path,
        fingerprint: str,
        *,
        cdn: bool = False,
        hysteria: bool = False,
        guest: str | None = None,
        server: bool = False,
        all_guests: bool = False,
    ) -> list[tuple[str, str]]:
        """Share URLs for user, guest, server, or all guests, as (label, url) pairs."""

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
                    hysteria=hysteria,
                    guest=label,
                ),
            )

        if cdn and hysteria:
            raise DeriveError("Flags 'cdn' and 'hysteria' are mutually exclusive")
        if cdn:
            if AccessType.CDN not in user.access:
                raise DeriveError(f"User {username!r} does not have CDN access")
        elif hysteria:
            if AccessType.HYSTERIA not in user.access:
                raise DeriveError(f"User {username!r} does not have Hysteria access")
        elif not server and not {AccessType.XHTTP, AccessType.TLS} & set(user.access):
            raise DeriveError(f"User {username!r} does not have xhttp or tls access")

        identity = self._resolve_identity(user, ns, guest=guest, server=server)

        group = next((g for g in cfg.groups if g.id == user.group), None)
        if group is None:
            raise DeriveError(f"Group not found for user {username!r}: {user.group!r}")
        g_short_id = ns.user_short_id(username) if guest is not None else ns.group_short_id(group)

        hub_node_pairs = self._hub_node_pairs(hub_id)

        if cdn:
            results = self._cdn_share_urls(hub_node_pairs, identity, g_short_id, keys_dir, fingerprint)
        elif hysteria:
            results = self._hysteria_share_urls(hub_node_pairs, identity, g_short_id, keys_dir, fingerprint)
        else:
            results = self._direct_share_urls(
                hub_node_pairs, user, identity, g_short_id, keys_dir, fingerprint, server=server
            )

        if not results:
            kind = "CDN" if cdn else "Hysteria" if hysteria else "direct"
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
        hub_nodes = [n for r in cfg.hub_regions for n in r.nodes]
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
