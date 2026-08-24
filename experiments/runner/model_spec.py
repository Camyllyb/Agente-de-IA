"""Especificação de modelo para o runner de experimentos.

Um :class:`ModelSpec` sabe construir um :class:`LLMProvider` para uma dada
questão. Isso permite tanto modelos reais (config fixa, ignora a questão) quanto
o oráculo determinístico (roteiriza a resposta por questão), sem acoplar o runner
a nenhum dos dois.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.models.llm import LLMConfig
from app.services.llm import LLMProvider, create_llm_provider


@dataclass
class ModelSpec:
    provider: str
    model: str
    build: Callable[[dict], LLMProvider]


def from_llm_config(config: LLMConfig) -> ModelSpec:
    """ModelSpec para um modelo real: mesma configuração para toda questão."""
    return ModelSpec(
        provider=config.provider,
        model=config.model,
        build=lambda _question, _config=config: create_llm_provider(_config),
    )
