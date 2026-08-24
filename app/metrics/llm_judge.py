"""LLM-as-a-judge (OPCIONAL).

Avalia respostas usando um modelo de linguagem. As notas produzidas aqui são
**claramente identificadas como avaliação por IA** (``evaluator`` começa com
``llm_judge:``) e **nunca** devem ser misturadas com a avaliação humana.
"""

from __future__ import annotations

import json
import re
from typing import Sequence

from langchain_core.messages import HumanMessage, SystemMessage

from app.metrics.human_eval import CRITERIA
from app.services.llm.base import LLMProvider

_JUDGE_SYSTEM = (
    "Você é um avaliador imparcial de respostas de assistentes financeiros. "
    "Avalie a resposta em uma escala de 1 a 5 para cada critério e responda "
    "APENAS com um objeto JSON válido, sem texto adicional."
)


def _build_messages(question: str, answer: str, criteria: Sequence[str]) -> list:
    criteria_list = ", ".join(criteria)
    instructions = (
        f"Pergunta:\n{question}\n\n"
        f"Resposta a avaliar:\n{answer}\n\n"
        f"Atribua uma nota inteira de 1 a 5 para cada critério ({criteria_list}). "
        "Formato de saída (JSON):\n"
        "{" + ", ".join(f'\"{c}\": <1-5>' for c in criteria) + ', "justificativa": "<texto breve>"}'
    )
    return [SystemMessage(content=_JUDGE_SYSTEM), HumanMessage(content=instructions)]


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _clamp_score(value) -> int | None:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return score if 1 <= score <= 5 else None


def judge_answer(
    provider: LLMProvider,
    question: str,
    answer: str,
    criteria: Sequence[str] = tuple(CRITERIA),
) -> dict:
    """Avalia uma resposta via LLM. Retorna notas 1–5 por critério.

    Notas ausentes/ inválidas retornam ``None`` (nunca inventadas).
    """
    response = provider.generate(_build_messages(question, answer, criteria))
    parsed = _extract_json(response.content)
    scores = {c: _clamp_score(parsed.get(c)) for c in criteria}
    return {
        "evaluator": f"llm_judge:{provider.provider_name}/{provider.config.model}",
        "is_ai": True,
        "scores": scores,
        "justificativa": parsed.get("justificativa", ""),
        "raw": response.content,
    }
