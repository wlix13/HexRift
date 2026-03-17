from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import rich_click as click
from rich.syntax import Syntax

from hexrift.components.render.controller import RenderController
from hexrift.core.component import BaseComponent
from hexrift.errors import NodeError, RenderError


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp


class RenderComponent(BaseComponent["HexRiftApp", RenderController]):
    name = "render"
    controller_class = RenderController
    expose_controller = True

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        @base.command()
        @click.argument("node_id", required=False, default="")
        @click.option(
            "--xray",
            is_flag=True,
            default=False,
            help="Render config.json for xray.",
        )
        @click.option(
            "--haproxy",
            is_flag=True,
            default=False,
            help="Render haproxy.cfg for haproxy.",
        )
        @click.option(
            "--all",
            "all_nodes",
            is_flag=True,
            help="Build configs for all nodes.",
        )
        @click.option(
            "--out-dir",
            type=click.Path(path_type=Path),
            default=Path("configs"),
            show_default=True,
        )
        @click.option(
            "--keys-dir",
            type=click.Path(path_type=Path),
            default=Path("keys"),
            show_default=True,
        )
        @click.pass_obj
        def build(
            app: HexRiftApp,
            node_id: str,
            xray: bool,
            haproxy: bool,
            all_nodes: bool,
            out_dir: Path,
            keys_dir: Path,
        ) -> None:
            """Generate Xray config.json and HAProxy .cfg for node(s)."""

            if not all_nodes and not node_id:
                raise click.UsageError("Provide NODE_ID or --all.")
            if all_nodes and node_id:
                raise click.UsageError("Provide either NODE_ID or --all, not both.")

            if not xray and not haproxy:
                raise click.UsageError("Render at least one of: --xray or --haproxy.")

            if all_nodes:
                nodes_to_build = app.schema.get_all_nodes()
            else:
                try:
                    nodes_to_build = [app.schema.get_node(node_id)]
                except KeyError:
                    raise NodeError(f"Node not found: {node_id!r}")

            ok = failed = 0
            for _, node in nodes_to_build:
                try:
                    app.render.build(node.id, out_dir, keys_dir, xray, haproxy)
                    app.console.print(f"  [green]built[/green]  {node.id}")
                    ok += 1
                except Exception as e:
                    app.console.print(f"  [red]error[/red]  {node.id}: {e}")
                    failed += 1

            app.console.print(f"\n[bold]Done[/bold] — {ok} built, {failed} failed  ([dim]{out_dir}/[/dim])")
            if failed:
                raise RenderError(f"{failed} node(s) failed to build")

        @base.command()
        @click.argument("node_id")
        @click.option(
            "--current-dir",
            type=click.Path(exists=True, path_type=Path),
            required=False,
            default=Path("configs"),
            help="Directory containing currently deployed configs.",
        )
        @click.option(
            "--keys-dir",
            type=click.Path(path_type=Path),
            default=Path("keys"),
            show_default=True,
        )
        @click.pass_obj
        def diff(app: HexRiftApp, node_id: str, current_dir: Path, keys_dir: Path) -> None:
            """Show diff between generated and currently deployed config.json."""

            result = app.render.diff(node_id, current_dir, keys_dir)
            if not result:
                app.console.print("[green]No differences.[/green]")
            else:
                app.console.print(Syntax(result, "diff", theme="monokai"))
