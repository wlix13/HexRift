from pydantic import BaseModel


class HubRoute(BaseModel):
    destination: str
    domains: list[str] | None = None
    ips: list[str] | None = None


class RoutingConfig(BaseModel):
    exit_warp_global: list[str]
    hub_routes: list[HubRoute]
    hub_default: str
