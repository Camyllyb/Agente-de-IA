"""Estratégias de prompting e seu registro.

Uso::

    from app.prompts import get_prompt_strategy
    strategy = get_prompt_strategy("zero_shot")   # ou "few_shot", "chain_of_thought"
"""

from __future__ import annotations

from app.prompts.base import PromptStrategy
from app.prompts.chain_of_thought import ChainOfThoughtStrategy
from app.prompts.few_shot import FewShotStrategy
from app.prompts.zero_shot import ZeroShotStrategy


class UnknownStrategyError(ValueError):
    """Estratégia de prompting solicitada não existe."""

    def __init__(self, name: str, available: list[str]):
        self.name = name
        self.available = available
        super().__init__(
            f"Estratégia '{name}' não existe. Disponíveis: {', '.join(available)}."
        )


# Registro de estratégias disponíveis.
_REGISTRY: dict[str, type[PromptStrategy]] = {
    ZeroShotStrategy.name: ZeroShotStrategy,
    FewShotStrategy.name: FewShotStrategy,
    ChainOfThoughtStrategy.name: ChainOfThoughtStrategy,
}


def available_strategies() -> list[str]:
    """Nomes das estratégias registradas."""
    return list(_REGISTRY.keys())


def get_prompt_strategy(name: str) -> PromptStrategy:
    """Instancia a estratégia pelo nome.

    Raises:
        UnknownStrategyError: se o nome não estiver registrado.
    """
    key = (name or "").strip().lower()
    strategy_cls = _REGISTRY.get(key)
    if strategy_cls is None:
        raise UnknownStrategyError(name, available_strategies())
    return strategy_cls()


__all__ = [
    "PromptStrategy",
    "ZeroShotStrategy",
    "FewShotStrategy",
    "ChainOfThoughtStrategy",
    "UnknownStrategyError",
    "get_prompt_strategy",
    "available_strategies",
]
