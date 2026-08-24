"""Protocolo experimental congelável.

Congela todas as decisões metodológicas antes do experimento real: dataset,
prompts, modelos, parâmetros, métricas e tipos de experimento (LLM_ONLY / AGENT).
Estados: draft → validated → frozen. Depois de ``frozen`` não pode ser alterado;
qualquer mudança gera nova versão (``protocol_v2`` etc.). Um checksum identifica o
conteúdo e é registrado pelo runner em todas as execuções.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProtocolStatus(str, Enum):
    draft = "draft"
    validated = "validated"
    frozen = "frozen"


class ExperimentType(str, Enum):
    llm_only = "llm_only"
    agent = "agent"


class ModelRef(BaseModel):
    provider: str
    model: str
    model_identifier: str | None = None  # identificador retornado pelo provedor


class ExperimentProtocol(BaseModel):
    model_config = ConfigDict(extra="allow")

    protocol_version: str = "protocol_v1"
    status: ProtocolStatus = ProtocolStatus.draft
    created_at: str = Field(default_factory=_now)
    frozen_at: str | None = None
    checksum: str | None = None

    # Dataset
    dataset_version: str | None = None
    snapshot_id: str | None = None
    total_questions: int = 0
    category_distribution: dict[str, int] = Field(default_factory=dict)
    difficulty_distribution: dict[str, int] = Field(default_factory=dict)

    # Prompts
    zero_shot_version: str | None = None
    few_shot_version: str | None = None
    structured_reasoning_version: str | None = None

    # Modelos
    models: list[ModelRef] = Field(default_factory=list)

    # Parâmetros
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout: int = 60
    repetitions: int = 5

    # Métricas
    primary_metrics: list[str] = Field(default_factory=list)
    secondary_metrics: list[str] = Field(default_factory=list)

    # Experimentos
    experiment_types: list[ExperimentType] = Field(default_factory=list)

    # --- checksum -----------------------------------------------------------
    def content(self) -> dict:
        """Conteúdo metodológico (exclui estado, timestamps e checksum)."""
        data = self.model_dump(mode="json")
        for volatile in ("status", "created_at", "frozen_at", "checksum"):
            data.pop(volatile, None)
        return data

    def compute_checksum(self) -> str:
        blob = json.dumps(self.content(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    # --- validação / congelamento ------------------------------------------
    def validate_protocol(self) -> list[str]:
        errors: list[str] = []
        if not self.models:
            errors.append("Nenhum modelo definido.")
        if not self.experiment_types:
            errors.append("Nenhum tipo de experimento definido (llm_only/agent).")
        if not self.primary_metrics:
            errors.append("Nenhuma métrica primária definida.")
        if self.total_questions <= 0:
            errors.append("total_questions deve ser > 0.")
        if not (self.zero_shot_version and self.few_shot_version and self.structured_reasoning_version):
            errors.append("Versões de prompt incompletas.")
        return errors

    def freeze(self) -> "ExperimentProtocol":
        if self.status == ProtocolStatus.frozen:
            raise ValueError("Protocolo já congelado; crie uma nova versão.")
        errors = self.validate_protocol()
        if errors:
            raise ValueError("Protocolo inválido: " + "; ".join(errors))
        self.checksum = self.compute_checksum()
        self.frozen_at = _now()
        self.status = ProtocolStatus.frozen
        return self

    def verify_checksum(self) -> bool:
        return self.checksum is not None and self.checksum == self.compute_checksum()


def build_default_protocol(
    dataset,
    models: list[ModelRef],
    *,
    protocol_version: str = "protocol_v1",
    snapshot_id: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    timeout: int = 60,
    repetitions: int = 5,
    experiment_types: list[ExperimentType] | None = None,
    primary_metrics: list[str] | None = None,
    secondary_metrics: list[str] | None = None,
) -> ExperimentProtocol:
    """Monta um protocolo a partir de um :class:`BenchmarkDataset` e modelos."""
    from app.prompts import get_prompt_strategy

    return ExperimentProtocol(
        protocol_version=protocol_version,
        dataset_version=getattr(dataset, "dataset_version", None),
        snapshot_id=snapshot_id or getattr(dataset, "snapshot_id", None),
        total_questions=len(dataset.questions),
        category_distribution=dataset.category_counts(),
        difficulty_distribution=dataset.difficulty_counts(),
        zero_shot_version=get_prompt_strategy("zero_shot").prompt_version,
        few_shot_version=get_prompt_strategy("few_shot").prompt_version,
        structured_reasoning_version=get_prompt_strategy("chain_of_thought").prompt_version,
        models=models,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        repetitions=repetitions,
        primary_metrics=primary_metrics or ["factual_precision", "task_success"],
        secondary_metrics=secondary_metrics or ["latency_ms", "total_tokens", "estimated_cost"],
        experiment_types=experiment_types or [ExperimentType.llm_only, ExperimentType.agent],
    )


class ProtocolManager:
    """Persistência e versionamento de protocolos."""

    def __init__(self, base_dir: str | Path = "data/protocols"):
        self.base_dir = Path(base_dir)

    def _path(self, version: str) -> Path:
        return self.base_dir / f"{version}.json"

    def save(self, protocol: ExperimentProtocol) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self._path(protocol.protocol_version)
        if path.exists():
            existing = self.load(protocol.protocol_version)
            if existing.status == ProtocolStatus.frozen:
                raise ValueError(
                    f"{protocol.protocol_version} está congelado; crie uma nova versão."
                )
        path.write_text(protocol.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, version: str) -> ExperimentProtocol:
        return ExperimentProtocol(**json.loads(self._path(version).read_text(encoding="utf-8")))

    def list_versions(self) -> list[str]:
        if not self.base_dir.exists():
            return []
        return sorted(p.stem for p in self.base_dir.glob("protocol_v*.json"))

    def next_version(self) -> str:
        versions = self.list_versions()
        n = 0
        for v in versions:
            try:
                n = max(n, int(v.split("_v")[-1]))
            except ValueError:
                continue
        return f"protocol_v{n + 1}"
