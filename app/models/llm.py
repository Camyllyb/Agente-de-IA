"""Modelos de dados da camada de LLM.

Estes tipos são independentes de qualquer provedor específico — descrevem a
configuração de um modelo (:class:`LLMConfig`) e o resultado de uma geração
(:class:`LLMResponse`), permitindo trocar de provedor sem alterar o restante do
sistema.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMConfig(BaseModel):
    """Configuração dinâmica de um modelo de linguagem.

    A mesma pergunta pode ser executada em diferentes provedores/modelos apenas
    trocando esta configuração — sem modificar a lógica do agente.
    """

    model_config = ConfigDict(frozen=False)

    provider: str = Field(..., description="Nome do provedor (openai, anthropic, ...).")
    model: str = Field(..., description="Identificador do modelo no provedor.")
    temperature: float = Field(0.0, description="Temperatura de amostragem.")
    max_tokens: int = Field(1024, description="Limite de tokens de saída.")
    timeout: int = Field(60, description="Timeout da chamada, em segundos.")
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Parâmetros adicionais específicos do provedor (opcional).",
    )

    @field_validator("provider", "model")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("provider e model não podem ser vazios.")
        return value.strip()

    @field_validator("temperature")
    @classmethod
    def _valid_temperature(cls, value: float) -> float:
        if not 0.0 <= value <= 2.0:
            raise ValueError("temperature deve estar entre 0.0 e 2.0.")
        return value

    @field_validator("max_tokens", "timeout")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("max_tokens e timeout devem ser positivos.")
        return value


class TokenUsage(BaseModel):
    """Consumo de tokens de uma geração."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def zero(cls) -> "TokenUsage":
        return cls(input_tokens=0, output_tokens=0, total_tokens=0)


class LLMResponse(BaseModel):
    """Resultado padronizado de uma geração de LLM."""

    content: str
    provider: str
    model: str
    usage: TokenUsage = Field(default_factory=TokenUsage.zero)
    finish_reason: str | None = None
    raw: dict[str, Any] | None = Field(
        default=None, description="Metadados brutos do provedor (opcional)."
    )
