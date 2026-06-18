from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.inbounds.context import build_exit_context


KEYS = NodeKeys(
    reality_private_key="FAKE_PRIV",
    reality_public_key="FAKE_PUB",
    decryption="none",
    encryption="none",
)


def _exit_cfg(node_haproxy: bool | None) -> ConglomerateConfig:
    """Exit node with CDN configured globally;
    But no `cdn_xhttp_path` on region, so disabling haproxy on node stays valid.
    """

    node: dict = {
        "id": "exitN1",
        "hostname": "exitN1.ap.t.ns",
        "reality": {
            "dest": "a.com:443",
            "xhttp_path": "/x/",
        },
    }
    if node_haproxy is not None:
        node["haproxy"] = node_haproxy
    return ConglomerateConfig.model_validate(
        {
            "global": {
                "namespace": "t.ns",
                "aphelion_domain": "ap.t.ns",
                "cdn": {
                    "exit_domain": "cdn-exit.t.ns",
                    "hub_domain": "cdn-hub.t.ns",
                },
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
                    "exit_connections": {
                        "method": "mlkem768x25519plus",
                        "fingerprint": "chrome",
                    },
                    "reality": {
                        "dest": "a.com:443",
                        "xhttp_path": "/x/",
                    },
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
            "routing": {
                "hub_default": "direct",
            },
            "regions": [
                {
                    "id": "exit1",
                    "type": "exit",
                    "vless_route": 1000,
                    "nodes": [node],
                },
            ],
        }
    )


def _shared(node_haproxy: bool | None):
    cfg = _exit_cfg(node_haproxy)
    region, node = cfg.regions[0], cfg.regions[0].nodes[0]
    return build_exit_context(cfg, region, node, KEYS).shared


class TestSharedContext:
    def test_haproxy_flag_default_true(self):
        assert _shared(node_haproxy=None).haproxy is True

    def test_haproxy_flag_node_override_false(self):
        assert _shared(node_haproxy=False).haproxy is False

    def test_trusted_headers_from_cdn(self):
        assert _shared(node_haproxy=True).trusted_forwarded_headers == ["X-Real-IP"]
