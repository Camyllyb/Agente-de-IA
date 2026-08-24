"""Avaliação humana cega.

Gera um CSV para avaliação **cega**: o avaliador não sabe o modelo nem a técnica.
As respostas são randomizadas e recebem identificadores anônimos. Um arquivo de
mapeamento (separado, não entregue ao avaliador) permite reassociar as notas
depois da importação.

Critérios (notas de 1 a 5): clareza, relevância, completude, precisão percebida.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from random import Random
from typing import Iterable

CRITERIA = ["clareza", "relevancia", "completude", "precisao_percebida"]

# Rubrica objetiva (mesma escala 1–5 para todos os critérios).
RUBRIC: dict[int, str] = {
    1: "Muito insatisfatório: não atende ao critério; ausente, incorreto ou incompreensível.",
    2: "Insatisfatório: atende apenas parcialmente; falhas relevantes.",
    3: "Regular: atende ao mínimo esperado, com limitações perceptíveis.",
    4: "Bom: atende bem ao critério, com pequenas ressalvas.",
    5: "Excelente: atende plenamente ao critério, sem ressalvas relevantes.",
}

_MAP_FIELDS = (
    "id", "experiment_id", "question_id", "category",
    "provider", "model", "strategy", "prompt_version",
)


def rubric_markdown() -> str:
    lines = [
        "# Rubrica de avaliação (1 a 5)",
        "",
        "Aplique a MESMA escala a cada critério: **clareza**, **relevância**, "
        "**completude** e **precisão percebida**.",
        "",
    ]
    for score, meaning in RUBRIC.items():
        lines.append(f"- **{score}** — {meaning}")
    lines += [
        "",
        "Definições dos critérios:",
        "- **Clareza**: a resposta é compreensível e bem estruturada.",
        "- **Relevância**: a resposta responde ao que foi perguntado.",
        "- **Completude**: a resposta cobre os aspectos necessários.",
        "- **Precisão percebida**: a resposta aparenta estar factualmente correta "
        "(com base nos dados apresentados).",
    ]
    return "\n".join(lines)


def generate_blind_evaluation(
    records: Iterable[dict],
    out_csv: str | Path,
    mapping_out: str | Path,
    seed: int = 42,
    write_rubric: bool = True,
) -> int:
    """Gera o CSV cego e o arquivo de mapeamento. Retorna o nº de respostas."""
    rows = [r for r in records if (r.get("answer") or "").strip() and not r.get("error")]
    Random(seed).shuffle(rows)

    out_csv = Path(out_csv)
    mapping_out = Path(mapping_out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    mapping_out.parent.mkdir(parents=True, exist_ok=True)

    mapping: dict[str, dict] = {}
    fieldnames = ["anon_id", "question", "answer", *CRITERIA, "comentario"]
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, record in enumerate(rows, start=1):
            anon_id = f"R{index:04d}"
            writer.writerow(
                {
                    "anon_id": anon_id,
                    "question": record.get("question", ""),
                    "answer": record.get("answer", ""),
                    **{c: "" for c in CRITERIA},
                    "comentario": "",
                }
            )
            mapping[anon_id] = {field: record.get(field) for field in _MAP_FIELDS}

    mapping_out.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    if write_rubric:
        (out_csv.parent / "RUBRICA.md").write_text(rubric_markdown(), encoding="utf-8")

    return len(rows)


def import_blind_evaluation(filled_csv: str | Path, mapping_json: str | Path) -> list[dict]:
    """Importa o CSV preenchido e reassocia às execuções via o mapeamento.

    As avaliações importadas são marcadas como ``evaluator = 'human'``.
    """
    mapping = json.loads(Path(mapping_json).read_text(encoding="utf-8"))
    results: list[dict] = []
    with Path(filled_csv).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            anon_id = row.get("anon_id")
            scores = {c: _to_score(row.get(c)) for c in CRITERIA}
            if all(v is None for v in scores.values()):
                continue  # linha não avaliada
            entry = {
                "anon_id": anon_id,
                "evaluator": "human",
                **(mapping.get(anon_id, {})),
                **scores,
                "comentario": row.get("comentario", ""),
            }
            results.append(entry)
    return results


def _to_score(value) -> int | None:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return None
    return score if 1 <= score <= 5 else None
