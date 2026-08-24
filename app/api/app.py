"""Fábrica da aplicação FastAPI.

Nesta etapa inicial expõe apenas ``/health``. Rotas do agente e dos experimentos
são adicionadas em etapas posteriores (ver ``app/api/routes``).
"""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.config.logging import get_logger, setup_logging
from app.config.settings import get_settings

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Cria e configura a instância do FastAPI."""
    setup_logging()
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "API do laboratório experimental de Engenharia de Prompt aplicada a "
            "agentes financeiros."
        ),
    )

    # Tradução de exceções de domínio em respostas HTTP limpas (sem stack trace).
    from app.api.errors import register_exception_handlers

    register_exception_handlers(app)

    # Rotas.
    from app.api.routes import chat, health

    app.include_router(health.router)
    app.include_router(chat.router)

    logger.info("Aplicação '%s' v%s inicializada.", settings.app_name, __version__)
    return app


# Instância padrão usada pelo servidor ASGI (uvicorn app.api.app:app).
app = create_app()
