"""Read/write key files from/to keys/ directory."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from hexrift.constants import VLESS_CLIENT_FLOW, VLESS_FLOW
from hexrift.errors import KeysError
from hexrift.shared.files import write_secret_file


ENCRYPTION_DISABLED = "none"
"""Sentinel stored in NodeKeys.decryption/encryption when VLESS encryption is disabled."""


class NodeKeys(BaseModel):
    """Cryptographic key material for a single node."""

    reality_private_key: str
    reality_public_key: str
    decryption: str  # {method}.{mode}.{session_time}[.{padding}].{private_key_b64}  — server inbound
    encryption: str  # {method}.{mode}.0rtt.{public_key_b64}                         — client outbound

    @property
    def encryption_enabled(self) -> bool:
        """True when node uses VLESS encryption."""

        return self.encryption != ENCRYPTION_DISABLED

    @property
    def flow(self) -> str:
        """Inbound VLESS flow, or empty when encryption is disabled."""

        return VLESS_FLOW if self.encryption_enabled else ""

    @property
    def client_flow(self) -> str:
        """Outbound (client) VLESS flow with udp443, or empty when encryption is disabled."""

        return VLESS_CLIENT_FLOW if self.encryption_enabled else ""


def _node_keys_path(node_id: str, keys_dir: Path) -> Path:
    if Path(node_id).name != node_id or "/" in node_id or "\\" in node_id:
        raise ValueError(f"Invalid node ID: {node_id!r}")
    return keys_dir / f"{node_id}.yaml"


def node_keys_exist(node_id: str, keys_dir: Path) -> bool:
    return _node_keys_path(node_id, keys_dir).exists()


def load_node_keys(node_id: str, keys_dir: Path) -> NodeKeys:
    path = _node_keys_path(node_id, keys_dir)
    if not path.exists():
        raise KeysError(f"No keys found for node {node_id!r}. Run: hexrift gen-keys {node_id}")
    try:
        data = yaml.safe_load(path.read_text())
        return NodeKeys.model_validate(data)
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValidationError) as e:
        raise KeysError(
            f"No keys found for node {node_id!r} or keys are corrupted; run: hexrift gen-keys {node_id} — error: {e}"
        ) from e


def save_node_keys(node_id: str, keys_dir: Path, keys: NodeKeys) -> None:
    keys_dir.mkdir(parents=True, exist_ok=True)
    path = _node_keys_path(node_id, keys_dir)
    content = yaml.dump(keys.model_dump(), default_flow_style=False)
    write_secret_file(path, content.encode())
