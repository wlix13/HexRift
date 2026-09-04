import json
import shutil
from pathlib import Path

import yaml
from click.testing import CliRunner

from hexrift.app import cli
from tests.component.conftest import make_topology


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
FIXTURE_CONFIGS_DIR = FIXTURES_DIR / "configs"
FIXTURE_TOPOLOGY = FIXTURES_DIR / "topology.yaml"
FIXTURE_KEYS_DIR = FIXTURES_DIR / "keys"
WIDE = {"COLUMNS": "260"}  # keep rich tables/trees from truncating asserted cells


def invoke(*args, catch_exceptions=False, **kwargs):
    runner = CliRunner()
    return runner.invoke(cli, args, catch_exceptions=catch_exceptions, **kwargs)


def invoke_catching(*args, **kwargs):
    return invoke(*args, catch_exceptions=True, **kwargs)


class TestValidateCommand:
    def test_valid_topology_exits_zero(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "validate")
        assert result.exit_code == 0

    def test_valid_topology_output_says_valid(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "validate")
        assert "Valid" in result.output

    def test_valid_topology_shows_group_count(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "validate")
        assert "2 groups" in result.output

    def test_invalid_topology_aborts(self, tmp_path):
        broken = tmp_path / "bad.yaml"
        broken.write_text("global: {namespace: x}\n# missing required fields\n")
        result = invoke_catching("--yaml", str(broken), "validate")
        assert result.exit_code != 0

    def test_invalid_topology_shows_error(self, tmp_path):
        broken = tmp_path / "bad.yaml"
        broken.write_text("global: {namespace: x}\n")
        result = invoke_catching("--yaml", str(broken), "validate")
        assert "Validation error" in result.output
        assert result.exit_code != 0


class TestGenKeysCommand:
    def test_no_args_shows_usage_error(self):
        result = invoke_catching("--yaml", str(FIXTURE_TOPOLOGY), "gen-keys")
        assert result.exit_code != 0

    def test_both_node_id_and_all_shows_error(self):
        result = invoke_catching("--yaml", str(FIXTURE_TOPOLOGY), "gen-keys", "nlA00", "--all")
        assert result.exit_code != 0

    def test_single_node_creates_key_file(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-keys",
            "nlA00",
            "--keys-dir",
            str(tmp_path),
        )
        assert result.exit_code == 0
        assert (tmp_path / "nlA00.yaml").exists()

    def test_single_node_reports_generated(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-keys",
            "nlA00",
            "--keys-dir",
            str(tmp_path),
        )
        assert "generated" in result.output

    def test_all_generates_both_nodes(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-keys",
            "--all",
            "--keys-dir",
            str(tmp_path),
        )
        assert result.exit_code == 0
        assert (tmp_path / "nlA00.yaml").exists()
        assert (tmp_path / "mskA00.yaml").exists()

    def test_all_summary_shows_all_generated(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-keys",
            "--all",
            "--keys-dir",
            str(tmp_path),
        )
        assert "3 generated" in result.output

    def test_skip_existing_without_force(self, tmp_path):
        invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-keys",
            "nlA00",
            "--keys-dir",
            str(tmp_path),
        )
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-keys",
            "nlA00",
            "--keys-dir",
            str(tmp_path),
        )
        assert "skipped" in result.output

    def test_force_overwrites_existing(self, tmp_path):
        invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-keys",
            "nlA00",
            "--keys-dir",
            str(tmp_path),
        )
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-keys",
            "nlA00",
            "--force",
            "--keys-dir",
            str(tmp_path),
        )
        assert "generated" in result.output
        # "1 generated, 0 skipped" — no node was skipped
        assert "1 generated, 0 skipped" in result.output


