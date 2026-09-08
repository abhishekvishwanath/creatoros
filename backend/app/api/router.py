from fastapi import APIRouter

from app.api.routes import audience, content, creators, health, opportunities, research, strategy

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(creators.router)
api_router.include_router(content.router)
api_router.include_router(research.router)
api_router.include_router(opportunities.router)
api_router.include_router(strategy.router)
api_router.include_router(audience.signals_router)
api_router.include_router(audience.analyze_router)
