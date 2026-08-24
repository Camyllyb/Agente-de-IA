"""Carregamento/gravação do dataset de benchmark (novo formato v2).

Mantém compatibilidade: o loader antigo (``load_questions``) continua válido para
o dataset sintético de 20 questões. Este módulo trata o formato v2 (30 questões).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models.benchmark import BenchmarkDataset, BenchmarkQuestion


def load_benchmark_dataset(path: str | Path) -> BenchmarkDataset:
    """Carrega e valida (via Pydantic) um dataset no formato v2."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return BenchmarkDataset(**data)


def save_benchmark_dataset(dataset: BenchmarkDataset, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        dataset.model_dump_json(indent=2, exclude_none=False), encoding="utf-8"
    )


def is_benchmark_v2(path: str | Path) -> bool:
    """Detecta se o arquivo está no formato v2 (schema_version == 'v2')."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return isinstance(data, dict) and data.get("schema_version") == "v2"


def to_runner_questions(dataset: BenchmarkDataset) -> list[dict]:
    """Converte as questões v2 para o formato consumido pelo ExperimentRunner."""
    return [q.to_runner_dict() for q in dataset.questions]
