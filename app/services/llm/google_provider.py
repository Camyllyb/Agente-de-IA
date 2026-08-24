"""Provedor Google Gemini (import lazy de ``langchain-google-genai``)."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.config.settings import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.errors import LLMConfigurationError, ProviderNotInstalledError


class GoogleProvider(LLMProvider):
    provider_name = "google"
    required_package = "langchain-google-genai"

    def build_chat_model(self) -> BaseChatModel:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:  # pragma: no cover - depende de instalação
            raise ProviderNotInstalledError(
                self.provider_name, self.required_package
            ) from exc

        api_key = self.config.extra.get("api_key") or get_settings().google_api_key
        if not api_key:
            raise LLMConfigurationError(
                "GOOGLE_API_KEY não configurada para o provedor 'google'."
            )

        # Gemini usa 'max_output_tokens' e 'google_api_key'.
        return ChatGoogleGenerativeAI(
            model=self.config.model,
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_tokens,
            timeout=self.config.timeout,
            google_api_key=api_key,
        )
