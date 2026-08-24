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
    """Carrega apenas a lista de questões."""
    return load_dataset(path).get("questions", [])
