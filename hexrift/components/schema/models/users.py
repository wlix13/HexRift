from uuid import UUID

from pydantic import BaseModel, ConfigDict

from hexrift.components.schema.models.fields import Identifier, IdentifierList
from hexrift.constants import AccessType


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Identifier
    group: Identifier
    access: list[AccessType]
    uuid: UUID | None = None
    guests: IdentifierList = []
