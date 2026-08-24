"""Camada de provedores de LLM.

Exporta a abstração (:class:`LLMProvider`), a fábrica (:func:`create_llm_provider`),
os modelos de dados e o provedor fake para testes.
"""

from app.models.llm import LLMConfig, LLMResponse, TokenUsage
from app.services.llm.base import LLMProvider, extract_token_usage
from app.services.llm.errors import (
    LLMConfigurationError,
    LLMError,
    ProviderNotInstalledError,
    UnsupportedProviderError,
)
from app.services.llm.factory import (
    create_llm_provider,
    create_llm_provider_from_params,
    supported_providers,
)
from app.services.llm.fake import FakeChatModel, FakeLLMProvider, make_fake_config

__all__ = [
    "LLMConfig",
    "LLMResponse",
    "TokenUsage",
    "LLMProvider",
    "extract_token_usage",
    "LLMError",
    "UnsupportedProviderError",
    "ProviderNotInstalledError",
    "LLMConfigurationError",
    "create_llm_provider",
    "create_llm_provider_from_params",
    "supported_providers",
    "FakeChatModel",
    "FakeLLMProvider",
    "make_fake_config",
]
