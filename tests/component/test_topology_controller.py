import shutil
import stat
import sys
from pathlib import Path

import pytest

from hexrift.app import HexRiftApp
from hexrift.components.schema.models.fields import validate_masquerade_url
from hexrift.components.schema.models.regions import ExitRegion, HubRegion
from hexrift.components.schema.models.resolve import resolve_link_protocol, resolve_node_hysteria
from hexrift.components.schema.models.shared import RealityConfig, XhttpOverride
from hexrift.components.topology.controller import VLESS_ROUTE_RANGE, masquerade_url, pick_vless_route, region_prefix
from hexrift.components.topology.edit import Topology
from hexrift.constants import ExitProtocol, RegionType
from hexrift.errors import TopologyError


FIXTURE_TOPOLOGY = Path(__file__).parent.parent / "fixtures" / "topology.yaml"

DE_A00_BLOCK = """\
      - id: deA00
        hostname: deA00.ap.test.hexrift
        reality:
          dest: www.microsoft.com:443
        xhttp:
          path: /update/
"""

DE_EMPTY_BLOCK = """\
  - id: de
    type: exit
    vless_route: 2000
    protocol: hysteria
    hysteria:
      obfs: true
      congestion: brutal
      up: "200 mbps"
      down: "500 mbps"
    nodes:
  - id: msk
"""

NL_A20_BLOCK = """\
      - id: nlA20
        hostname: nlA20.ap.test.hexrift
        reality:
          dest: www.samsung.com:443
          server_names: [www.samsung.com, samsung.com]
        xhttp:
          path: /login/
        hysteria:
          obfs: true
          sni: nlA20.ap.test.hexrift
          masquerade_url: https://www.samsung.com
  - id: de
"""


@pytest.fixture()
def topo(tmp_path: Path) -> Path:
    return Path(shutil.copy(FIXTURE_TOPOLOGY, tmp_path / "topology.yaml"))


@pytest.fixture()
def fixture_app(topo: Path) -> HexRiftApp:
    return HexRiftApp(yaml_path=topo)


class TestRegionPrefix:
    @pytest.mark.parametrize(("node_id", "prefix"), [("nlA20", "nl"), ("mskX00", "msk"), ("us1", "us")])
    def test_leading_lowercase_letters(self, node_id, prefix):
        assert region_prefix(node_id) == prefix

    def test_rejects_id_without_prefix(self):
        with pytest.raises(TopologyError, match="pass --region"):
            region_prefix("A20")


class TestPickVlessRoute:
    def test_exhausted_range_is_rejected(self):
        low, high = VLESS_ROUTE_RANGE
        with pytest.raises(TopologyError, match="No unused vless_route"):
            pick_vless_route(set(range(low, high + 1)))


class TestMasqueradeUrl:
    @pytest.mark.parametrize(
        ("dest", "url"),
        [
            ("www.samsung.com:443", "https://www.samsung.com"),
            ("a.com:8443", "https://a.com:8443"),
            ("[2001:db8::1]:443", "https://[2001:db8::1]"),
        ],
    )
    def test_https_with_port_kept_unless_443(self, dest, url):
        assert masquerade_url(dest) == url
        assert validate_masquerade_url(url) == url


