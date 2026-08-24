"""Fontes de dados financeiros (MarketDataProvider) e sua fábrica."""

from __future__ import annotations

from app.config.settings import get_settings
from app.tools.market_data.base import (
    DataNotFoundError,
    MarketDataError,
    MarketDataProvider,
    SymbolNotFoundError,
)
from app.tools.market_data.live import LiveMarketDataProvider
from app.tools.market_data.snapshot import SnapshotMarketDataProvider

__all__ = [
    "MarketDataProvider",
    "MarketDataError",
    "SymbolNotFoundError",
    "DataNotFoundError",
    "SnapshotMarketDataProvider",
    "LiveMarketDataProvider",
    "get_market_data_provider",
]


def get_market_data_provider(
    source: str | None = None,
    snapshot_set: str | None = None,
) -> MarketDataProvider:
    """Cria a fonte de dados apropriada.

    Args:
        source: "snapshot" (padrão em experimentos) ou "live". Se ``None``, usa
            ``MARKET_DATA_SOURCE`` das configurações.
        snapshot_set: conjunto de snapshots (apenas para a fonte "snapshot").
    """
    settings = get_settings()
    resolved = (source or settings.market_data_source).lower()
    if resolved == "snapshot":
        return SnapshotMarketDataProvider(snapshot_set=snapshot_set)
    if resolved == "live":
        return LiveMarketDataProvider()
    raise ValueError(
        f"Fonte de dados desconhecida: '{resolved}'. Use 'snapshot' ou 'live'."
    )
