"""API route definitions."""
from fastapi import APIRouter

from app.api.endpoints.agent import router as agent_router
from app.core.config import get_settings

router = APIRouter()


@router.get("/health", tags=["system"], summary="Service health check")
async def health_check() -> dict[str, str]:
    """Return a basic health payload for uptime monitoring."""

    settings = get_settings()
    return {"status": "ok", "service": settings.app_name}


router.include_router(agent_router)
