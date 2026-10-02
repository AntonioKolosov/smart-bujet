from pydantic import BaseModel, ConfigDict
from uuid import UUID

class FamilyGroupCreate(BaseModel):
    name: str

class FamilyGroupRead(BaseModel):
    id: UUID
    name: str
    owner_id: int
    invite_code: str

    model_config = ConfigDict(from_attributes=True)

