from __future__ import annotations

from pathlib import Path

import rich_click as click

from hexrift.components.derive.component import DeriveComponent
from hexrift.components.derive.controller import DeriveController
from hexrift.components.keys.component import KeysComponent
from hexrift.components.keys.controller import KeysController
from hexrift.components.render.component import RenderComponent
from hexrift.components.render.controller import RenderController
from hexrift.components.schema.component import SchemaComponent
from hexrift.components.schema.controller import SchemaController
from hexrift.core.application import BaseApplication


click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.USE_MARKDOWN = False
click.rich_click.STYLE_ERRORS_SUGGESTION = "dim italic"
click.rich_click.MAX_WIDTH = 100
click.rich_click.COMMAND_GROUPS = {
    "hexrift": [
        {
            "name": "Generate",
            "commands": ["gen-keys", "build"],
        },
        {"name": "Visualize", "commands": ["show", "derive", "share"]},
        {
            "name": "Validate",
            "commands": ["validate", "diff"],
        },
    ],
}


class HexRiftApp(BaseApplication["HexRiftApp"]):
    """Main application — component registry and dependency injector."""

    default_components = (SchemaComponent, DeriveComponent, KeysComponent, RenderComponent)

    schema: SchemaController
    derive: DeriveController
    keys: KeysController
    render: RenderController

    def __init__(self, yaml_path: Path) -> None:
        self.yaml_path = yaml_path
        super().__init__()


@click.group()
@click.option(
    "--yaml",
    "yaml_path",
    type=click.Path(path_type=Path),
    default="conglomerate.yaml",
    show_default=True,
    help="Path to topology yaml",
)
@click.pass_context
def cli(ctx: click.Context, yaml_path: Path) -> None:
    """HexRift — config generator for the Conglomerate proxy network."""

    ctx.obj = HexRiftApp(yaml_path=yaml_path)


HexRiftApp.register_cli(cli)
