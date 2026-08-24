"""Cliente HTTP do backend FastAPI (chat, health, models, strategies).

Trata erros de conexão de forma amigável, sem vazar detalhes técnicos.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_TIMEOUT = httpx.Timeout(120.0, connect=5.0)


def api_base_url() -> str:
    return os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")


class ApiResult:
    def __init__(self, ok: bool, data: dict[str, Any] | None = None, error: str | None = None):
        self.ok = ok
        self.data = data or {}
        self.error = error


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


def _request(method: str, path: str, json_body: dict | None = None) -> ApiResult:
    url = f"{api_base_url()}{path}"
    try:
        response = httpx.request(method, url, json=json_body, timeout=_TIMEOUT)
    except httpx.ConnectError:
        return ApiResult(False, error="Serviço indisponível. Inicie o backend (python main.py).")
    except httpx.HTTPError as exc:
        return ApiResult(False, error=f"Falha de conexão: {type(exc).__name__}")
    if response.status_code != 200:
        return ApiResult(False, error=_extract_error(response))
    try:
        return ApiResult(True, data=response.json())
    except Exception:
        return ApiResult(False, error="Resposta inválida do servidor.")


def health() -> ApiResult:
    return _request("GET", "/health")


def get_strategies() -> ApiResult:
    return _request("GET", "/api/strategies")


def get_models() -> ApiResult:
    return _request("GET", "/api/models")


def post_chat(payload: dict[str, Any]) -> ApiResult:
    return _request("POST", "/api/chat", json_body=payload)
