import uuid

import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.portals import Portal, PortalPublish, PortalRoutes
from hexrift.constants import PublishNetwork


class TestPortalRoutes:
    def test_domains_only_valid(self):
        pr = PortalRoutes(domains=["home.example.com"])
        assert pr.domains == ["home.example.com"]
        assert pr.ips is None

    def test_ips_only_valid(self):
        pr = PortalRoutes(ips=["192.168.1.0/24"])
        assert pr.ips == ["192.168.1.0/24"]

    def test_no_matchers_rejected(self):
        with pytest.raises(ValidationError, match="at least one matcher"):
            PortalRoutes()

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            PortalRoutes.model_validate({"domains": ["a.com"], "extra": "x"})

    def test_blank_domain_rejected(self):
        with pytest.raises(ValidationError, match="at least 1 character"):
            PortalRoutes(domains=["ok.example.com", "  "])


class TestPortalPublish:
    def test_defaults(self):
        pub = PortalPublish(port=8443, target="192.168.1.10:443")
        assert pub.network == PublishNetwork.TCP
        assert pub.allow is None
        assert pub.nodes is None
        assert pub.target_host_port == ("192.168.1.10", 443)

    @pytest.mark.parametrize("port", [0, 65536, -1])
    def test_port_out_of_range_rejected(self, port):
        with pytest.raises(ValidationError):
            PortalPublish.model_validate({"port": port, "target": "1.2.3.4:443"})

    @pytest.mark.parametrize(
        "target",
        [
            "192.168.1.10",
            "192.168.1.10:0",
            "192.168.1.10:http",
            ":443",
            "::1:443",
        ],
    )
    def test_malformed_target_rejected(self, target):
        with pytest.raises(ValidationError):
            PortalPublish.model_validate({"port": 8443, "target": target})

    def test_bracketed_ipv6_target(self):
        pub = PortalPublish(port=8443, target="[fd00::1]:443")
        assert pub.target_host_port == ("fd00::1", 443)

    def test_network_enum(self):
        assert PortalPublish(port=8443, target="a.lan:443", network="tcp,udp").network == PublishNetwork.TCP_UDP
        with pytest.raises(ValidationError):
            PortalPublish.model_validate({"port": 8443, "target": "a.lan:443", "network": "sctp"})

    @pytest.mark.parametrize(
        "target",
        [
            "foo bar:443",
            "*.example.com:443",
            "[not-an-ip]:443",
        ],
    )
    def test_malformed_host_rejected(self, target):
        with pytest.raises(ValidationError):
            PortalPublish.model_validate({"port": 8443, "target": target})

    def test_allow_normalized_to_networks(self):
        pub = PortalPublish(
            port=8443,
            target="a.lan:443",
            allow=["203.0.113.7", "10.1.2.0/24", "fd00::1"],
        )
        assert pub.allow == ["203.0.113.7/32", "10.1.2.0/24", "fd00::1/128"]

    def test_allow_with_host_bits_rejected(self):
        # Silently widening an allowlist would open an unauthenticated ingress
        with pytest.raises(ValidationError, match="has host bits set"):
            PortalPublish.model_validate(
                {
                    "port": 8443,
                    "target": "a.lan:443",
                    "allow": ["203.0.113.7/24"],
                }
            )

    def test_allow_invalid_cidr_rejected(self):
        with pytest.raises(ValidationError, match="invalid CIDR subnet"):
            PortalPublish.model_validate(
                {
                    "port": 8443,
                    "target": "a.lan:443",
                    "allow": ["not-an-ip"],
                }
            )

    def test_empty_allow_rejected(self):
        with pytest.raises(ValidationError):
            PortalPublish.model_validate(
                {
                    "port": 8443,
                    "target": "a.lan:443",
                    "allow": [],
                }
            )

    def test_empty_nodes_rejected(self):
        with pytest.raises(ValidationError):
            PortalPublish.model_validate(
                {
                    "port": 8443,
                    "target": "a.lan:443",
                    "nodes": [],
                }
            )

    def test_duplicate_nodes_rejected(self):
        with pytest.raises(ValidationError, match="duplicate node 'hubN1'"):
            PortalPublish.model_validate(
                {
                    "port": 8443,
                    "target": "a.lan:443",
                    "nodes": ["hubN1", "hubN1"],
                }
            )

    def test_invalid_node_identifier_rejected(self):
        with pytest.raises(ValidationError, match="should match pattern"):
            PortalPublish.model_validate(
                {
                    "port": 8443,
                    "target": "a.lan:443",
                    "nodes": ["bad node"],
                }
            )

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            PortalPublish.model_validate(
                {
                    "port": 8443,
                    "target": "a.lan:443",
                    "protocol": "tcp",
                }
            )


class TestPortal:
    def test_valid(self):
        p = Portal(
            id="home",
            users=["alice"],
            routes=PortalRoutes(domains=["home.example.com"]),
        )
        assert p.id == "home"
        assert p.users == ["alice"]
        assert p.uuid is None
        assert p.publish == []
        assert p.strict is True

    def test_publish_and_strict(self):
        p = Portal.model_validate(
            {
                "id": "home",
                "users": ["alice"],
                "routes": {"domains": ["home.example.com"]},
                "strict": False,
                "publish": [{"port": 8443, "target": "192.168.1.10:443", "allow": ["203.0.113.7"]}],
            },
        )
        assert p.strict is False
        assert p.publish[0].target_host_port == ("192.168.1.10", 443)
        assert p.publish[0].allow == ["203.0.113.7/32"]

    def test_uuid_override(self):
        uid = uuid.uuid4()
        p = Portal(
            id="home",
            users=["alice"],
            routes=PortalRoutes(domains=["home.example.com"]),
            uuid=uid,
        )
        assert p.uuid == uid

    def test_users_required(self):
        with pytest.raises(ValidationError):
            Portal.model_validate(
                {
                    "id": "home",
                    "routes": {"domains": ["home.example.com"]},
                },
            )

    def test_empty_users_rejected(self):
        with pytest.raises(ValidationError):
            Portal.model_validate(
                {
                    "id": "home",
                    "users": [],
                    "routes": {"domains": ["home.example.com"]},
                },
            )

    def test_duplicate_users_rejected(self):
        with pytest.raises(ValidationError, match="duplicate user"):
            Portal.model_validate(
                {
                    "id": "home",
                    "users": ["alice", "alice"],
                    "routes": {"domains": ["home.example.com"]},
                },
            )

    def test_invalid_id_rejected(self):
        with pytest.raises(ValidationError):
            Portal.model_validate(
                {
                    "id": "bad id",
                    "users": ["alice"],
                    "routes": {"domains": ["home.example.com"]},
                },
            )

    def test_invalid_user_rejected(self):
        with pytest.raises(ValidationError, match="should match pattern"):
            Portal.model_validate(
                {
                    "id": "home",
                    "users": ["bad user"],
                    "routes": {"domains": ["home.example.com"]},
                },
            )

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            Portal.model_validate(
                {
                    "id": "home",
                    "users": ["alice"],
                    "routes": {"domains": ["home.example.com"]},
                    "bad_field": "x",
                },
            )