class TestAddNode:
    def test_exit_node_joins_its_region_with_derived_hostname(self, fixture_app: HexRiftApp, topo: Path):
        result = fixture_app.topology.add_node(
            "nlA20",
            reality=RealityConfig(
                dest="www.samsung.com:443",
                server_names=["www.samsung.com", "samsung.com"],
            ),
            xhttp=XhttpOverride(path="/login/"),
        )
        assert result is not None and not result.created
        assert result.region.id == "nl"
        assert result.region.type == RegionType.EXIT
        assert result.node.hostname == "nlA20.ap.test.hexrift"
        assert result.validation_error is None
        assert NL_A20_BLOCK in topo.read_text()
        region, node = fixture_app.schema.get_node("nlA20")
        assert region.id == "nl"
        assert node.reality is not None and node.reality.dest == "www.samsung.com:443"
        assert node.hysteria is not None and node.hysteria.obfs is True
        assert node.hysteria.sni == "nlA20.ap.test.hexrift"
        assert node.hysteria.masquerade_url == "https://www.samsung.com"

    def test_hub_node_follows_sibling_hostname_domain(self, fixture_app: HexRiftApp, topo: Path):
        result = fixture_app.topology.add_node("mskA20")
        assert result is not None and not result.created
        assert result.region.type == RegionType.HUB
        assert result.node.hostname == "mskA20.ap.test.hexrift"
        assert result.validation_error is None
        assert [n.id for n in fixture_app.schema.get_region("msk").nodes] == ["mskA00", "mskA20"]
        assert ("      - id: mskA20\n        hostname: mskA20.ap.test.hexrift\n  - id: jp\n") in topo.read_text()

    def test_new_exit_region_gets_unused_vless_route(self, fixture_app: HexRiftApp):
        result = fixture_app.topology.add_node(
            "usA00",
            node_type=RegionType.EXIT,
            reality=RealityConfig(dest="www.samsung.com:443"),
            xhttp=XhttpOverride(path="/login/"),
        )
        assert result is not None and result.created and isinstance(result.region, ExitRegion)
        route = result.region.vless_route
        assert route is not None and VLESS_ROUTE_RANGE[0] <= route <= VLESS_ROUTE_RANGE[1]
        assert route not in {1000, 2000, 3000, 3001}
        assert result.validation_error is None
        region = fixture_app.schema.get_region("us")
        assert isinstance(region, ExitRegion) and region.vless_route == route
        assert [n.id for n in region.nodes] == ["usA00"]

    @pytest.mark.parametrize(
        ("node_id", "hysteria", "written"),
        [
            ("jpA00", False, "    nodes:\n      - id: jpA00\n        hostname: jpA00.ap.test.hexrift\n"),
            (
                "jpA00",
                True,
                "    nodes:\n      - id: jpA00\n        hostname: jpA00.ap.test.hexrift\n"
                "        hysteria:\n          obfs: true\n          sni: jpA00.ap.test.hexrift\n",
            ),
            (
                "deA10",
                False,
                "      - id: deA10\n        hostname: deA10.ap.test.hexrift\n"
                "        hysteria:\n          obfs: true\n          sni: deA10.ap.test.hexrift\n  - id: msk\n",
            ),
        ],
    )
    def test_hysteria_block_on_flag_or_listening_region(
        self, fixture_app: HexRiftApp, topo: Path, node_id, hysteria, written
    ):
        fixture_app.topology.add_node(node_id, hysteria=hysteria)
        assert written in topo.read_text()

    def test_new_region_requires_type(self, fixture_app: HexRiftApp, topo: Path):
        before = topo.read_text()
        with pytest.raises(TopologyError, match="pass --type"):
            fixture_app.topology.add_node("usA00")
        assert topo.read_text() == before

    def test_missing_aphelion_domain_requires_hostname(self, tmp_path: Path):
        topo = tmp_path / "topology.yaml"
        topo.write_text("regions:\n  - id: nl\n    type: exit\n    nodes:\n      - id: nlA00\n        hostname: h.x\n")
        app = HexRiftApp(yaml_path=topo)
        with pytest.raises(TopologyError, match="pass --hostname"):
            app.topology.add_node("nlA10")

    def test_type_mismatch_is_reported_before_hostname_derivation(self, tmp_path: Path):
        topo = tmp_path / "topology.yaml"
        topo.write_text("regions:\n  - id: nl\n    type: exit\n    nodes:\n      - id: nlA00\n        hostname: h.x\n")
        with pytest.raises(TopologyError, match="has type 'exit'"):
            HexRiftApp(yaml_path=topo).topology.add_node("nlA20", node_type=RegionType.HUB)

    def test_exit_without_reality_is_written_with_validation_error(self, fixture_app: HexRiftApp, topo: Path):
        result = fixture_app.topology.add_node("nlA20")
        assert result is not None and not result.created
        assert result.validation_error is not None
        assert "Exit node 'nlA20' in region 'nl' must have reality config" in result.validation_error
        assert (
            "      - id: nlA20\n        hostname: nlA20.ap.test.hexrift\n"
            "        hysteria:\n          obfs: true\n          sni: nlA20.ap.test.hexrift\n  - id: de\n"
        ) in topo.read_text()

    def test_edits_keep_working_while_file_is_invalid(self, fixture_app: HexRiftApp):
        fixture_app.topology.add_node("nlA20")
        result = fixture_app.topology.add_node(
            "nlA30",
            reality=RealityConfig(dest="a.com:443"),
            xhttp=XhttpOverride(path="/x/"),
        )
        assert result is not None and not result.created
        assert result.validation_error is not None

    def test_existing_node_is_skipped_without_writing(self, fixture_app: HexRiftApp, topo: Path):
        before = topo.read_text()
        assert fixture_app.topology.add_node("nlA00", node_type=RegionType.HUB) is None
        assert topo.read_text() == before

    def test_add_node_exit_all_nodes_have_hysteria_no_region_key(self, tmp_path: Path):
        topo = tmp_path / "topology.yaml"
        topo.write_text("""\
global:
  namespace: test.hexrift
  aphelion_domain: ap.test.hexrift

defaults:
  exit:
    ipv6: true
    keys:
      auth: mlkem768
      mode: native
      session_time: 600s
  hub:
    ipv6: true
    keys:
      auth: x25519
      mode: native
      session_time: 600s
    exit_connections:
      method: mlkem768x25519plus
      fingerprint: chrome
    reality:
      dest: www.microsoft.com:443
    xhttp:
      path: /update/

regions:
  - id: nl
    type: exit
    vless_route: 1000
    nodes:
      - id: nlA00
        hostname: nlA00.ap.test.hexrift
        reality:
          dest: www.microsoft.com:443
        xhttp:
          path: /update/
        hysteria:
          obfs: true
      - id: nlA10
        hostname: nlA10.ap.test.hexrift
        reality:
          dest: www.microsoft.com:443
        xhttp:
          path: /update/
        hysteria:
          obfs: true

routing:
  hub_default: nl
""")
        app = HexRiftApp(yaml_path=topo)
        app.topology.add_node(
            "nlA20", reality=RealityConfig(dest="www.samsung.com:443"), xhttp=XhttpOverride(path="/login/")
        )
        assert (
            "      - id: nlA20\n"
            "        hostname: nlA20.ap.test.hexrift\n"
            "        reality:\n"
            "          dest: www.samsung.com:443\n"
            "        xhttp:\n"
            "          path: /login/\n"
            "        hysteria:\n"
            "          obfs: true\n"
            "          sni: nlA20.ap.test.hexrift\n"
            "          masquerade_url: https://www.samsung.com\n"
            "\n"
            "routing:"
        ) in topo.read_text()

    def test_add_node_exit_bare_hysteria_null_key(self, tmp_path: Path):
        topo = tmp_path / "topology.yaml"
        topo.write_text("""\
global:
  namespace: test.hexrift
  aphelion_domain: ap.test.hexrift

defaults:
  exit:
    ipv6: true
    keys:
      auth: mlkem768
      mode: native
      session_time: 600s
  hub:
    ipv6: true
    keys:
      auth: x25519
      mode: native
      session_time: 600s
    exit_connections:
      method: mlkem768x25519plus
      fingerprint: chrome
    reality:
      dest: www.microsoft.com:443
    xhttp:
      path: /update/

regions:
  - id: nl
    type: exit
    vless_route: 1000
    hysteria:
    nodes:
      - id: nlA00
        hostname: nlA00.ap.test.hexrift
        reality:
          dest: www.microsoft.com:443
        xhttp:
          path: /update/

routing:
  hub_default: nl
""")
        app = HexRiftApp(yaml_path=topo)
        app.topology.add_node(
            "nlA20", reality=RealityConfig(dest="www.samsung.com:443"), xhttp=XhttpOverride(path="/login/")
        )
        assert (
            "      - id: nlA20\n"
            "        hostname: nlA20.ap.test.hexrift\n"
            "        reality:\n"
            "          dest: www.samsung.com:443\n"
            "        xhttp:\n"
            "          path: /login/\n"
            "\n"
            "routing:"
        ) in topo.read_text()

    def test_add_node_hub_region_every_node_opted_out(self, tmp_path: Path):
        topo = tmp_path / "topology.yaml"
        topo.write_text("""\
global:
  namespace: test.hexrift
  aphelion_domain: ap.test.hexrift
groups: []
users: []

defaults:
  exit:
    ipv6: true
    keys:
      auth: mlkem768
      mode: native
      session_time: 600s
  hub:
    ipv6: true
    keys:
      auth: x25519
      mode: native
      session_time: 600s
    exit_connections:
      method: mlkem768x25519plus
      fingerprint: chrome
    reality:
      dest: www.microsoft.com:443
    xhttp:
      path: /update/
    hysteria:
      port: 8443

regions:
  - id: nl
    type: exit
    vless_route: 1000
    xhttp:
      path: /update/
    nodes:
      - id: nlA00
        hostname: nlA00.ap.test.hexrift
        reality:
          dest: www.microsoft.com:443
  - id: msk
    type: hub
    nodes:
      - id: mskA00
        hostname: mskA00.ap.test.hexrift
        hysteria:
          enabled: false

routing:
  hub_default: nl
""")
        app = HexRiftApp(yaml_path=topo)
        app.topology.add_node("mskA10")
        written = topo.read_text()
        topo_edit = Topology(written)
        region = topo_edit.region("msk")
        assert region is not None
        node = next(n for n in region.nodes if n.id == "mskA10")
        block = "\n".join(written.splitlines()[node.start : region.end])
        assert "enabled: false" in block
        assert app.schema.get_region("msk") is not None

    def test_add_node_hub_region_nodes_carry_the_listener(self, tmp_path: Path):
        topo = tmp_path / "topology.yaml"
        topo.write_text("""\
global:
  namespace: test.hexrift
  aphelion_domain: ap.test.hexrift

defaults:
  exit:
    ipv6: true
    keys:
      auth: mlkem768
      mode: native
      session_time: 600s
  hub:
    ipv6: true
    keys:
      auth: x25519
      mode: native
      session_time: 600s
    exit_connections:
      method: mlkem768x25519plus
      fingerprint: chrome
    reality:
      dest: www.microsoft.com:443
    xhttp:
      path: /update/

regions:
  - id: msk
    type: hub
    nodes:
      - id: mskA00
        hostname: mskA00.ap.test.hexrift
        hysteria:
          obfs: true

routing:
  hub_default: msk
""")
        app = HexRiftApp(yaml_path=topo)
        app.topology.add_node("mskA10")
        written = topo.read_text()
        assert (
            "      - id: mskA10\n"
            "        hostname: mskA10.ap.test.hexrift\n"
            "        hysteria:\n"
            "          obfs: true\n"
            "          sni: mskA10.ap.test.hexrift\n"
        ) in written

    def test_parity_topology_yaml_edit_vs_resolve(self, fixture_app: HexRiftApp):
        topo = Topology(FIXTURE_TOPOLOGY.read_text())
        defaults = fixture_app.schema.config.defaults
        for region_item in topo.regions:
            assert region_item.id is not None
            schema_region = fixture_app.schema.get_region(region_item.id)
            assert schema_region is not None
            for node_item in region_item.nodes:
                schema_node = next((n for n in schema_region.nodes if n.id == node_item.id), None)
                assert schema_node is not None, f"Node {node_item.id} not found in schema region {region_item.id}"
                resolves = resolve_node_hysteria(schema_node, schema_region, defaults) is not None
                assert node_item.hysteria == resolves, (
                    f"Mismatch for node {node_item.id} in region {region_item.id}: "
                    f"edit.hysteria={node_item.hysteria} vs resolve={resolves}"
                )
            all_listening = all(
                resolve_node_hysteria(node, schema_region, defaults) is not None for node in schema_region.nodes
            )
            if isinstance(schema_region, HubRegion):
                bare = defaults.hub.hysteria is not None
                node_flags = [
                    resolve_node_hysteria(n, schema_region, defaults) is not None for n in schema_region.nodes
                ]
                expected = (bool(node_flags) and all(node_flags)) and not bare
            else:
                bare = (
                    schema_region.hysteria is not None or resolve_link_protocol(schema_region) == ExitProtocol.HYSTERIA
                )
                expected = bare or (bool(schema_region.nodes) and all_listening)
            assert region_item.hysteria == expected

    def test_add_node_hub_region_writes_opt_out_when_serving_tls(self, fixture_app: HexRiftApp, topo: Path):
        fixture_app.topology.add_node("mskA20")
        fixture_app.topology.add_node("spbA10")
        written = topo.read_text()
        topo_edit = Topology(written)
        for region_id, node_id, has_hysteria in (("msk", "mskA20", False), ("spb", "spbA10", True)):
            region = topo_edit.region(region_id)
            assert region is not None
            node = next(n for n in region.nodes if n.id == node_id)
            block = "\n".join(written.splitlines()[node.start : region.end])
            assert ("hysteria" in block) is has_hysteria
            if has_hysteria:
                assert "enabled: false" in block


