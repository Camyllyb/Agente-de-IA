"""Serviço de orquestração do agente para a API.

Constrói um :class:`~app.agents.FinancialAgent` a partir de uma
:class:`~app.models.chat.ChatRequest`, executa-o e converte o resultado em
:class:`~app.models.chat.ChatResponse`.

As exceções de domínio (provedor não suportado, estratégia inexistente,
credencial ausente etc.) são propagadas para a camada de API, que as traduz em
respostas HTTP limpas — este serviço não constrói respostas HTTP.
"""

from __future__ import annotations

import json

from app.agents import FinancialAgent
from app.config.logging import get_logger
from app.config.settings import get_settings
from app.models.chat import ChatRequest, ChatResponse, Metrics
from app.models.llm import LLMConfig
from app.prompts import get_prompt_strategy
from app.services.llm import create_llm_provider
from app.tools.market_data import get_market_data_provider

logger = get_logger(__name__)


class AgentRuntimeError(Exception):
    """Falha em tempo de execução do agente (ex.: modelo indisponível, timeout)."""

    def __init__(self, raw_message: str):
        self.raw_message = raw_message
        lowered = raw_message.lower()
        self.is_timeout = "timeout" in lowered or "timed out" in lowered
        if self.is_timeout:
            self.safe_message = "Tempo limite excedido ao consultar o modelo."
        else:
            self.safe_message = "Falha ao consultar o modelo de linguagem."
        super().__init__(self.safe_message)


def build_agent(request: ChatRequest) -> tuple[FinancialAgent, str]:
    """Constrói o agente conforme a requisição. Retorna (agente, data_source).

    Pode levantar UnknownStrategyError, UnsupportedProviderError,
    LLMConfigurationError, ProviderNotInstalledError ou ValueError.
    """
    settings = get_settings()

    strategy = get_prompt_strategy(request.strategy)

    config = LLMConfig(
        provider=request.provider or settings.default_provider,
        model=request.model or settings.default_model,
        temperature=(
            request.temperature
            if request.temperature is not None
            else settings.default_temperature
        ),
        max_tokens=request.max_tokens or settings.default_max_tokens,
        timeout=settings.default_timeout,
    )
    llm_provider = create_llm_provider(config)

    data_source = (request.data_source or settings.market_data_source).lower()
    market = get_market_data_provider(data_source, snapshot_set=request.snapshot_set)

    agent = FinancialAgent(
        model=llm_provider,
        prompt_strategy=strategy,
        market_data_provider=market,
    )
    return agent, data_source


def run_chat(request: ChatRequest) -> ChatResponse:
    """Executa o agente e retorna a resposta estruturada.

    Raises:
        AgentRuntimeError: se a execução do agente falhar.
        (demais exceções de domínio são propagadas por build_agent)
    """
    agent, data_source = build_agent(request)
    result = agent.run(request.message)

    if result.error:
        logger.warning("Agente retornou erro: %s", result.error)
        raise AgentRuntimeError(result.error)

    return ChatResponse(
        answer=result.answer,
        strategy=result.strategy,
        prompt_version=result.prompt_version,
        provider=result.provider,
        model=result.model,
        data_source=data_source,
        tools_used=result.tools_used,
        data_used=_extract_data_used(result.tool_calls),
        metrics=Metrics(
            latency_ms=result.latency_ms,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=result.usage.total_tokens,
            estimated_cost=_estimate_cost(result.model, result.usage.input_tokens, result.usage.output_tokens),
        ),
    )


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Custo estimado via tabela de preços configurável (None se não configurado)."""
    from app.metrics import load_price_table

    return load_price_table().estimate(model, input_tokens, output_tokens)


def _extract_data_used(tool_calls) -> list[dict]:
    """Converte as saídas das ferramentas em linhas (ativo, valor, data, moeda, fonte).

    Nunca inventa: quando um dado não foi encontrado, marca como indisponível.
    """
    rows: list[dict] = []
    for call in tool_calls or []:
        output = call.output
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except (json.JSONDecodeError, TypeError):
                continue
        if not isinstance(output, dict):
            continue

        # compare_stocks: uma linha por cotação
        if "quotes" in output:
            for quote in output.get("quotes", []):
                rows.append({
                    "ativo": quote.get("symbol"), "valor": quote.get("price"),
                    "data": quote.get("date"), "moeda": quote.get("currency"),
                    "fonte": quote.get("source"),
                })
            continue

        if output.get("found") is False:
            rows.append({"ativo": output.get("symbol"), "valor": "Indisponível",
                         "data": None, "moeda": None, "fonte": output.get("source")})
            continue

        if output.get("return_pct") is not None:  # calculate_return
            rows.append({
                "ativo": output.get("symbol"),
                "valor": f"{output.get('return_pct')}%",
                "data": f"{output.get('start_observed_date')} → {output.get('end_observed_date')}",
                "moeda": output.get("currency"), "fonte": output.get("source"),
            })
        elif "price" in output:  # get_stock_quote
            rows.append({"ativo": output.get("symbol"), "valor": output.get("price"),
                         "data": output.get("date"), "moeda": output.get("currency"),
                         "fonte": output.get("source")})
        elif "bars" in output and output.get("bars"):  # get_stock_history
            bars = output["bars"]
            rows.append({
                "ativo": output.get("symbol"),
                "valor": f"{bars[0]['close']} → {bars[-1]['close']}",
                "data": f"{output.get('start_date')} → {output.get('end_date')}",
                "moeda": output.get("currency"), "fonte": output.get("source"),
            })
    return rows
