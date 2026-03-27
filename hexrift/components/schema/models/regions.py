import pydantic
from pydantic import BaseModel

from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import AuthMethod, LbRole, RegionType


class NodeKeysOverride(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    enabled: bool | None = None
    mode: str | None = None
    session_time: str | None = None
    auth: AuthMethod | None = None
    padding: str | None = None


class NodeExitConnectionsOverride(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    method: str | None = None
    fingerprint: str | None = None


class RegionRouting(BaseModel):
    warp_extra: list[str] | None = None


class WarpConfig(BaseModel):
    vless_route: int


class Node(BaseModel):
    id: str
    hostname: str
    ipv6: bool | None = None
    lb_role: LbRole | None = None
    reality: RealityConfig | None = None
    keys: NodeKeysOverride | None = None
    exit_connections: NodeExitConnectionsOverride | None = None
    proxy_inbound: bool | None = None


class Region(BaseModel):
    id: str
    type: RegionType
    vless_route: int | None = None
    cdn_xhttp_path: str | None = None
    lb_strategy: str | None = None
    lb_fallback: str | None = None
    routing: RegionRouting | None = None
    warp: WarpConfig | None = None
    nodes: list[Node]
