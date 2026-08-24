"""Provedor Anthropic (import lazy de ``langchain-anthropic``)."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.config.settings import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.errors import LLMConfigurationError, ProviderNotInstalledError


class AnthropicProvider(LLMProvider):
    provider_name = "anthropic"
    required_package = "langchain-anthropic"

    def build_chat_model(self) -> BaseChatModel:
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover - depende de instalação
            raise ProviderNotInstalledError(
                self.provider_name, self.required_package
            ) from exc

        api_key = self.config.extra.get("api_key") or get_settings().anthropic_api_key
        if not api_key:
            raise LLMConfigurationError(
                "ANTHROPIC_API_KEY não configurada para o provedor 'anthropic'."
            )

        return ChatAnthropic(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout,
            api_key=api_key,
        )
