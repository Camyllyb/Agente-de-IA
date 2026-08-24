"""Métricas específicas do EXPERIMENTO B (agente com ferramentas).

- Tool Selection Accuracy: a ferramenta esperada foi utilizada?
- Tool Execution Success: as chamadas de ferramenta retornaram dados válidos?
- Data Grounding Accuracy: a resposta está fundamentada nos dados obtidos?
- Task Success Rate: a tarefa foi concluída com sucesso?

As métricas retornam ``None`` quando não se aplicam (ex.: sem ferramentas no
experimento A) — nunca são forçadas.
"""

from __future__ import annotations

from typing import Iterable


def tool_execution_success(tool_calls: list[dict] | None) -> bool | None:
    """True se todas as chamadas retornaram dados válidos (sem 'found=false')."""
    if not tool_calls:
        return None
    for call in tool_calls:
        output = call.get("output")
        if isinstance(output, dict) and output.get("found") is False:
            return False
    return True


def data_grounding(factual_applicable: bool, is_correct: bool | None,
                   exec_ok: bool | None, tools_called: list[str] | None) -> bool | None:
    """Fundamentação: a resposta reflete os dados obtidos pelas ferramentas."""
    if not tools_called:
        return None
    if exec_ok is False:
        return False
    if factual_applicable:
        return bool(is_correct)
    return True  # ferramentas executaram; resposta qualitativa considerada fundamentada


def task_success(success: bool, factual_applicable: bool, is_correct: bool | None,
                 answer: str | None) -> bool:
    """A tarefa foi concluída com sucesso?"""
    if not success:
        return False
    if factual_applicable:
        return bool(is_correct)
    return bool((answer or "").strip())


# --- agregações --------------------------------------------------------------

def _rate(records: Iterable[dict], field: str) -> float | None:
    values = [r.get(field) for r in records if r.get(field) is not None]
    if not values:
        return None
    return sum(1 for v in values if v) / len(values)


def tool_selection_accuracy(scored: Iterable[dict]) -> float | None:
    required = [r for r in scored if r.get("tool_required")]
    return _rate(required, "tool_correct")


def tool_execution_success_rate(scored: Iterable[dict]) -> float | None:
    return _rate(scored, "tool_execution_ok")


def data_grounding_accuracy(scored: Iterable[dict]) -> float | None:
    return _rate(scored, "data_grounded")


def task_success_rate(scored: Iterable[dict]) -> float | None:
    return _rate(scored, "task_success")
