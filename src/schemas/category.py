from pydantic import BaseModel, ConfigDict
from typing import Optional

class CategoryRead(BaseModel):
    id: int
    name: str
    type: str
    icon: Optional[str]
    is_system: bool
    
    model_config = ConfigDict(from_attributes=True)
