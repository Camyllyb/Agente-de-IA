"""Avaliação humana cega DEFINITIVA (protocolo científico final).

O avaliador não vê provider, modelo, técnica nem repetição. Cada resposta recebe
um identificador anônimo ``R000001``. A ordem é randomizada e a seed é registrada.
Suporta múltiplos avaliadores e o cálculo de concordância.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from random import Random
from typing import Iterable

from app.metrics.agreement import cohen_kappa, krippendorff_alpha, weighted_kappa

CRITERIA_FINAL = ["relevancia", "clareza", "completude", "precisao_percebida"]
EXTRA_FIELDS = ["afirmacoes_nao_sustentadas", "fatos_obrigatorios_atendidos"]

# Campos ocultados do avaliador, preservados apenas no mapeamento.
_HIDDEN = ("id", "experiment_id", "experiment_type", "question_id", "category",
           "provider", "model", "strategy", "prompt_version", "repetition")


def generate_final_blind_evaluation(
    records: Iterable[dict],
    out_csv: str | Path,
    mapping_out: str | Path,
    seed: int = 20260824,
) -> int:
    """Gera o CSV cego (IDs R000001) e o mapeamento (com a seed registrada)."""
    rows = [r for r in records if (r.get("answer") or "").strip() and not r.get("error")]
    Random(seed).shuffle(rows)

    out_csv, mapping_out = Path(out_csv), Path(mapping_out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    mapping_out.parent.mkdir(parents=True, exist_ok=True)

    mapping: dict[str, dict] = {}
    header = ["anon_id", "question", "answer", *CRITERIA_FINAL, *EXTRA_FIELDS, "comentario"]
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for i, record in enumerate(rows, start=1):
            anon_id = f"R{i:06d}"
            writer.writerow({
                "anon_id": anon_id,
                "question": record.get("question", ""),
                "answer": record.get("answer", ""),
                **{c: "" for c in CRITERIA_FINAL},
                **{c: "" for c in EXTRA_FIELDS},
                "comentario": "",
            })
            mapping[anon_id] = {field: record.get(field) for field in _HIDDEN}

    payload = {"seed": seed, "criteria": CRITERIA_FINAL, "extra_fields": EXTRA_FIELDS,
               "n": len(rows), "map": mapping}
    mapping_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)


def _to_score(value) -> int | None:
    try:
        s = int(float(value))
    except (TypeError, ValueError):
        return None
    return s if 1 <= s <= 5 else None


def _to_binary(value) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    v = str(value).strip().lower()
    if v in {"1", "sim", "true", "yes"}:
        return 1
    if v in {"0", "nao", "não", "false", "no"}:
        return 0
    return None


def import_final_blind_evaluation(
    filled_csv: str | Path, mapping_json: str | Path, rater: str = "rater1"
) -> list[dict]:
    """Importa um CSV preenchido por um avaliador e reassocia via o mapeamento."""
    payload = json.loads(Path(mapping_json).read_text(encoding="utf-8"))
    mapping = payload.get("map", payload)  # compat
    results: list[dict] = []
    with Path(filled_csv).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            anon_id = row.get("anon_id")
            scores = {c: _to_score(row.get(c)) for c in CRITERIA_FINAL}
            if all(v is None for v in scores.values()):
                continue
            results.append({
                "anon_id": anon_id,
                "rater": rater,
                "evaluator": "human",
                **(mapping.get(anon_id, {})),
                **scores,
                "afirmacoes_nao_sustentadas": _to_binary(row.get("afirmacoes_nao_sustentadas")),
                "fatos_obrigatorios_atendidos": _to_binary(row.get("fatos_obrigatorios_atendidos")),
                "comentario": row.get("comentario", ""),
            })
    return results


def compute_agreement(
    evaluations_by_rater: dict[str, list[dict]], criterion: str = "precisao_percebida"
) -> dict:
    """Concordância entre avaliadores para um critério (quando os dados permitem).

    Retorna Cohen/weighted Kappa (para pares) e Krippendorff's Alpha (geral).
    Valores ``None`` quando não aplicável — nunca forçados.
    """
    raters = list(evaluations_by_rater)
    if len(raters) < 2:
        return {"n_raters": len(raters), "cohen_kappa": None,
                "weighted_kappa": None, "krippendorff_alpha": None,
                "note": "concordância exige ≥2 avaliadores"}

    # Itens comuns (por anon_id).
    per_rater_scores: dict[str, dict[str, int]] = {}
    for rater, evals in evaluations_by_rater.items():
        per_rater_scores[rater] = {e["anon_id"]: e.get(criterion) for e in evals}
    common = set.intersection(*[set(v) for v in per_rater_scores.values()])
    common = sorted(common)

    aligned = {r: [per_rater_scores[r].get(a) for a in common] for r in raters}
    reliability = [aligned[r] for r in raters]

    result = {
        "n_raters": len(raters),
        "n_items": len(common),
        "krippendorff_alpha": krippendorff_alpha(reliability, level="ordinal"),
    }
    if len(raters) == 2:
        a, b = aligned[raters[0]], aligned[raters[1]]
        result["cohen_kappa"] = cohen_kappa(a, b)
        result["weighted_kappa"] = weighted_kappa(a, b, weights="quadratic")
    else:
        result["cohen_kappa"] = None
        result["weighted_kappa"] = None
    return result
