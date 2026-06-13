from pydantic import BaseModel, ConfigDict, model_validator

from hexrift.components.schema.models.fields import NonBlankList


class ExitRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str
    domains: NonBlankList | None = None
    ips: NonBlankList | None = None

    @model_validator(mode="after")
    def validate_matchers(self):
        if not self.domains and not self.ips:
            raise ValueError("ExitRoute requires at least one matcher: domains or ips")
        return self


class HubRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str
    domains: NonBlankList | None = None
    ips: NonBlankList | None = None
    users: list[str] | None = None
    proxy_users: list[str] | None = None

    @model_validator(mode="after")
    def validate_matchers(self):
        if not self.domains and not self.ips and not self.users and not self.proxy_users:
            raise ValueError("HubRoute requires at least one matcher: domains, ips, users, or proxy_users")
        return self


class RoutingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exit_warp_global: list[str] = []
    exit_routes_global: list[ExitRoute] = []
    hub_routes: list[HubRoute] = []
    hub_default: str
