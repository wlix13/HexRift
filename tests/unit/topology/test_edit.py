import pytest

from hexrift.components.topology.edit import HysteriaSpec, NodeSpec, RealitySpec, RegionSpec, Topology, node_lines
from hexrift.constants import RegionType
from hexrift.errors import TopologyError


NL_A00_BLOCK = """\
      - id: nlA00
        hostname: nlA00.ap.t.ns
        reality:
          dest: a.com:443
          xhttp_path: /x/
"""

NL_TAIL = """\
      - id: nlA10
        hostname: nlA10.ap.t.ns
        ipv6: false
        reality:
          dest: a.com:443
          xhttp_path: /x/
"""

DE_A00_BLOCK = """\
      - id: deA00
        hostname: deA00.ap.t.ns
        reality:
          dest: a.com:443
          xhttp_path: /x/
"""

DE_REGION = (
    """\
  - id: de
    type: exit
    vless_route: 2000
    nodes:
"""
    + DE_A00_BLOCK
    + """\
    routing:
      warp_extra:
        - geosite:github
"""
)

MSK_A00_BLOCK = """\
      - id: mskA00
        hostname: mskA00.hub.t.ns
"""

MSK_REGION = "  - id: msk\n    type: hub\n    nodes:\n" + MSK_A00_BLOCK

BASE = (
    """\
global:
  namespace: t.ns
  aphelion_domain: ap.t.ns

regions:
  - id: nl
    type: exit
    vless_route: 1000
    # TODO: revisit fallback
    lb_fallback: nlA00
    nodes:
"""
    + NL_A00_BLOCK
    + NL_TAIL
    + "\n"
    + DE_REGION
    + "\n"
    + MSK_REGION
)

TAIL = """
routing:
  hub_default: nl
"""

NEW_NODE = NodeSpec(id="nlA20", hostname="nlA20.ap.t.ns")
NEW_NODE_BLOCK = """\
      - id: nlA20
        hostname: nlA20.ap.t.ns
"""

FR_REGION = RegionSpec(id="fr", type=RegionType.EXIT, vless_route=4242)
FR_NODE = NodeSpec(id="frA00", hostname="frA00.ap.t.ns", reality=RealitySpec(dest="b.com:443", xhttp_path="/y/"))
FR_NODE_BLOCK = """\
      - id: frA00
        hostname: frA00.ap.t.ns
        reality:
          dest: b.com:443
          xhttp_path: /y/
"""
FR_BLOCK = "  - id: fr\n    type: exit\n    vless_route: 4242\n    nodes:\n" + FR_NODE_BLOCK


class TestNodeLines:
    def test_full_spec_renders_every_field(self):
        spec = NodeSpec(
            id="nlA20",
            hostname="nlA20.ap.t.ns",
            ipv6=False,
            reality=RealitySpec(
                dest="www.samsung.com:443",
                server_names=("www.samsung.com", "samsung.com"),
                xhttp_path="/login/",
            ),
            hysteria=HysteriaSpec(sni="nlA20.ap.t.ns", masquerade_url="https://www.samsung.com"),
        )
        assert node_lines(spec) == [
            "      - id: nlA20",
            "        hostname: nlA20.ap.t.ns",
            "        ipv6: false",
            "        reality:",
            "          dest: www.samsung.com:443",
            "          server_names: [www.samsung.com, samsung.com]",
            "          xhttp_path: /login/",
            "        hysteria:",
            "          obfs: true",
            "          sni: nlA20.ap.t.ns",
            "          masquerade_url: https://www.samsung.com",
        ]

    def test_quotes_values_yaml_would_misread(self):
        spec = NodeSpec(id="no", hostname="h.t.ns", reality=RealitySpec(dest="a.com:443", xhttp_path="/a:"))
        assert node_lines(spec) == [
            '      - id: "no"',
            "        hostname: h.t.ns",
            "        reality:",
            "          dest: a.com:443",
            '          xhttp_path: "/a:"',
        ]


