"""Agente financeiro construído sobre a API atual do LangChain (``create_agent``).

O agente é totalmente parametrizável pelos três eixos experimentais:

* ``model``            — provedor/modelo de LLM (troca o modelo sem alterar o agente);
* ``prompt_strategy``  — técnica de prompting (zero-shot, few-shot, chain-of-thought);
* ``market_data_provider`` — fonte de dados financeiros (live ou snapshot).

Isso permite executar exatamente a mesma pergunta com estratégias diferentes,
mantendo tudo o mais constante.

Fluxo: pergunta → agente → ferramenta financeira → dados → cálculo/análise →
resposta. O agente nunca cria cotações inexistentes: os valores vêm sempre das
ferramentas, e cada execução registra quais ferramentas foram utilizadas.
"""

from __future__ import annotations

import time

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from app.config.logging import get_logger
from app.models.agent import AgentResult, ToolCallRecord
from app.models.llm import LLMConfig, TokenUsage
from app.prompts import PromptStrategy, get_prompt_strategy
from app.prompts.shared import BASE_AGENT_INSTRUCTIONS
from app.services.llm import LLMProvider, create_llm_provider
from app.services.llm.base import extract_token_usage
from app.tools.financial_tools import build_market_tools
from app.tools.market_data.base import MarketDataProvider

logger = get_logger(__name__)


class FinancialAgent:
    """Agente financeiro parametrizável (modelo × estratégia × fonte de dados)."""

    def __init__(
        self,
        model: LLMProvider | LLMConfig,
        prompt_strategy: PromptStrategy | str,
        market_data_provider: MarketDataProvider,
        base_instructions: str | None = None,
        recursion_limit: int = 25,
    ) -> None:
        self.provider: LLMProvider = (
            model if isinstance(model, LLMProvider) else create_llm_provider(model)
        )
        self.strategy: PromptStrategy = (
            prompt_strategy
            if isinstance(prompt_strategy, PromptStrategy)
            else get_prompt_strategy(prompt_strategy)
        )
        self.market_data_provider = market_data_provider
        self.base_instructions = base_instructions or BASE_AGENT_INSTRUCTIONS
        self.recursion_limit = recursion_limit

        self._tools = build_market_tools(market_data_provider)
        self._system_prompt = self.strategy.build_system_prompt(self.base_instructions)
        self._agent = self._build_agent()

    # --- construção ---------------------------------------------------------
    def _build_agent(self):
        from langchain.agents import create_agent

        chat_model = self.provider.build_chat_model()
        return create_agent(
            chat_model,
            tools=self._tools,
            system_prompt=self._system_prompt,
        )

    # --- execução -----------------------------------------------------------
    def run(self, question: str) -> AgentResult:
        """Executa o agente para uma pergunta e retorna um resultado estruturado."""
        task = self.strategy.build_task_message(question)
        start = time.perf_counter()
        error: str | None = None
        messages: list[BaseMessage] = []

        try:
            state = self._agent.invoke(
                {"messages": [HumanMessage(content=task)]},
                config={"recursion_limit": self.recursion_limit},
            )
            messages = state.get("messages", [])
        except Exception as exc:  # não vaza stack trace; registra e reporta
            logger.exception("Falha na execução do agente.")
            error = f"{type(exc).__name__}: {exc}"

        latency_ms = int((time.perf_counter() - start) * 1000)
        answer, tool_calls = self._extract(messages)
        usage = self._sum_usage(messages)

        return AgentResult(
            answer=answer,
            provider=self.provider.provider_name,
            model=self.provider.config.model,
            strategy=self.strategy.name,
            prompt_version=self.strategy.prompt_version,
            tools_used=self._unique_tool_names(tool_calls),
            tool_calls=tool_calls,
            usage=usage,
            latency_ms=latency_ms,
            error=error,
        )

    # --- extração -----------------------------------------------------------
    @staticmethod
    def _extract(messages: list[BaseMessage]) -> tuple[str, list[ToolCallRecord]]:
        outputs_by_id: dict[str, str] = {}
        for message in messages:
            if isinstance(message, ToolMessage) and message.tool_call_id:
                outputs_by_id[message.tool_call_id] = _as_text(message.content)

        tool_calls: list[ToolCallRecord] = []
        final_answer = ""
        for message in messages:
            if isinstance(message, AIMessage):
                for call in message.tool_calls or []:
                    tool_calls.append(
                        ToolCallRecord(
                            name=call.get("name", ""),
                            args=call.get("args", {}) or {},
                            output=outputs_by_id.get(call.get("id", "")),
                        )
                    )
                text = _as_text(message.content)
                if text.strip():
                    final_answer = text  # mantém o último conteúdo textual
        return final_answer, tool_calls

    @staticmethod
    def _sum_usage(messages: list[BaseMessage]) -> TokenUsage:
        total = TokenUsage.zero()
        for message in messages:
            if isinstance(message, AIMessage):
                usage = extract_token_usage(message)
                total.input_tokens += usage.input_tokens
                total.output_tokens += usage.output_tokens
                total.total_tokens += usage.total_tokens
        return total

    @staticmethod
    def _unique_tool_names(tool_calls: list[ToolCallRecord]) -> list[str]:
        seen: list[str] = []
        for call in tool_calls:
            if call.name and call.name not in seen:
                seen.append(call.name)
        return seen

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return (
            f"FinancialAgent(provider={self.provider.provider_name!r}, "
            f"model={self.provider.config.model!r}, strategy={self.strategy.name!r}, "
            f"source={self.market_data_provider.source_name!r})"
        )


def _as_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content) if content is not None else ""


__all__ = ["FinancialAgent"]
