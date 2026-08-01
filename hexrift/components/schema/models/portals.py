from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hexrift.components.schema.models.fields import Identifier, IdentifierList, NonBlankList


class PortalRoutes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domains: NonBlankList | None = None
    ips: NonBlankList | None = None

    @model_validator(mode="after")
    def validate_matchers(self):
        if not self.domains and not self.ips:
            raise ValueError("PortalRoutes requires at least one matcher: domains or ips")
        return self


class Portal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Identifier
    users: IdentifierList = Field(min_length=1)
    routes: PortalRoutes
    uuid: UUID | None = None

    @model_validator(mode="after")
    def validate_unique_users(self):
        seen: set[str] = set()
        for username in self.users:
            if username in seen:
                raise ValueError(f"duplicate user {username!r} in portal {self.id!r}")
            seen.add(username)
        return self
