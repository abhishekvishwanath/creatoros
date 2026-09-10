from fastapi import APIRouter

from app.api.routes import (
    audience,
    brands,
    calendar,
    commercial,
    content,
    creators,
    health,
    learnings,
    opportunities,
    outreach,
    performance,
    research,
    strategy,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(creators.router)
api_router.include_router(content.router)
api_router.include_router(research.router)
api_router.include_router(opportunities.router)
api_router.include_router(strategy.router)
api_router.include_router(audience.signals_router)
api_router.include_router(audience.analyze_router)
api_router.include_router(calendar.router)
api_router.include_router(calendar.capacity_router)
api_router.include_router(performance.router)
api_router.include_router(performance.overview_router)
api_router.include_router(learnings.router)
api_router.include_router(commercial.router)
api_router.include_router(brands.router)
api_router.include_router(brands.radar_router)
api_router.include_router(outreach.router)
