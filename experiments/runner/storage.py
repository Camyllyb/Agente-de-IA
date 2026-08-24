"""Persistência dos resultados dos experimentos (SQLite) e exportação CSV."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

# Colunas registradas para cada execução (ver PROMPT 7).
COLUMNS: tuple[str, ...] = (
    "experiment_id",
    "timestamp",
    "question_id",
    "category",
    "provider",
    "model",
    "strategy",
    "prompt_version",
    "repetition",
    "question",
    "answer",
    "expected_answer",     # JSON
    "financial_data",      # JSON (saídas das ferramentas)
    "tools_called",        # JSON (lista)
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "estimated_cost",      # nullable
    "attempts",
    "retry_reason",        # nullable
    "error",               # nullable
)

_JSON_FIELDS = {"expected_answer", "financial_data", "tools_called"}


class ResultStore:
    """Armazena registros de execução em SQLite e exporta para CSV."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self) -> None:
        cols_sql = ",\n  ".join(f"{c} TEXT" for c in COLUMNS)
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS runs (\n"
            f"  id INTEGER PRIMARY KEY AUTOINCREMENT,\n  {cols_sql}\n)"
        )
        self._conn.commit()

    def insert(self, record: dict[str, Any]) -> None:
        row = self._serialize(record)
        placeholders = ", ".join("?" for _ in COLUMNS)
        values = [row.get(c) for c in COLUMNS]
        self._conn.execute(
            f"INSERT INTO runs ({', '.join(COLUMNS)}) VALUES ({placeholders})", values
        )
        self._conn.commit()

    @staticmethod
    def _serialize(record: dict[str, Any]) -> dict[str, Any]:
        row = dict(record)
        for field in _JSON_FIELDS:
            if field in row and not isinstance(row[field], str) and row[field] is not None:
                row[field] = json.dumps(row[field], ensure_ascii=False)
        return row

    def fetch_all(self, experiment_id: str | None = None) -> list[dict[str, Any]]:
        if experiment_id:
            cursor = self._conn.execute(
                "SELECT * FROM runs WHERE experiment_id = ? ORDER BY id", (experiment_id,)
            )
        else:
            cursor = self._conn.execute("SELECT * FROM runs ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]

    def count(self, experiment_id: str | None = None) -> int:
        if experiment_id:
            cursor = self._conn.execute(
                "SELECT COUNT(*) FROM runs WHERE experiment_id = ?", (experiment_id,)
            )
        else:
            cursor = self._conn.execute("SELECT COUNT(*) FROM runs")
        return int(cursor.fetchone()[0])

    def export_csv(self, path: str | Path, experiment_id: str | None = None) -> int:
        rows = self.fetch_all(experiment_id)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["id", *COLUMNS]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k) for k in fieldnames})
        return len(rows)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ResultStore":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()
