import json
from pathlib import Path

import pytest

from hexrift.app import HexRiftApp
from hexrift.components.render.portal import build_portal_config
from hexrift.errors import KeysError, RenderError


def _gen_all_keys(app: HexRiftApp, keys_dir):
    """Generate keys for all nodes in minimal topology."""

    for _region, node in app.schema.get_all_nodes():
        app.keys.gen_keys(node.id, keys_dir)


class TestBuildExit:
    def test_creates_config_json(self, app: HexRiftApp, tmp_path):
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "out"
        _gen_all_keys(app, keys_dir)
        app.render.build("exitN1", out_dir, keys_dir, xray=True, haproxy=True)
        assert (out_dir / "exitN1" / "config.json").exists()

    def test_creates_haproxy_cfg(self, app: HexRiftApp, tmp_path):
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "out"
        _gen_all_keys(app, keys_dir)
        app.render.build("exitN1", out_dir, keys_dir, xray=True, haproxy=True)
        assert (out_dir / "exitN1" / "haproxy.cfg").exists()

    def test_config_json_is_valid_json(self, app: HexRiftApp, tmp_path):
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "out"
        _gen_all_keys(app, keys_dir)
        app.render.build("exitN1", out_dir, keys_dir, xray=True, haproxy=True)
        raw = (out_dir / "exitN1" / "config.json").read_bytes()
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_config_json_has_expected_top_keys(self, app: HexRiftApp, tmp_path):
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "out"
        _gen_all_keys(app, keys_dir)
        app.render.build("exitN1", out_dir, keys_dir, xray=True, haproxy=True)
        parsed = json.loads((out_dir / "exitN1" / "config.json").read_bytes())
        for key in ("log", "inbounds", "outbounds", "routing", "dns"):
            assert key in parsed, f"Missing top-level key: {key!r}"

    def test_xray_only_no_haproxy(self, app: HexRiftApp, tmp_path):
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "out"
        _gen_all_keys(app, keys_dir)
        app.render.build("exitN1", out_dir, keys_dir, xray=True, haproxy=False)
        assert (out_dir / "exitN1" / "config.json").exists()
        assert not (out_dir / "exitN1" / "haproxy.cfg").exists()

    def test_haproxy_only_no_config_json(self, app: HexRiftApp, tmp_path):
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "out"
        _gen_all_keys(app, keys_dir)
        app.render.build("exitN1", out_dir, keys_dir, xray=False, haproxy=True)
        assert not (out_dir / "exitN1" / "config.json").exists()
        assert (out_dir / "exitN1" / "haproxy.cfg").exists()


class TestBuildHub:
    def test_creates_config_json(self, app: HexRiftApp, tmp_path):
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "out"
        _gen_all_keys(app, keys_dir)
        app.render.build("hubN1", out_dir, keys_dir, xray=True, haproxy=True)
        assert (out_dir / "hubN1" / "config.json").exists()

    def test_hub_config_json_is_valid_json(self, app: HexRiftApp, tmp_path):
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "out"
        _gen_all_keys(app, keys_dir)
        app.render.build("hubN1", out_dir, keys_dir, xray=True, haproxy=True)
        raw = (out_dir / "hubN1" / "config.json").read_bytes()
        parsed = json.loads(raw)
        assert "inbounds" in parsed
        assert "outbounds" in parsed


class TestDiff:
    def test_diff_empty_when_matching(self, app: HexRiftApp, tmp_path):
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "current"
        _gen_all_keys(app, keys_dir)
        app.render.build("exitN1", out_dir, keys_dir, xray=True, haproxy=False)
        diff = app.render.diff("exitN1", out_dir, keys_dir)
        assert diff == ""

    def test_diff_shows_changes_when_different(self, app: HexRiftApp, tmp_path):
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "current"
        _gen_all_keys(app, keys_dir)
        app.render.build("exitN1", out_dir, keys_dir, xray=True, haproxy=False)

        # Modify the stored config
        config_path = out_dir / "exitN1" / "config.json"
        config_path.write_text(config_path.read_text() + "\n// modified\n")

        diff = app.render.diff("exitN1", out_dir, keys_dir)
        assert len(diff) > 0

    def test_diff_returns_message_when_no_current(self, app: HexRiftApp, tmp_path):
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "empty"
        _gen_all_keys(app, keys_dir)
        diff = app.render.diff("exitN1", out_dir, keys_dir)
        assert "no current config" in diff