class TestFileHandling:
    def test_keeps_crlf_line_endings(self, topo: Path):
        crlf = topo.read_bytes().replace(b"\n", b"\r\n")
        topo.write_bytes(crlf)
        HexRiftApp(yaml_path=topo).topology.remove_node("deA00")
        assert topo.read_bytes() == crlf.replace(DE_A00_BLOCK.encode().replace(b"\n", b"\r\n"), b"")

    def test_edits_symlink_target_in_place(self, tmp_path: Path):
        real = tmp_path / "real.yaml"
        shutil.copy(FIXTURE_TOPOLOGY, real)
        link = tmp_path / "topology.yaml"
        link.symlink_to(real)
        HexRiftApp(yaml_path=link).topology.remove_node("deA00")
        assert link.is_symlink()
        assert DE_EMPTY_BLOCK in real.read_text()

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not enforced on Windows")
    def test_keeps_file_mode(self, topo: Path):
        topo.chmod(0o600)
        HexRiftApp(yaml_path=topo).topology.remove_node("deA00")
        assert stat.S_IMODE(topo.stat().st_mode) == 0o600

    def test_failed_replace_leaves_no_tmp_file(self, topo: Path, monkeypatch: pytest.MonkeyPatch):
        def refuse(self: Path, target: Path) -> Path:
            raise OSError("locked")

        monkeypatch.setattr(Path, "replace", refuse)
        with pytest.raises(TopologyError, match="locked"):
            HexRiftApp(yaml_path=topo).topology.remove_node("deA00")
        assert [p.name for p in topo.parent.iterdir()] == ["topology.yaml"]


