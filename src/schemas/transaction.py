from pydantic import BaseModel, ConfigDict
from typing import Optional
from decimal import Decimal
from datetime import datetime

class TransactionCreate(BaseModel):
    amount: Decimal
    category_id: int
    description: Optional[str] = None
    type: str = "expense"

class TransactionRead(BaseModel):
    id: int
    user_id: int
    amount: Decimal
    category_id: int
    description: Optional[str]
    type: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
