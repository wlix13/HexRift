"""Shared builders for inbound spec unit tests."""

from hexrift.components.schema.models.defaults import (
    DefaultsConfig,
    ExitConnectionsConfig,
    ExitDefaults,
    HubDefaults,
    KeysConfig,
    ObservatoryConfig,
)
from hexrift.components.schema.models.portals import Portal, PortalRoutes
from hexrift.components.schema.models.regions import HysteriaConfig, Node, Region, WireguardConfig, XdnsConfig
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.components.schema.models.users import User
from hexrift.constants import AccessType, AuthMethod, HandshakeMethod, RegionType, TlsFingerprint


_EXIT_KEYS = KeysConfig(mode="native", session_time="600s", auth=AuthMethod.MLKEM768)
_HUB_KEYS = KeysConfig(mode="native", session_time="600s", auth=AuthMethod.X25519)
_HUB_REALITY = RealityConfig(dest="vk.com:443", xhttp_path="/hub/")
_EXIT_CONNS = ExitConnectionsConfig(method=HandshakeMethod.MLKEM768, fingerprint=TlsFingerprint.CHROME)


def make_defaults(
    *,
    proxy_inbound: bool = False,
    xdns: XdnsConfig | None = None,
    wireguard: WireguardConfig | None = None,
    hysteria: HysteriaConfig | None = None,
    exit_hysteria: HysteriaConfig | None = None,
) -> DefaultsConfig:
    return DefaultsConfig(
        exit=ExitDefaults(ipv6=True, keys=_EXIT_KEYS, hysteria=exit_hysteria),
        hub=HubDefaults(
            ipv6=False,
            keys=_HUB_KEYS,
            exit_connections=_EXIT_CONNS,
            reality=_HUB_REALITY,
            proxy_inbound=proxy_inbound,
            xdns=xdns,
            wireguard=wireguard,
            hysteria=hysteria,
            observatory=ObservatoryConfig(),
        ),
    )


def make_user(
    username: str = "alice",
    group: str = "grp1",
    access: list[str] | None = None,
    guests: list[str] | None = None,
) -> User:
    # None means "default"; an explicit empty access list stays empty.
    access_list = ["xhttp"] if access is None else access
    return User.model_construct(
        username=username,
        group=group,
        access=[AccessType(a) for a in access_list],
        uuid=None,
        guests=guests or [],
    )


def make_portal(
    portal_id: str = "home",
    users: list[str] | None = None,
    domains: list[str] | None = None,
    ips: list[str] | None = None,
) -> Portal:
    routes = PortalRoutes.model_construct(domains=domains, ips=ips)
    return Portal.model_construct(
        id=portal_id,
        users=users or ["alice"],
        routes=routes,
        uuid=None,
        group=None,
    )


def make_hub_region(**kwargs) -> Region:
    defaults = {
        "id": "hub1",
        "type": RegionType.HUB,
        "nodes": [Node(id="hubN1", hostname="h.test.ns")],
    }
    defaults.update(kwargs)
    return Region.model_validate(defaults)
