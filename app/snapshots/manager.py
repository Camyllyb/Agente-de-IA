"""SnapshotManager: cria, valida, congela e verifica snapshots científicos.

Um snapshot congelado não pode ser alterado. A integridade é garantida por
checksum SHA-256 sobre os arquivos de dados. Nova coleta deve gerar novo
``snapshot_id`` e nova ``dataset_version`` — nunca sobrescrever um snapshot
congelado.

Layout em disco (``data/snapshots/<snapshot_id>/``):
    metadata.json · market_data.json · fii_data.json
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from app.config.settings import get_settings
from app.snapshots.errors import (
    SnapshotFrozenError,
    SnapshotIntegrityError,
    SnapshotNotFoundError,
)
from app.snapshots.metadata import SnapshotMetadata, SnapshotStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(record) -> dict:
    return record.model_dump() if hasattr(record, "model_dump") else dict(record)


@dataclass
class SnapshotValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)


class SnapshotManager:
    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else get_settings().snapshots_dir

    # --- caminhos -----------------------------------------------------------
    def _dir(self, snapshot_id: str) -> Path:
        return self.base_dir / snapshot_id

    def _market_path(self, snapshot_id: str) -> Path:
        return self._dir(snapshot_id) / "market_data.json"

    def _fii_path(self, snapshot_id: str) -> Path:
        return self._dir(snapshot_id) / "fii_data.json"

    def _meta_path(self, snapshot_id: str) -> Path:
        return self._dir(snapshot_id) / "metadata.json"

    def exists(self, snapshot_id: str) -> bool:
        return self._meta_path(snapshot_id).exists()

    # --- checksum -----------------------------------------------------------
    def _compute_checksum(self, snapshot_id: str) -> str:
        sha = hashlib.sha256()
        for path in (self._market_path(snapshot_id), self._fii_path(snapshot_id)):
            if path.exists():
                sha.update(path.read_bytes())
        return sha.hexdigest()

    # --- metadados ----------------------------------------------------------
    def read_metadata(self, snapshot_id: str) -> SnapshotMetadata:
        path = self._meta_path(snapshot_id)
        if not path.exists():
            raise SnapshotNotFoundError(f"Snapshot '{snapshot_id}' não existe.")
        return SnapshotMetadata(**json.loads(path.read_text(encoding="utf-8")))

    def _write_metadata(self, meta: SnapshotMetadata) -> None:
        self._meta_path(meta.snapshot_id).write_text(
            meta.model_dump_json(indent=2), encoding="utf-8"
        )

    def is_frozen(self, snapshot_id: str) -> bool:
        return self.exists(snapshot_id) and self.read_metadata(snapshot_id).status == SnapshotStatus.frozen

    # --- criação ------------------------------------------------------------
    def create(
        self,
        snapshot_id: str,
        market_records: list,
        fii_records: list | None = None,
        sources: list[str] | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
        dataset_version: str | None = None,
        tickers: list[str] | None = None,
        note: str | None = None,
    ) -> SnapshotMetadata:
        if self.exists(snapshot_id) and self.is_frozen(snapshot_id):
            raise SnapshotFrozenError(
                f"Snapshot '{snapshot_id}' está congelado; gere um novo snapshot_id."
            )
        market = [_as_dict(r) for r in market_records]
        fii = [_as_dict(r) for r in (fii_records or [])]

        directory = self._dir(snapshot_id)
        directory.mkdir(parents=True, exist_ok=True)
        self._market_path(snapshot_id).write_text(
            json.dumps(market, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        self._fii_path(snapshot_id).write_text(
            json.dumps(fii, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )

        if tickers is None:
            tickers = sorted({r.get("ticker") for r in market if r.get("ticker")})
        dates = [r.get("date") for r in market if r.get("date")]
        meta = SnapshotMetadata(
            snapshot_id=snapshot_id,
            created_at=_now(),
            status=SnapshotStatus.draft,
            sources=sources or [],
            tickers=list(tickers),
            period_start=period_start or (min(dates) if dates else None),
            period_end=period_end or (max(dates) if dates else None),
            records=len(market),
            fii_records=len(fii),
            dataset_version=dataset_version,
            note=note,
        )
        self._write_metadata(meta)
        return meta

    # --- validação ----------------------------------------------------------
    def validate(self, snapshot_id: str, required_tickers: list[str] | None = None) -> SnapshotValidation:
        meta = self.read_metadata(snapshot_id)
        market = json.loads(self._market_path(snapshot_id).read_text(encoding="utf-8"))
        errors: list[str] = []

        if not market:
            errors.append("Snapshot sem registros de mercado.")
        for r in market:
            if not r.get("ticker"):
                errors.append("Registro sem ticker.")
            d = r.get("date")
            if d:
                try:
                    date.fromisoformat(d)
                except ValueError:
                    errors.append(f"Data inválida: {d}")
        present = {r.get("ticker") for r in market}
        for t in (required_tickers or []):
            if t not in present:
                errors.append(f"Ticker obrigatório ausente: {t}")

        validation = SnapshotValidation(ok=not errors, errors=errors)
        if validation.ok and meta.status == SnapshotStatus.draft:
            meta.status = SnapshotStatus.validated
            self._write_metadata(meta)
        return validation

    # --- congelamento -------------------------------------------------------
    def freeze(self, snapshot_id: str) -> SnapshotMetadata:
        meta = self.read_metadata(snapshot_id)
        if meta.status == SnapshotStatus.frozen:
            raise SnapshotFrozenError(f"Snapshot '{snapshot_id}' já está congelado.")
        meta.checksum = self._compute_checksum(snapshot_id)
        meta.frozen_at = _now()
        meta.status = SnapshotStatus.frozen
        self._write_metadata(meta)
        return meta

    # --- integridade --------------------------------------------------------
    def verify_integrity(self, snapshot_id: str) -> bool:
        meta = self.read_metadata(snapshot_id)
        if meta.status != SnapshotStatus.frozen or not meta.checksum:
            return True  # nada a verificar (não congelado)
        return self._compute_checksum(snapshot_id) == meta.checksum

    # --- carregamento -------------------------------------------------------
    def load(self, snapshot_id: str, verify: bool = True) -> dict:
        meta = self.read_metadata(snapshot_id)
        if verify and meta.status == SnapshotStatus.frozen and not self.verify_integrity(snapshot_id):
            raise SnapshotIntegrityError(
                f"Snapshot '{snapshot_id}' foi ALTERADO após o congelamento "
                "(checksum não confere). Experimento deve ser interrompido."
            )
        market = json.loads(self._market_path(snapshot_id).read_text(encoding="utf-8"))
        fii = json.loads(self._fii_path(snapshot_id).read_text(encoding="utf-8"))
        return {"metadata": meta, "market_records": market, "fii_records": fii}

    # --- listagem -----------------------------------------------------------
    def list_snapshots(self) -> list[SnapshotMetadata]:
        if not self.base_dir.exists():
            return []
        metas: list[SnapshotMetadata] = []
        for child in sorted(self.base_dir.iterdir()):
            if child.is_dir() and (child / "metadata.json").exists():
                metas.append(self.read_metadata(child.name))
        return metas

    # --- provider a partir de um snapshot congelado -------------------------
    def build_provider(self, snapshot_id: str, verify: bool = True):
        from app.snapshots.provider import FrozenSnapshotDataProvider

        loaded = self.load(snapshot_id, verify=verify)
        return FrozenSnapshotDataProvider(snapshot_id, loaded["market_records"])
