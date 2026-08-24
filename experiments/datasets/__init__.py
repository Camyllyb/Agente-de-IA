"""Datasets de questões para os experimentos."""

from __future__ import annotations

import json
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent / "questions.json"


def load_dataset(path: Path | None = None) -> dict:
    """Carrega o dataset completo (com metadados)."""
    path = path or _DEFAULT_PATH
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_questions(path: Path | None = None) -> list[dict]:
    """Carrega apenas a lista de questões (dataset antigo/sintético)."""
    return load_dataset(path).get("questions", [])


# Loader do benchmark v2 (novo formato de 30 questões) — importado aqui para
# conveniência, mantendo o loader antigo intacto.
from experiments.datasets.benchmark_loader import (  # noqa: E402
    is_benchmark_v2,
    load_benchmark_dataset,
    save_benchmark_dataset,
    to_runner_questions,
)

__all__ = [
    "load_dataset",
    "load_questions",
    "load_benchmark_dataset",
    "save_benchmark_dataset",
    "is_benchmark_v2",
    "to_runner_questions",
]
