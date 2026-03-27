from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hexrift.components.derive.defaults import resolve_node_keys
from hexrift.components.keys.decryption import generate_auth_keypair
from hexrift.components.keys.reality import generate_x25519_keypair
from hexrift.components.keys.store import NodeKeys, load_node_keys, node_keys_exist, save_node_keys
from hexrift.constants import RegionType
from hexrift.core.controller import BaseController


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp  # noqa: F401


class KeysController(BaseController["HexRiftApp"]):
    def gen_keys(self, node_id: str, keys_dir: Path, force: bool = False) -> bool:
        """Generate key material for node.

        Hub nodes in the same region share the same keypairs so clients can
        use identical connection parameters (pbk, encryption, sid) across all
        nodes in the region — only the hostname differs.

        Returns True if keys were (re)generated, False if skipped.
        """

        if node_keys_exist(keys_dir, node_id) and not force:
            return False

        region, node = self.app.schema.get_node(node_id)
        cfg = self.app.schema.config
        keys_cfg = resolve_node_keys(node, region, cfg.defaults)

        if region.type == RegionType.HUB and not force:
            # Reuse keys from the first hub node that already has keys and matching config
            for sibling in region.nodes:
                if sibling.id != node_id and node_keys_exist(keys_dir, sibling.id):
                    sibling_keys_cfg = resolve_node_keys(sibling, region, cfg.defaults)
                    if sibling_keys_cfg == keys_cfg:
                        sibling_keys = load_node_keys(keys_dir, sibling.id)
                        save_node_keys(keys_dir, node_id, sibling_keys)
                        return True

        priv, pub = generate_x25519_keypair()
        if keys_cfg.enabled:
            decryption, encryption = generate_auth_keypair(
                keys_cfg.auth,
                keys_cfg.mode,
                keys_cfg.session_time,
                keys_cfg.padding,
            )
        else:
            decryption, encryption = "none", "none"

        save_node_keys(
            keys_dir,
            node_id,
            NodeKeys(
                reality_private_key=priv,
                reality_public_key=pub,
                decryption=decryption,
                encryption=encryption,
            ),
        )
        return True

    def load_node_keys(self, node_id: str, keys_dir: Path) -> NodeKeys:
        return load_node_keys(keys_dir, node_id)
