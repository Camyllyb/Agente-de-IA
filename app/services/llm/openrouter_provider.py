"""Provedor OpenRouter.

O OpenRouter expõe uma API compatível com a da OpenAI, portanto reutilizamos
``langchain-openai`` (``ChatOpenAI``) apontando para a base URL do OpenRouter.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.config.settings import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.errors import LLMConfigurationError, ProviderNotInstalledError


class OpenRouterProvider(LLMProvider):
    provider_name = "openrouter"
    required_package = "langchain-openai"

    def build_chat_model(self) -> BaseChatModel:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - depende de instalação
            raise ProviderNotInstalledError(
                self.provider_name, self.required_package
            ) from exc

        settings = get_settings()
        api_key = self.config.extra.get("api_key") or settings.openrouter_api_key
        if not api_key:
            raise LLMConfigurationError(
                "OPENROUTER_API_KEY não configurada para o provedor 'openrouter'."
            )
        base_url = self.config.extra.get("base_url") or settings.openrouter_base_url

        return ChatOpenAI(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout,
            api_key=api_key,
            base_url=base_url,
        )
