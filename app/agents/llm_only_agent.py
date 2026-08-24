"""Agente do EXPERIMENTO A (LLM isolado).

Fluxo: questão → estratégia de prompt → LLM → resposta. O modelo NÃO utiliza
ferramentas. Objetivo: medir o efeito da estratégia de prompting sobre a geração
da resposta (sem acesso a dados externos).
"""

from __future__ import annotations

import time

from app.config.logging import get_logger
from app.models.agent import AgentResult
from app.models.llm import LLMConfig, TokenUsage
from app.prompts import PromptStrategy, get_prompt_strategy
from app.services.llm import LLMProvider, create_llm_provider

logger = get_logger(__name__)


class LLMOnlyAgent:
    """Executa a estratégia diretamente no LLM, sem ferramentas."""

    def __init__(self, model: LLMProvider | LLMConfig, prompt_strategy: PromptStrategy | str):
        self.provider: LLMProvider = (
            model if isinstance(model, LLMProvider) else create_llm_provider(model)
        )
        self.strategy: PromptStrategy = (
            prompt_strategy if isinstance(prompt_strategy, PromptStrategy)
            else get_prompt_strategy(prompt_strategy)
        )

    def run(self, question: str) -> AgentResult:
        messages = self.strategy.build_messages(question)
        start = time.perf_counter()
        error: str | None = None
        answer = ""
        usage = TokenUsage.zero()

        try:
            response = self.provider.generate(messages)
            answer = response.content
            usage = response.usage
        except Exception as exc:  # não vaza stack trace
            logger.exception("Falha no LLM (experimento A).")
            error = f"{type(exc).__name__}: {exc}"

        latency_ms = int((time.perf_counter() - start) * 1000)
        return AgentResult(
            answer=answer,
            provider=self.provider.provider_name,
            model=self.provider.config.model,
            strategy=self.strategy.name,
            prompt_version=self.strategy.prompt_version,
            tools_used=[],       # experimento A não usa ferramentas
            tool_calls=[],
            usage=usage,
            latency_ms=latency_ms,
            error=error,
        )