@pytest.fixture()
def portal_config(app: HexRiftApp, tmp_path: Path):
    keys_dir = tmp_path / "keys"
    out_dir = tmp_path / "out"
    _gen_all_keys(app, keys_dir)
    app.render.gen_portal("home", out_dir, keys_dir, "chrome")
    config_path = out_dir / "home" / "config.json"
    return {
        "keys_dir": keys_dir,
        "out_dir": out_dir,
        "config_path": config_path,
        "config": json.loads(config_path.read_bytes()),
    }


class TestPortalGen:
    def test_creates_portal_config_file(self, portal_config):
        assert portal_config["config_path"].exists()

    def test_portal_config_is_valid_json(self, portal_config):
        assert isinstance(portal_config["config"], dict)

    def test_portal_config_top_level_keys(self, portal_config):
        cfg = portal_config["config"]
        for key in ("log", "outbounds", "routing"):
            assert key in cfg, f"Missing top-level key: {key!r}"
        assert "inbounds" not in cfg
        assert "dns" not in cfg

    def test_portal_config_has_hub_outbound(self, portal_config):
        tags = [ob["tag"] for ob in portal_config["config"]["outbounds"]]
        assert "portal-hubN1" in tags

    def test_portal_config_has_direct_outbound(self, portal_config):
        tags = [ob["tag"] for ob in portal_config["config"]["outbounds"]]
        assert "direct" in tags

    def test_portal_config_outbound_count(self, portal_config):
        # 1 hub node (hubN1) + 1 direct freedom outbound
        assert len(portal_config["config"]["outbounds"]) == 2

    def test_portal_outbound_uses_hostname(self, portal_config):
        cfg = portal_config["config"]
        portal_ob = next((ob for ob in cfg["outbounds"] if ob["tag"] == "portal-hubN1"), None)
        assert portal_ob is not None, "Outbound 'portal-hubN1' not found in outbounds"
        assert portal_ob["settings"]["address"] == "hubN1.ap.test.ns"

    def test_portal_routing_reverse_inbound_rule_first(self, portal_config):
        rules = portal_config["config"]["routing"]["rules"]
        assert rules[0] == {"inboundTag": ["home-portal"], "outboundTag": "direct"}

    def test_portal_routing_catchall_direct_last(self, portal_config):
        rules = portal_config["config"]["routing"]["rules"]
        assert len(rules) == 2
        assert rules[-1]["network"] == "TCP,UDP"
        assert rules[-1]["outboundTag"] == "direct"

    def test_portal_outbound_reverse_tag(self, portal_config):
        ob = next(o for o in portal_config["config"]["outbounds"] if o["tag"] == "portal-hubN1")
        assert ob["settings"]["reverse"]["tag"] == "home-portal"

    def test_raises_for_unknown_portal(self, app: HexRiftApp, tmp_path: Path) -> None:
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "out"
        _gen_all_keys(app, keys_dir)
        with pytest.raises(RenderError, match="Portal not found"):
            app.render.gen_portal("nope", out_dir, keys_dir, "chrome")

    def test_dial_sockopt_follows_hub_ipv6(self, portal_config) -> None:
        ob = next(o for o in portal_config["config"]["outbounds"] if o["tag"] == "portal-hubN1")
        assert ob["streamSettings"]["sockopt"]["domainStrategy"] == "UseIPv6v4"

    def test_builder_raises_for_unknown_portal(self, app: HexRiftApp) -> None:
        with pytest.raises(RenderError, match="Portal not found: 'nope'"):
            build_portal_config(app.schema.config, "nope", {}, "chrome")

    def test_raises_when_keys_not_generated(self, app: HexRiftApp, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        with pytest.raises(KeysError):
            app.render.gen_portal("home", out_dir, tmp_path / "keys", "chrome")
