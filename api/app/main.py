"""FastAPI application factory."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    """Create and configure a FastAPI application."""

    settings = get_settings()
    setup_logging(settings)
    application = FastAPI(title=settings.app_name, debug=settings.debug)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    application.include_router(router, prefix=settings.api_prefix)
    return application


app = create_app()
