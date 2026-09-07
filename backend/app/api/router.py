from fastapi import APIRouter

from app.api.routes import creators, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(creators.router)
