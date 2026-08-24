"""Testes da avaliação humana cega definitiva e da concordância (PROMPT 21)."""

from __future__ import annotations

import pytest

from app.metrics.agreement import cohen_kappa, krippendorff_alpha, weighted_kappa
from app.metrics.human_eval_final import (
    compute_agreement,
    generate_final_blind_evaluation,
    import_final_blind_evaluation,
)


# --- Concordância ------------------------------------------------------------

def test_cohen_kappa_perfect() -> None:
    assert cohen_kappa([1, 2, 3, 1], [1, 2, 3, 1]) == pytest.approx(1.0)


def test_cohen_kappa_chance_level() -> None:
    # po = 0.5, pe = 0.5 -> kappa = 0
    assert cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0]) == pytest.approx(0.0, abs=1e-9)


def test_weighted_kappa_perfect() -> None:
    assert weighted_kappa([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)


def test_krippendorff_perfect_and_imperfect() -> None:
    perfect = krippendorff_alpha([[1, 2, 3], [1, 2, 3]], level="interval")
    assert perfect == pytest.approx(1.0)
    imperfect = krippendorff_alpha([[1, 2, 3, 4], [1, 2, 3, 1]], level="ordinal")
    assert imperfect is not None and imperfect < 1.0


def test_agreement_none_with_single_rater() -> None:
    assert cohen_kappa([1], [1]) is None


# --- Avaliação cega definitiva ----------------------------------------------

def _records():
    return [
        {"id": i, "question": f"Q{i}?", "answer": f"Resposta {i}", "provider": "openai",
         "model": "modelo-x", "strategy": "zero_shot", "prompt_version": "zero_shot_v1",
         "repetition": 1, "question_id": f"Q{i:03d}", "category": "calculation",
         "experiment_id": "e", "experiment_type": "llm_only", "error": None}
        for i in range(1, 6)
    ]


def test_generate_blind_hides_identity_and_records_seed(tmp_path) -> None:
    csv_path = tmp_path / "blind.csv"
    map_path = tmp_path / "map.json"
    n = generate_final_blind_evaluation(_records(), csv_path, map_path, seed=123)
    assert n == 5
    content = csv_path.read_text(encoding="utf-8")
    # IDs de 6 dígitos e sem vazar identidade.
    assert "R000001" in content
    for hidden in ("openai", "modelo-x", "zero_shot"):
        assert hidden not in content

    import json
    payload = json.loads(map_path.read_text(encoding="utf-8"))
    assert payload["seed"] == 123
    assert "map" in payload


def _fill(csv_path, mapping_scores):
    """Preenche o CSV cego com notas por anon_id."""
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    header = lines[0]
    out = [header]
    for line in lines[1:]:
        anon = line.split(",")[0]
        rel, cla, com, pre = mapping_scores[anon]
        out.append(f"{anon},pergunta,resposta,{rel},{cla},{com},{pre},1,1,ok")
    csv_path.write_text("\n".join(out), encoding="utf-8")


def test_import_and_agreement(tmp_path) -> None:
    csv1 = tmp_path / "r1.csv"
    csv2 = tmp_path / "r2.csv"
    map_path = tmp_path / "map.json"
    generate_final_blind_evaluation(_records(), csv1, map_path, seed=1)
    # segundo avaliador usa o mesmo CSV base
    csv2.write_text(csv1.read_text(encoding="utf-8"), encoding="utf-8")

    import json
    anon_ids = sorted(json.loads(map_path.read_text(encoding="utf-8"))["map"].keys())
    # precisão percebida com variância e concordância perfeita entre avaliadores.
    scores1, scores2 = {}, {}
    for i, a in enumerate(anon_ids):
        pre = 5 if i % 2 == 0 else 3
        scores1[a] = (5, 4, 4, pre)
        scores2[a] = (5, 4, 3, pre)
    _fill(csv1, scores1)
    _fill(csv2, scores2)

    ev1 = import_final_blind_evaluation(csv1, map_path, rater="r1")
    ev2 = import_final_blind_evaluation(csv2, map_path, rater="r2")
    assert all(e["evaluator"] == "human" for e in ev1)
    assert {e["model"] for e in ev1} == {"modelo-x"}  # reassociado pelo mapeamento

    agreement = compute_agreement({"r1": ev1, "r2": ev2}, criterion="precisao_percebida")
    assert agreement["n_raters"] == 2
    assert agreement["cohen_kappa"] == pytest.approx(1.0)  # precisao idêntica (5)
