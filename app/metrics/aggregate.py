"""Agregação de métricas automáticas a partir dos registros de execução.

Produz registros "pontuados" (com precisão factual, acerto de ferramenta, sucesso
e custo) e utilitários de agregação. É a ponte usada pelo painel de resultados e
pela análise estatística.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from app.metrics.agentic import data_grounding, task_success, tool_execution_success
from app.metrics.factual import score_answer
from app.metrics.pricing import PriceTable


def _load_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def tool_correct(expected_tools: list[str], tools_called: list[str]) -> bool | None:
    """Verifica se ao menos uma ferramenta esperada foi utilizada.

    Retorna ``None`` quando a questão não exige consulta externa.
    """
    if not expected_tools:
        return None
    called = set(tools_called or [])
    return any(tool in called for tool in expected_tools)


def build_scored_records(
    records: Iterable[dict],
    questions_by_id: dict[str, dict],
    price_table: PriceTable | None = None,
) -> list[dict]:
    """Aumenta cada registro com métricas automáticas derivadas."""
    scored: list[dict] = []
    for record in records:
        expected = _load_json(record.get("expected_answer")) or {}
        tools_called = _load_json(record.get("tools_called")) or []
        tool_calls = _load_json(record.get("financial_data")) or []
        answer = record.get("answer") or ""

        factual = score_answer(expected, answer)
        question = questions_by_id.get(record.get("question_id"), {})
        expected_tools = question.get("expected_tools") or []

        success = not record.get("error")
        tcorrect = tool_correct(expected_tools, tools_called)
        exec_ok = tool_execution_success(tool_calls)
        grounded = data_grounding(factual.applicable, factual.correct, exec_ok, tools_called)
        task_ok = task_success(success, factual.applicable, factual.correct, answer)
        input_tokens = _to_int(record.get("input_tokens"))
        output_tokens = _to_int(record.get("output_tokens"))
        cost = _to_float(record.get("estimated_cost"))
        if cost is None and price_table is not None and success:
            cost = price_table.estimate(record.get("model"), input_tokens, output_tokens)

        scored.append(
            {
                **record,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": _to_int(record.get("total_tokens")),
                "latency_ms": _to_int(record.get("latency_ms")),
                "success": success,
                "factual_applicable": factual.applicable,
                "is_correct": factual.correct,
                "predicted_value": factual.predicted,
                "expected_value": factual.expected,
                "tool_required": bool(expected_tools),
                "tool_correct": tcorrect,
                "tool_execution_ok": exec_ok,
                "data_grounded": grounded,
                "task_success": task_ok,
                "experiment_type": record.get("experiment_type"),
                "estimated_cost": cost,
            }
        )
    return scored


def success_rate(records: Iterable[dict]) -> float | None:
    records = list(records)
    if not records:
        return None
    ok = sum(1 for r in records if not r.get("error"))
    return ok / len(records)


def factual_accuracy(scored: Iterable[dict]) -> float | None:
    """Precisão factual sobre as questões com métrica automática aplicável."""
    applicable = [r for r in scored if r.get("factual_applicable")]
    if not applicable:
        return None
    correct = sum(1 for r in applicable if r.get("is_correct"))
    return correct / len(applicable)


def tool_accuracy(scored: Iterable[dict]) -> float | None:
    """Acurácia de uso de ferramenta sobre as questões que a exigem."""
    required = [r for r in scored if r.get("tool_required")]
    if not required:
        return None
    correct = sum(1 for r in required if r.get("tool_correct"))
    return correct / len(required)


def to_dataframe(scored: list[dict]):
    """Converte os registros pontuados em ``pandas.DataFrame`` (import lazy)."""
    import pandas as pd

    return pd.DataFrame(scored)
