from uuid import UUID

from pydantic import BaseModel, ConfigDict

from hexrift.components.schema.models.fields import Identifier, IdentifierList, NonBlankList
from hexrift.constants import AccessType


class PortalRoutes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domains: NonBlankList | None = None
    ips: NonBlankList | None = None


class Portal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Identifier
    routes: PortalRoutes


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Identifier
    group: Identifier
    access: list[AccessType]
    uuid: UUID | None = None
    portals: list[Portal] = []
    guests: IdentifierList = []
