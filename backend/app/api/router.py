from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.alerts import router as alerts_router
from app.api.incidents import router as incidents_router
from app.api.investigations import router as investigations_router
from app.api.responses import router as responses_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(alerts_router)
api_router.include_router(incidents_router)
api_router.include_router(investigations_router)
api_router.include_router(responses_router)
