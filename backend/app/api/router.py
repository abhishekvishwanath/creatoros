from fastapi import APIRouter

from app.api.routes import content, creators, health, opportunities, research

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(creators.router)
api_router.include_router(content.router)
api_router.include_router(research.router)
api_router.include_router(opportunities.router)
