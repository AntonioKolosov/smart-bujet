from fastapi import APIRouter
from src.api.v1 import webhook, auth, transactions, categories, family, analytics, assets

api_router = APIRouter()
api_router.include_router(webhook.router, tags=["webhook"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(family.router, prefix="/family", tags=["family"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
