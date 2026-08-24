"""Oráculo determinístico para VALIDAÇÃO DE PIPELINE (não é um LLM real).

Constrói um provedor fake que, para cada questão, chama a ferramenta correta
(com base em ``params``/``expected_tools`` do dataset) e ecoa a resposta obtida
da fonte de dados. É útil para exercitar o pipeline de ponta a ponta (agente →
ferramenta → dados → resposta → métricas) sem rede.

⚠️  Os resultados obtidos com o oráculo **não representam o desempenho de um
modelo de linguagem**. Servem apenas para verificar o funcionamento do pipeline.
"""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from app.services.llm.fake import FakeLLMProvider, make_fake_config
from experiments.runner.model_spec import ModelSpec


def _tool_call(name: str, args: dict, call_id: str = "call_oracle") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def _format_answer(data: dict) -> str:
    if data.get("found") is False:
        symbol = data.get("symbol", "o ativo")
        return f"Resposta final: dados não disponíveis para {symbol}."

    if data.get("return_pct") is not None:
        return (
            f"Resposta final: {data['return_pct']}%.\n"
            f"Justificativa: variação de {data.get('start_price')} para "
            f"{data.get('end_price')} ({data.get('currency','')}).\n"
            f"Dados utilizados: {data.get('symbol')} — fonte {data.get('source')}."
        )
    if "price" in data:
        return (
            f"Resposta final: {data['price']} {data.get('currency','')}.\n"
            f"Justificativa: cotação obtida diretamente da fonte.\n"
            f"Dados utilizados: {data.get('symbol')} em {data.get('date')} — "
            f"fonte {data.get('source')}."
        )
    if "quotes" in data:  # compare_stocks
        quotes = data.get("quotes", [])
        if not quotes:
            return "Resposta final: nenhum ativo encontrado."
        top = max(quotes, key=lambda q: q["price"])
        return (
            f"Resposta final: {top['symbol']} (maior cotação: {top['price']} "
            f"{top.get('currency','')}).\n"
            f"Dados utilizados: {', '.join(q['symbol'] for q in quotes)} — "
            f"fonte {data.get('source')}."
        )
    if "bars" in data:  # get_stock_history -> tendência
        bars = data.get("bars", [])
        if not bars:
            return "Resposta final: sem dados no período."
        first, last = bars[0]["close"], bars[-1]["close"]
        if last > first:
            direction = "subiu (tendência de alta)"
        elif last < first:
            direction = "caiu (tendência de baixa)"
        else:
            direction = "manteve-se estável"
        return (
            f"Resposta final: o preço {direction}, de {first} para {last} "
            f"({data.get('currency','')}).\n"
            f"Dados utilizados: {data.get('symbol')} — fonte {data.get('source')}."
        )
    return "Resposta final: " + json.dumps(data, ensure_ascii=False)[:180]


def _echo(messages: list[BaseMessage]) -> AIMessage:
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    if not tool_messages:
        return AIMessage(content="Resposta final: dados não disponíveis.")
    try:
        data = json.loads(tool_messages[-1].content)
    except (json.JSONDecodeError, TypeError):
        return AIMessage(content="Resposta final: não foi possível interpretar os dados.")
    return AIMessage(content=_format_answer(data))


def build_oracle_provider(question: dict) -> FakeLLMProvider:
    """Constrói o provedor oráculo roteirizado para uma questão."""
    params = question.get("params", {})
    tools = question.get("expected_tools") or []
    tool = tools[0] if tools else None

    if tool == "calculate_return":
        responses = [
            _tool_call("calculate_return", {
                "symbol": params.get("symbol"),
                "start_date": params.get("start_date"),
                "end_date": params.get("end_date"),
            }),
            _echo,
        ]
    elif tool == "get_stock_quote":
        responses = [_tool_call("get_stock_quote", {"symbol": params.get("symbol")}), _echo]
    elif tool == "compare_stocks":
        responses = [_tool_call("compare_stocks", {"symbols": params.get("symbols", [])}), _echo]
    elif tool == "get_stock_history":
        responses = [
            _tool_call("get_stock_history", {
                "symbol": params.get("symbol"),
                "start_date": params.get("start_date"),
                "end_date": params.get("end_date"),
            }),
            _echo,
        ]
    else:
        responses = [AIMessage(content="Resposta final: (resposta qualitativa de exemplo do pipeline).")]

    return FakeLLMProvider(make_fake_config(model="oracle-fake", responses=responses))


def oracle_model_spec() -> ModelSpec:
    """ModelSpec do oráculo (para o runner)."""
    return ModelSpec(provider="fake", model="oracle-fake", build=build_oracle_provider)
