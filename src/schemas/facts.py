import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class FactCreateRequest(BaseModel):
    fact_text: str = Field(..., min_length=2, max_length=1000)
    category: str | None = None  # None triggers AI auto-classification


class FactUpdateRequest(BaseModel):
    fact_text: str | None = Field(None, min_length=2, max_length=1000)
    category: str | None = None
    is_active: bool | None = None


class FactResponse(BaseModel):
    id: uuid.UUID
    user_id: int
    category: str
    category_label: str
    category_badge: str
    fact_text: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
