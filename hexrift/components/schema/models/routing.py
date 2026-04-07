from pydantic import BaseModel, ConfigDict


class HubRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str
    domains: list[str] | None = None
    ips: list[str] | None = None
    users: list[str] | None = None
    proxy_users: list[str] | None = None


class RoutingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exit_warp_global: list[str]
    hub_routes: list[HubRoute]
    hub_default: str