class TestSpecValidation:
    @pytest.mark.parametrize(
        "spec",
        [
            lambda: NodeSpec(id="bad id", hostname="h.t.ns"),
            lambda: NodeSpec(id="nlA20", hostname="host name"),
            lambda: RealitySpec(dest="www.samsung.com", xhttp_path="/x/"),
            lambda: RealitySpec(dest="a.com:0", xhttp_path="/x/"),
            lambda: RealitySpec(dest="a.com:443", xhttp_path="/x/", server_names=("bad name",)),
            lambda: RealitySpec(dest="a.com:443", xhttp_path="login/"),
        ],
    )
    def test_rejects_values_outside_the_schema_charsets(self, spec):
        with pytest.raises(TopologyError, match="Invalid"):
            spec()


class TestParsedView:
    def test_used_vless_routes_include_warp(self):
        warped = BASE.replace(
            "    vless_route: 2000\n",
            "    vless_route: 2000\n    warp:\n      vless_route: 65_535\n",
        )
        assert Topology(warped).used_vless_routes == {1000, 2000, 65535}

    @pytest.mark.parametrize(
        ("text", "match"),
        [
            ("global:\n  namespace: t.ns\n", "No top-level 'regions:'"),
            ("regions: []\n", "block sequence"),
            (
                "regions:\n  - id: nl\n    type: hub\n    nodes:\n      - id: a\n        hostname: h.x\n"
                "regions:\n  - id: de\n    type: hub\n    nodes:\n      - id: b\n        hostname: h.y\n",
                "Duplicate 'regions'",
            ),
            (
                "shared: &s [x]\nregions:\n  - id: nl\n    type: hub\n    nodes:\n"
                "      - id: a\n        hostname: h.x\n        tags: *s\n",
                "anchors or aliases",
            ),
            ("regions: null\n", "block sequence"),
            (
                "regions:\n  - id: nl\n    type: hub\n    nodes:\n      - id: a\n        hostname: h.x\n"
                "routing:\n  hub_routes: [{destination: a, domains: [x.com]}]\n",
                "'routing.hub_routes' must be",
            ),
            (
                "regions:\n  - id: nl\n    type: hub\n    nodes:\n      - id: a\n        hostname: h.x\n"
                "    nodes:\n      - id: b\n        hostname: h.y\n",
                "Duplicate 'nodes'",
            ),
            (
                "regions:\n  - id: nl\n    type: hub\n    nodes:\n      - id: a\n        hostname: h.x\n"
                "routing:\n  hub_routes:\n    - destination: a\n      destination: b\n",
                "Duplicate 'destination'",
            ),
        ],
    )
    def test_refuses_files_it_cannot_edit_safely(self, text, match):
        with pytest.raises(TopologyError, match=match):
            Topology(text)


class TestUnsplicableRegions:
    FLOW_NL = "regions:\n  - id: nl\n    type: hub\n    nodes: [{id: a, hostname: h.x}]\n"

    def test_flow_nodes_list_refuses_only_its_own_edits(self):
        topo = Topology(self.FLOW_NL + MSK_REGION)
        assert topo.has_node("a")
        with pytest.raises(TopologyError, match="block sequence"):
            topo.remove_node("a")
        with pytest.raises(TopologyError, match="block sequence"):
            topo.add_node(RegionSpec("nl", RegionType.HUB), NodeSpec(id="b", hostname="h.y"))
        assert topo.remove_node("mskA00").text == self.FLOW_NL + MSK_REGION.replace(MSK_A00_BLOCK, "")

    def test_flow_region_mapping_refuses_only_its_own_edits(self):
        topo = Topology("regions:\n  - {id: nl, type: hub, nodes: }\n" + MSK_REGION)
        with pytest.raises(TopologyError, match="block mapping"):
            topo.add_node(RegionSpec("nl", RegionType.HUB), NodeSpec(id="a", hostname="h.x"))
        assert topo.remove_node("mskA00").emptied

    def test_empty_flow_nodes_list_becomes_block_on_add(self):
        text = "regions:\n  - id: nl\n    type: hub\n    nodes: []\n"
        result = Topology(text).add_node(RegionSpec("nl", RegionType.HUB), NodeSpec(id="a", hostname="h.x"))
        assert result.text == "regions:\n  - id: nl\n    type: hub\n    nodes:\n      - id: a\n        hostname: h.x\n"


