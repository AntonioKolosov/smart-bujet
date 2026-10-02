from pydantic import BaseModel, ConfigDict

class FamilyGroupCreate(BaseModel):
    name: str

class FamilyGroupRead(BaseModel):
    id: int
    name: str
    owner_id: int
    
    model_config = ConfigDict(from_attributes=True)
