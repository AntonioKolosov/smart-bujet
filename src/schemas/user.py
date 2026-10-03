from pydantic import BaseModel, ConfigDict
from uuid import UUID

class UserCreate(BaseModel):
    id: int
    username: str | None = None
    first_name: str | None = None
    currency: str = "RUB"

class UserRead(BaseModel):
    id: int
    username: str | None = None
    first_name: str | None = None
    currency: str = "RUB"
    family_group_id: UUID | None = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)

