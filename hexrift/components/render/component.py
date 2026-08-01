from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import rich_click as click
from rich.syntax import Syntax

from hexrift.components.render.controller import RenderController
from hexrift.core.component import BaseComponent
from hexrift.errors import RenderError


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
                nodes_to_build = [app.schema.get_node(node_id)]

            def report(node_id: str, error: Exception | None) -> None:
                if error is None:
                    app.console.print(f"  [green]built[/green]  {node_id}")
                else:
                    app.console.print(f"  [red]error[/red]  {node_id}: {error}")

            node_ids = [node.id for _, node in nodes_to_build]
            result = app.render.build_nodes(node_ids, out_dir, keys_dir, xray, haproxy, on_item=report)

            app.console.print(
                f"\n[bold]Done[/bold] — {result.ok} built, {result.failed} failed  ([dim]{out_dir}/[/dim])"
            )
            if result.failed:
                raise RenderError(f"{result.failed} node(s) failed to build")

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

        @base.command("gen-portal")
        @click.argument("portal_id", required=False, default="")
        @click.option(
            "--all",
            "all_portals",
            is_flag=True,
            help="Build bridge configs for all portals.",
        )
        @click.option("--fp", default=None, help="TLS fingerprint (default: from config).")
        @click.option(
            "--out-dir",
            type=click.Path(path_type=Path),
            default=Path("configs/portals"),
            show_default=True,
        )
        @click.option(
            "--keys-dir",
            type=click.Path(path_type=Path),
            default=Path("keys"),
            show_default=True,
        )
        @click.pass_obj
        def gen_portal(
            app: HexRiftApp,
            portal_id: str,
            all_portals: bool,
            fp: str | None,
            out_dir: Path,
            keys_dir: Path,
        ) -> None:
            """Generate Xray config.json for portal bridge client(s)."""

            if not all_portals and not portal_id:
                raise click.UsageError("Provide PORTAL_ID or --all.")
            if all_portals and portal_id:
                raise click.UsageError("Provide either PORTAL_ID or --all, not both.")

            cfg = app.schema.config
            if all_portals:
                if not cfg.portals:
                    raise RenderError("No portals configured.")
                portal_ids = [p.id for p in cfg.portals]
            else:
                portal_ids = [portal_id]

            fingerprint = fp or cfg.defaults.hub.exit_connections.fingerprint

            def report(pid: str, error: Exception | None) -> None:
                if error is None:
                    app.console.print(f"  [green]built[/green]  {out_dir}/{pid}/config.json")
                else:
                    app.console.print(f"  [red]error[/red]  {pid}: {error}")

            result = app.render.gen_portals(
                portal_ids,
                out_dir,
                keys_dir,
                fingerprint,
                on_item=report,
            )

            app.console.print(
                f"\n[bold]Done[/bold] — {result.ok} built, {result.failed} failed  ([dim]{out_dir}/[/dim])"
            )
            if result.failed:
                raise RenderError(f"{result.failed} portal(s) failed to build")
