from pydantic import BaseModel, ConfigDict

from hexrift.components.schema.models.fields import Identifier, ShortId


class Group(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Identifier
    short_id: ShortId | None = None