class TestBuildCommand:
    def test_no_args_shows_usage_error(self):
        result = invoke_catching("--yaml", str(FIXTURE_TOPOLOGY), "build")
        assert result.exit_code != 0

    def test_both_node_and_all_shows_error(self, tmp_path):
        result = invoke_catching(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "build",
            "nlA00",
            "--all",
            "--xray",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code != 0

    def test_no_format_shows_usage_error(self, tmp_path):
        result = invoke_catching(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "build",
            "nlA00",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code != 0

    def test_exit_node_xray_creates_config(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "build",
            "nlA00",
            "--xray",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code == 0
        assert (tmp_path / "nlA00" / "config.json").exists()

    def test_hub_node_xray_creates_config(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "build",
            "mskA00",
            "--xray",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code == 0
        assert (tmp_path / "mskA00" / "config.json").exists()

    def test_all_haproxy_creates_both_cfgs(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "build",
            "--all",
            "--haproxy",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code == 0
        assert (tmp_path / "nlA00" / "haproxy.cfg").exists()
        assert (tmp_path / "mskA00" / "haproxy.cfg").exists()

    def test_build_reports_built(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "build",
            "nlA00",
            "--xray",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert "built" in result.output


class TestDeriveCommand:
    def test_users_shows_usernames(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "derive", "users")
        assert result.exit_code == 0
        assert "alice" in result.output
        assert "bob" in result.output

    def test_groups_shows_group_ids(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "derive", "groups")
        assert result.exit_code == 0
        assert "main" in result.output
        assert "guest" in result.output

    def test_nodes_shows_node_ids(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "derive", "nodes")
        assert result.exit_code == 0
        assert "nlA00" in result.output
        assert "mskA00" in result.output

    def test_all_exits_zero(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "derive", "all")
        assert result.exit_code == 0

    def test_portals_shows_strict_and_published_ports(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "derive", "portals", env=WIDE)
        assert result.exit_code == 0
        assert "home-portal" in result.output
        assert "8443/tcp -> 192.168.1.10:443  allow: 203.0.113.7/32  nodes: all" in result.output
        assert "9000/tcp,udp -> nas.home.arpa:5000  allow: any  nodes: all" in result.output

    def test_portals_reports_strict_per_portal(self, tmp_path):
        topo = tmp_path / "topology.yaml"
        topo.write_text(
            yaml.dump(
                make_topology(
                    portals=[
                        {"id": "home", "users": ["alice"], "routes": {"domains": ["home.example.com"]}},
                        {
                            "id": "lab",
                            "users": ["alice"],
                            "routes": {"ips": ["172.16.0.0/12"]},
                            "strict": False,
                        },
                    ],
                ),
            ),
        )
        result = invoke("--yaml", str(topo), "derive", "portals", env=WIDE)
        assert result.exit_code == 0
        home_row = next(line for line in result.output.splitlines() if "home-portal" in line)
        lab_row = next(line for line in result.output.splitlines() if "lab-portal" in line)
        assert "on" in home_row and "off" not in home_row
        assert "off" in lab_row

    def test_portals_keeps_bracketed_ipv6_target(self, tmp_path):
        # rich parses "[fd00::10]" as markup unless escaped, silently dropping the host
        topo = tmp_path / "topology.yaml"
        topo.write_text(
            yaml.dump(
                make_topology(
                    portals=[
                        {
                            "id": "home",
                            "users": ["alice"],
                            "routes": {"domains": ["home.example.com"]},
                            "publish": [{"port": 8443, "target": "[fd00::10]:443"}],
                        },
                    ],
                ),
            ),
        )
        result = invoke("--yaml", str(topo), "derive", "portals", env=WIDE)
        assert result.exit_code == 0
        assert "8443/tcp -> [fd00::10]:443" in result.output


class TestNodesCommand:
    def test_lists_both_nodes(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "nodes", "list")
        assert result.exit_code == 0
        assert "nlA00" in result.output
        assert "mskA00" in result.output

    def test_names_only_flag(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "nodes", "list", "--names")
        lines = [line.strip() for line in result.output.splitlines() if line.strip()]
        # Should be just IDs, no tabs
        assert all("\t" not in line for line in lines)
        assert "nlA00" in lines
        assert "mskA00" in lines

    def test_domains_only_flag(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "nodes", "list", "--domains")
        assert "nlA00.ap.test.hexrift" in result.output
        assert "mskA00.ap.test.hexrift" in result.output

    def test_type_filter_exit(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "nodes", "list", "--type", "exit")
        assert "nlA00" in result.output
        assert "mskA00" not in result.output

    def test_type_filter_hub(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "nodes", "list", "--type", "hub")
        assert "mskA00" in result.output
        assert "nlA00" not in result.output

    def test_json_output(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "nodes", "list", "--json")
        assert result.exit_code == 0
        assert json.loads(result.output) == [
            {"id": "nlA00", "hostname": "nlA00.ap.test.hexrift", "region": "nl", "type": "exit"},
            {"id": "deA00", "hostname": "deA00.ap.test.hexrift", "region": "de", "type": "exit"},
            {"id": "mskA00", "hostname": "mskA00.ap.test.hexrift", "region": "msk", "type": "hub"},
        ]

    def test_json_output_honours_type_filter(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "nodes", "list", "--json", "--type", "hub")
        assert json.loads(result.output) == [
            {"id": "mskA00", "hostname": "mskA00.ap.test.hexrift", "region": "msk", "type": "hub"},
        ]


class TestTopologyCommands:
    @staticmethod
    def _copy(tmp_path: Path) -> Path:
        return Path(shutil.copy(FIXTURE_TOPOLOGY, tmp_path / "topology.yaml"))

    def test_add_node_appends_to_region(self, tmp_path):
        topo = self._copy(tmp_path)
        result = invoke(
            "--yaml",
            str(topo),
            "nodes",
            "add",
            "nlA20",
            "--no-ipv6",
            "--reality-dest",
            "www.samsung.com:443",
            "--reality-server-names",
            "www.samsung.com, samsung.com",
            "--reality-xhttp-path",
            "/login/",
        )
        assert result.exit_code == 0
        assert "added" in result.output and "nlA20.ap.test.hexrift" in result.output
        assert (
            "      - id: nlA20\n"
            "        hostname: nlA20.ap.test.hexrift\n"
            "        ipv6: false\n"
            "        reality:\n"
            "          dest: www.samsung.com:443\n"
            "          server_names: [www.samsung.com, samsung.com]\n"
            "          xhttp_path: /login/\n"
            "        hysteria:\n"
            "          obfs: true\n"
            "          sni: nlA20.ap.test.hexrift\n"
            "          masquerade_url: https://www.samsung.com\n"
            "  - id: de\n"
        ) in topo.read_text()

    def test_add_node_creates_region_and_warns_when_invalid(self, tmp_path):
        topo = self._copy(tmp_path)
        result = invoke("--yaml", str(topo), "nodes", "add", "usA00", "--type", "exit")
        assert result.exit_code == 0
        assert "created" in result.output
        assert "must have reality config" in result.output
        assert "  - id: us\n    type: exit\n    vless_route: " in topo.read_text()

    def test_reality_options_require_dest(self, tmp_path):
        topo = self._copy(tmp_path)
        result = invoke_catching("--yaml", str(topo), "nodes", "add", "nlA20", "--reality-xhttp-path", "/x/")
        assert result.exit_code != 0
        assert "--reality-dest" in result.output

    def test_reality_dest_requires_xhttp_path(self, tmp_path):
        topo = self._copy(tmp_path)
        result = invoke_catching("--yaml", str(topo), "nodes", "add", "nlA20", "--reality-dest", "a.com:443")
        assert result.exit_code != 0
        assert "--reality-xhttp-path" in result.output

    def test_remove_node_reports_emptied_region(self, tmp_path):
        topo = self._copy(tmp_path)
        result = invoke("--yaml", str(topo), "nodes", "remove", "deA00")
        assert result.exit_code == 0
        assert result.output.strip() == "removed  deA00 from region de  (region now empty)"


class TestShareCommand:
    def test_reality_url_output(self):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "share",
            "alice",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
        )
        assert result.exit_code == 0
        assert "vless://" in result.output

    def test_cdn_url_output(self):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "share",
            "alice",
            "--cdn",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
        )
        assert result.exit_code == 0
        assert "security=tls" in result.output

    def test_hysteria_url_output(self):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "share",
            "alice",
            "--hy2",
            "--bare",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
        )
        assert result.exit_code == 0
        assert result.output.startswith("hysteria2://")

    def test_hysteria_and_cdn_mutually_exclusive(self):
        result = invoke_catching(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "share",
            "alice",
            "--hy2",
            "--cdn",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
        )
        assert result.exit_code != 0
        assert "--hy2" in result.output and "--cdn" in result.output

    def test_all_guests_flag(self):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "share",
            "bob",
            "--all-guests",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
        )
        assert result.exit_code == 0
        # Both guests should appear
        assert "laptop" in result.output
        assert "phone" in result.output

    def test_guest_and_all_guests_mutually_exclusive(self):
        result = invoke_catching(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "share",
            "bob",
            "--guest",
            "laptop",
            "--all-guests",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
        )
        assert result.exit_code != 0

    def test_bare_output_contains_only_url(self):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "share",
            "alice",
            "--bare",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
        )
        assert result.exit_code == 0
        # In bare mode every line is a raw URL
        lines = [line for line in result.output.splitlines() if line.strip()]
        assert all(line.startswith("vless://") for line in lines)

    def test_show_command_exits_zero(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "show")
        assert result.exit_code == 0

    def test_show_command_lists_portal_publishes(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "show", env=WIDE)
        assert result.exit_code == 0
        assert "strict: on" in result.output
        assert "publish 8443/tcp -> 192.168.1.10:443  allow: 203.0.113.7/32  nodes: all" in result.output
        assert "publish 9000/tcp,udp -> nas.home.arpa:5000  allow: any  nodes: all" in result.output

    def test_show_badges_exit_listening_under_vless(self, tmp_path):
        topology = make_topology()
        topology["regions"][0]["hysteria"] = {"port": 8443}
        topo = tmp_path / "topology.yaml"
        topo.write_text(yaml.dump(topology))
        result = invoke("--yaml", str(topo), "show", env=WIDE)
        assert result.exit_code == 0
        exit_row = next(line for line in result.output.splitlines() if "exit1" in line)
        assert "hysteria" in exit_row


class TestGenPortalCommand:
    def test_builds_portal(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-portal",
            "home",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code == 0
        assert "built" in result.output
        assert (tmp_path / "home" / "config.json").exists()

    def test_builds_all_portals(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-portal",
            "--all",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code == 0
        assert (tmp_path / "home" / "config.json").exists()

    def test_no_args_fails(self, tmp_path):
        result = invoke_catching(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-portal",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code != 0

    def test_all_without_portals_fails(self, tmp_path):
        topology = tmp_path / "no-portals.yaml"
        data = yaml.safe_load(FIXTURE_TOPOLOGY.read_text())
        data.pop("portals")
        topology.write_text(yaml.dump(data))
        result = invoke_catching(
            "--yaml",
            str(topology),
            "gen-portal",
            "--all",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code != 0

    def test_id_and_all_fails(self, tmp_path):
        result = invoke_catching(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-portal",
            "home",
            "--all",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code != 0

    def test_unknown_portal_fails(self, tmp_path):
        result = invoke_catching(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-portal",
            "ghost",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code != 0


class TestDiffCommand:
    def test_matching_config_reports_no_differences(self):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "diff",
            "mskA00",
            "--current-dir",
            str(FIXTURE_CONFIGS_DIR),
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
        )
        assert result.exit_code == 0
        assert "No differences" in result.output

    def test_missing_current_config_is_reported(self, tmp_path):
        # current-dir exists but holds no config for the node
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "diff",
            "mskA00",
            "--current-dir",
            str(tmp_path),
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
        )
        assert result.exit_code == 0
        assert "no current config" in result.output
