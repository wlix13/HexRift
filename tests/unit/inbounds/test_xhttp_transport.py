from dataclasses import replace
from uuid import UUID

from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.inbounds.base import InboundEnv, ShareClient
from hexrift.inbounds.xhttp import XHTTP_SPEC, TcpRealityContext
from hexrift.shared.xhttp import make_xhttp_settings
from tests.unit.render.helpers import make_shared


_KEYS = NodeKeys(
    reality_private_key="FAKE_PRIV",
    reality_public_key="FAKE_PUB",
    decryption="mlkem768x25519plus.native.600s.FAKE",
    encryption="mlkem768x25519plus.native.0rtt.FAKE",
)
_CLIENT = ShareClient(
    UUID(int=1),
    "0123456789abcdef",
    "chrome",
    "hub1-exit1",
)


def _config(transport: str | None = None, xhttp_path: str | None = "/x/") -> ConglomerateConfig:
    node: dict = {
        "id": "exit1N1",
        "hostname": "exit1N1.ap.t.ns",
        "reality": {"dest": "a.com:443"},
    }
    if xhttp_path is not None:
        node["xhttp"] = {"path": xhttp_path}
    region: dict = {
        "id": "exit1",
        "type": "exit",
        "vless_route": 1000,
        "nodes": [node],
    }
    if transport is not None:
        region["transport"] = transport
    return ConglomerateConfig.model_validate(
        {
            "global": {
                "namespace": "t.ns",
                "aphelion_domain": "ap.t.ns",
            },
            "defaults": {
                "exit": {
                    "ipv6": True,
                    "keys": {
                        "auth": "mlkem768",
                        "mode": "native",
                        "session_time": "600s",
                    },
                },
                "hub": {
                    "ipv6": True,
                    "keys": {
                        "auth": "x25519",
                        "mode": "native",
                        "session_time": "600s",
                    },
                    "exit_connections": {"method": "mlkem768x25519plus", "fingerprint": "chrome"},
                    "reality": {"dest": "a.com:443"},
                    "xhttp": {"path": "/hub/"},
                },
            },
            "groups": [{"id": "grp1"}],
            "users": [
                {
                    "username": "alice",
                    "group": "grp1",
                    "access": ["xhttp"],
                },
            ],
            "routing": {"hub_default": "direct"},
            "regions": [
                region,
                {
                    "id": "hub1",
                    "type": "hub",
                    "nodes": [{"id": "hub1N1", "hostname": "hub1N1.ap.t.ns"}],
                },
            ],
        }
    )


def _env(transport: str | None = None) -> InboundEnv:
    config = _config(transport, xhttp_path=None if transport == "tcp" else "/x/")
    region = config.exit_regions[0]
    return InboundEnv(
        config=config,
        region=region,
        node=region.nodes[0],
        node_keys=_KEYS,
    )


def test_tcp_region_needs_no_xhttp_path_and_builds_tcp_context():
    assert isinstance(XHTTP_SPEC.build_context(_env("tcp")), TcpRealityContext)


def test_tcp_inbound_is_raw_tcp_with_reality():
    frag = XHTTP_SPEC.fragment(XHTTP_SPEC.build_context(_env("tcp")), make_shared(haproxy=False, ipv6=True))

    assert frag["tag"] == "direct-tcp"
    assert frag["streamSettings"]["network"] == "tcp"
    assert "xhttpSettings" not in frag["streamSettings"]
    assert frag["streamSettings"]["realitySettings"]["dest"] == "a.com:443"
    assert [client["flow"] for client in frag["settings"]["clients"]] == ["xtls-rprx-vision"]


def test_tcp_inbound_keeps_vision_without_vless_encryption():
    env = replace(
        _env("tcp"),
        node_keys=_KEYS.model_copy(update={"decryption": "none", "encryption": "none"}),
    )
    frag = XHTTP_SPEC.fragment(
        XHTTP_SPEC.build_context(env),
        make_shared(
            haproxy=False,
            ipv6=True,
            decryption="none",
        ),
    )

    assert frag["settings"]["decryption"] == "none"
    assert [client["flow"] for client in frag["settings"]["clients"]] == ["xtls-rprx-vision"]


def test_tcp_share_url_carries_no_http_layer():
    env = _env("tcp")
    url = XHTTP_SPEC.share_url(XHTTP_SPEC.build_context(env), env, _CLIENT)

    assert "type=tcp" in url
    assert "host=" not in url and "path=" not in url
    assert "flow=xtls-rprx-vision-udp443" in url


def test_xhttp_region_keeps_the_http_layer():
    frag = XHTTP_SPEC.fragment(XHTTP_SPEC.build_context(_env()), make_shared(haproxy=False, ipv6=True))

    assert frag["tag"] == "direct-xhttp"
    assert frag["streamSettings"]["xhttpSettings"] == make_xhttp_settings("a.com", "/x/")
