import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.models.user import User
from src.models.asset import AssetAccount, AssetType
from src.services.asset_service import AssetService

router = APIRouter()


class CreateAssetRequest(BaseModel):
    name: str
    type: AssetType = AssetType.deposit
    currency: str = "KZT"
    initial_balance: float = 0.0
    interest_rate: Optional[float] = None


class AssetActionRequest(BaseModel):
    amount: float
    note: Optional[str] = None


@router.get("/")
async def list_assets(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = AssetService(session)
    assets = await service.get_user_assets(current_user.id)
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "type": a.type.value if hasattr(a.type, "value") else str(a.type),
            "currency": a.currency,
            "balance": float(a.balance),
            "interest_rate": float(a.interest_rate) if a.interest_rate else None,
            "is_active": a.is_active,
            "created_at": a.created_at.isoformat() if a.created_at else None
        }
        for a in assets
    ]


@router.get("/summary")
async def get_assets_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = AssetService(session)
    summary = await service.get_portfolio_summary(current_user.id)
    return summary


@router.post("/")
async def create_asset(
    payload: CreateAssetRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Название актива обязательно")

    service = AssetService(session)
    asset = await service.create_asset(
        user_id=current_user.id,
        name=payload.name,
        asset_type=payload.type,
        currency=payload.currency,
        initial_balance=payload.initial_balance,
        interest_rate=payload.interest_rate
    )
    return {
        "status": "ok",
        "asset": {
            "id": str(asset.id),
            "name": asset.name,
            "type": asset.type.value if hasattr(asset.type, "value") else str(asset.type),
            "currency": asset.currency,
            "balance": float(asset.balance),
            "interest_rate": float(asset.interest_rate) if asset.interest_rate else None,
        }
    }


@router.post("/{asset_id}/deposit")
async def deposit_to_asset(
    asset_id: uuid.UUID,
    payload: AssetActionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше нуля")

    service = AssetService(session)
    try:
        asset = await service.deposit_to_asset(
            user_id=current_user.id,
            asset_id=asset_id,
            amount=payload.amount,
            note=payload.note
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "status": "ok",
        "balance": float(asset.balance)
    }


@router.post("/{asset_id}/withdraw")
async def withdraw_from_asset(
    asset_id: uuid.UUID,
    payload: AssetActionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше нуля")

    service = AssetService(session)
    try:
        asset = await service.withdraw_from_asset(
            user_id=current_user.id,
            asset_id=asset_id,
            amount=payload.amount,
            note=payload.note
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "status": "ok",
        "balance": float(asset.balance)
    }
