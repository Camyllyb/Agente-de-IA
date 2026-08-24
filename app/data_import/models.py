"""Modelos de dados do pipeline de importação (com proveniência)."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field


class Provenance(BaseModel):
    """Proveniência de um registro importado (preservada, nunca alterada)."""

    source_name: str | None = None
    source_url: str | None = None
    collection_datetime: str | None = None
    original_date: str | None = None
    dataset_version: str | None = None


class MarketRecord(BaseModel):
    """Registro histórico de mercado (ação, FII ou índice)."""

    model_config = ConfigDict(extra="allow")

    ticker: str
    date: str
    asset_type: str | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    dividends: float | None = None
    currency: str = "BRL"
    snapshot_id: str | None = None
    validated: bool = False
    provenance: Provenance = Field(default_factory=Provenance)


class FIIRecord(BaseModel):
    """Registro periódico de FII (dados CVM)."""

    model_config = ConfigDict(extra="allow")

    ticker: str
    reference_date: str
    net_worth: float | None = None            # patrimônio líquido
    num_shareholders: int | None = None       # nº de cotistas
    num_shares: float | None = None           # quantidade de cotas
    nav_per_share: float | None = None        # valor patrimonial por cota
    income_per_share: float | None = None     # rendimento por cota
    segment: str | None = None
    snapshot_id: str | None = None
    source_document: str | None = None
    validated: bool = False
    provenance: Provenance = Field(default_factory=Provenance)


class Asset(BaseModel):
    """Ativo do universo da pesquisa."""

    ticker: str
    name: str | None = None
    asset_type: str | None = None
    segment: str | None = None
    benchmark: str | None = None
    use_in_experiment: bool = True
    preferred_source: str | None = None
    notes: str | None = None


class SourceRef(BaseModel):
    """Fonte de dados registrada (proveniência do dataset)."""

    id: str | None = None
    name: str | None = None
    data_type: str | None = None
    url: str | None = None
    usage: str | None = None
    verified_at: str | None = None
    notes: str | None = None


@dataclass
class ImportBundle:
    """Conjunto de dados importados de uma fonte."""

    assets: list[Asset] = field(default_factory=list)
    market_records: list[MarketRecord] = field(default_factory=list)
    fii_records: list[FIIRecord] = field(default_factory=list)
    questions: list = field(default_factory=list)  # list[BenchmarkQuestion]
    sources: list[SourceRef] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dataset_version: str | None = None

    def summary(self) -> dict:
        return {
            "assets": len(self.assets),
            "market_records": len(self.market_records),
            "fii_records": len(self.fii_records),
            "questions": len(self.questions),
            "sources": len(self.sources),
            "errors": len(self.errors),
        }
