"""Provedor OpenAI (import lazy de ``langchain-openai``)."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.config.settings import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.errors import LLMConfigurationError, ProviderNotInstalledError


class OpenAIProvider(LLMProvider):
    provider_name = "openai"
    required_package = "langchain-openai"

    def build_chat_model(self) -> BaseChatModel:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - depende de instalação
            raise ProviderNotInstalledError(
                self.provider_name, self.required_package
            ) from exc

        api_key = self.config.extra.get("api_key") or get_settings().openai_api_key
        if not api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY não configurada para o provedor 'openai'."
            )

        return ChatOpenAI(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout,
            api_key=api_key,
        )
