"""Endpoint de verificação de saúde do serviço."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.config.settings import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Resposta do endpoint ``/health``."""

    status: str
    app: str
    environment: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Verificação de saúde")
def health() -> HealthResponse:
    """Retorna o estado básico do serviço (não realiza chamadas externas)."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
        version=__version__,
    )
