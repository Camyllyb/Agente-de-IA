"""Cliente HTTP para o backend FastAPI do agente.

Encapsula as chamadas à API e trata erros de conexão de forma amigável, sem
vazar detalhes técnicos ao usuário.
"""

from __future__ import annotations

from typing import Any

import httpx

from .bootstrap import api_base_url

_TIMEOUT = httpx.Timeout(120.0, connect=5.0)


class ApiResult:
    """Resultado padronizado de uma chamada à API."""

    def __init__(self, ok: bool, data: dict[str, Any] | None = None, error: str | None = None):
        self.ok = ok
        self.data = data or {}
        self.error = error


def _get(path: str) -> ApiResult:
    try:
        response = httpx.get(f"{api_base_url()}{path}", timeout=_TIMEOUT)
    except httpx.ConnectError:
        return ApiResult(False, error="Backend indisponível. Inicie a API (python main.py).")
    except httpx.HTTPError as exc:
        return ApiResult(False, error=f"Erro de conexão: {type(exc).__name__}")
    if response.status_code != 200:
        return ApiResult(False, error=_extract_error(response))
    return ApiResult(True, data=response.json())


def _extract_error(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict) and "error" in body:
            return body["error"].get("message", "Erro desconhecido.")
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
    except Exception:
        pass
    return f"Erro HTTP {response.status_code}."


def health() -> ApiResult:
    return _get("/health")


def get_strategies() -> ApiResult:
    return _get("/api/strategies")


def get_models() -> ApiResult:
    return _get("/api/models")


def post_chat(payload: dict[str, Any]) -> ApiResult:
    """Envia uma mensagem ao agente via ``POST /api/chat``."""
    try:
        response = httpx.post(
            f"{api_base_url()}/api/chat", json=payload, timeout=_TIMEOUT
        )
    except httpx.ConnectError:
        return ApiResult(False, error="Backend indisponível. Inicie a API (python main.py).")
    except httpx.HTTPError as exc:
        return ApiResult(False, error=f"Erro de conexão: {type(exc).__name__}")
    if response.status_code != 200:
        return ApiResult(False, error=_extract_error(response))
    return ApiResult(True, data=response.json())
