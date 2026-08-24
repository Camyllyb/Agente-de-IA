"""MarketDataProvider que serve dados de um snapshot congelado (em memória)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.models.market import HistoryBar, Quote, StockHistory
from app.tools.market_data.base import (
    DataNotFoundError,
    MarketDataProvider,
    SymbolNotFoundError,
)


class FrozenSnapshotDataProvider(MarketDataProvider):
    """Serve cotações/histórico a partir dos registros de um snapshot."""

    def __init__(self, snapshot_id: str, market_records: list[dict]):
        self.snapshot_id = snapshot_id
        self.source_name = f"snapshot:{snapshot_id}"
        self._by_ticker: dict[str, list[dict]] = defaultdict(list)
        for record in market_records:
            ticker = record.get("ticker")
            if ticker and record.get("close") is not None and record.get("date"):
                self._by_ticker[ticker].append(record)
        for ticker in self._by_ticker:
            self._by_ticker[ticker].sort(key=lambda r: r["date"])

    def available_symbols(self) -> list[str]:
        return sorted(self._by_ticker.keys())

    def get_quote(self, symbol: str) -> Quote:
        records = self._by_ticker.get(symbol)
        if not records:
            raise SymbolNotFoundError(symbol, self.source_name)
        last = records[-1]
        return Quote(
            symbol=symbol,
            price=float(last["close"]),
            currency=last.get("currency", "BRL"),
            date=last["date"],
            timestamp=None,
            source=self.source_name,
        )

    def get_history(self, symbol: str, start_date: str, end_date: str) -> StockHistory:
        records = self._by_ticker.get(symbol)
        if not records:
            raise SymbolNotFoundError(symbol, self.source_name)
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        bars = [
            HistoryBar(
                date=r["date"],
                open=r.get("open"),
                high=r.get("high"),
                low=r.get("low"),
                close=float(r["close"]),
                volume=int(r["volume"]) if r.get("volume") is not None else None,
            )
            for r in records
            if start <= date.fromisoformat(r["date"]) <= end
        ]
        if not bars:
            raise DataNotFoundError(
                symbol, f"nenhum dado entre {start_date} e {end_date}", self.source_name
            )
        currency = records[0].get("currency", "BRL")
        return StockHistory(
            symbol=symbol,
            currency=currency,
            source=self.source_name,
            start_date=start_date,
            end_date=end_date,
            bars=bars,
        )
