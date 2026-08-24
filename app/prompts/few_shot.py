"""Estratégia few-shot: mesma tarefa acrescida de exemplos representativos."""

from __future__ import annotations

from app.prompts.base import PromptStrategy
from app.prompts.shared import FEW_SHOT_EXAMPLES


class FewShotStrategy(PromptStrategy):
    """Acrescenta exemplos representativos de entrada/saída, separados do problema.

    Os exemplos usam ativos fictícios e ficam claramente demarcados, para não se
    confundirem com os dados do problema real.
    """

    name = "few_shot"
    prompt_version = "few_shot_v1"

    def technique_instructions(self) -> str:
        # O few-shot não altera as instruções de tarefa; sua característica são os
        # exemplos (fornecidos por few_shot_examples()).
        return ""

    def few_shot_examples(self) -> str:
        return FEW_SHOT_EXAMPLES