class TestAddNode:
    def test_appends_after_last_node_of_region(self):
        result = Topology(BASE).add_node(RegionSpec("nl", RegionType.EXIT), NEW_NODE)
        assert not result.created
        assert result.text == BASE.replace(NL_TAIL + "\n", NL_TAIL + NEW_NODE_BLOCK + "\n")

    @pytest.mark.parametrize("node_id", ["nlA05", "nlA5"])
    def test_inserts_in_natural_id_order(self, node_id):
        node = NodeSpec(id=node_id, hostname=f"{node_id}.ap.t.ns")
        result = Topology(BASE).add_node(RegionSpec("nl", RegionType.EXIT), node)
        block = f"      - id: {node_id}\n        hostname: {node_id}.ap.t.ns\n"
        assert result.text == BASE.replace(NL_TAIL, block + NL_TAIL)

    def test_inserts_after_last_earlier_node_in_file_order(self):
        swapped = BASE.replace(NL_A00_BLOCK + NL_TAIL, NL_TAIL + NL_A00_BLOCK)
        node = NodeSpec(id="nlA05", hostname="nlA05.ap.t.ns")
        result = Topology(swapped).add_node(RegionSpec("nl", RegionType.EXIT), node)
        block = "      - id: nlA05\n        hostname: nlA05.ap.t.ns\n"
        assert result.text == swapped.replace(NL_A00_BLOCK + "\n", NL_A00_BLOCK + block + "\n")

    def test_inserts_first_above_comment_owned_by_next_node(self):
        text = BASE.replace("    nodes:\n" + NL_A00_BLOCK, "    nodes:\n      # primary\n")
        node = NodeSpec(id="nlA00", hostname="nlA00.ap.t.ns", reality=RealitySpec(dest="a.com:443", xhttp_path="/x/"))
        result = Topology(text).add_node(RegionSpec("nl", RegionType.EXIT), node)
        assert result.text == text.replace("      # primary\n", NL_A00_BLOCK + "      # primary\n")

    def test_appends_after_last_node_not_after_trailing_region_keys(self):
        node = NodeSpec(id="deA10", hostname="deA10.ap.t.ns")
        result = Topology(BASE).add_node(RegionSpec("de", RegionType.EXIT), node)
        expected_region = DE_REGION.replace(
            "          xhttp_path: /x/\n    routing:",
            "          xhttp_path: /x/\n      - id: deA10\n        hostname: deA10.ap.t.ns\n    routing:",
        )
        assert result.text == BASE.replace(DE_REGION, expected_region)

    def test_creates_missing_region_before_next_top_level_key(self):
        result = Topology(BASE + TAIL).add_node(FR_REGION, FR_NODE)
        assert result.created
        assert result.text == BASE + "\n" + FR_BLOCK + TAIL

    def test_appends_under_bare_nodes_key(self):
        text = "regions:\n  - id: nl\n    type: exit\n    nodes:\n"
        result = Topology(text).add_node(RegionSpec("nl", RegionType.EXIT), NEW_NODE)
        assert result.text == text + NEW_NODE_BLOCK

    def test_keeps_trailing_blank_lines(self):
        result = Topology(BASE + "\n\n").add_node(RegionSpec("nl", RegionType.EXIT), NEW_NODE)
        assert result.text == BASE.replace(NL_TAIL + "\n", NL_TAIL + NEW_NODE_BLOCK + "\n") + "\n\n"

    def test_handles_missing_final_newline(self):
        result = Topology(BASE.rstrip("\n")).add_node(RegionSpec("nl", RegionType.EXIT), NEW_NODE)
        assert result.text == BASE.replace(NL_TAIL + "\n", NL_TAIL + NEW_NODE_BLOCK + "\n")

    def test_hub_region_omits_vless_route(self):
        node = NodeSpec(id="novA00", hostname="novA00.hub.t.ns")
        result = Topology(BASE).add_node(RegionSpec("nov", RegionType.HUB), node)
        assert result.text == BASE + "\n" + (
            "  - id: nov\n    type: hub\n    nodes:\n      - id: novA00\n        hostname: novA00.hub.t.ns\n"
        )

    def test_adding_node_materializes_lb_fallback_on_first_primary(self):
        strategic = (
            BASE.replace("    vless_route: 2000\n", "    vless_route: 2000\n    lb_strategy: leastPing\n")
            .replace("      - id: deA00\n", "      - id: deA00\n        lb_role: backup\n")
            .replace(
                "          xhttp_path: /x/\n    routing:",
                "          xhttp_path: /x/\n      - id: deA05\n        hostname: deA05.ap.t.ns\n    routing:",
            )
        )
        node = NodeSpec(id="deA10", hostname="deA10.ap.t.ns")
        result = Topology(strategic).add_node(RegionSpec("de", RegionType.EXIT), node)
        assert result.set_lb_fallback == "deA05"
        expected = strategic.replace(
            "    lb_strategy: leastPing\n", "    lb_strategy: leastPing\n    lb_fallback: deA05\n"
        ).replace(
            "        hostname: deA05.ap.t.ns\n",
            "        hostname: deA05.ap.t.ns\n      - id: deA10\n        hostname: deA10.ap.t.ns\n",
        )
        assert result.text == expected

    def test_rejects_duplicate_node(self):
        with pytest.raises(TopologyError, match="already in the topology"):
            Topology(BASE).add_node(RegionSpec("nl", RegionType.EXIT), NodeSpec(id="nlA10", hostname="other.t.ns"))

    def test_rejects_region_type_mismatch(self):
        with pytest.raises(TopologyError, match="has type 'exit'"):
            Topology(BASE).add_node(RegionSpec("nl", RegionType.HUB), NEW_NODE)

    @pytest.mark.parametrize("node_id", ["nlA00", "nlA20"])
    def test_rejects_differently_indented_items(self, node_id):
        text = "regions:\n- id: nl\n  type: exit\n  nodes:\n  - id: nlA10\n    hostname: h.t.ns\n"
        with pytest.raises(TopologyError, match="indented"):
            Topology(text).add_node(RegionSpec("nl", RegionType.EXIT), NodeSpec(id=node_id, hostname="h.t.ns"))


