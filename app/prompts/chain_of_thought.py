"""Estratégia chain-of-thought: instrui a decompor o problema antes de concluir."""

from __future__ import annotations

from app.prompts.base import PromptStrategy
from app.prompts.shared import CHAIN_OF_THOUGHT_INSTRUCTIONS


class ChainOfThoughtStrategy(PromptStrategy):
    """Solicita raciocínio estruturado antes da conclusão.

    Não exige a exposição do raciocínio privado completo: a resposta persistida
    contém resposta final, justificativa concisa e dados utilizados.
    """

    name = "chain_of_thought"
    prompt_version = "chain_of_thought_v1"

    def technique_instructions(self) -> str:
        return CHAIN_OF_THOUGHT_INSTRUCTIONS
