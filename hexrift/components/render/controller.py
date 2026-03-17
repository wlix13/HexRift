from __future__ import annotations

import difflib
from pathlib import Path
from typing import TYPE_CHECKING

from hexrift.components.render.context import build_exit_context, build_hub_context
from hexrift.components.render.haproxy import render_haproxy
from hexrift.components.render.xray import build_exit_config, build_hub_config, serialize_config
from hexrift.constants import RegionType
from hexrift.core.controller import BaseController


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp  # noqa: F401
    from hexrift.components.schema.models import Node


class RenderController(BaseController["HexRiftApp"]):
    def _load_context(self, node_id: str, keys_dir: Path) -> tuple[Node, dict, str]:
        """Load node context and build xray config + haproxy cfg."""

        region, node = self.app.schema.get_node(node_id)
        cfg = self.app.schema.config
        node_keys = self.app.keys.load_node_keys(node_id, keys_dir)

        if region.type == RegionType.EXIT:
            hub_nodes = [n for r in cfg.regions if r.type == RegionType.HUB for n in r.nodes]
            ctx = build_exit_context(cfg, region, node, node_keys, hub_nodes)
            xray_config = build_exit_config(ctx)
            haproxy_cfg = render_haproxy(ctx, RegionType.EXIT)
        else:
            exit_node_keys = {
                n.id: self.app.keys.load_node_keys(n.id, keys_dir)
                for r in cfg.regions
                if r.type == RegionType.EXIT
                for n in r.nodes
            }
            ctx = build_hub_context(cfg, region, node, node_keys, exit_node_keys)
            xray_config = build_hub_config(ctx)
            haproxy_cfg = render_haproxy(ctx, RegionType.HUB)

        return node, xray_config, haproxy_cfg

    def build(
        self,
        node_id: str,
        out_dir: Path,
        keys_dir: Path,
        xray: bool,
        haproxy: bool,
    ) -> None:
        """Generate config.json and haproxy.cfg for node."""

        _node, xray_config, haproxy_cfg = self._load_context(node_id, keys_dir)

        node_dir = out_dir / node_id
        node_dir.mkdir(parents=True, exist_ok=True)
        if xray:
            (node_dir / "config.json").write_bytes(serialize_config(xray_config))
        if haproxy:
            (node_dir / "haproxy.cfg").write_text(haproxy_cfg)

    def diff(self, node_id: str, current_dir: Path, keys_dir: Path) -> str:
        """Return unified diff between generated and current config.json."""

        _node, xray_config, _haproxy_cfg = self._load_context(node_id, keys_dir)

        generated = serialize_config(xray_config).decode()
        current_path = current_dir / node_id / "config.json"
        if not current_path.exists():
            return f"(no current config at {current_path})"
        current = current_path.read_text()

        lines = list(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile=f"current/{node_id}/config.json",
                tofile=f"generated/{node_id}/config.json",
            )
        )
        return "".join(lines)
