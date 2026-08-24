"""Abstração de provedor de LLM.

:class:`LLMProvider` desacopla o restante do sistema (agente, API, experimentos)
de qualquer biblioteca específica de provedor. As implementações concretas apenas
precisam saber construir um ``BaseChatModel`` do LangChain — todo o resto (invocar,
extrair tokens, padronizar a resposta) é fornecido aqui.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.models.llm import LLMConfig, LLMResponse, TokenUsage


def extract_token_usage(message: AIMessage) -> TokenUsage:
    """Extrai o consumo de tokens de uma ``AIMessage`` de forma robusta.

    Prioriza ``usage_metadata`` (padrão moderno do LangChain) e recorre a
    ``response_metadata`` quando necessário. Se nada estiver disponível, retorna
    zeros — nunca inventa valores.
    """
    usage = getattr(message, "usage_metadata", None)
    if usage:
        return TokenUsage(
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
        )

    meta = getattr(message, "response_metadata", {}) or {}
    token_usage = meta.get("token_usage") or meta.get("usage") or {}
    input_tokens = int(
        token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0)) or 0
    )
    output_tokens = int(
        token_usage.get("completion_tokens", token_usage.get("output_tokens", 0)) or 0
    )
    total_tokens = int(token_usage.get("total_tokens", input_tokens + output_tokens) or 0)
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


class LLMProvider(ABC):
    """Interface comum para provedores de LLM.

    A biblioteca específica do provedor é importada apenas dentro de
    :meth:`build_chat_model`, ou seja, somente quando o provedor é de fato usado.
    """

    #: Nome canônico do provedor (sobrescrito nas subclasses).
    provider_name: str = "base"

    #: Nome do pacote necessário (para mensagens de erro amigáveis).
    required_package: str | None = None

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    def build_chat_model(self) -> BaseChatModel:
        """Constrói o ``BaseChatModel`` do LangChain para este provedor.

        Deve importar a biblioteca do provedor localmente (import lazy) e
        levantar :class:`~app.services.llm.errors.ProviderNotInstalledError` ou
        :class:`~app.services.llm.errors.LLMConfigurationError` quando aplicável.
        """
        raise NotImplementedError

    def generate(self, messages: str | list[BaseMessage]) -> LLMResponse:
        """Executa uma geração simples (sem ferramentas) e padroniza a resposta."""
        chat_model = self.build_chat_model()
        if isinstance(messages, str):
            messages = [HumanMessage(content=messages)]
        result = chat_model.invoke(messages)
        return self._to_response(result)

    def _to_response(self, message: Any) -> LLMResponse:
        content = getattr(message, "content", "")
        if isinstance(content, list):  # alguns provedores retornam blocos
            content = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        usage = (
            extract_token_usage(message)
            if isinstance(message, AIMessage)
            else TokenUsage.zero()
        )
        meta = getattr(message, "response_metadata", {}) or {}
        return LLMResponse(
            content=content or "",
            provider=self.provider_name,
            model=self.config.model,
            usage=usage,
            finish_reason=meta.get("finish_reason") or meta.get("stop_reason"),
        )

    def __repr__(self) -> str:  # pragma: no cover - representação trivial
        return (
            f"{self.__class__.__name__}(provider={self.provider_name!r}, "
            f"model={self.config.model!r})"
        )
