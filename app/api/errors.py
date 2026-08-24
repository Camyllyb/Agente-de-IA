"""Tradução de exceções de domínio em respostas HTTP limpas.

Nenhum stack trace é enviado ao cliente. Erros inesperados viram uma resposta
500 genérica (com log no servidor).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.logging import get_logger
from app.prompts import UnknownStrategyError
from app.services.agent_service import AgentRuntimeError
from app.services.llm.errors import (
    LLMConfigurationError,
    ProviderNotInstalledError,
    UnsupportedProviderError,
)

logger = get_logger(__name__)


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra os handlers de exceção da aplicação."""

    @app.exception_handler(UnknownStrategyError)
    async def _unknown_strategy(_: Request, exc: UnknownStrategyError) -> JSONResponse:
        return _error(400, "unknown_strategy", str(exc))

    @app.exception_handler(UnsupportedProviderError)
    async def _unsupported_provider(_: Request, exc: UnsupportedProviderError) -> JSONResponse:
        return _error(400, "unsupported_provider", str(exc))

    @app.exception_handler(LLMConfigurationError)
    async def _missing_credentials(_: Request, exc: LLMConfigurationError) -> JSONResponse:
        # Não expõe detalhes sensíveis; orienta a configuração.
        return _error(
            400,
            "missing_credentials",
            "Credencial do provedor ausente ou inválida. Configure a variável de "
            "ambiente correspondente (ver .env.example).",
        )

    @app.exception_handler(ProviderNotInstalledError)
    async def _provider_not_installed(_: Request, exc: ProviderNotInstalledError) -> JSONResponse:
        return _error(501, "provider_not_installed", str(exc))

    @app.exception_handler(AgentRuntimeError)
    async def _agent_runtime(_: Request, exc: AgentRuntimeError) -> JSONResponse:
        status = 504 if exc.is_timeout else 502
        code = "model_timeout" if exc.is_timeout else "model_unavailable"
        return _error(status, code, exc.safe_message)

    @app.exception_handler(ValueError)
    async def _value_error(_: Request, exc: ValueError) -> JSONResponse:
        # Ex.: fonte de dados desconhecida.
        return _error(400, "invalid_request", str(exc))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Erro inesperado na API.")
        return _error(500, "internal_error", "Erro interno inesperado.")
