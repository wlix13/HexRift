from uuid import UUID

from pydantic import BaseModel, ConfigDict

from hexrift.constants import AccessType


class PortalRoutes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domains: list[str] | None = None
    ips: list[str] | None = None


class Portal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    routes: PortalRoutes


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    group: str
    access: list[AccessType]
    uuid: UUID | None = None
    portals: list[Portal] = []
    guests: list[str] = []
