"""Inbound specification base."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar
from uuid import UUID

from hexrift.components.derive.identity import Namespace
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.observability import ObservabilityConfig
from hexrift.components.schema.models.regions import ExitNode, HubNode, HubRegion, Node, Region
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.constants import AccessType, RegionType
from hexrift.errors import RenderError


@dataclass(frozen=True)
class InboundContext:
    """Base type for per-inbound resolved node data."""


@dataclass(frozen=True)
class SharedContext:
    """Cross-inbound node data consumed by fragments and HAProxy."""

    node_id: str
    hostname: str
    ipv6: bool
    decryption: str
    dns_address: str
    dns_port: int
    trusted_forwarded_headers: list[str]
    haproxy: bool
    route_only: bool
    observability: ObservabilityConfig


@dataclass(frozen=True)
class InboundEnv:
    """Resolution inputs for one node, handed to every spec."""

    config: ConglomerateConfig
    region: Region
    node: Node
    node_keys: NodeKeys

    @property
    def role(self) -> RegionType:
        return self.region.type

    @cached_property
    def ns(self) -> Namespace:
        return Namespace(self.config.global_.namespace)

    @cached_property
    def hub_nodes(self) -> list[HubNode]:
        return [n for r in self.config.hub_regions for n in r.nodes]

    @property
    def hub_region(self) -> HubRegion:
        if not isinstance(self.region, HubRegion):
            raise RenderError(f"Region {self.region.id!r} is not a hub region")
        return self.region

    @property
    def hub_node(self) -> HubNode:
        if not isinstance(self.node, HubNode):
            raise RenderError(f"Node {self.node.id!r} is not a hub node")
        return self.node

    @property
    def exit_node(self) -> ExitNode:
        if not isinstance(self.node, ExitNode):
            raise RenderError(f"Node {self.node.id!r} is not an exit node")
        return self.node


@dataclass(frozen=True)
class ShareClient:
    """One identity dialing hub inbound, as its share URL names it."""

    uuid: UUID
    short_id: str
    fingerprint: str
    fragment: str


class InboundSpec[C: InboundContext](ABC):
    """One inbound type: config resolution, client list, Xray fragment, share URL."""

    access_type: ClassVar[AccessType]
    roles: ClassVar[frozenset[RegionType]]
    context_type: type[C]

    @abstractmethod
    def build_context(self, env: InboundEnv) -> C | None:
        """Resolve node and defaults into inbound context; None disables inbound."""

    @abstractmethod
    def fragment(self, ctx: C, shared: SharedContext) -> dict:
        """Build Xray inbound JSON fragment."""

    def share_url(self, ctx: C, env: InboundEnv, client: ShareClient) -> str:
        """Build client share URL, mirror of fragment()."""

        raise RenderError(f"Inbound {self.access_type!r} has no share URL")

    def narrow(self, slots: Mapping[AccessType, InboundContext]) -> C | None:
        slot = slots.get(self.access_type)
        if slot is None:
            return None
        if not isinstance(slot, self.context_type):
            raise RenderError(
                f"Slot {self.access_type!r} holds {type(slot).__name__}, expected {self.context_type.__name__}"
            )
        return slot
