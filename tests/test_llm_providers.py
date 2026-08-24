"""Testes da camada de LLM (offline, sem internet e sem API key).

Cobrem: criação do provider, configuração inválida, provider não suportado e uso
do provedor fake (inclusive respostas roteirizadas e contagem de tokens).
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from app.config.models import load_models_config
from app.models.llm import LLMConfig, LLMResponse
from app.services.llm import (
    FakeLLMProvider,
    LLMConfigurationError,
    LLMError,
    ProviderNotInstalledError,
    UnsupportedProviderError,
    create_llm_provider,
    create_llm_provider_from_params,
    make_fake_config,
    supported_providers,
)


# --- Criação do provider ----------------------------------------------------

def test_create_fake_provider() -> None:
    provider = create_llm_provider(make_fake_config())
    assert isinstance(provider, FakeLLMProvider)
    assert provider.provider_name == "fake"


def test_create_provider_from_params() -> None:
    provider = create_llm_provider_from_params("fake", "fake-model", temperature=0.5)
    assert provider.provider_name == "fake"
    assert provider.config.temperature == 0.5


def test_supported_providers_contains_all() -> None:
    providers = supported_providers()
    for expected in ("openai", "anthropic", "google", "openrouter", "fake"):
        assert expected in providers


# --- Configuração inválida ---------------------------------------------------

def test_invalid_temperature_raises() -> None:
    with pytest.raises(ValidationError):
        LLMConfig(provider="openai", model="x", temperature=-1.0)


def test_invalid_temperature_too_high_raises() -> None:
    with pytest.raises(ValidationError):
        LLMConfig(provider="openai", model="x", temperature=5.0)


def test_empty_model_raises() -> None:
    with pytest.raises(ValidationError):
        LLMConfig(provider="openai", model="   ")


def test_non_positive_max_tokens_raises() -> None:
    with pytest.raises(ValidationError):
        LLMConfig(provider="openai", model="x", max_tokens=0)


# --- Provider não suportado --------------------------------------------------

def test_unsupported_provider_raises() -> None:
    config = LLMConfig(provider="banana", model="x")
    with pytest.raises(UnsupportedProviderError) as exc_info:
        create_llm_provider(config)
    assert "banana" in str(exc_info.value)


# --- Provedores reais sem chave / sem biblioteca ----------------------------

def test_openai_without_key_or_lib_raises_llm_error() -> None:
    """Sem a lib instalada ou sem chave, deve levantar um erro claro (LLMError)."""
    provider = create_llm_provider_from_params("openai", "some-model")
    with pytest.raises((ProviderNotInstalledError, LLMConfigurationError)) as exc_info:
        provider.build_chat_model()
    assert isinstance(exc_info.value, LLMError)


# --- Uso do provedor fake ----------------------------------------------------

def test_fake_provider_generate_returns_response() -> None:
    provider = create_llm_provider(make_fake_config())
    response = provider.generate("Qual é a variação da PETR4?")
    assert isinstance(response, LLMResponse)
    assert response.content
    assert response.provider == "fake"
    assert response.usage.output_tokens > 0
    assert response.usage.total_tokens >= response.usage.output_tokens


def test_fake_provider_scripted_responses() -> None:
    config = make_fake_config(
        responses=["Primeira resposta roteirizada.", AIMessage(content="Segunda.")],
        default_response="Padrão.",
    )
    provider = create_llm_provider(config)
    model = provider.build_chat_model()

    first = model.invoke("oi")
    second = model.invoke("oi")
    third = model.invoke("oi")  # esgotou o roteiro -> resposta padrão

    assert "Primeira resposta" in first.content
    assert second.content == "Segunda."
    assert third.content == "Padrão."


def test_fake_provider_deterministic() -> None:
    p1 = create_llm_provider(make_fake_config())
    p2 = create_llm_provider(make_fake_config())
    assert p1.generate("mesma pergunta").content == p2.generate("mesma pergunta").content


# --- Loader de configuração de modelos --------------------------------------

def test_load_models_config_has_fake_entry() -> None:
    configs = load_models_config()
    assert any(c.provider == "fake" for c in configs)
