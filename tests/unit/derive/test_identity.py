import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hexrift.components.derive.identity import Namespace
from hexrift.components.schema.models.groups import Group
from hexrift.constants import SHORT_ID_LENGTH, WARP_UUID_SEGMENT


NS_NAME = "test.conglomerate.example"

_text = st.text(alphabet=st.characters(codec="utf-8"), min_size=1, max_size=32)


@pytest.fixture
def ns() -> Namespace:
    return Namespace(NS_NAME)


class TestNamespaceInit:
    def test_uuid_is_uuid5_of_null_uuid(self, ns: Namespace):
        expected = uuid.uuid5(uuid.UUID(int=0), NS_NAME)
        assert ns._uuid == expected

    def test_different_names_produce_different_namespaces(self):
        ns1 = Namespace("a.example.com")
        ns2 = Namespace("b.example.com")
        assert ns1._uuid != ns2._uuid


class TestUserUuid:
    def test_deterministic(self, ns: Namespace):
        a = ns.user_uuid("alice")
        b = ns.user_uuid("alice")
        assert a == b

    def test_override_respected(self, ns: Namespace):
        fixed = uuid.UUID("12345678-1234-5678-1234-567812345678")
        assert ns.user_uuid("alice", override=fixed) == fixed

    def test_different_users_differ(self, ns: Namespace):
        assert ns.user_uuid("alice") != ns.user_uuid("bob")

    @given(_text, _text)
    def test_user_uuid_is_scoped_to_its_namespace(self, name: str, username: str):
        other = Namespace(name + "-other")
        assert Namespace(name).user_uuid(username) != other.user_uuid(username)

    @given(_text, _text)
    def test_override_always_wins_for_any_input(self, name: str, username: str):
        fixed = uuid.UUID("12345678-1234-5678-1234-567812345678")
        assert Namespace(name).user_uuid(username, override=fixed) == fixed


class TestServerUuid:
    def test_deterministic(self, ns: Namespace):
        assert ns.server_uuid("alice") == ns.server_uuid("alice")

    def test_differs_from_user_uuid(self, ns: Namespace):
        assert ns.server_uuid("alice") != ns.user_uuid("alice")

    def test_explicit_user_base(self, ns: Namespace):
        base = ns.user_uuid("alice")
        result = ns.server_uuid("alice", user_base=base)
        assert result == ns.server_uuid("alice")


class TestGuestUuid:
    def test_deterministic(self, ns: Namespace):
        a = ns.guest_uuid("phone", "alice")
        b = ns.guest_uuid("phone", "alice")
        assert a == b

    def test_different_labels_differ(self, ns: Namespace):
        assert ns.guest_uuid("phone", "alice") != ns.guest_uuid("laptop", "alice")


class TestPortalUuid:
    def test_deterministic(self, ns: Namespace):
        assert ns.portal_uuid("k2") == ns.portal_uuid("k2")

    def test_override_respected(self, ns: Namespace):
        fixed = uuid.UUID("12345678-1234-5678-1234-567812345678")
        assert ns.portal_uuid("home", override=fixed) == fixed

    def test_different_portals_differ(self, ns: Namespace):
        assert ns.portal_uuid("home") != ns.portal_uuid("k2")

    def test_scoped_to_namespace(self):
        assert Namespace("a.example").portal_uuid("home") != Namespace("b.example").portal_uuid("home")

    @given(_text)
    def test_seed_domain_separated_from_user_uuid(self, name: str):
        # A user literally named "{id}-portal" must not collide with portal "{id}".
        ns = Namespace(NS_NAME)
        assert ns.portal_uuid(name) != ns.user_uuid(f"{name}-portal")

    def test_seed_domain_separated_from_hub_exit_uuid(self, ns: Namespace):
        # hub "a" + exit "b-portal" seeds "a-b-portal"; portal "a-b" must differ.
        assert ns.portal_uuid("a-b") != ns.hub_exit_uuid("a", "b-portal")


class TestHubExitUuid:
    def test_deterministic(self, ns: Namespace):
        a = ns.hub_exit_uuid("hubN1", "exitN1")
        b = ns.hub_exit_uuid("hubN1", "exitN1")
        assert a == b

    def test_asymmetric(self, ns: Namespace):
        assert ns.hub_exit_uuid("A", "B") != ns.hub_exit_uuid("B", "A")


