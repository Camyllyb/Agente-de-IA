"""Estratégia zero-shot: apresenta a tarefa diretamente, sem exemplos."""

from __future__ import annotations

from app.prompts.base import PromptStrategy


class ZeroShotStrategy(PromptStrategy):
    """Fornece diretamente a tarefa, sem exemplos e sem roteiro de raciocínio."""

    name = "zero_shot"
    prompt_version = "zero_shot_v1"

    def technique_instructions(self) -> str:
        # A característica do zero-shot é justamente a ausência de exemplos e de
        # instruções adicionais de raciocínio.
        return ""
