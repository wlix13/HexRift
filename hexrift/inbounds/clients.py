"""Client entry types and client-list helpers."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from hexrift.components.derive.identity import Namespace
from hexrift.components.schema.models.regions import Node
from hexrift.components.schema.models.users import User
from hexrift.constants import VLESS_FLOW, AccessType


class ClientEntry(TypedDict):
    """VLESS inbound client entry. `reverse` is present only for portal clients."""

    email: str
    id: str
    flow: str
    reverse: NotRequired[dict]


def get_exit_clients(
    hub_nodes: list[Node],
    exit_node: Node,
    ns: Namespace,
    flow: str = VLESS_FLOW,
) -> list[ClientEntry]:
    """Hub-exit clients for exit direct/cdn inbounds."""

    return [
        {
            "email": ns.hub_exit_email(hub.id, exit_node.id),
            "id": str(ns.hub_exit_uuid(hub.id, exit_node.id)),
            "flow": flow,
        }
        for hub in hub_nodes
    ]


def get_hub_access_clients(
    users: list[User],
    ns: Namespace,
    access_type: AccessType,
    flow: str,
    include_server: bool = False,
) -> list[ClientEntry]:
    """Clients (user, optional server, guests) for hub inbound gated by access type."""

    clients: list[ClientEntry] = []
    for u in users:
        if access_type not in u.access:
            continue
        user_base = ns.user_uuid(u.username, override=u.uuid)
        clients.append(
            {
                "id": str(user_base),
                "email": ns.user_email(u.username),
                "flow": flow,
            }
        )
        if include_server and AccessType.SERVER in u.access:
            clients.append(
                {
                    "id": str(ns.server_uuid(u.username, user_base=user_base)),
                    "email": ns.server_email(u.username),
                    "flow": flow,
                }
            )
        for label in u.guests:
            clients.append(
                {
                    "id": str(ns.guest_uuid(label, u.username, user_base=user_base)),
                    "email": ns.guest_email(label, u.username),
                    "flow": flow,
                }
            )
    return clients
