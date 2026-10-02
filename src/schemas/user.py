from pydantic import BaseModel, ConfigDict
from typing import Optional

class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    currency: str = "KZT"

class UserRead(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str]
    currency: str
    
    model_config = ConfigDict(from_attributes=True)
