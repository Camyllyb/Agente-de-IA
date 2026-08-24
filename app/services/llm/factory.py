"""Fábrica de provedores de LLM.

Ponto único para criar um :class:`~app.services.llm.base.LLMProvider` a partir de
uma :class:`~app.models.llm.LLMConfig`. Trocar de provedor/modelo é apenas trocar
a configuração — a lógica do agente não muda.
"""

from __future__ import annotations

from app.models.llm import LLMConfig
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.base import LLMProvider
from app.services.llm.errors import UnsupportedProviderError
from app.services.llm.fake import FakeLLMProvider
from app.services.llm.google_provider import GoogleProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.openrouter_provider import OpenRouterProvider

# Registro de provedores suportados. A biblioteca de cada provedor só é
# importada quando o provedor é efetivamente utilizado (ver build_chat_model).
_REGISTRY: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "openrouter": OpenRouterProvider,
    "fake": FakeLLMProvider,
}


def supported_providers() -> tuple[str, ...]:
    """Retorna a tupla de provedores suportados."""
    return tuple(_REGISTRY.keys())


def create_llm_provider(config: LLMConfig) -> LLMProvider:
    """Cria o provedor correspondente a ``config.provider``.

    Raises:
        UnsupportedProviderError: se o provedor não for suportado.
    """
    provider = config.provider.lower()
    provider_cls = _REGISTRY.get(provider)
    if provider_cls is None:
        raise UnsupportedProviderError(config.provider, supported_providers())
    return provider_cls(config)


def create_llm_provider_from_params(
    provider: str,
    model: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    timeout: int = 60,
    extra: dict | None = None,
) -> LLMProvider:
    """Atalho para criar um provedor a partir de parâmetros soltos."""
    config = LLMConfig(
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        extra=extra or {},
    )
    return create_llm_provider(config)
