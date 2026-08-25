"""Testes dos endpoints da API (offline, provedor fake).

Cobrem /health, /api/models, /api/strategies, /api/chat e o tratamento de erros
(estratégia inexistente, provedor não suportado, fonte inválida) sem vazar stack
traces.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app

client = TestClient(create_app())


# --- Endpoints informativos --------------------------------------------------

def test_health() -> None:
    assert client.get("/health").status_code == 200


def test_list_strategies() -> None:
    response = client.get("/api/strategies")
    assert response.status_code == 200
    names = {s["name"] for s in response.json()["strategies"]}
    assert names == {"zero_shot", "few_shot", "chain_of_thought"}
    for strategy in response.json()["strategies"]:
        assert strategy["prompt_version"]


def test_list_models_includes_fake_and_hides_keys() -> None:
    response = client.get("/api/models")
    assert response.status_code == 200
    body = response.json()
    providers = {m["provider"] for m in body["models"]}
    assert "fake" in providers
    # Nenhuma chave de API é exposta.
    assert "api_key" not in response.text.lower()
    fake = next(m for m in body["models"] if m["provider"] == "fake")
    assert fake["available"] is True
    assert fake["requires_key"] is False


# --- Chat com provedor fake --------------------------------------------------

def test_chat_with_fake_provider() -> None:
    response = client.post(
        "/api/chat",
        # Provider explícito -> teste isolado do provedor padrão do .env (offline).
        json={"message": "Olá, o que você faz?", "strategy": "zero_shot",
              "provider": "fake", "model": "fake-model"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["strategy"] == "zero_shot"
    assert body["prompt_version"] == "zero_shot_v1"
    assert body["provider"] == "fake"
    assert body["tools_used"] == []
    metrics = body["metrics"]
    for field in ("latency_ms", "input_tokens", "output_tokens", "total_tokens"):
        assert field in metrics
    assert metrics["total_tokens"] > 0


# --- Tratamento de erros -----------------------------------------------------

def test_chat_unknown_strategy() -> None:
    response = client.post(
        "/api/chat", json={"message": "oi", "strategy": "inexistente"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unknown_strategy"


def test_chat_unsupported_provider() -> None:
    response = client.post(
        "/api/chat",
        json={"message": "oi", "strategy": "zero_shot", "provider": "banana"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_provider"


def test_chat_invalid_data_source() -> None:
    response = client.post(
        "/api/chat",
        json={"message": "oi", "strategy": "zero_shot", "data_source": "marte"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_chat_real_provider_without_key_or_lib() -> None:
    """openai sem lib/chave: erro estruturado (501 ou 400), nunca stack trace."""
    response = client.post(
        "/api/chat",
        json={
            "message": "oi",
            "strategy": "zero_shot",
            "provider": "openai",
            "model": "algum-modelo",
        },
    )
    assert response.status_code in (400, 501)
    assert response.json()["error"]["code"] in (
        "provider_not_installed",
        "missing_credentials",
    )
    assert "traceback" not in response.text.lower()


def test_chat_validation_error_returns_422() -> None:
    """Falta o campo obrigatório 'message' -> validação do FastAPI (422)."""
    response = client.post("/api/chat", json={"strategy": "zero_shot"})
    assert response.status_code == 422


def test_extract_data_used_from_tool_outputs() -> None:
    """A resposta do chat converte saídas de ferramentas em linhas estruturadas."""
    import json

    from app.models.agent import ToolCallRecord
    from app.services.agent_service import _extract_data_used

    calls = [
        ToolCallRecord(name="get_stock_quote", args={},
                       output=json.dumps({"found": True, "symbol": "PETR4.SA", "price": 41.0,
                                          "currency": "BRL", "date": "2024-07-01", "source": "snapshot:default"})),
        ToolCallRecord(name="calculate_return", args={},
                       output=json.dumps({"found": True, "symbol": "PETR4.SA", "return_pct": 5.0,
                                          "currency": "BRL", "start_observed_date": "2024-01-02",
                                          "end_observed_date": "2024-06-03", "source": "snapshot:default"})),
        ToolCallRecord(name="get_stock_quote", args={},
                       output=json.dumps({"found": False, "symbol": "XPTO", "source": "snapshot:default"})),
    ]
    rows = _extract_data_used(calls)
    assert rows[0]["ativo"] == "PETR4.SA" and rows[0]["valor"] == 41.0
    assert rows[1]["valor"] == "5.0%"
    assert rows[2]["valor"] == "Indisponível"  # nunca inventa
