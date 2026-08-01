from functools import cached_property
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hexrift.components.schema.models.fields import (
    CidrList,
    HostPort,
    Identifier,
    IdentifierList,
    NonBlankList,
    Port,
    parse_host_port,
)
from hexrift.constants import PublishNetwork


class PortalRoutes(BaseModel):
    """Destinations steered into portal's reverse tunnel."""

    model_config = ConfigDict(extra="forbid", use_attribute_docstrings=True)

    domains: NonBlankList | None = None
    """Domain matchers, like Xray prefixes (`full:`, `domain:`, `regexp:`)."""

    ips: NonBlankList | None = None
    """CIDR/IP matchers."""

    @model_validator(mode="after")
    def validate_matchers(self):
        if not self.domains and not self.ips:
            raise ValueError("PortalRoutes requires at least one matcher: domains or ips")
        return self


class PortalPublish(BaseModel):
    """Port forwarded from hub nodes into portal's reverse tunnel."""

    model_config = ConfigDict(extra="forbid", use_attribute_docstrings=True)

    port: Port
    """Port bound by hub node."""

    target: HostPort
    """`host:port` dialed from portal machine."""

    network: PublishNetwork = PublishNetwork.TCP
    """Transports published: `tcp`, `udp`, or `tcp,udp`."""

    allow: Annotated[CidrList, Field(min_length=1)] | None = None
    """Source allowlist (CIDR or bare IP); unset means any source."""

    nodes: Annotated[IdentifierList, Field(min_length=1)] | None = None
    """Hub nodes that bind port; unset means every hub node."""

    @cached_property
    def target_host_port(self) -> tuple[str, int]:
        return parse_host_port(self.target)

    @model_validator(mode="after")
    def validate_unique_nodes(self):
        seen: set[str] = set()
        for node_id in self.nodes or []:
            if node_id in seen:
                raise ValueError(f"duplicate node {node_id!r} in publish port {self.port}")
            seen.add(node_id)
        return self


class Portal(BaseModel):
    """Reverse tunnel to machine outside hub/exit topology."""

    model_config = ConfigDict(extra="forbid", use_attribute_docstrings=True)

    id: Identifier
    """Portal id, also reverse tunnel tag prefix."""

    users: IdentifierList = Field(min_length=1)
    """Users whose traffic portal routes."""

    routes: PortalRoutes
    """Destinations steered into portal."""

    uuid: UUID | None = None
    """Override for derived portal identity UUID."""

    publish: list[PortalPublish] = []
    """Ports published by hub nodes into portal's reverse tunnel."""

    strict: bool = True
    """Restrict portal-side egress to `routes` and `publish` targets, blackholing all else."""

    @model_validator(mode="after")
    def validate_unique_users(self):
        seen: set[str] = set()
        for username in self.users:
            if username in seen:
                raise ValueError(f"duplicate user {username!r} in portal {self.id!r}")
            seen.add(username)
        return self
