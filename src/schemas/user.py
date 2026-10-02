from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID

class UserCreate(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    currency: str = "RUB"

class UserRead(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    currency: str = "RUB"
    family_group_id: Optional[UUID] = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)

