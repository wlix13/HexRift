from pathlib import Path

from click.testing import CliRunner

from hexrift.app import cli


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
FIXTURE_CONFIGS_DIR = FIXTURES_DIR / "configs"
FIXTURE_TOPOLOGY = FIXTURES_DIR / "topology.yaml"
FIXTURE_KEYS_DIR = FIXTURES_DIR / "keys"


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

    def test_all_summary_shows_two_generated(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-keys",
            "--all",
            "--keys-dir",
            str(tmp_path),
        )
        assert "2 generated" in result.output

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


class TestNodesCommand:
    def test_lists_both_nodes(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "nodes")
        assert result.exit_code == 0
        assert "nlA00" in result.output
        assert "mskA00" in result.output

    def test_names_only_flag(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "nodes", "--names")
        lines = [line.strip() for line in result.output.splitlines() if line.strip()]
        # Should be just IDs, no tabs
        assert all("\t" not in line for line in lines)
        assert "nlA00" in lines
        assert "mskA00" in lines

    def test_domains_only_flag(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "nodes", "--domains")
        assert "nlA00.ap.test.hexrift" in result.output
        assert "mskA00.ap.test.hexrift" in result.output

    def test_type_filter_exit(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "nodes", "--type", "exit")
        assert "nlA00" in result.output
        assert "mskA00" not in result.output

    def test_type_filter_hub(self):
        result = invoke("--yaml", str(FIXTURE_TOPOLOGY), "nodes", "--type", "hub")
        assert "mskA00" in result.output
        assert "nlA00" not in result.output


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


class TestGenPortalCommand:
    def test_builds_portal(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-portal",
            "alice",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code == 0
        assert "built" in result.output
        assert (tmp_path / "alice-home.json").exists()

    def test_single_label(self, tmp_path):
        result = invoke(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-portal",
            "alice",
            "--label",
            "home",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code == 0
        assert (tmp_path / "alice-home.json").exists()

    def test_unknown_user_fails(self, tmp_path):
        result = invoke_catching(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-portal",
            "nobody",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code != 0

    def test_user_without_portals_fails(self, tmp_path):
        # bob has no portals configured
        result = invoke_catching(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-portal",
            "bob",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code != 0

    def test_unknown_label_fails(self, tmp_path):
        result = invoke_catching(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-portal",
            "alice",
            "--label",
            "ghost",
            "--keys-dir",
            str(FIXTURE_KEYS_DIR),
            "--out-dir",
            str(tmp_path),
        )
        assert result.exit_code != 0

    def test_unknown_group_fails(self, tmp_path):
        result = invoke_catching(
            "--yaml",
            str(FIXTURE_TOPOLOGY),
            "gen-portal",
            "alice",
            "--group",
            "ghostgroup",
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