class TestRemoveNode:
    def test_removes_node_and_keeps_region(self):
        result = Topology(BASE).remove_node("nlA10")
        assert not result.emptied
        assert result.region_id == "nl"
        assert result.text == BASE.replace(NL_TAIL, "")

    def test_keeps_comment_owned_by_the_next_item(self):
        noted = BASE.replace("  - id: de\n", "  # de is temporary\n  - id: de\n")
        result = Topology(noted).remove_node("nlA10")
        assert result.text == noted.replace(NL_TAIL, "")

    def test_removing_last_node_keeps_region(self):
        result = Topology(BASE).remove_node("deA00")
        assert result.emptied
        assert result.region_id == "de"
        assert result.text == BASE.replace(DE_A00_BLOCK, "")

    def test_emptying_last_region_keeps_blank_before_next_key(self):
        result = Topology(BASE + TAIL).remove_node("mskA00")
        assert result.text == BASE.replace(MSK_A00_BLOCK, "") + TAIL

    def test_emptying_region_drops_routes_targeting_it(self):
        tail = (
            "\nrouting:\n  hub_routes:\n    - destination: deA00\n      domains: [x.com]\n"
            "    - destination: de\n      domains: [y.com]\n    - destination: nl\n      domains: [z.com]\n"
            "  hub_default: nl\n"
        )
        result = Topology(BASE + tail).remove_node("deA00")
        assert result.dropped_routes == ("deA00", "de")
        assert result.text == BASE.replace(DE_A00_BLOCK, "") + (
            "\nrouting:\n  hub_routes:\n    - destination: nl\n      domains: [z.com]\n  hub_default: nl\n"
        )

    def test_removing_one_of_many_keeps_routes_targeting_region(self):
        tail = "\nrouting:\n  hub_routes:\n    - destination: nl\n      domains: [y.com]\n  hub_default: nl\n"
        result = Topology(BASE + tail).remove_node("nlA10")
        assert result.dropped_routes == ()
        assert result.text == BASE.replace(NL_TAIL, "") + tail

    def test_dropping_node_drops_its_routes_lb_fallback_and_emptied_hub_routes_key(self):
        tail = "\nrouting:\n  hub_routes:\n    - destination: nlA00\n      domains: [x.com]\n  hub_default: nl\n"
        result = Topology(BASE + tail).remove_node("nlA00")
        assert result.dropped_routes == ("nlA00",)
        assert result.dropped_lb_fallback is True
        expected = BASE.replace(NL_A00_BLOCK, "").replace("    lb_fallback: nlA00\n", "")
        assert result.text == expected + "\nrouting:\n  hub_default: nl\n"

    def test_refuses_item_with_dash_on_its_own_line(self):
        dashed = BASE.replace("      - id: nlA00\n", "      -\n        id: nlA00\n")
        with pytest.raises(TopologyError, match="list item"):
            Topology(dashed).remove_node("nlA00")

    def test_reports_each_dropped_destination_once(self):
        tail = (
            "\nrouting:\n  hub_routes:\n    - destination: nlA00\n      domains: [x.com]\n"
            "    - destination: nlA00\n      ips: [10.0.0.0/8]\n  hub_default: nl\n"
        )
        result = Topology(BASE + tail).remove_node("nlA00")
        assert result.dropped_routes == ("nlA00",)
        expected = BASE.replace(NL_A00_BLOCK, "").replace("    lb_fallback: nlA00\n", "")
        assert result.text == expected + "\nrouting:\n  hub_default: nl\n"

    def test_missing_node_is_rejected(self):
        with pytest.raises(TopologyError, match="not in the topology"):
            Topology(BASE).remove_node("ghost")


