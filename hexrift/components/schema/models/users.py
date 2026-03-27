from uuid import UUID

from pydantic import BaseModel

from hexrift.constants import AccessType


class PortalRoutes(BaseModel):
    domains: list[str] | None = None
    ips: list[str] | None = None


class Portal(BaseModel):
    label: str
    routes: PortalRoutes


class User(BaseModel):
    username: str
    group: str
    access: list[AccessType]
    uuid: UUID | None = None
    portals: list[Portal] = []
    guests: list[str] = []
