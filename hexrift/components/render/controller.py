from __future__ import annotations

import difflib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from hexrift.components.render.haproxy import render_haproxy
from hexrift.components.render.portal import build_portal_config
from hexrift.components.render.xray import build_exit_config, build_hub_config, serialize_config
from hexrift.constants import RegionType
from hexrift.core.controller import BaseController
from hexrift.errors import RenderError
from hexrift.inbounds.context import ExitContext, HubContext, build_exit_context, build_hub_context
from hexrift.shared.files import write_secret_file


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp  # noqa: F401


ItemCallback = Callable[[str, "Exception | None"], None]
"""Per-item progress callback: receives item ID and failure (None on success)."""


@dataclass
class BatchResult:
    """Counts of successes and failures from multi-item build."""

    ok: int
    failed: int


class RenderController(BaseController["HexRiftApp"]):
    @staticmethod
    def _write_secret_config(path: Path, data: bytes) -> None:
        """Write rendered config that embeds private key material, restricting it to 0o600."""

        write_secret_file(path, data)

    def _build_context(self, node_id: str, keys_dir: Path) -> ExitContext | HubContext:
        """Build context for node."""

        region, node = self.app.schema.get_node(node_id)
        cfg = self.app.schema.config
        node_keys = self.app.keys.load_node_keys(node_id, keys_dir)

        if region.type == RegionType.EXIT:
            return build_exit_context(cfg, region, node, node_keys)
        exit_node_keys = {
            n.id: self.app.keys.load_node_keys(n.id, keys_dir)
            for r in cfg.regions
            if r.type == RegionType.EXIT
            for n in r.nodes
        }
        return build_hub_context(cfg, region, node, node_keys, exit_node_keys)

    @staticmethod
    def _xray_config(ctx: ExitContext | HubContext) -> dict:
        return build_exit_config(ctx) if isinstance(ctx, ExitContext) else build_hub_config(ctx)

    def build(
        self,
        node_id: str,
        out_dir: Path,
        keys_dir: Path,
        xray: bool,
        haproxy: bool,
    ) -> None:
        """Generate config.json and haproxy.cfg for node."""

        ctx = self._build_context(node_id, keys_dir)

        node_dir = out_dir / node_id
        node_dir.mkdir(parents=True, exist_ok=True)
        if xray:
            self._write_secret_config(
                node_dir / "config.json",
                serialize_config(self._xray_config(ctx)),
            )
        if haproxy:
            (node_dir / "haproxy.cfg").write_text(render_haproxy(ctx))

    def build_nodes(
        self,
        node_ids: list[str],
        out_dir: Path,
        keys_dir: Path,
        xray: bool,
        haproxy: bool,
        on_item: ItemCallback | None = None,
    ) -> BatchResult:
        """Build configs for several nodes, isolating per-node failures and tallying results."""

        return self._run_batch(
            node_ids,
            lambda nid: self.build(nid, out_dir, keys_dir, xray, haproxy),
            on_item,
        )

    def gen_portal(
        self,
        username: str,
        label: str,
        out_dir: Path,
        keys_dir: Path,
        fingerprint: str,
        group_id: str | None = None,
    ) -> None:
        """Generate portal client config.json."""

        cfg = self.app.schema.config
        user = next((u for u in cfg.users if u.username == username), None)
        if user is None:
            raise RenderError(f"User not found: {username!r}")
        if not any(p.label == label for p in user.portals):
            raise RenderError(f"Portal {label!r} not found for user {username!r}.")
        resolved_group_id = group_id if group_id is not None else user.group
        if not any(g.id == resolved_group_id for g in cfg.groups):
            raise RenderError(f"Group not found: {resolved_group_id!r}")
        hub_node_keys = {
            n.id: self.app.keys.load_node_keys(n.id, keys_dir)
            for r in cfg.regions
            if r.type == RegionType.HUB
            for n in r.nodes
        }
        config = build_portal_config(
            cfg,
            username,
            label,
            hub_node_keys,
            fingerprint,
            group_id=group_id,
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        self._write_secret_config(out_dir / f"{username}-{label}.json", serialize_config(config))

    def gen_portals(
        self,
        username: str,
        label: str | None,
        out_dir: Path,
        keys_dir: Path,
        fingerprint: str,
        group_id: str | None = None,
        on_item: ItemCallback | None = None,
    ) -> BatchResult:
        """Generate user's portal configs: one named portal, or all of them."""

        cfg = self.app.schema.config
        user = next((u for u in cfg.users if u.username == username), None)
        if user is None:
            raise RenderError(f"User not found: {username!r}")
        if not user.portals:
            raise RenderError(f"User {username!r} has no portals configured.")
        if label is not None and not any(p.label == label for p in user.portals):
            raise RenderError(f"Portal {label!r} not found for user {username!r}.")
        labels = [label] if label is not None else [p.label for p in user.portals]
        return self._run_batch(
            labels,
            lambda lbl: self.gen_portal(username, lbl, out_dir, keys_dir, fingerprint, group_id=group_id),
            on_item,
        )

    @staticmethod
    def _run_batch(items: list[str], action: Callable[[str], None], on_item: ItemCallback | None) -> BatchResult:
        ok = failed = 0
        for item in items:
            try:
                action(item)
                ok += 1
                error: Exception | None = None
            except Exception as e:
                failed += 1
                error = e
            if on_item is not None:
                on_item(item, error)
        return BatchResult(ok, failed)

    def diff(self, node_id: str, current_dir: Path, keys_dir: Path) -> str:
        """Return unified diff between generated and current config.json."""

        ctx = self._build_context(node_id, keys_dir)

        generated = serialize_config(self._xray_config(ctx)).decode()
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
