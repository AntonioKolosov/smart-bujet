from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ValidateInitDataRequest(BaseModel):
    initData: str

@router.post("/validate")
async def validate_auth(data: ValidateInitDataRequest):
    # TODO: implement initData validation and return user info
    return {"status": "ok"}
