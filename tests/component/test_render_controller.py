import orjson

from hexrift.app import HexRiftApp


def _gen_all_keys(app: HexRiftApp, keys_dir):
    """Generate keys for all nodes in the minimal topology."""

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
        parsed = orjson.loads(raw)
        assert isinstance(parsed, dict)

    def test_config_json_has_expected_top_keys(self, app: HexRiftApp, tmp_path):
        keys_dir = tmp_path / "keys"
        out_dir = tmp_path / "out"
        _gen_all_keys(app, keys_dir)
        app.render.build("exitN1", out_dir, keys_dir, xray=True, haproxy=True)
        parsed = orjson.loads((out_dir / "exitN1" / "config.json").read_bytes())
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
        parsed = orjson.loads(raw)
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
