from typing import Any

from hexrift.components.derive.topology import PublishedPort
from hexrift.components.render.xray import build_hub_config
from hexrift.constants import PublishNetwork
from hexrift.inbounds.forward import forward_fragment
from hexrift.shared.xray_defaults import make_sockopt
from tests.unit.render.helpers import hub_ctx, make_shared


def _published(**overrides: Any) -> PublishedPort:
    defaults: dict[str, Any] = {
        "tag": "home-publish-8443",
        "reverse_tag": "home-portal",
        "port": 8443,
        "target_host": "192.168.1.10",
        "target_port": 443,
        "network": PublishNetwork.TCP,
        "allow": [],
    }
    defaults.update(overrides)
    return PublishedPort(**defaults)


class TestForwardFragment:
    def test_fragment_shape(self):
        assert forward_fragment(_published(), make_shared(ipv6=False)) == {
            "tag": "home-publish-8443",
            "listen": "0.0.0.0",  # noqa: S104
            "port": 8443,
            "protocol": "dokodemo-door",
            "settings": {
                "address": "192.168.1.10",
                "port": 443,
                "network": "tcp",
                "followRedirect": False,
            },
            "streamSettings": {"sockopt": make_sockopt(False)},
            "sniffing": {"enabled": False},
        }

    def test_dualstack_listen_when_ipv6(self):
        assert forward_fragment(_published(), make_shared(ipv6=True))["listen"] == "::"

    def test_network_passthrough(self):
        fragment = forward_fragment(_published(network=PublishNetwork.TCP_UDP), make_shared())
        assert fragment["settings"]["network"] == "tcp,udp"


class TestHubForwardInbounds:
    def test_appended_after_registry_inbounds(self):
        fragment = forward_fragment(_published(), make_shared())
        config = build_hub_config(hub_ctx(forward_inbounds=[fragment]))
        assert [ib["tag"] for ib in config["inbounds"]] == ["direct-xhttp", "home-publish-8443"]
