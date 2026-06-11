"""Filesystem utilities shared between components."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_secret_file(path: Path, data: bytes) -> None:
    """Atomically write file restricted to 0o600."""

    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
