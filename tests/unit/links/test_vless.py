from types import SimpleNamespace
from typing import cast

import pytest

from hexrift.components.derive.defaults import derive_xhttp_host, resolve_node_reality
from hexrift.components.derive.identity import Namespace
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.defaults import ExitConnectionsConfig
from hexrift.components.schema.models.regions import ExitNode, ExitRegion, HubNode
from hexrift.components.schema.models.resolve import resolve_node_xhttp
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.components.schema.models.shared import RealityConfig, XhttpConfig
from hexrift.constants import ExitTransport, HandshakeMethod, RegionType, TlsFingerprint, XrayNetwork
from hexrift.links.base import LinkEnv
from hexrift.links.registry import build_link, render_link
from hexrift.links.vless import TcpVlessLinkContext, VlessLinkSpec, XhttpVlessLinkContext
from hexrift.shared.xhttp import make_xhttp_settings
from tests.unit.inbounds.helpers import make_defaults


_KEYS = NodeKeys(
    reality_private_key="FAKE_PRIV",
    reality_public_key="FAKE_PUB",
    decryption="mlkem768x25519plus.native.600s.FAKE",
    encryption="mlkem768x25519plus.native.0rtt.FAKE",
)
_EXIT_CONNECTIONS = ExitConnectionsConfig(
    method=HandshakeMethod.MLKEM768,
    fingerprint=TlsFingerprint.CHROME,
)
_IDENTITY = "aaaaaaaa-0000-0000-0000-000000000001"


def _region(transport: ExitTransport | None) -> ExitRegion:
    fields: dict = {
        "id": "exit1",
        "type": RegionType.EXIT,
        "vless_route": 1000,
        "nodes": [
            ExitNode(
                id="exitN1",
                hostname="exitN1.ap.t.ns",
                reality=RealityConfig(dest="a.com:443"),
            ),
        ],
    }
    if transport is not None:
        fields["transport"] = transport
    return ExitRegion.model_validate(fields)


def _env(region: ExitRegion, exit_xhttp: XhttpConfig | None = XhttpConfig(path="/x/")) -> LinkEnv:
    config = cast(
        ConglomerateConfig,
        SimpleNamespace(
            defaults=make_defaults(exit_xhttp=exit_xhttp),
            global_=SimpleNamespace(aphelion_domain="ap.t.ns"),
        ),
    )
    return LinkEnv(
        config=config,
        hub=HubNode.model_construct(id="hubN1", hostname="hubN1.ap.t.ns"),
        exit_region=region,
        exit_node=region.nodes[0],
        exit_keys=_KEYS,
        ns=Namespace("ap.t.ns"),
        exit_connections=_EXIT_CONNECTIONS,
    )


def _render(region: ExitRegion, exit_xhttp: XhttpConfig | None = XhttpConfig(path="/x/")) -> dict:
    return render_link(build_link(_env(region, exit_xhttp), _IDENTITY, ""), ipv6=False)


@pytest.mark.parametrize("transport", [None, ExitTransport.XHTTP])
def test_xhttp_region_renders_the_http_layer(transport):
    region = _region(transport)
    env = _env(region)
    reality = resolve_node_reality(region.nodes[0], region, env.config.defaults)
    xhttp = resolve_node_xhttp(region.nodes[0], region, env.config.defaults)
    stream = _render(region)["streamSettings"]

    assert stream["network"] == XrayNetwork.XHTTP
    assert stream["xhttpSettings"] == make_xhttp_settings(derive_xhttp_host(reality, xhttp), xhttp.path)
    assert stream["realitySettings"]["serverName"] == "a.com"


@pytest.mark.parametrize("exit_xhttp", [XhttpConfig(path="/x/"), None])
def test_tcp_region_renders_raw_tcp_and_needs_no_xhttp_path(exit_xhttp):
    stream = _render(_region(ExitTransport.TCP), exit_xhttp)["streamSettings"]

    assert stream["network"] == XrayNetwork.TCP
    assert stream["security"] == "reality"
    assert stream["realitySettings"]["serverName"] == "a.com"
    assert "xhttpSettings" not in stream


def test_tcp_region_outbound_carries_the_vision_flow():
    vnext = _render(_region(ExitTransport.TCP))["settings"]["vnext"][0]

    assert vnext["address"] == "exitN1.ap.t.ns"
    assert vnext["users"] == [
        {
            "id": _IDENTITY,
            "encryption": _KEYS.encryption,
            "flow": "xtls-rprx-vision-udp443",
        }
    ]


@pytest.mark.parametrize(
    ("transport", "context_type"),
    [
        (ExitTransport.TCP, TcpVlessLinkContext),
        (ExitTransport.XHTTP, XhttpVlessLinkContext),
    ],
)
def test_build_context_picks_the_context_for_the_transport(transport, context_type):
    ctx = VlessLinkSpec().build_context(_env(_region(transport)), _IDENTITY, "")

    assert isinstance(ctx, context_type)
    assert ctx.transport is transport
