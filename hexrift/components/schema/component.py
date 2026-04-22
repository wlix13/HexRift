from __future__ import annotations

from typing import TYPE_CHECKING

import rich_click as click

from hexrift.components.schema.controller import SchemaController
from hexrift.core.component import BaseComponent


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp


class SchemaComponent(BaseComponent["HexRiftApp", SchemaController]):
    name = "schema"
    controller_class = SchemaController
    expose_controller = True

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        @base.command()
        @click.pass_obj
        def validate(app: HexRiftApp) -> None:
            """Validate YAML configuration and report any errors."""

            try:
                cfg = app.schema.load(app.yaml_path)
                exit_regions = app.schema.get_exit_regions()
                hub_regions = app.schema.get_hub_regions()
                total_nodes = sum(len(r.nodes) for r in cfg.regions)
                app.console.print(f"[bold green]Valid[/bold green] — {app.yaml_path}")
                app.console.print(
                    f"  {len(cfg.groups)} groups, {len(cfg.users)} users, "
                    f"{len(exit_regions)} exit regions, {len(hub_regions)} hub regions, "
                    f"{total_nodes} nodes"
                )
            except Exception as e:
                app.console.print(f"[bold red]Validation error:[/bold red] {e}")
                raise click.Abort() from e
