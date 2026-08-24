"""Interface desacoplada de importadores de dados de mercado.

A fonte de dados (Excel, CSV, Brapi, CVM) NÃO fica acoplada ao benchmark: cada
importador produz registros com proveniência; o restante do pipeline
(SnapshotManager) os consome.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.data_import.models import FIIRecord, MarketRecord


class MarketDataImporter(ABC):
    """Interface comum dos importadores de dados de mercado."""

    #: Nome da fonte (para proveniência).
    source_name: str = "base"

    @abstractmethod
    def import_market_data(self) -> list[MarketRecord]:
        """Importa registros históricos de mercado (OHLCV)."""
        raise NotImplementedError

    def import_fii_data(self) -> list[FIIRecord]:
        """Importa dados periódicos de FIIs (opcional)."""
        return []
