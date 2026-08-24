"""Fonte de dados financeiros baseada em snapshots locais.

Lê arquivos JSON congelados em ``data/snapshots/<conjunto>/<SYMBOL>.json``. É a
implementação usada nos experimentos científicos: como valores de mercado mudam
com o tempo, os mesmos dados precisam ser fornecidos a todas as técnicas
(zero-shot, few-shot, chain-of-thought) e a todos os modelos avaliados.

Formato esperado de cada arquivo::

    {
      "symbol": "PETR4.SA",
      "currency": "BRL",
      "as_of": "2024-06-03",
      "quote": {"price": 37.8, "date": "2024-06-03", "timestamp": "2024-06-03T21:00:00Z"},
      "history": [
        {"date": "2024-01-02", "open": .., "high": .., "low": .., "close": .., "volume": ..},
        ...
      ]
    }
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.config.logging import get_logger
from app.config.settings import get_settings
from app.models.market import HistoryBar, Quote, StockHistory
from app.tools.market_data.base import (
    DataNotFoundError,
    MarketDataProvider,
    SymbolNotFoundError,
)

logger = get_logger(__name__)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


class SnapshotMarketDataProvider(MarketDataProvider):
    """Provedor de dados a partir de snapshots locais (offline, determinístico)."""

    def __init__(self, snapshot_set: str | None = None, base_dir: Path | None = None):
        settings = get_settings()
        self.snapshot_set = snapshot_set or settings.snapshot_set
        self.base_dir = (base_dir or settings.snapshots_dir) / self.snapshot_set
        self.source_name = f"snapshot:{self.snapshot_set}"
        self._cache: dict[str, dict] = {}

    # --- carregamento -------------------------------------------------------
    def _path_for(self, symbol: str) -> Path:
        return self.base_dir / f"{symbol}.json"

    def _load(self, symbol: str) -> dict:
        if symbol in self._cache:
            return self._cache[symbol]
        path = self._path_for(symbol)
        if not path.exists():
            raise SymbolNotFoundError(symbol, self.source_name)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - arquivo corrompido
            raise DataNotFoundError(symbol, f"JSON inválido: {exc}", self.source_name) from exc
        self._cache[symbol] = data
        return data

    def available_symbols(self) -> list[str]:
        """Lista os ativos disponíveis neste conjunto de snapshots."""
        if not self.base_dir.exists():
            return []
        return sorted(p.stem for p in self.base_dir.glob("*.json"))

    # --- interface ----------------------------------------------------------
    def get_quote(self, symbol: str) -> Quote:
        data = self._load(symbol)
        quote = data.get("quote")
        if not quote or "price" not in quote:
            raise DataNotFoundError(symbol, "sem cotação no snapshot", self.source_name)
        return Quote(
            symbol=data.get("symbol", symbol),
            price=float(quote["price"]),
            currency=data.get("currency", "UNKNOWN"),
            date=quote.get("date", data.get("as_of", "")),
            timestamp=quote.get("timestamp"),
            source=self.source_name,
        )

    def get_history(self, symbol: str, start_date: str, end_date: str) -> StockHistory:
        data = self._load(symbol)
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        if start > end:
            raise DataNotFoundError(
                symbol, f"intervalo inválido ({start_date} > {end_date})", self.source_name
            )

        raw_bars = data.get("history", []) or []
        bars: list[HistoryBar] = []
        for entry in raw_bars:
            bar_date = _parse_date(entry["date"])
            if start <= bar_date <= end:
                bars.append(
                    HistoryBar(
                        date=entry["date"],
                        open=entry.get("open"),
                        high=entry.get("high"),
                        low=entry.get("low"),
                        close=float(entry["close"]),
                        volume=entry.get("volume"),
                    )
                )

        if not bars:
            raise DataNotFoundError(
                symbol,
                f"nenhum dado entre {start_date} e {end_date}",
                self.source_name,
            )

        bars.sort(key=lambda b: b.date)
        return StockHistory(
            symbol=data.get("symbol", symbol),
            currency=data.get("currency", "UNKNOWN"),
            source=self.source_name,
            start_date=start_date,
            end_date=end_date,
            bars=bars,
        )
