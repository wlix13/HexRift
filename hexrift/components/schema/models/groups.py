from pydantic import BaseModel


class Group(BaseModel):
    id: str
    short_id: str | None = None
