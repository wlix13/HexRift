from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING

from hexrift.constants import SHORT_ID_LENGTH, WARP_UUID_SEGMENT, UserSuffix


if TYPE_CHECKING:
    from hexrift.components.schema.models.groups import Group


class Namespace:
    """Derived identity factory bound to single namespace string."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._uuid = uuid.uuid5(uuid.UUID(int=0), name)

    @staticmethod
    def warp_uuid(base: uuid.UUID) -> uuid.UUID:
        """Hub-exit UUID with 3rd segment replaced by WARP_UUID_SEGMENT (0xFFFF = 65535).

        The exit node always routes vlessRoute 65535 → warp interface.
        """

        parts = str(base).split("-")
        parts[2] = WARP_UUID_SEGMENT
        return uuid.UUID("-".join(parts))

    @staticmethod
    def server_email(username: str) -> str:
        return f"{username}{UserSuffix.SERVER}@{username}"

    @staticmethod
    def portal_email(label: str, username: str) -> str:
        return f"{label}{UserSuffix.PORTAL}@{username}"

    @staticmethod
    def guest_email(label: str, username: str) -> str:
        return f"{label}@{username}"

    def user_uuid(self, username: str, override: uuid.UUID | None = None) -> uuid.UUID:
        if override is not None:
            return override
        return uuid.uuid5(self._uuid, username)

    def server_uuid(self, username: str, user_base: uuid.UUID | None = None) -> uuid.UUID:
        return uuid.uuid5(user_base or self.user_uuid(username), f"{username}{UserSuffix.SERVER}")

    def guest_uuid(self, label: str, username: str, user_base: uuid.UUID | None = None) -> uuid.UUID:
        return uuid.uuid5(user_base or self.user_uuid(username), label)

    def portal_uuid(self, label: str, username: str, user_base: uuid.UUID | None = None) -> uuid.UUID:
        return uuid.uuid5(user_base or self.user_uuid(username), f"{label}{UserSuffix.PORTAL}")

    def hub_exit_uuid(self, hub_id: str, exit_id: str) -> uuid.UUID:
        return uuid.uuid5(self._uuid, f"{hub_id}-{exit_id}")

    def group_short_id(self, group: Group) -> str:
        return group.short_id if group.short_id is not None else self._gen_group_short_id(group.id)

    def hub_short_id(self, node_id: str) -> str:
        return self._gen_short_id(f"{node_id}.hub.{self.name}")

    def exit_short_id(self, node_id: str) -> str:
        return self._gen_short_id(f"{node_id}.exit.{self.name}")

    def _gen_group_short_id(self, group_id: str) -> str:
        return self._gen_short_id(f"{group_id}.{self.name}")

    def _gen_short_id(self, txt: str) -> str:
        return hashlib.sha256(txt.encode()).hexdigest()[:SHORT_ID_LENGTH]

    def user_email(self, username: str) -> str:
        return f"{username}@{self.name}"

    def hub_exit_email(self, hub_id: str, exit_id: str) -> str:
        return f"{hub_id}-{exit_id}@{self.name}"

    def warp_email(self, hub_id: str, exit_id: str) -> str:
        return f"warp-{hub_id}-{exit_id}@{self.name}"