class TestWarpUuid:
    def test_third_segment_is_ffff(self, ns: Namespace):
        base = ns.hub_exit_uuid("hubN1", "exitN1")
        w = Namespace.warp_uuid(base)
        parts = str(w).split("-")
        assert parts[2] == WARP_UUID_SEGMENT

    def test_other_segments_preserved(self, ns: Namespace):
        base = ns.hub_exit_uuid("hubN1", "exitN1")
        w = Namespace.warp_uuid(base)
        base_parts = str(base).split("-")
        warp_parts = str(w).split("-")
        assert base_parts[0] == warp_parts[0]
        assert base_parts[1] == warp_parts[1]
        assert base_parts[3] == warp_parts[3]
        assert base_parts[4] == warp_parts[4]

    def test_differs_from_base(self, ns: Namespace):
        base = ns.hub_exit_uuid("hubN1", "exitN1")
        assert Namespace.warp_uuid(base) != base


class TestShortIds:
    def test_exit_short_id_length(self, ns: Namespace):
        sid = ns.exit_short_id("nlA00")
        assert len(sid) == SHORT_ID_LENGTH

    def test_hub_short_id_length(self, ns: Namespace):
        sid = ns.hub_short_id("mskA00")
        assert len(sid) == SHORT_ID_LENGTH

    def test_user_short_id_length(self, ns: Namespace):
        sid = ns.user_short_id("alice")
        assert len(sid) == SHORT_ID_LENGTH

    def test_exit_short_id_deterministic(self, ns: Namespace):
        assert ns.exit_short_id("nlA00") == ns.exit_short_id("nlA00")

    def test_different_nodes_produce_different_short_ids(self, ns: Namespace):
        assert ns.exit_short_id("nlA00") != ns.exit_short_id("nlA01")

    def test_hub_and_exit_short_ids_differ_for_same_id(self, ns: Namespace):
        assert ns.hub_short_id("nodeX") != ns.exit_short_id("nodeX")

    def test_short_id_is_hex(self, ns: Namespace):
        sid = ns.exit_short_id("nlA00")
        int(sid, 16)  # raises ValueError if not hex

    def test_group_short_id_uses_explicit_value(self, ns: Namespace):
        g = Group(id="grp1", short_id="aabbccdd11223344")
        assert ns.group_short_id(g) == "aabbccdd11223344"

    def test_group_short_id_derives_when_not_set(self, ns: Namespace):
        g = Group(id="grp1", short_id=None)
        sid = ns.group_short_id(g)
        assert len(sid) == SHORT_ID_LENGTH
        int(sid, 16)

    @given(_text, _text)
    def test_hub_and_exit_short_ids_are_fixed_length_hex(self, name: str, node_id: str):
        ns = Namespace(name)
        for sid in (ns.hub_short_id(node_id), ns.exit_short_id(node_id)):
            assert len(sid) == SHORT_ID_LENGTH
            int(sid, 16)  # raises ValueError if the digest slice is not hex


class TestEmails:
    def test_user_email_format(self, ns: Namespace):
        assert ns.user_email("alice") == f"alice@{NS_NAME}"

    def test_hub_exit_email_format(self, ns: Namespace):
        assert ns.hub_exit_email("hubN1", "exitN1") == f"hubN1-exitN1@{NS_NAME}"

    def test_warp_email_format(self, ns: Namespace):
        assert ns.warp_email("hubN1", "exitN1") == f"warp-hubN1-exitN1@{NS_NAME}"

    def test_server_email_static(self):
        assert Namespace.server_email("alice") == "alice-server@alice"

    def test_portal_email_format(self, ns: Namespace):
        assert ns.portal_email("home") == f"home@portal.{NS_NAME}"

    def test_portal_email_cannot_collide_with_user_email(self, ns: Namespace):
        # The portal. subdomain is disjoint from the bare namespace domain.
        assert ns.portal_email("home") != ns.user_email("home")

    def test_guest_email_static(self):
        assert Namespace.guest_email("phone", "alice") == "phone@alice"