class TestRoundtrip:
    def test_add_then_remove_in_existing_region_restores_text(self):
        added = Topology(BASE).add_node(RegionSpec("nl", RegionType.EXIT), NEW_NODE).text
        assert Topology(added).remove_node("nlA20").text == BASE

    def test_remove_last_node_then_add_restores_text(self):
        text = "regions:\n" + FR_BLOCK
        emptied = Topology(text).remove_node("frA00").text
        assert emptied == text.replace(FR_NODE_BLOCK, "")
        assert Topology(emptied).add_node(FR_REGION, FR_NODE).text == text

    def test_emptied_region_keeps_strategy_and_regains_fallback(self):
        strategic = BASE.replace(
            "    vless_route: 2000\n", "    vless_route: 2000\n    lb_strategy: leastPing\n    lb_fallback: deA00\n"
        )
        emptied = Topology(strategic).remove_node("deA00")
        assert emptied.dropped_lb_fallback is True
        assert emptied.text == strategic.replace("    lb_fallback: deA00\n", "").replace(DE_A00_BLOCK, "")
        de = RegionSpec("de", RegionType.EXIT)
        first = NodeSpec(id="deA00", hostname="deA00.ap.t.ns", reality=RealitySpec(dest="a.com:443", xhttp_path="/x/"))
        refilled = Topology(emptied.text).add_node(de, first)
        assert refilled.set_lb_fallback is None
        result = Topology(refilled.text).add_node(de, NodeSpec(id="deA10", hostname="deA10.ap.t.ns"))
        assert result.set_lb_fallback == "deA00"
        assert result.text == strategic.replace(
            DE_A00_BLOCK, DE_A00_BLOCK + "      - id: deA10\n        hostname: deA10.ap.t.ns\n"
        )
