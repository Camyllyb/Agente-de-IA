"""Verificação de runtime da interface (AppTest) com API mockada.

Cobre: carregamento das páginas sem exceção, health, envio de mensagem, erro da
API, ausência de modelos, seleção de estratégia (modo pesquisador), páginas
Mercado/Comparar/Laboratório e bloqueio do experimento final quando readiness
falha. Sem internet, sem API key, sem mercado aberto.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
for _p in (str(ROOT), str(FRONTEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services import api_client  # noqa: E402

PAGES = FRONTEND / "pages"

_CHAT_RESPONSE = {
    "answer": "Resposta final: 5.0%.\nJustificativa: variação de 36,0 para 37,8.\n"
              "Dados utilizados: PETR4.SA, snapshot.",
    "strategy": "chain_of_thought", "prompt_version": "chain_of_thought_v1",
    "provider": "fake", "model": "fake-model", "data_source": "snapshot",
    "tools_used": ["calculate_return"],
    "data_used": [{"ativo": "PETR4.SA", "valor": "5.0%", "data": "2024-01-02 → 2024-06-03",
                   "moeda": "BRL", "fonte": "snapshot:default"}],
    "metrics": {"latency_ms": 10, "input_tokens": 5, "output_tokens": 5, "total_tokens": 10},
}


@pytest.fixture()
def mock_api(monkeypatch):
    """Mocka o cliente da API (sem rede)."""
    def _ok(*_a, **_k):
        return api_client.ApiResult(True, {"status": "ok"})

    monkeypatch.setattr(api_client, "health", lambda: api_client.ApiResult(True, {"status": "ok"}))
    monkeypatch.setattr(api_client, "get_models", lambda: api_client.ApiResult(
        True, {"default_provider": "fake", "default_model": "fake-model",
               "models": [{"provider": "fake", "model": "fake-model", "requires_key": False, "available": True}]}))
    monkeypatch.setattr(api_client, "get_strategies", lambda: api_client.ApiResult(
        True, {"strategies": [{"name": "zero_shot", "prompt_version": "zero_shot_v1", "description": ""}]}))
    monkeypatch.setattr(api_client, "post_chat", lambda payload: api_client.ApiResult(True, _CHAT_RESPONSE))
    return monkeypatch


def _run(page: str, timeout: int = 60) -> AppTest:
    at = AppTest.from_file(str(PAGES / page), default_timeout=timeout)
    at.run()
    return at


# --- Assistente --------------------------------------------------------------

def test_assistente_loads(mock_api) -> None:
    at = _run("1_Assistente.py")
    assert not at.exception


def test_assistente_backend_down(monkeypatch) -> None:
    monkeypatch.setattr(api_client, "health", lambda: api_client.ApiResult(False, error="down"))
    monkeypatch.setattr(api_client, "get_models", lambda: api_client.ApiResult(False, error="down"))
    at = _run("1_Assistente.py")
    assert not at.exception  # degrada com elegância


def test_assistente_send_message(mock_api) -> None:
    at = _run("1_Assistente.py")
    at.chat_input[0].set_value("Qual a cotação da PETR4.SA?").run()
    assert not at.exception
    assert len(at.session_state["history"]) >= 1


def test_assistente_api_error(monkeypatch, mock_api) -> None:
    monkeypatch.setattr(api_client, "post_chat",
                        lambda payload: api_client.ApiResult(False, error="Estratégia inexistente."))
    at = _run("1_Assistente.py")
    at.chat_input[0].set_value("pergunta").run()
    assert not at.exception
    assert any("não foi possível" in e.value.lower() for e in at.error)


def test_assistente_no_models(monkeypatch) -> None:
    monkeypatch.setattr(api_client, "health", lambda: api_client.ApiResult(True, {"status": "ok"}))
    monkeypatch.setattr(api_client, "get_models", lambda: api_client.ApiResult(True, {"models": []}))
    at = _run("1_Assistente.py")
    assert not at.exception  # fallback para o provedor fake


def test_assistente_researcher_mode_shows_strategy(mock_api) -> None:
    at = _run("1_Assistente.py")
    # ativa o modo pesquisador -> aparece a escolha de estratégia (radio)
    at.toggle[0].set_value(True).run()
    assert not at.exception
    assert len(at.radio) >= 2  # fonte de dados + estratégia


# --- Mercado / Comparar / Histórico / Sobre ---------------------------------

def test_mercado_loads() -> None:
    at = _run("2_Mercado.py")
    assert not at.exception


def test_comparar_loads() -> None:
    at = _run("3_Comparar_Ativos.py")
    assert not at.exception


def test_historico_loads() -> None:
    at = _run("4_Historico.py")
    assert not at.exception


def test_sobre_loads() -> None:
    at = _run("6_Sobre.py")
    assert not at.exception


# --- Laboratório -------------------------------------------------------------

def test_laboratorio_loads_and_blocks_final_experiment() -> None:
    at = _run("5_Laboratorio.py", timeout=90)
    assert not at.exception
    # readiness não está pronto -> experimento final bloqueado
    assert any("bloqueado" in w.value.lower() for w in at.warning)
