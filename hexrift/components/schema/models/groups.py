from pydantic import BaseModel, ConfigDict


class Group(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    short_id: str | None = None
