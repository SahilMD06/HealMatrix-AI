"""Version 1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1 import agents, analytics, auth, clinical, hospitals, sustainability

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(hospitals.router)
api_router.include_router(clinical.router)
api_router.include_router(agents.router)
api_router.include_router(analytics.router)
api_router.include_router(sustainability.router)

__all__ = ["api_router"]
