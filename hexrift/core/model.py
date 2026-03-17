from __future__ import annotations

import pydantic
from rich.console import Console
from rich.table import Table


_console = Console()


class BaseModel(pydantic.BaseModel):
    """Base model with rich display support."""

    model_config = pydantic.ConfigDict(populate_by_name=True)

    _REDACTED_FIELDS = frozenset({"reality_private_key", "decryption"})

    def display(self, console: Console | None = None) -> None:
        con = console or _console
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Field", style="bold")
        table.add_column("Value")
        for field, value in self.model_dump().items():
            display_value = "[dim]<redacted>[/dim]" if field in self._REDACTED_FIELDS else str(value)
            table.add_row(field, display_value)
        con.print(table)
