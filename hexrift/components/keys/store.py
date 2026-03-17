"""Read/write key files from/to keys/ directory."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from hexrift.errors import KeysError


class NodeKeys(BaseModel):
    """Cryptographic key material for a single node."""

    reality_private_key: str
    reality_public_key: str
    decryption: str  # {method}.{mode}.{session_time}[.{padding}].{private_key_b64}  — server inbound
    encryption: str  # {method}.{mode}.0rtt.{public_key_b64}                         — client outbound


def _node_keys_path(keys_dir: Path, node_id: str) -> Path:
    if Path(node_id).name != node_id or "/" in node_id or "\\" in node_id:
        raise ValueError(f"Invalid node ID: {node_id!r}")
    return keys_dir / f"{node_id}.yaml"


def node_keys_exist(keys_dir: Path, node_id: str) -> bool:
    return _node_keys_path(keys_dir, node_id).exists()


def load_node_keys(keys_dir: Path, node_id: str) -> NodeKeys:
    path = _node_keys_path(keys_dir, node_id)
    if not path.exists():
        raise KeysError(f"No keys found for node {node_id!r}. Run: hexrift gen-keys {node_id}")
    try:
        data = yaml.safe_load(path.read_text())
        return NodeKeys.model_validate(data)
    except (yaml.YAMLError, ValidationError) as err:
        raise KeysError(
            f"No keys found for node {node_id!r} or keys are corrupted; run: hexrift gen-keys {node_id} — error: {err}"
        ) from err


def save_node_keys(keys_dir: Path, node_id: str, keys: NodeKeys) -> None:
    keys_dir.mkdir(parents=True, exist_ok=True)
    path = _node_keys_path(keys_dir, node_id)
    path.write_text(yaml.dump(keys.model_dump(), default_flow_style=False))
    path.chmod(0o600)
