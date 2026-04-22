from __future__ import annotations

from typing import TYPE_CHECKING

import rich_click as click

from hexrift.components.schema.controller import SchemaController
from hexrift.core.component import BaseComponent
from hexrift.i18n import LazyString, _


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp


class SchemaComponent(BaseComponent["HexRiftApp", SchemaController]):
    name = "schema"
    controller_class = SchemaController
    expose_controller = True

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        @base.command(help=LazyString("Validate YAML configuration and report any errors."))
        @click.pass_obj
        def validate(app: HexRiftApp) -> None:
            try:
                cfg = app.schema.load(app.yaml_path)
                exit_regions = app.schema.get_exit_regions()
                hub_regions = app.schema.get_hub_regions()
                total_nodes = sum(len(r.nodes) for r in cfg.regions)
                app.console.print(f"[bold green]{_('Valid')}[/bold green] — {app.yaml_path}")
                app.console.print(
                    _("  {groups} groups, {users} users, {exit} exit regions, {hub} hub regions, {total} nodes").format(
                        groups=len(cfg.groups),
                        users=len(cfg.users),
                        exit=len(exit_regions),
                        hub=len(hub_regions),
                        total=total_nodes,
                    )
                )
            except Exception as e:
                app.console.print(f"[bold red]{_('Validation error:')}[/bold red] {e}")
                raise click.Abort() from e
