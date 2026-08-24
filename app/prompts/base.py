"""Abstração das estratégias de prompting.

:class:`PromptStrategy` define como um prompt é montado. As subclasses variam
**apenas** a característica experimental da técnica (o "bloco de técnica" e, no
caso few-shot, os exemplos). Todo o resto — instruções base, restrições, tarefa,
contexto e formato de resposta — é idêntico entre as estratégias.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.prompts.shared import (
    BASE_AGENT_INSTRUCTIONS,
    RESPONSE_FORMAT,
    SHARED_CONSTRAINTS,
)


class PromptStrategy(ABC):
    """Interface comum das estratégias de prompting."""

    #: Nome canônico da estratégia (ex.: "zero_shot").
    name: str = "base"

    #: Versão do prompt, para rastreabilidade científica (ex.: "zero_shot_v1").
    prompt_version: str = "base_v1"

    # --- característica experimental (a ÚNICA variável manipulada) -----------
    @abstractmethod
    def technique_instructions(self) -> str:
        """Bloco de instruções específico da técnica (pode ser vazio)."""
        raise NotImplementedError

    def few_shot_examples(self) -> str:
        """Exemplos representativos (apenas a estratégia few-shot sobrescreve)."""
        return ""

    # --- partes compartilhadas (idênticas entre estratégias) ----------------
    def build_system_prompt(self, base_instructions: str | None = None) -> str:
        """Monta o prompt de sistema: base + restrições + técnica + formato.

        A ordem e o conteúdo dos blocos compartilhados são iguais para todas as
        estratégias; somente o bloco de técnica (e os exemplos, no few-shot)
        muda.
        """
        base = (base_instructions or BASE_AGENT_INSTRUCTIONS).strip()
        blocks: list[str] = [base, SHARED_CONSTRAINTS.strip()]

        technique = self.technique_instructions().strip()
        if technique:
            blocks.append(technique)

        examples = self.few_shot_examples().strip()
        if examples:
            blocks.append(examples)

        blocks.append(RESPONSE_FORMAT.strip())
        return "\n\n".join(blocks)

    def build_task_message(
        self, question: str, financial_context: str | None = None
    ) -> str:
        """Monta a mensagem da tarefa (idêntica entre estratégias).

        O ``financial_context`` (quando fornecido) é inserido **verbatim** — as
        estratégias nunca alteram os dados financeiros.
        """
        parts = [f"Tarefa: {question.strip()}"]
        if financial_context:
            parts.append("Dados financeiros fornecidos:\n" + financial_context.strip())
        return "\n\n".join(parts)

    def build_messages(
        self,
        question: str,
        financial_context: str | None = None,
        base_instructions: str | None = None,
    ) -> list[BaseMessage]:
        """Constrói as mensagens (System + Human) para uma chamada direta ao LLM."""
        return [
            SystemMessage(content=self.build_system_prompt(base_instructions)),
            HumanMessage(content=self.build_task_message(question, financial_context)),
        ]

    def describe(self) -> dict[str, str]:
        """Metadados da estratégia (para API e registro dos experimentos)."""
        return {"name": self.name, "prompt_version": self.prompt_version}

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"{self.__class__.__name__}(version={self.prompt_version!r})"
