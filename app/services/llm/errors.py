"""Exceções da camada de LLM."""

from __future__ import annotations


class LLMError(Exception):
    """Erro base da camada de LLM."""


class UnsupportedProviderError(LLMError):
    """Provedor solicitado não é suportado."""

    def __init__(self, provider: str, supported: tuple[str, ...] | list[str]):
        self.provider = provider
        self.supported = tuple(supported)
        super().__init__(
            f"Provedor '{provider}' não é suportado. "
            f"Suportados: {', '.join(self.supported)}."
        )


class ProviderNotInstalledError(LLMError):
    """A biblioteca específica do provedor não está instalada."""

    def __init__(self, provider: str, package: str):
        self.provider = provider
        self.package = package
        super().__init__(
            f"Provedor '{provider}' requer o pacote '{package}', que não está "
            f"instalado. Instale com: pip install {package}"
        )


class LLMConfigurationError(LLMError):
    """Configuração inválida ou incompleta (ex.: chave de API ausente)."""
