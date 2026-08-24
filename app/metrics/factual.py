"""Precisão factual: compara a resposta com o valor de referência do dataset.

- Numérica: compara dentro da tolerância definida no dataset.
- Categórica: verifica se algum termo aceito aparece na resposta.
- Qualitativa: não aplicável à avaliação automática (vai para avaliação humana).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.metrics.answer_parsing import extract_number, final_answer_line


@dataclass
class FactualScore:
    applicable: bool          # se a métrica automática se aplica a esta questão
    correct: bool | None      # None quando não aplicável
    predicted: float | str | None
    expected: float | str | None
    detail: str = ""


def score_answer(expected_answer: dict, answer_text: str) -> FactualScore:
    """Pontua a precisão factual de ``answer_text`` contra ``expected_answer``."""
    etype = (expected_answer or {}).get("type")

    if etype == "numeric":
        expected = float(expected_answer["value"])
        tolerance = float(expected_answer.get("tolerance", 0.0))
        predicted = extract_number(final_answer_line(answer_text))
        if predicted is None:
            return FactualScore(True, False, None, expected, "sem número na resposta")
        correct = abs(predicted - expected) <= tolerance
        return FactualScore(True, correct, predicted, expected)

    if etype == "categorical":
        expected = expected_answer.get("value")
        accept = expected_answer.get("accept") or [expected]
        haystack = (answer_text or "").lower()
        correct = any(str(term).lower() in haystack for term in accept if term)
        return FactualScore(True, correct, None, expected)

    # qualitativa / desconhecida -> avaliação humana
    return FactualScore(False, None, None, None, "avaliação humana")
