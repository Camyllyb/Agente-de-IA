"""Metadados de um snapshot científico."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SnapshotStatus(str, Enum):
    draft = "draft"
    validated = "validated"
    frozen = "frozen"


class SnapshotMetadata(BaseModel):
    """Metadados registrados para cada snapshot."""

    model_config = ConfigDict(extra="allow")

    snapshot_id: str
    created_at: str
    frozen_at: str | None = None
    status: SnapshotStatus = SnapshotStatus.draft
    sources: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    period_start: str | None = None
    period_end: str | None = None
    records: int = 0
    fii_records: int = 0
    checksum: str | None = None
    dataset_version: str | None = None
    note: str | None = None