class TestRemoveNode:
    def test_removing_only_node_keeps_region(self, fixture_app: HexRiftApp, topo: Path):
        result = fixture_app.topology.remove_node("deA00")
        assert result is not None and result.emptied
        assert result.region_id == "de"
        assert result.validation_error is None
        assert DE_EMPTY_BLOCK in topo.read_text()
        assert fixture_app.schema.get_region("de").nodes == []

    def test_emptying_default_region_warns_about_hub_default(self, fixture_app: HexRiftApp):
        result = fixture_app.topology.remove_node("nlA00")
        assert result is not None and result.emptied
        assert result.validation_error is not None
        assert "hub_default 'nl' is a region with no nodes" in result.validation_error

    def test_missing_node_leaves_file_untouched(self, fixture_app: HexRiftApp, topo: Path):
        before = topo.read_text()
        assert fixture_app.topology.remove_node("ghost") is None
        assert topo.read_text() == before

    def test_readding_node_reuses_kept_region(self, fixture_app: HexRiftApp):
        reality, xhttp = RealityConfig(dest="a.com:443"), XhttpOverride(path="/x/")
        created = fixture_app.topology.add_node("usA00", node_type=RegionType.EXIT, reality=reality, xhttp=xhttp)
        fixture_app.topology.remove_node("usA00")
        readded = fixture_app.topology.add_node("usA00", reality=reality, xhttp=xhttp)
        assert readded is not None and not readded.created
        assert readded.validation_error is None
        assert created is not None and isinstance(created.region, ExitRegion)
        region = fixture_app.schema.get_region("us")
        assert isinstance(region, ExitRegion) and region.vless_route == created.region.vless_route
