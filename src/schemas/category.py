from pydantic import BaseModel, ConfigDict
from typing import Optional

class CategoryCreate(BaseModel):
    name: str
    type: str = "expense"

class CategoryRead(BaseModel):
    id: int
    user_id: Optional[int] = None
    name: str
    type: str
    is_system: bool

    model_config = ConfigDict(from_attributes=True)

