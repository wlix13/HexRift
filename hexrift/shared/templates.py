"""Jinja environment and rendering helpers for bundled config templates."""

from __future__ import annotations

import functools
import re

from jinja2 import Environment, PackageLoader


BLANK_RUN_RE = re.compile(r"\n{3,}")
"""Two or more consecutive blank lines."""


@functools.cache
def jinja_env(subdir: str) -> Environment:
    """Return cached Jinja environment for `hexrift/templates/<subdir>`."""

    return Environment(
        loader=PackageLoader("hexrift", f"templates/{subdir}"),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,  # noqa: S701
    )


def render_template(subdir: str, name: str, **context: object) -> str:
    text = jinja_env(subdir).get_template(name).render(**context)
    return BLANK_RUN_RE.sub("\n\n", text).rstrip("\n") + "\n"
