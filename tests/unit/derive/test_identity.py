import uuid

import pytest

from hexrift.components.derive.identity import Namespace
from hexrift.components.schema.models.groups import Group
from hexrift.constants import SHORT_ID_LENGTH, WARP_UUID_SEGMENT


NS_NAME = "test.conglomerate.example"


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

    def test_differs_from_portal_uuid_same_label(self, ns: Namespace):
        assert ns.guest_uuid("home", "alice") != ns.portal_uuid("home", "alice")

    def test_different_labels_differ(self, ns: Namespace):
        assert ns.guest_uuid("phone", "alice") != ns.guest_uuid("laptop", "alice")


class TestPortalUuid:
    def test_deterministic(self, ns: Namespace):
        assert ns.portal_uuid("k2", "alice") == ns.portal_uuid("k2", "alice")

    def test_differs_from_user_uuid(self, ns: Namespace):
        assert ns.portal_uuid("home", "alice") != ns.user_uuid("alice")


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


class TestEmails:
    def test_user_email_format(self, ns: Namespace):
        assert ns.user_email("alice") == f"alice@{NS_NAME}"

    def test_hub_exit_email_format(self, ns: Namespace):
        assert ns.hub_exit_email("hubN1", "exitN1") == f"hubN1-exitN1@{NS_NAME}"

    def test_warp_email_format(self, ns: Namespace):
        assert ns.warp_email("hubN1", "exitN1") == f"warp-hubN1-exitN1@{NS_NAME}"

    def test_server_email_static(self):
        assert Namespace.server_email("alice") == "alice-server@alice"

    def test_portal_email_static(self):
        assert Namespace.portal_email("home", "alice") == "home-portal@alice"

    def test_guest_email_static(self):
        assert Namespace.guest_email("phone", "alice") == "phone@alice"
