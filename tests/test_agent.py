"""Testes do agente financeiro (offline).

Usam o modelo falso (FakeLLM) roteirizado e a fonte de dados por snapshot, sem
internet nem API key. Exercitam o laço real do agente LangChain:
pergunta → ferramenta → dados → resposta.
"""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

from app.agents import FinancialAgent
from app.services.llm.fake import FakeLLMProvider, make_fake_config
from app.tools.market_data import SnapshotMarketDataProvider


def _tool_call(name: str, args: dict, call_id: str = "call_1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


@pytest.fixture()
def market() -> SnapshotMarketDataProvider:
    return SnapshotMarketDataProvider(snapshot_set="default")


def _agent_with_script(script, market, strategy="chain_of_thought") -> FinancialAgent:
    provider = FakeLLMProvider(make_fake_config(responses=script))
    return FinancialAgent(
        model=provider,
        prompt_strategy=strategy,
        market_data_provider=market,
    )


def test_agent_uses_tool_then_answers(market: SnapshotMarketDataProvider) -> None:
    script = [
        _tool_call(
            "calculate_return",
            {"symbol": "PETR4.SA", "start_date": "2024-01-02", "end_date": "2024-06-03"},
        ),
        AIMessage(content="Resposta final: +5,0%.\nJustificativa: 36,00 -> 37,80.\nDados utilizados: PETR4.SA snapshot."),
    ]
    agent = _agent_with_script(script, market)
    result = agent.run("Qual foi a variação da PETR4.SA entre 2024-01-02 e 2024-06-03?")

    assert result.error is None
    assert "calculate_return" in result.tools_used
    assert "Resposta final" in result.answer
    # O dado veio da ferramenta (não foi inventado pelo modelo).
    tool_output = json.loads(result.tool_calls[0].output)
    assert tool_output["found"] is True
    assert tool_output["return_pct"] == pytest.approx(5.0, abs=1e-6)
    # Metadados experimentais.
    assert result.provider == "fake"
    assert result.strategy == "chain_of_thought"
    assert result.prompt_version == "chain_of_thought_v1"
    assert result.usage.total_tokens > 0
    assert result.latency_ms >= 0


def test_agent_answers_without_tools(market: SnapshotMarketDataProvider) -> None:
    script = [AIMessage(content="Resposta final: sem necessidade de dados de mercado.")]
    agent = _agent_with_script(script, market, strategy="zero_shot")
    result = agent.run("Explique o conceito de retorno percentual.")

    assert result.error is None
    assert result.tools_used == []
    assert "Resposta final" in result.answer


def test_agent_reports_missing_data(market: SnapshotMarketDataProvider) -> None:
    """Ativo inexistente: a ferramenta retorna not-found; o agente não inventa."""
    script = [
        _tool_call("get_stock_quote", {"symbol": "INVALIDO.SA"}),
        AIMessage(content="Resposta final: dados não disponíveis para INVALIDO.SA."),
    ]
    agent = _agent_with_script(script, market, strategy="few_shot")
    result = agent.run("Qual a cotação da INVALIDO.SA?")

    tool_output = json.loads(result.tool_calls[0].output)
    assert tool_output["found"] is False
    assert "não disponíveis" in result.answer


def test_same_question_different_strategies(market: SnapshotMarketDataProvider) -> None:
    """A arquitetura permite a mesma pergunta com estratégias diferentes."""
    question = "Qual foi a variação da PETR4.SA entre 2024-01-02 e 2024-06-03?"
    for strategy in ("zero_shot", "few_shot", "chain_of_thought"):
        script = [
            _tool_call(
                "calculate_return",
                {"symbol": "PETR4.SA", "start_date": "2024-01-02", "end_date": "2024-06-03"},
            ),
            AIMessage(content="Resposta final: +5,0%."),
        ]
        agent = _agent_with_script(script, market, strategy=strategy)
        result = agent.run(question)
        assert result.strategy == strategy
        assert "calculate_return" in result.tools_used


def test_agent_accepts_llm_config(market: SnapshotMarketDataProvider) -> None:
    """model_config pode ser passado como LLMConfig (não só como provider)."""
    config = make_fake_config(responses=[AIMessage(content="Resposta final: ok.")])
    agent = FinancialAgent(
        model=config,
        prompt_strategy="zero_shot",
        market_data_provider=market,
    )
    result = agent.run("Pergunta qualquer.")
    assert result.answer.startswith("Resposta final")
    assert result.model == "fake-model"
