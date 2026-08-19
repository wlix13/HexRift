"""Pluggable hub→exit link protocols."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from hexrift.errors import RenderError


if TYPE_CHECKING:
    from hexrift.components.derive.identity import Namespace
    from hexrift.components.keys.store import NodeKeys
    from hexrift.components.schema.models.defaults import ExitConnectionsConfig
    from hexrift.components.schema.models.regions import Node, Region
    from hexrift.components.schema.models.root import ConglomerateConfig
    from hexrift.constants import ExitProtocol


@dataclass(frozen=True, kw_only=True)
class LinkContext:
    """Resolved data for one hub→exit outbound."""

    protocol: ClassVar[ExitProtocol]

    exit_id: str
    tag_prefix: str = ""  # "backup-" for lb backups, "warp-" for the warp variant

    @property
    def tag(self) -> str:
        return f"{self.tag_prefix}{self.exit_id}"


@dataclass(frozen=True)
class LinkEnv:
    """Inputs for dialing one exit node from one hub node."""

    config: ConglomerateConfig
    hub: Node
    exit_region: Region
    exit_node: Node
    exit_keys: NodeKeys
    ns: Namespace
    exit_connections: ExitConnectionsConfig

    @property
    def address(self) -> str:
        return f"{self.exit_node.id}.{self.config.global_.aphelion_domain}"


class LinkSpec[C: LinkContext](ABC):
    """One hub→exit link protocol: dial context plus the Xray outbound it renders to."""

    protocol: ClassVar[ExitProtocol]
    context_type: type[C]

    @abstractmethod
    def build_context(self, env: LinkEnv, identity: str, tag_prefix: str) -> C:
        """Resolve the dial for one hub-exit identity."""

    @abstractmethod
    def fragment(self, ctx: C, ipv6: bool) -> dict:
        """Xray outbound for the resolved dial."""

    def narrow(self, ctx: LinkContext) -> C:
        if not isinstance(ctx, self.context_type):
            raise RenderError(f"Link {self.protocol!r} got {type(ctx).__name__}, expected {self.context_type.__name__}")
        return ctx
